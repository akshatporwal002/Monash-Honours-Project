import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import (
    FeedbackRecord,
    FeedbackReport,
    FeedbackReportCategory,
    FeedbackStatus,
    WorkflowOutcome,
    WorkflowRun,
    WorkflowStage,
)
from app.services.feedback.application import (
    FeedbackWorkflowApplication,
    InProcessFeedbackExecutor,
)
from app.services.feedback.contracts import FeedbackReportWrite
from app.services.feedback.errors import (
    ContextCollectionError,
    FeedbackReportConflictError,
    LostWorkflowLeaseError,
)
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
WORKFLOW_ID = "00000000-0000-4000-8000-000000000201"
FEEDBACK_ID = "00000000-0000-4000-8000-000000000202"


def test_claim_is_idempotent_and_failed_or_stale_work_is_reclaimed(
    db_session: Session,
) -> None:
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    application = FeedbackWorkflowApplication(
        repository,
        now=lambda: NOW,
        uuid_factory=lambda: WORKFLOW_ID,
    )

    first = application.start("submission-1")
    active = repository.claim_workflow(
        "submission-1",
        "00000000-0000-4000-8000-000000000299",
        started_at=NOW + timedelta(minutes=1),
        lease_expires_at=NOW + timedelta(minutes=6),
    )

    assert first.should_start is True
    assert active.should_start is False
    assert active.workflow_run_id == WORKFLOW_ID

    repository.mark_failed(
        WORKFLOW_ID,
        "context_unavailable",
        NOW + timedelta(minutes=2),
        execution_token=first.execution_token,
    )
    failed = application.get("submission-1")
    assert failed is not None
    assert failed.stage is WorkflowStage.FAILED
    assert failed.failure_category == "context_unavailable"

    retry = repository.claim_workflow(
        "submission-1",
        "00000000-0000-4000-8000-000000000298",
        started_at=NOW + timedelta(minutes=3),
        lease_expires_at=NOW + timedelta(minutes=8),
    )
    assert retry.should_start is True
    assert retry.workflow_run_id == WORKFLOW_ID
    assert retry.failure_category is None

    repository.record_stage(
        WORKFLOW_ID,
        WorkflowStage.GENERATING,
        execution_token=retry.execution_token,
    )
    stale = repository.claim_workflow(
        "submission-1",
        "00000000-0000-4000-8000-000000000297",
        started_at=NOW + timedelta(minutes=9),
        lease_expires_at=NOW + timedelta(minutes=14),
    )
    assert stale.should_start is True
    assert stale.workflow_run_id == WORKFLOW_ID


def test_concurrent_claims_schedule_only_one_winner(tmp_path: Path) -> None:
    database_path = tmp_path / "claim-race.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    def claim(workflow_id: str) -> bool:
        with session_factory() as session:
            result = SqlAlchemyFeedbackWorkflowRepository(session).claim_workflow(
                "submission-race",
                workflow_id,
                started_at=NOW,
                lease_expires_at=NOW + timedelta(minutes=5),
            )
            return result.should_start

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                claim,
                [
                    "00000000-0000-4000-8000-000000000211",
                    "00000000-0000-4000-8000-000000000212",
                ],
            )
        )

    assert sorted(results) == [False, True]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(WorkflowRun)) == 1
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_reclaimed_execution_fences_stale_stage_and_failure_writes(
    db_session: Session,
) -> None:
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    first = repository.claim_workflow(
        "submission-fenced",
        WORKFLOW_ID,
        started_at=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
    )
    assert first.execution_token is not None
    repository.record_stage(
        WORKFLOW_ID,
        WorkflowStage.CONTEXT_COLLECTION,
        execution_token=first.execution_token,
        lease_expires_at=NOW + timedelta(minutes=5),
    )

    reclaimed = repository.claim_workflow(
        "submission-fenced",
        "00000000-0000-4000-8000-000000000299",
        started_at=NOW + timedelta(minutes=6),
        lease_expires_at=NOW + timedelta(minutes=11),
    )
    assert reclaimed.should_start is True
    assert reclaimed.execution_token is not None
    assert reclaimed.execution_token != first.execution_token
    assert reclaimed.execution_attempt_count == 2

    with pytest.raises(LostWorkflowLeaseError):
        repository.record_stage(
            WORKFLOW_ID,
            WorkflowStage.CONTEXT_COLLECTION,
            execution_token=first.execution_token,
            lease_expires_at=NOW + timedelta(minutes=12),
        )
    with pytest.raises(LostWorkflowLeaseError):
        repository.mark_failed(
            WORKFLOW_ID,
            "stale_failure",
            NOW + timedelta(minutes=7),
            execution_token=first.execution_token,
        )

    workflow = db_session.get(WorkflowRun, WORKFLOW_ID)
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.PENDING
    assert workflow.execution_token == reclaimed.execution_token


