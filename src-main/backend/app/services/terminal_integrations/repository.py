from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.enums import (
    TerminalIntegrationFailureCategory,
    TerminalIntegrationState,
)
from app.models.terminal_integration import TerminalIntegrationOutbox
from app.services.terminal_integrations.contracts import (
    ContinuationIntegrationIntent,
    ResearchIntegrationIntent,
    TerminalIntegrationClaim,
    TerminalIntegrationIntent,
)

_PSEUDONYM = re.compile(r"^v1_[0-9a-f]{64}$")
_SCHEMA_VERSION = "terminal-integration.v1"
_MAX_PAYLOAD_BYTES = 131_072
_MAX_REFERENCES = 100


class TerminalIntegrationPersistenceError(Exception):
    """A sanitized durable-handoff persistence failure."""


class TerminalIntegrationPayloadError(TerminalIntegrationPersistenceError):
    """A handoff contained invalid or privacy-unsafe metadata."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _valid_uuid4(value: str) -> bool:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError):
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _bounded_text(value: object, *, maximum: int = 255) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
    return value


def _serialize_intent(intent: TerminalIntegrationIntent) -> dict[str, object]:
    if not _valid_uuid4(intent.correlation_id):
        raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
    if isinstance(intent, ContinuationIntegrationIntent):
        if _PSEUDONYM.fullmatch(intent.pseudonymous_actor_reference) is None:
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
        payload: dict[str, object] = {
            "schema_version": _SCHEMA_VERSION,
            "pseudonymous_actor_reference": intent.pseudonymous_actor_reference,
            "course_reference": _bounded_text(intent.course_reference),
            "completed_task_reference": _bounded_text(intent.completed_task_reference),
        }
    elif isinstance(intent, ResearchIntegrationIntent):
        if (
            _PSEUDONYM.fullmatch(intent.pseudonymous_user_id) is None
            or _PSEUDONYM.fullmatch(intent.pseudonymous_submission_reference) is None
            or len(intent.input_references) > _MAX_REFERENCES
            or len(intent.retrieved_sources) > _MAX_REFERENCES
            or intent.retrieval_request_count < 0
            or not 0 <= intent.retrieval_hit_count <= intent.retrieval_request_count
        ):
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "pseudonymous_user_id": intent.pseudonymous_user_id,
            "pseudonymous_submission_reference": intent.pseudonymous_submission_reference,
            "task_type": _bounded_text(intent.task_type),
            "fallback_provider": _bounded_text(intent.fallback_provider, maximum=100),
            "fallback_model": _bounded_text(intent.fallback_model),
            "input_references": [_bounded_text(reference) for reference in intent.input_references],
            "retrieved_sources": [
                {
                    "source_id": _bounded_text(source.source_id),
                    "label": _bounded_text(source.label),
                    "relevance_score": source.relevance_score,
                }
                for source in intent.retrieved_sources
            ],
            "retrieval_request_count": intent.retrieval_request_count,
            "retrieval_hit_count": intent.retrieval_hit_count,
            "simulation_reference": (
                _bounded_text(intent.simulation_reference)
                if intent.simulation_reference is not None
                else None
            ),
            "simulation_status": _bounded_text(intent.simulation_status, maximum=100),
        }
        if any(
            not isinstance(source.relevance_score, (int, float))
            or isinstance(source.relevance_score, bool)
            or not 0 <= float(source.relevance_score) <= 1
            for source in intent.retrieved_sources
        ):
            raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
    else:
        raise TerminalIntegrationPayloadError("terminal integration payload is invalid")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > _MAX_PAYLOAD_BYTES:
        raise TerminalIntegrationPayloadError("terminal integration payload exceeds limit")
    return payload


def outbox_record(
    workflow_run_id: str,
    intent: TerminalIntegrationIntent,
) -> TerminalIntegrationOutbox:
    if not _valid_uuid4(workflow_run_id):
        raise TerminalIntegrationPayloadError("terminal integration workflow is invalid")
    return TerminalIntegrationOutbox(
        workflow_run_id=workflow_run_id,
        integration_type=intent.integration_type,
        correlation_id=intent.correlation_id,
        payload=_serialize_intent(intent),
        state=TerminalIntegrationState.PENDING,
    )


def valid_intent(
    workflow_run_id: str,
    intent: TerminalIntegrationIntent,
) -> bool:
    try:
        outbox_record(workflow_run_id, intent)
    except TerminalIntegrationPayloadError:
        return False
    return True


class SqlAlchemyTerminalIntegrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim_next(
        self,
        *,
        now: datetime,
        lease_expires_at: datetime,
        execution_token: str,
        maximum_attempts: int,
    ) -> TerminalIntegrationClaim | None:
        observed_at = _utc(now)
        lease = _utc(lease_expires_at)
        if (
            not _valid_uuid4(execution_token)
            or not 1 <= maximum_attempts <= 3
            or lease <= observed_at
        ):
            raise TerminalIntegrationPersistenceError("terminal integration claim is invalid")
        try:
            candidate = self._session.scalar(
                select(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.processing_attempts < maximum_attempts,
                    or_(
                        TerminalIntegrationOutbox.state == TerminalIntegrationState.PENDING,
                        and_(
                            TerminalIntegrationOutbox.state
                            == TerminalIntegrationState.RETRY_SCHEDULED,
                            TerminalIntegrationOutbox.next_retry_at <= observed_at,
                        ),
                        and_(
                            TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                            TerminalIntegrationOutbox.lease_expires_at <= observed_at,
                        ),
                    ),
                )
                .order_by(
                    TerminalIntegrationOutbox.created_at,
                    TerminalIntegrationOutbox.id,
                )
                .limit(1)
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise TerminalIntegrationPersistenceError(
                "terminal integration could not be claimed"
            ) from None
        if candidate is None:
            return None

        previous_state = candidate.state
        previous_token = candidate.execution_token
        previous_lease = candidate.lease_expires_at
        previous_attempts = candidate.processing_attempts
        statement = update(TerminalIntegrationOutbox).where(
            TerminalIntegrationOutbox.id == candidate.id,
            TerminalIntegrationOutbox.state == previous_state,
            TerminalIntegrationOutbox.processing_attempts == previous_attempts,
        )
        statement = (
            statement.where(TerminalIntegrationOutbox.execution_token.is_(None))
            if previous_token is None
            else statement.where(TerminalIntegrationOutbox.execution_token == previous_token)
        )
        statement = (
            statement.where(TerminalIntegrationOutbox.lease_expires_at.is_(None))
            if previous_lease is None
            else statement.where(TerminalIntegrationOutbox.lease_expires_at == previous_lease)
        )
        try:
            result = self._session.execute(
                statement.values(
                    state=TerminalIntegrationState.RUNNING,
                    processing_attempts=previous_attempts + 1,
                    execution_token=execution_token,
                    lease_expires_at=lease,
                    next_retry_at=None,
                    failure_category=None,
                    updated_at=observed_at,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise TerminalIntegrationPersistenceError(
                "terminal integration could not be claimed"
            ) from None
        if result.rowcount != 1:
            return None
        return TerminalIntegrationClaim(
            outbox_id=candidate.id,
            workflow_run_id=candidate.workflow_run_id,
            integration_type=candidate.integration_type,
            correlation_id=candidate.correlation_id,
            payload=dict(candidate.payload),
            execution_token=execution_token,
            processing_attempts=previous_attempts + 1,
            lease_expires_at=lease,
        )

    def complete(
        self,
        claim: TerminalIntegrationClaim,
        *,
        completed_at: datetime,
    ) -> bool:
        return self._terminal_update(
            claim,
            {
                "state": TerminalIntegrationState.COMPLETED,
                "execution_token": None,
                "lease_expires_at": None,
                "next_retry_at": None,
                "failure_category": None,
                "completed_at": _utc(completed_at),
                "updated_at": _utc(completed_at),
            },
        )

    def fail(
        self,
        claim: TerminalIntegrationClaim,
        category: TerminalIntegrationFailureCategory,
        *,
        failed_at: datetime,
        retryable: bool,
        next_retry_at: datetime | None,
    ) -> bool:
        failed = _utc(failed_at)
        if not isinstance(category, TerminalIntegrationFailureCategory):
            raise TerminalIntegrationPersistenceError(
                "terminal integration failure category is invalid"
            )
        if retryable:
            if claim.processing_attempts >= 3 or next_retry_at is None:
                raise TerminalIntegrationPersistenceError("terminal integration retry is invalid")
            retry_at = _utc(next_retry_at)
            if retry_at < failed:
                raise TerminalIntegrationPersistenceError("terminal integration retry is invalid")
            state = TerminalIntegrationState.RETRY_SCHEDULED
            completed_at = None
        else:
            state = TerminalIntegrationState.FAILED
            completed_at = failed
            retry_at = None
        return self._terminal_update(
            claim,
            {
                "state": state,
                "execution_token": None,
                "lease_expires_at": None,
                "next_retry_at": retry_at,
                "failure_category": category,
                "completed_at": completed_at,
                "updated_at": failed,
            },
        )

    def recover_expired(self, workflow_run_id: str, *, observed_at: datetime) -> int:
        if not _valid_uuid4(workflow_run_id):
            return 0
        observed = _utc(observed_at)
        try:
            retry = self._session.execute(
                update(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.workflow_run_id == workflow_run_id,
                    TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                    TerminalIntegrationOutbox.lease_expires_at <= observed,
                    TerminalIntegrationOutbox.processing_attempts < 3,
                )
                .values(
                    state=TerminalIntegrationState.RETRY_SCHEDULED,
                    execution_token=None,
                    lease_expires_at=None,
                    next_retry_at=observed,
                    failure_category=(TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE),
                    updated_at=observed,
                )
            )
            failed = self._session.execute(
                update(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.workflow_run_id == workflow_run_id,
                    TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                    TerminalIntegrationOutbox.lease_expires_at <= observed,
                    TerminalIntegrationOutbox.processing_attempts >= 3,
                )
                .values(
                    state=TerminalIntegrationState.FAILED,
                    execution_token=None,
                    lease_expires_at=None,
                    next_retry_at=None,
                    failure_category=(TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE),
                    completed_at=observed,
                    updated_at=observed,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise TerminalIntegrationPersistenceError(
                "terminal integration recovery failed"
            ) from None
        return int(retry.rowcount or 0) + int(failed.rowcount or 0)

    def finalize_next_exhausted(
        self,
        *,
        observed_at: datetime,
        maximum_attempts: int,
    ) -> str | None:
        observed = _utc(observed_at)
        if not 1 <= maximum_attempts <= 3:
            raise TerminalIntegrationPersistenceError("terminal integration recovery is invalid")
        try:
            candidate = self._session.scalar(
                select(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                    TerminalIntegrationOutbox.lease_expires_at <= observed,
                    TerminalIntegrationOutbox.processing_attempts >= maximum_attempts,
                )
                .order_by(
                    TerminalIntegrationOutbox.created_at,
                    TerminalIntegrationOutbox.id,
                )
                .limit(1)
            )
            if candidate is None:
                return None
            result = self._session.execute(
                update(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.id == candidate.id,
                    TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                    TerminalIntegrationOutbox.execution_token == candidate.execution_token,
                    TerminalIntegrationOutbox.processing_attempts == candidate.processing_attempts,
                    TerminalIntegrationOutbox.lease_expires_at == candidate.lease_expires_at,
                )
                .values(
                    state=TerminalIntegrationState.FAILED,
                    execution_token=None,
                    lease_expires_at=None,
                    failure_category=(TerminalIntegrationFailureCategory.INTEGRATION_UNAVAILABLE),
                    completed_at=observed,
                    updated_at=observed,
                )
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise TerminalIntegrationPersistenceError(
                "terminal integration recovery failed"
            ) from None
        return candidate.id if result.rowcount == 1 else None

    def _terminal_update(
        self,
        claim: TerminalIntegrationClaim,
        values: dict[str, object],
    ) -> bool:
        try:
            result = self._session.execute(
                update(TerminalIntegrationOutbox)
                .where(
                    TerminalIntegrationOutbox.id == claim.outbox_id,
                    TerminalIntegrationOutbox.state == TerminalIntegrationState.RUNNING,
                    TerminalIntegrationOutbox.execution_token == claim.execution_token,
                    TerminalIntegrationOutbox.processing_attempts == claim.processing_attempts,
                )
                .values(**values)
            )
            self._session.commit()
        except SQLAlchemyError:
            self._session.rollback()
            raise TerminalIntegrationPersistenceError(
                "terminal integration could not be updated"
            ) from None
        return result.rowcount == 1
