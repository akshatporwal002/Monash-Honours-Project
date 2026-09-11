"""Real persistence, lease fencing, and mounted choice boundaries."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import create_session_factory
from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.continuation import ContinuationJob
from app.models.enums import (
    FeedbackStatus,
    JudgeDecision,
    JudgeEvaluationStatus,
    WorkflowOutcome,
    WorkflowStage,
)
from app.models.learner_model import LearnerModelSnapshot
from app.models.lms import Enrollment, EnrollmentStatus
from app.models.persistence import FeedbackRecord, JudgeEvaluation, WorkflowRun
from app.schemas.activity_continuation import ActivityAction
from app.schemas.lms import SubmissionCreate
from app.services.continuation import SqlAlchemyContinuationRepository, TerminalFeedbackNotice
from app.services.continuation.activity import ActivityService, ApprovedActivityAdapter
from app.services.continuation.contracts import NextTaskRequest, ProgressUpdate
from app.services.lms import LmsService
from app.worker import _ContinuationDatabasePass, build_offline_worker_adapters

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")

NOW = datetime.now(UTC)


@pytest.fixture
def context(db_session):
    from support.curriculum import setup_curriculum

    curriculum = setup_curriculum(db_session)
    _, teacher, student, course, tasks, _, _ = curriculum
    attempt = LmsService(db_session).submit(
        student, tasks[0].id, SubmissionCreate(answer="b", idempotency_key="activity-response")
    )
    workflow = db_session.scalar(select(WorkflowRun).where(WorkflowRun.submission_id == attempt.id))
    workflow.current_stage = WorkflowStage.COMPLETED
    workflow.final_outcome = WorkflowOutcome.FIRST_PASS
    workflow.completed_at = NOW
    workflow.execution_token = None
    workflow.lease_expires_at = None
    db_session.flush()
    feedback = FeedbackRecord(
        id=str(uuid4()),
        submission_id=attempt.id,
        workflow_run_id=workflow.id,
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="local",
        model="checked-fixture",
        prompt_version="v1",
        feedback_content={"summary": "Review the approved concept"},
    )
    db_session.add(feedback)
    db_session.flush()
    db_session.add(
        JudgeEvaluation(
            feedback_id=feedback.id,
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=JudgeDecision.PASS,
            decision=JudgeDecision.PASS,
            reason="Checked feedback",
            provider="local",
            model="checked-fixture",
            prompt_version="v1",
            correctness_score=90,
            relevance_score=90,
            grounding_score=90,
            actionability_score=90,
            safety_score=90,
        )
    )
    db_session.commit()
    notice = TerminalFeedbackNotice(
        workflow.id, "v1_" + "a" * 64, course.id, tasks[0].id, str(uuid4())
    )
    SqlAlchemyContinuationRepository(db_session).ensure_pending(notice)
    factory = create_session_factory(db_session.get_bind())
    return curriculum, workflow.id, factory, notice


def run_worker(factory, now=NOW):
    worker = _ContinuationDatabasePass(
        factory,
        build_offline_worker_adapters(Settings(_env_file=None, research_enabled=False)),
        now=lambda: now,
        lease_duration=timedelta(minutes=5),
        provider_timeout_seconds=30,
        maximum_attempts=3,
    )
    return asyncio.run(worker.run_once())


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def claim(context, now=NOW):
    _, _, factory, _ = context
    with factory() as session:
        result = SqlAlchemyContinuationRepository(session).claim_next(
            now=now,
            lease_expires_at=now + timedelta(seconds=10),
            execution_token=str(uuid4()),
            maximum_attempts=3,
        )
    return result


def progress_request(claim):
    return ProgressUpdate(
        claim.workflow_run_id,
        claim.pseudonymous_actor_reference,
        claim.course_reference,
        claim.completed_task_reference,
        claim.workflow_run_id,
        claim.correlation_id,
        claim.execution_token,
    )


def next_request(claim):
    return NextTaskRequest(
        claim.workflow_run_id,
        claim.pseudonymous_actor_reference,
        claim.course_reference,
        claim.completed_task_reference,
        claim.correlation_id,
        claim.execution_token,
    )


def test_shipped_worker_updates_once_and_choices_survive_reload(context, db_session):
    curriculum, identity, factory, notice = context
    _, teacher, learner, _, tasks, _, _ = curriculum
    result = run_worker(factory)
    assert result.state.value == "completed", result
    assert not run_worker(factory).processed
    SqlAlchemyContinuationRepository(db_session).ensure_pending(notice)
    assert (
        count(db_session, ActivityProgress)
        == count(db_session, ActivitySuggestion)
        == count(db_session, LearnerModelSnapshot)
        == 1
    )
    service = ActivityService(db_session)
    view = service.read(learner, identity)
    assert view.next_task_id == tasks[1].id and view.next_task_id != tasks[0].id
    assert view.uncertainty == 1 and view.evidence_ids and view.snapshot_id
    for version, action in enumerate(("accept", "defer", "replace", "educator_override")):
        command = ActivityAction(
            expected_version=version,
            request_key=action,
            action=action,
            task_id=tasks[1].id if action in {"replace", "educator_override"} else None,
            reason="Keep the approved practice sequence" if action == "educator_override" else "",
        )
        actor = teacher if action == "educator_override" else learner
        assert service.act(actor, identity, command).version == version + 1
        assert service.act(actor, identity, command).version == version + 1
    with factory() as reloaded:
        saved = ActivityService(reloaded).read(learner, identity)
        assert [item.action for item in saved.history] == [
            "accept",
            "defer",
            "replace",
            "educator_override",
        ]
        assert saved.next_task_id == tasks[1].id


def test_restart_after_model_receipt_and_stale_worker(context, db_session):
    _, _, factory, _ = context
    old = claim(context)
    adapter = ApprovedActivityAdapter(factory, now=lambda: NOW)
    asyncio.run(adapter.record_terminal_feedback(progress_request(old)))
    asyncio.run(adapter.record_terminal_feedback(progress_request(old)))
    assert count(db_session, LearnerModelSnapshot) == 1
    assert run_worker(factory, NOW + timedelta(seconds=11)).state.value == "completed"
    for operation, request in (
        (adapter.record_terminal_feedback, progress_request(old)),
        (adapter.recommend_next_task, next_request(old)),
    ):
        with pytest.raises(RuntimeError, match="claim"):
            asyncio.run(operation(request))
    assert count(db_session, LearnerModelSnapshot) == count(db_session, ActivitySuggestion) == 1


def test_expired_lease_without_replacement_cannot_write(context, db_session):
    _, _, factory, _ = context
    old = claim(context)
    adapter = ApprovedActivityAdapter(factory, now=lambda: NOW + timedelta(seconds=11))
    with pytest.raises(RuntimeError, match="claim"):
        asyncio.run(adapter.record_terminal_feedback(progress_request(old)))
    assert count(db_session, ActivityProgress) == count(db_session, LearnerModelSnapshot) == 0


def test_failed_progress_receipt_rolls_back_model(context, db_session, monkeypatch):
    _, _, factory, _ = context
    current = claim(context)
    original = Session.flush

    def failed(session, *args, **kwargs):
        if any(isinstance(item, ActivityProgress) for item in session.new):
            raise RuntimeError("injected receipt failure")
        return original(session, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "flush", failed)
        with pytest.raises(RuntimeError, match="receipt"):
            asyncio.run(
                ApprovedActivityAdapter(factory, now=lambda: NOW).record_terminal_feedback(
                    progress_request(current)
                )
            )
    assert count(db_session, LearnerModelSnapshot) == count(db_session, ActivityProgress) == 0
    asyncio.run(
        ApprovedActivityAdapter(factory, now=lambda: NOW).record_terminal_feedback(
            progress_request(current)
        )
    )
    assert count(db_session, LearnerModelSnapshot) == 1


def test_concurrent_delivery_same_claim_is_idempotent(context, db_session):
    from concurrent.futures import ThreadPoolExecutor

    _, _, factory, _ = context
    current = claim(context)
    db_session.rollback()

    def deliver():
        adapter = ApprovedActivityAdapter(factory, now=lambda: NOW)
        asyncio.run(adapter.record_terminal_feedback(progress_request(current)))
        return asyncio.run(adapter.recommend_next_task(next_request(current)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: deliver(), range(2)))
    assert results[0] == results[1]
    assert (
        count(db_session, ActivityProgress)
        == count(db_session, ActivitySuggestion)
        == count(db_session, LearnerModelSnapshot)
        == 1
    )


def test_opt_out_stops_model_and_optional_suggestion(context, db_session):
    from app.schemas.learner_preferences import PreferenceUpdate, PreferenceValues
    from app.services.learner_preferences import LearnerPreferenceService

    curriculum, identity, factory, _ = context
    learner = curriculum[2]
    LearnerPreferenceService(db_session).save(
        learner,
        PreferenceUpdate(
            expected_version=0,
            request_key="off",
            values=PreferenceValues(personalisation_enabled=False),
        ),
    )
    assert run_worker(factory).state.value == "completed"
    assert ActivityService(db_session).read(learner, identity).state == "personalisation_disabled"
    assert count(db_session, LearnerModelSnapshot) == 0
    db_session.expire_all()
    assert db_session.get(ContinuationJob, identity).next_task_reference is None


def test_revoked_access_and_forged_scope_cannot_write(context, db_session):
    curriculum, _, factory, _ = context
    current = claim(context)
    adapter = ApprovedActivityAdapter(factory, now=lambda: NOW)
    with pytest.raises(RuntimeError, match="scope"):
        asyncio.run(
            adapter.record_terminal_feedback(
                replace(progress_request(current), completed_task_reference="foreign")
            )
        )
    db_session.execute(
        update(Enrollment)
        .where(Enrollment.student_id == curriculum[2].id)
        .values(status=EnrollmentStatus.WITHDRAWN)
    )
    db_session.commit()
    with pytest.raises(HTTPException):
        asyncio.run(adapter.record_terminal_feedback(progress_request(current)))
    assert count(db_session, ActivityProgress) == 0


def test_changed_approval_rejects_action_and_retains_history(context, db_session):
    curriculum, identity, factory, _ = context
    run_worker(factory)
    _, teacher, learner, _, tasks, _, _ = curriculum
    service = ActivityService(db_session)
    service.act(
        learner, identity, ActivityAction(expected_version=0, request_key="defer", action="defer")
    )
    tasks[1].title = "A changed approved task"
    db_session.commit()
    assert service.read(learner, identity).state == "stale_approval"
    with pytest.raises(HTTPException):
        service.act(
            teacher,
            identity,
            ActivityAction(
                expected_version=1,
                request_key="override",
                action="educator_override",
                task_id=tasks[1].id,
                reason="Try another activity",
            ),
        )
    assert count(db_session, ActivityChoice) == 1


def test_expiry_during_write_rolls_back_every_side_effect(context, db_session):
    _, _, factory, _ = context
    current = claim(context)
    moments = iter([NOW, NOW + timedelta(seconds=11)])
    adapter = ApprovedActivityAdapter(factory, now=lambda: next(moments))
    with pytest.raises(RuntimeError, match="claim"):
        asyncio.run(adapter.record_terminal_feedback(progress_request(current)))
    assert count(db_session, ActivityProgress) == count(db_session, LearnerModelSnapshot) == 0


def test_failed_suggestion_commit_retries_without_another_model_update(
    context, db_session, monkeypatch
):
    _, _, factory, _ = context
    current = claim(context)
    adapter = ApprovedActivityAdapter(factory, now=lambda: NOW)
    asyncio.run(adapter.record_terminal_feedback(progress_request(current)))
    original = Session.flush

    def fail(session, *args, **kwargs):
        if any(isinstance(item, ActivitySuggestion) for item in session.new):
            raise RuntimeError("injected suggestion failure")
        return original(session, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "flush", fail)
        with pytest.raises(RuntimeError, match="suggestion"):
            asyncio.run(adapter.recommend_next_task(next_request(current)))
    assert count(db_session, ActivitySuggestion) == 0
    assert run_worker(factory, NOW + timedelta(seconds=11)).state.value == "completed"
    assert count(db_session, LearnerModelSnapshot) == count(db_session, ActivitySuggestion) == 1


def test_conflicting_concurrent_choices_keep_one_linear_history(context, db_session):
    from concurrent.futures import ThreadPoolExecutor

    curriculum, identity, factory, _ = context
    run_worker(factory)
    learner = curriculum[2]
    db_session.rollback()

    def choose(action):
        with factory() as session:
            try:
                return (
                    ActivityService(session)
                    .act(
                        learner,
                        identity,
                        ActivityAction(expected_version=0, request_key=action, action=action),
                    )
                    .version
                )
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(choose, ("accept", "defer")))
    assert sorted(results) == [1, 409]
    assert count(db_session, ActivityChoice) == 1


def test_safe_fallback_never_updates_the_model(context, db_session):
    curriculum, identity, factory, _ = context
    workflow = db_session.get(WorkflowRun, identity)
    workflow.final_outcome = WorkflowOutcome.SAFE_FALLBACK
    db_session.commit()
    assert run_worker(factory).state.value == "completed"
    view = ActivityService(db_session).read(curriculum[2], identity)
    assert view.state == "feedback_not_eligible" and view.next_task_id is None
    assert count(db_session, LearnerModelSnapshot) == 0


def test_completed_path_returns_null_and_never_repeats_completed_task(context, db_session):
    curriculum, identity, factory, _ = context
    learner, tasks = curriculum[2], curriculum[4]
    for task, answer in zip(tasks[1:], ('["b"]', "practice"), strict=True):
        LmsService(db_session).submit(
            learner, task.id, SubmissionCreate(answer=answer, idempotency_key=task.id)
        )
    assert run_worker(factory).state.value == "completed"
    view = ActivityService(db_session).read(learner, identity)
    assert view.state == "no_eligible_activity" and view.next_task_id is None and not view.options


def test_approved_practice_exit_uses_response_not_legacy_score(context, db_session):
    from app.services.curriculum import pathway_completions

    curriculum, _, _, _ = context
    learner, tasks = curriculum[2], curriculum[4]
    # The approved graph says accepted response; this answer need not pass legacy grading.
    LmsService(db_session).submit(
        learner,
        tasks[1].id,
        SubmissionCreate(answer='["b"]', idempotency_key="practice-exit"),
    )
    assert tasks[1].id in pathway_completions(db_session, learner.id, tasks[2])
    LmsService(db_session)._require_unlocked(learner, tasks[2])
    assert (
        LmsService(db_session).get_student_task(learner, tasks[2].id).access_status == "available"
    )


def test_route_scope_strict_fields_csrf_and_choice_rollback(context, db_session, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError

    from app.api.dependencies.authentication import get_current_user
    from app.core.config import settings
    from app.db.session import get_db
    from app.main import create_app

    curriculum, identity, factory, _ = context
    run_worker(factory)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: curriculum[2]
    url = f"/api/v1/activity-continuation/{identity}"
    with TestClient(app) as client:
        response = client.get(url)
        assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
        command = dict(expected_version=0, request_key="api-choice", action="accept")
        client.cookies.set(settings.csrf_cookie_name, "task22-csrf")
        assert client.post(url + "/actions", json=command).status_code == 403
        client.cookies.set(settings.csrf_cookie_name, "task22-csrf")
        headers = {
            settings.csrf_header_name: "task22-csrf",
            "Origin": settings.allowed_cors_origins[0],
        }
        for field in (
            "learner_id",
            "bloom_target",
            "pass_rule",
            "formal_result",
            "diagnosis",
            "research_condition",
        ):
            assert (
                client.post(
                    url + "/actions", json={**command, field: "forged"}, headers=headers
                ).status_code
                == 422
            )
        original = Session.commit

        def fail(session):
            if any(isinstance(item, ActivityChoice) for item in session.new):
                raise OperationalError("injected", {}, Exception())
            return original(session)

        with monkeypatch.context() as patch:
            patch.setattr(Session, "commit", fail)
            assert client.post(url + "/actions", json=command, headers=headers).status_code == 503
        assert count(db_session, ActivityChoice) == 0
        assert client.post(url + "/actions", json=command, headers=headers).status_code == 200
        assert client.post(url + "/actions", json=command, headers=headers).json()["version"] == 1
        db_session.execute(
            update(Enrollment)
            .where(Enrollment.student_id == curriculum[2].id)
            .values(status=EnrollmentStatus.WITHDRAWN)
        )
        db_session.commit()
        assert client.get(url).status_code == 404


def test_migration_replay_protects_populated_activity_history(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, text
    from test_migrations import migration_config

    url = f"sqlite:///{(tmp_path / 'activity.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with Session(engine) as session:
        fixture = context.__wrapped__(session)
        assert run_worker(fixture[2]).state.value == "completed"
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER activity_suggestions_no_delete"))
    command.stamp(config, "20260909_0041")
    command.upgrade(config, "head")
    with engine.begin() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        for statement in (
            "DELETE FROM activity_suggestions",
            "UPDATE activity_progress_receipts SET state='changed'",
            "INSERT OR REPLACE INTO activity_suggestions SELECT * FROM activity_suggestions",
        ):
            with pytest.raises(Exception, match="history is protected"):
                connection.execute(text(statement))
    with pytest.raises(RuntimeError):
        command.downgrade(config, "20260909_0041")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260911_0051"
        )
        assert (
            connection.execute(text("SELECT COUNT(*) FROM activity_suggestions")).scalar_one() == 1
        )
    engine.dispose()


def test_accepted_task19_correction_is_consumed_without_rewriting_prior_model(context, db_session):
    from app.domain.platform_enums import (
        CorrectionAction,
        CorrectionTargetKind,
        EvidenceLinkRelation,
    )
    from app.models.learner_model import LearnerModelCorrectionSnapshotLink
    from app.models.learning_evidence import LearningEvidence
    from app.services.continuation.activity import MODEL_RULE, RULE, ObservationBuilder
    from app.services.learner_model.builder import (
        DeterministicLearnerModelBuilder,
        LearnerModelBuildService,
    )
    from app.services.learner_model.contracts import (
        LearnerModelEvidenceSignal,
        LearnerModelUpdateCommand,
    )
    from app.services.learner_model.correction_contracts import (
        CorrectionTarget,
        EducatorCorrectionReviewCommand,
        LearnerAnnotationCommand,
    )
    from app.services.learner_model.correction_repository import (
        SqlAlchemyLearnerModelCorrectionRepository,
    )
    from app.services.learner_model.corrections import LearnerModelCorrectionService
    from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository

    curriculum, identity, factory, notice = context
    _, teacher, learner, course, tasks, _, _ = curriculum
    evidence = db_session.scalar(select(LearningEvidence))
    result = LearnerModelBuildService(
        SqlAlchemyLearnerModelRepository(db_session), ObservationBuilder([evidence.id])
    ).update(
        LearnerModelUpdateCommand(
            course_id=course.id,
            learner_id=str(learner.id),
            outcome_id=tasks[0].learning_outcome_id,
            model_version=DeterministicLearnerModelBuilder.model_version,
            rule_version=MODEL_RULE,
            actor_reference=str(learner.id),
            agent_reference=RULE,
            adjudicator_reference="learner-model-rule-engine.v1",
            adjudication_rule_version=MODEL_RULE,
            correlation_id=notice.correlation_id,
            evidence_signals=(
                LearnerModelEvidenceSignal(
                    evidence_id=evidence.id, relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    original_id = result.snapshot.snapshot_id
    target = CorrectionTarget(target_kind=CorrectionTargetKind.EVIDENCE, evidence_id=evidence.id)
    common = dict(
        course_id=course.id,
        learner_id=str(learner.id),
        outcome_id=tasks[0].learning_outcome_id,
        target=target,
        correlation_id=notice.correlation_id,
        occurred_at=NOW,
    )
    corrections = LearnerModelCorrectionService(
        SqlAlchemyLearnerModelCorrectionRepository(db_session)
    )
    annotation = corrections.annotate(
        LearnerAnnotationCommand(
            **common,
            annotation_id=str(uuid4()),
            record_version=1,
            actor_reference=str(learner.id),
            idempotency_key="annotate",
            note="The observation needs more context.",
        )
    ).annotation
    corrections.review(
        EducatorCorrectionReviewCommand(
            **common,
            review_id=str(uuid4()),
            annotation_id=annotation.annotation_id,
            review_version=1,
            expected_latest_review_version=0,
            action=CorrectionAction.ACCEPTED,
            actor_reference=str(teacher.id),
            idempotency_key="review",
            reason="The context should be reviewed.",
        )
    )
    assert run_worker(factory).state.value == "completed"
    assert count(db_session, LearnerModelSnapshot) == 2
    assert db_session.get(LearnerModelSnapshot, original_id) is not None
    assert count(db_session, LearnerModelCorrectionSnapshotLink) == 1
    view = ActivityService(db_session).read(learner, identity)
    assert view.state == "conflicting_evidence" and view.next_task_id is None
    assert view.options
    assert not run_worker(factory).processed
    assert count(db_session, LearnerModelSnapshot) == 2


def test_missing_legacy_evidence_records_no_inference(context, db_session):
    from app.models.lms import AttemptStatus, SubmissionAttempt

    curriculum, identity, factory, _ = context
    workflow = db_session.get(WorkflowRun, identity)
    original = db_session.get(SubmissionAttempt, workflow.submission_id)
    legacy = SubmissionAttempt(
        id=str(uuid4()),
        draft_id=original.draft_id,
        student_id=original.student_id,
        task_id=original.task_id,
        attempt_number=2,
        status=AttemptStatus.SUBMITTED,
        answer="Legacy response",
        feedback="Preserved legacy response",
    )
    db_session.add(legacy)
    db_session.flush()
    # Simulate an old imported workflow that predates live evidence capture.
    previous_feedback = db_session.scalar(
        select(FeedbackRecord).where(FeedbackRecord.workflow_run_id == identity)
    )
    previous_judge = previous_feedback.judge_evaluation
    legacy_workflow = WorkflowRun(
        id=str(uuid4()),
        submission_id=legacy.id,
        task_id=original.task_id,
        course_id=curriculum[3].id,
        current_stage=WorkflowStage.COMPLETED,
        final_outcome=WorkflowOutcome.FIRST_PASS,
        completed_at=NOW,
        started_at=NOW,
    )
    db_session.add(legacy_workflow)
    db_session.flush()
    feedback = FeedbackRecord(
        **{
            column.name: getattr(previous_feedback, column.name)
            for column in FeedbackRecord.__table__.columns
            if column.name not in {"id", "workflow_run_id", "submission_id"}
        },
        id=str(uuid4()),
        workflow_run_id=legacy_workflow.id,
        submission_id=legacy.id,
    )
    db_session.add(feedback)
    db_session.flush()
    db_session.add(
        JudgeEvaluation(
            **{
                column.name: getattr(previous_judge, column.name)
                for column in JudgeEvaluation.__table__.columns
                if column.name not in {"id", "feedback_id"}
            },
            id=str(uuid4()),
            feedback_id=feedback.id,
        )
    )
    db_session.commit()
    SqlAlchemyContinuationRepository(db_session).ensure_pending(
        TerminalFeedbackNotice(
            legacy_workflow.id, "v1_" + "a" * 64, curriculum[3].id, original.task_id, str(uuid4())
        )
    )
    assert run_worker(factory).state.value == "completed"
    assert run_worker(factory).state.value == "completed"
    view = ActivityService(db_session).read(curriculum[2], legacy_workflow.id)
    assert view.state == "insufficient_evidence" and view.next_task_id is None
    assert count(db_session, LearnerModelSnapshot) == 1


def test_dashboard_projects_saved_choice_and_respects_deferral_and_opt_out(context, db_session):
    from app.schemas.learner_preferences import PreferenceUpdate, PreferenceValues
    from app.services.learner_preferences import LearnerPreferenceService

    curriculum, identity, factory, _ = context
    learner, tasks = curriculum[2], curriculum[4]
    assert run_worker(factory).state.value == "completed"
    lms = LmsService(db_session)
    assert [row.task_id for row in lms.student_dashboard(learner).recommendations] == [tasks[1].id]
    activity = ActivityService(db_session)
    activity.act(
        learner,
        identity,
        ActivityAction(expected_version=0, request_key="defer-dashboard", action="defer"),
    )
    assert lms.student_dashboard(learner).recommendations == []
    activity.act(
        learner,
        identity,
        ActivityAction(
            expected_version=1,
            request_key="replace-dashboard",
            action="replace",
            task_id=tasks[1].id,
        ),
    )
    restored = lms.student_dashboard(learner).recommendations
    assert [row.task_id for row in restored] == [tasks[1].id]
    assert "average" not in restored[0].reason
    LearnerPreferenceService(db_session).save(
        learner,
        PreferenceUpdate(
            expected_version=0,
            request_key="off-dashboard",
            values=PreferenceValues(personalisation_enabled=False),
        ),
    )
    assert lms.student_dashboard(learner).recommendations == []
    assert count(db_session, ActivityChoice) == 2
    assert count(db_session, ActivitySuggestion) == 1