def test_claimed_workflow_rejects_unfenced_stage_and_failure_writes(
    db_session: Session,
) -> None:
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    claim = repository.claim_workflow(
        "submission-fence-required",
        WORKFLOW_ID,
        started_at=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
    )

    with pytest.raises(LostWorkflowLeaseError):
        repository.record_stage(
            claim.workflow_run_id,
            WorkflowStage.GENERATING,
        )
    with pytest.raises(LostWorkflowLeaseError):
        repository.mark_failed(
            claim.workflow_run_id,
            "unfenced_failure",
            NOW + timedelta(seconds=1),
        )

    workflow = db_session.get(WorkflowRun, claim.workflow_run_id)
    assert workflow is not None
    assert workflow.current_stage is WorkflowStage.PENDING
    assert workflow.execution_token == claim.execution_token


def test_expired_claim_is_retryable_but_execution_attempts_are_bounded(
    db_session: Session,
) -> None:
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    claim = repository.claim_workflow(
        "submission-bounded",
        WORKFLOW_ID,
        started_at=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
    )
    assert claim.execution_attempt_count == 1

    expired = repository.get_workflow_claim(
        "submission-bounded",
        observed_at=NOW + timedelta(minutes=6),
    )
    assert expired is not None
    assert expired.stage is WorkflowStage.FAILED
    assert expired.retryable is True
    assert expired.failure_category == "workflow_interrupted"

    for minute, expected_attempt in [(6, 2), (12, 3)]:
        claim = repository.claim_workflow(
            "submission-bounded",
            str(uuid4()),
            started_at=NOW + timedelta(minutes=minute),
            lease_expires_at=NOW + timedelta(minutes=minute + 5),
        )
        assert claim.should_start is True
        assert claim.execution_attempt_count == expected_attempt

    exhausted = repository.claim_workflow(
        "submission-bounded",
        str(uuid4()),
        started_at=NOW + timedelta(minutes=18),
        lease_expires_at=NOW + timedelta(minutes=23),
    )
    assert exhausted.should_start is False
    assert exhausted.stage is WorkflowStage.FAILED
    assert exhausted.retryable is False
    assert exhausted.failure_category == "retry_attempts_exhausted"
    stored = db_session.get(WorkflowRun, WORKFLOW_ID)
    assert stored is not None
    assert stored.current_stage is WorkflowStage.FAILED
    assert stored.final_outcome is WorkflowOutcome.WORKFLOW_FAILED
    assert stored.execution_token is None
    assert stored.lease_expires_at is None


