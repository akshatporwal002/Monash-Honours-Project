"""Persist a released feedback view's two events independently of student work."""

import logging
from typing import Protocol

from sqlalchemy.exc import DBAPIError, IntegrityError

from app.services.audit import AuditConflictError, AuditRecorder
from app.services.audit_events import FeedbackAuditEvents, StudentAuditTracker
from app.services.learning_events import (
    BestEffortFeedbackViewTracker,
    LearningEventRecorder,
    TrustedLearningEventHooks,
)
from app.services.learning_events.repository import SqlAlchemyLearningEventRepository


class FeedbackViewEvents(Protocol):
    def record(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
        feedback_id: str | None,
    ) -> None: ...


class NoOpFeedbackViewEvents:
    def record(self, **values) -> None:
        return


class _PreparedEvents:
    def __init__(self, prepare=lambda value: value):
        self.values = []
        self.prepare = prepare

    def record(self, command):
        self.values.append(self.prepare(command))
        return None


class IndependentFeedbackViewEvents:
    """One fresh transaction, with isolated failures for each telemetry record."""

    def __init__(self, session_factory, pseudonymizer):
        self._session_factory = session_factory
        self._pseudonymizer = pseudonymizer
        self._logger = logging.getLogger(__name__)

    def record(
        self,
        *,
        actor_reference: str,
        course_id: str,
        task_id: str,
        workflow_run_id: str,
        correlation_id: str,
        feedback_status: str,
        feedback_id: str | None = None,
    ) -> None:
        # Reuse the original typed mappings and strict validation. Each adapter
        # keeps its original best-effort failure boundary during preparation.
        learning = _PreparedEvents(
            LearningEventRecorder(self._session_factory, self._pseudonymizer).prepare
        )
        audit = _PreparedEvents()
        BestEffortFeedbackViewTracker(TrustedLearningEventHooks(learning)).record_terminal_view(
            actor_reference=actor_reference,
            course_id=course_id,
            task_id=task_id,
            workflow_run_id=workflow_run_id,
            correlation_id=correlation_id,
            feedback_status=feedback_status,
        )
        if feedback_id is not None:
            StudentAuditTracker(
                FeedbackAuditEvents(audit), self._pseudonymizer
            ).record_feedback_view(
                actor_reference=actor_reference,
                feedback_id=feedback_id,
                correlation_id=correlation_id,
            )
        settled = []
        try:
            # This session is never shared with the request, another view, or a
            # cached tracker. Replayed reads need no writer reservation or commit.
            with self._session_factory() as session:
                repositories = (
                    (SqlAlchemyLearningEventRepository(session), learning.values),
                    (AuditRecorder(session), audit.values),
                )
                pending = []
                for repository, values in repositories:
                    for value in values:
                        try:
                            if repository.lookup(value) is None:
                                pending.append((repository, value))
                            else:
                                settled.append(value)
                        except AuditConflictError:
                            # Keep the original audit tracker's silent conflict
                            # boundary, including a new correlation on a replay.
                            settled.append(value)
                        except Exception:
                            # No writes exist yet. Release a failed/invalidated
                            # read transaction before checking the other event.
                            session.rollback()
                            settled.append(value)
                            self._failed(correlation_id)
                if not pending:
                    return
                session.rollback()
                if session.get_bind().dialect.name == "sqlite":
                    # SQLAlchemy's logical begin is not a SQLite BEGIN in legacy
                    # mode. A real outer transaction prevents SAVEPOINT release
                    # from committing a row before the owning commit succeeds.
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                for repository, value in pending:
                    try:
                        with session.begin_nested():
                            receipt = repository.record_in_transaction(value)
                        if not receipt.created:
                            settled.append(value)
                    except AuditConflictError:
                        settled.append(value)
                    except IntegrityError:
                        settled.append(value)
                        # Another database writer may win the unique-key race.
                        # After only this savepoint rolls back, check the winner
                        # once and retain the original content-conflict rules.
                        try:
                            if repository.lookup(value) is None:
                                self._failed(correlation_id)
                        except AuditConflictError:
                            pass
                        except Exception:
                            self._failed(correlation_id)
                    except DBAPIError as error:
                        if error.connection_invalidated:
                            # A savepoint cannot isolate loss of its connection.
                            # Close this outer transaction before bounded recovery.
                            raise
                        settled.append(value)
                        self._failed(correlation_id)
                    except Exception:
                        settled.append(value)
                        self._failed(correlation_id)
                session.commit()
        except DBAPIError:
            self._failed(correlation_id)
            self._recover_independently(learning.values, audit.values, settled, correlation_id)
        except Exception:
            # Session close rolls back a failed outer transaction. Neither event
            # may change the already-authorized feedback response.
            self._failed(correlation_id)

    def _recover_independently(self, learning, audit, settled, correlation_id):
        # One attempt per prepared record, without recursive batch retries. The
        # original IDs and replay checks also cover an ambiguous lost COMMIT.
        for repository_type, values in (
            (SqlAlchemyLearningEventRepository, learning),
            (AuditRecorder, audit),
        ):
            for value in values:
                # Do not retry a known logical conflict/failure or a replay
                # already known to be durable before this outer transaction.
                if any(value is prior for prior in settled):
                    continue
                try:
                    with self._session_factory() as session:
                        repository_type(session).record(value)
                except AuditConflictError:
                    pass
                except Exception:
                    self._failed(correlation_id)

    def _failed(self, correlation_id):
        self._logger.warning(
            "feedback_view_event_recording_failed",
            extra={
                "correlation_id": correlation_id,
                "stage": "feedback_view_recording",
                "failure_category": "telemetry_persistence_unavailable",
            },
        )