def test_post_recovery_audits_terminal_exhaustion(
    db_session: Session,
) -> None:
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    submission_id = "submission-post-exhaustion"
    claim = repository.claim_workflow(
        submission_id,
        WORKFLOW_ID,
        started_at=NOW,
        lease_expires_at=NOW + timedelta(minutes=5),
    )
    for minute in (6, 12):
        claim = repository.claim_workflow(
            submission_id,
            str(uuid4()),
            started_at=NOW + timedelta(minutes=minute),
            lease_expires_at=NOW + timedelta(minutes=minute + 5),
        )
        assert claim.should_start is True
    assert claim.execution_attempt_count == 3

    failures: list[tuple[str, str, str]] = []

    class AuditEvents:
        def workflow_failed(
            self,
            workflow_id: str,
            correlation_id: str,
            failure_category: str,
        ) -> None:
            failures.append((workflow_id, correlation_id, failure_category))

    correlation_id = str(uuid4())
    application = FeedbackWorkflowApplication(
        repository,
        now=lambda: NOW + timedelta(minutes=18),
        audit_events=AuditEvents(),  # type: ignore[arg-type]
    )

    exhausted = application.start(
        submission_id,
        correlation_id=correlation_id,
    )

    assert exhausted.stage is WorkflowStage.FAILED
    assert exhausted.retryable is False
    assert exhausted.failure_category == "retry_attempts_exhausted"
    assert failures == [
        (
            WORKFLOW_ID,
            correlation_id,
            "retry_attempts_exhausted",
        )
    ]


def _released_feedback(db_session: Session) -> None:
    db_session.add_all(
        [
            WorkflowRun(
                id=WORKFLOW_ID,
                submission_id="submission-1",
                current_stage=WorkflowStage.COMPLETED,
                final_outcome=WorkflowOutcome.FIRST_PASS,
                started_at=NOW,
                completed_at=NOW,
            ),
            FeedbackRecord(
                id=FEEDBACK_ID,
                submission_id="submission-1",
                workflow_run_id=WORKFLOW_ID,
                feedback_content={"summary": "Released feedback."},
                status=FeedbackStatus.ACCEPTED,
                generation_attempt=1,
                provider="provider",
                model="model",
                prompt_version="feedback-v2",
                source_references=[],
                simulation_references=[],
                source_attributions=[],
            ),
        ]
    )
    db_session.commit()


def test_report_persistence_is_idempotent_and_conflicting_payload_is_rejected(
    db_session: Session,
) -> None:
    _released_feedback(db_session)
    repository = SqlAlchemyFeedbackWorkflowRepository(db_session)
    report = FeedbackReportWrite(
        feedback_id=FEEDBACK_ID,
        reporter_reference="student-1",
        category=FeedbackReportCategory.UNCLEAR,
        note="The explanation is unclear.",
    )

    first = repository.save_report(report)
    replay = repository.save_report(report)

    assert first.created is True
    assert replay.created is False
    assert replay.report_id == first.report_id
    assert repository.get_released_submission_id(FEEDBACK_ID) == "submission-1"
    assert db_session.scalar(select(func.count()).select_from(FeedbackReport)) == 1

    with pytest.raises(FeedbackReportConflictError):
        repository.save_report(
            FeedbackReportWrite(
                feedback_id=FEEDBACK_ID,
                reporter_reference="student-1",
                category=FeedbackReportCategory.UNSAFE,
                note=None,
            )
        )


def test_rejected_feedback_is_not_reportable(db_session: Session) -> None:
    _released_feedback(db_session)
    feedback = db_session.get(FeedbackRecord, FEEDBACK_ID)
    assert feedback is not None
    feedback.status = FeedbackStatus.REJECTED
    db_session.commit()

    assert (
        SqlAlchemyFeedbackWorkflowRepository(db_session).get_released_submission_id(FEEDBACK_ID)
        is None
    )


def test_in_process_executor_persists_sanitized_failure_with_a_fresh_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "executor.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        claim = SqlAlchemyFeedbackWorkflowRepository(session).claim_workflow(
            "submission-1",
            WORKFLOW_ID,
            started_at=NOW,
            lease_expires_at=NOW + timedelta(minutes=5),
        )

    class FailingPipeline:
        def attach_progress_recorder(self, recorder: object) -> None:
            self.recorder = recorder

        def attach_audit_events(self, events: object) -> None:
            self.events = events

        async def run(
            self,
            submission_id: str,
            workflow_run_id: str,
            execution_token: str | None = None,
            correlation_id: str | None = None,
        ) -> None:
            del submission_id, workflow_run_id, execution_token, correlation_id
            raise ContextCollectionError()

    audited_failures: list[tuple[str, str, str]] = []

    class AuditEvents:
        def workflow_failed(
            self,
            workflow_id: str,
            correlation_id: str,
            failure_category: str,
        ) -> None:
            audited_failures.append((workflow_id, correlation_id, failure_category))

    executor = InProcessFeedbackExecutor(
        session_factory,
        lambda repository: FailingPipeline(),  # type: ignore[arg-type,return-value]
        now=lambda: NOW + timedelta(seconds=1),
        audit_events=AuditEvents(),  # type: ignore[arg-type]
    )
    asyncio.run(
        executor.execute(
            WORKFLOW_ID,
            "submission-1",
            claim.execution_token,
        )
    )

    with session_factory() as session:
        workflow = session.get(WorkflowRun, WORKFLOW_ID)
        assert workflow is not None
        assert workflow.current_stage is WorkflowStage.FAILED
        assert workflow.final_outcome is WorkflowOutcome.WORKFLOW_FAILED
        assert workflow.failure_category == "context_unavailable"
        assert workflow.lease_expires_at is None
    assert audited_failures == []

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_in_process_executor_audits_only_the_terminal_infrastructure_failure(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "terminal-executor.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    submission_id = "submission-terminal-failure"
    observed_at = NOW

    with session_factory() as session:
        repository = SqlAlchemyFeedbackWorkflowRepository(session)
        claim = repository.claim_workflow(
            submission_id,
            WORKFLOW_ID,
            started_at=observed_at,
            lease_expires_at=observed_at + timedelta(minutes=5),
        )
        for attempt in (1, 2):
            assert claim.execution_attempt_count == attempt
            repository.mark_failed(
                WORKFLOW_ID,
                "context_unavailable",
                observed_at,
                execution_token=claim.execution_token,
                retryable=True,
                next_retry_at=observed_at,
            )
            observed_at += timedelta(seconds=1)
            claim = repository.claim_workflow(
                submission_id,
                str(uuid4()),
                started_at=observed_at,
                lease_expires_at=observed_at + timedelta(minutes=5),
            )
        assert claim.execution_attempt_count == 3
        final_token = claim.execution_token

    class FailingPipeline:
        def attach_progress_recorder(self, recorder: object) -> None:
            del recorder

        def attach_audit_events(self, events: object) -> None:
            del events

        async def run(
            self,
            submission_id: str,
            workflow_run_id: str,
            execution_token: str | None = None,
            correlation_id: str | None = None,
        ) -> None:
            del submission_id, workflow_run_id, execution_token, correlation_id
            raise ContextCollectionError()

    audited_failures: list[tuple[str, str, str]] = []

    class AuditEvents:
        def workflow_failed(
            self,
            workflow_id: str,
            correlation_id: str,
            failure_category: str,
        ) -> None:
            audited_failures.append((workflow_id, correlation_id, failure_category))

    correlation_id = str(uuid4())
    executor = InProcessFeedbackExecutor(
        session_factory,
        lambda repository: FailingPipeline(),  # type: ignore[arg-type,return-value]
        now=lambda: observed_at,
        audit_events=AuditEvents(),  # type: ignore[arg-type]
    )
    asyncio.run(
        executor.execute(
            WORKFLOW_ID,
            submission_id,
            execution_token=final_token,
            correlation_id=correlation_id,
        )
    )

    assert audited_failures == [(WORKFLOW_ID, correlation_id, "context_unavailable")]
    with session_factory() as session:
        workflow = session.get(WorkflowRun, WORKFLOW_ID)
        assert workflow is not None
        assert workflow.current_stage is WorkflowStage.FAILED
        assert workflow.next_retry_at is None

    Base.metadata.drop_all(engine)
    engine.dispose()
