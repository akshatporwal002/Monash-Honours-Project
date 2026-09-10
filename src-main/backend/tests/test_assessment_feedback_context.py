import ast
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt
from support.task_review import bind_reviewed_fixture_form

from app.domain.assessment import CriterionDecision
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDefinitionVersion,
    CriterionEvaluation,
    TaskApproval,
    TaskFormVersion,
)
from app.models.lms import AttemptStatus, SubmissionAttempt
from app.models.persistence import LearningMaterial, LearningTask, MaterialChunk
from app.schemas.assessment import EvidenceReference
from app.schemas.feedback import (
    AssessmentContextStatus,
    AssessmentFeedbackContext,
    FeedbackPipelineStatus,
    SubmissionContext,
)
from app.services.assessment.feedback_context import (
    SqlAlchemyAssessmentFeedbackContextProvider,
)
from app.services.feedback.agent import PendingAssessmentFeedbackGenerator
from app.services.feedback.context import DefaultFeedbackContextCollector
from app.services.feedback.errors import AssessedFeedbackNotReadyError
from app.services.feedback.fakes import FakeFeedbackGenerator
from app.services.feedback.pipeline import FeedbackPipeline
from app.services.feedback.prompt import feedback_context_payload
from app.services.feedback.providers import SqlAlchemyTaskProvider
from app.services.feedback.repository import SqlAlchemyFeedbackWorkflowRepository
from app.services.feedback.runtime import LmsSubmissionProvider
from app.services.local_ai import LocalFeedbackJudge
from app.services.rag.source_history import bind_sources, record_approval, snapshot_source

NOW = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def _approved_attempt(db_session: Session):
    attempt, response, criterion, rule, owner = build_assessment_attempt(db_session)
    definition = db_session.get(
        AssessmentDefinitionVersion,
        attempt.assessment_definition_version_id,
    )
    task = db_session.get(LearningTask, attempt.task_id)
    assert definition is not None
    assert task is not None
    definition.formal_result_eligible = True
    definition.transfer_rule = {"required": False}
    definition.result_eligibility_declared_at = NOW
    material = LearningMaterial(
        course_id=attempt.course_id,
        original_filename="source.pdf",
        mime_type="application/pdf",
        content_hash="fixture-source",
    )
    db_session.add(material)
    db_session.flush()
    chunk = MaterialChunk(
        id="approved-source-1",
        material_id=material.id,
        chunk_index=0,
        chunk_text="The preserved source explains the interference pattern.",
        token_count=8,
        chunk_hash="fixture-passage",
    )
    db_session.add(chunk)
    revision = snapshot_source(db_session, material, [chunk])
    record_approval(
        db_session,
        course_id=attempt.course_id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id=str(owner.id),
        state="APPROVED",
        reason="Synthetic source reviewed for feedback context",
        expected_sequence=0,
    )
    task.source_references = [chunk.id]
    bind_sources(
        db_session,
        course_id=attempt.course_id,
        output_type="assessment",
        output_id=attempt.id,
        output_version=attempt.task_form_version_id,
        references=[chunk.id],
        strict=True,
    )
    db_session.commit()
    form = db_session.get(TaskFormVersion, attempt.task_form_version_id)
    review_event = bind_reviewed_fixture_form(db_session, form)
    form.approval_state = AssessmentApprovalState.APPROVED
    form.approved_at = NOW
    form.approved_by_user_id = owner.id
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = NOW
    definition.approved_by_user_id = owner.id
    db_session.add(
        TaskApproval(
            course_id=attempt.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=attempt.task_form_version_id,
            task_review_event_id=review_event.id,
            actor_user_id=owner.id,
            approval_reason="The frozen task form is approved for feedback context tests.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=NOW,
            approved_by_user_id=owner.id,
        )
    )
    db_session.commit()
    from app.schemas.episode import ResponseContent
    from app.services.episode_evidence import canonical_response_digest

    digest = canonical_response_digest(
        content=ResponseContent(
            answer=response.answer, code=response.code, circuit=response.circuit
        ),
        episode=None,
        schema_version=response.response_schema_version,
        assessment_work_start_id=response.assessment_work_start_id,
        task_form_version_id=response.task_form_version_id,
        declared_conditions=response.declared_conditions,
    )
    db_session.execute(
        update(SubmissionAttempt)
        .where(SubmissionAttempt.id == response.id)
        .values(content_digest=digest)
    )
    db_session.commit()
    return attempt, response, criterion, rule


def _submission(db_session: Session, response_id: str) -> SubmissionContext:
    submission = asyncio.run(LmsSubmissionProvider(db_session).get_submission(response_id))
    assert submission is not None
    return submission


def test_provider_resolves_frozen_assessment_and_criterion_evidence(
    db_session: Session,
) -> None:
    attempt, response, criterion, _ = _approved_attempt(db_session)
    submission = _submission(db_session, response.id)
    provider = SqlAlchemyAssessmentFeedbackContextProvider(db_session)

    first = asyncio.run(provider.resolve(submission))

    assert first.status is AssessmentContextStatus.RESOLVED
    assert first.context is not None
    assert first.context.assessment.assessment_attempt_id == attempt.id
    assert first.context.assessment.response_version_id == response.id
    assert first.context.response_content_digest == response.content_digest
    assert first.context.bloom_process.value == "ANALYSE"
    assert first.context.task.source_references == ["approved-source-1"]
    assert first.context.criteria[0].criterion_version_id == criterion.id
    assert first.context.criteria[0].evaluation is None

    evidence = EvidenceReference(
        assessment=first.context.assessment,
        evidence_id="criterion-evidence-1",
        evidence_type="learner_response",
        schema_version="learner-response.v1",
        record_version=1,
        content_digest=response.content_digest,
        source_record_id=response.id,
        source_record_version=1,
        occurred_at=NOW,
    )
    db_session.add(
        CriterionEvaluation(
            assessment_attempt_id=attempt.id,
            criterion_version_id=criterion.id,
            decision=CriterionDecision.MET,
            evidence_references=[evidence.model_dump(mode="json")],
            evaluator_reference="rules.v1",
            model_version="model.v1",
            prompt_version="prompt.v1",
            retrieval_version="retrieval.v1",
            reason="The response makes the evidence-to-claim link explicit.",
            evaluated_at=NOW,
        )
    )
    db_session.commit()

    resolved = asyncio.run(provider.resolve(submission))

    assert resolved.status is AssessmentContextStatus.RESOLVED
    assert resolved.context is not None
    evaluation = resolved.context.criteria[0].evaluation
    # Automated evidence is preserved but is not a current human judgement.
    assert evaluation is None


def test_collector_uses_frozen_task_context_without_legacy_marking_fields(
    db_session: Session,
) -> None:
    _, response, _, _ = _approved_attempt(db_session)
    submission = _submission(db_session, response.id)
    collector = DefaultFeedbackContextCollector(
        SqlAlchemyTaskProvider(db_session),
        assessment_context_provider=SqlAlchemyAssessmentFeedbackContextProvider(db_session),
    )

    context = asyncio.run(collector.collect(submission, "00000000-0000-4000-8000-000000000001"))

    assert not hasattr(context.submission, "score")
    assert context.assessment_context is not None
    assert context.task == context.assessment_context.task
    assert context.task.marking_criteria is not None


def test_provider_fails_closed_for_cross_course_stale_and_missing_context(
    db_session: Session,
) -> None:
    attempt, response, _, _ = _approved_attempt(db_session)
    submission = _submission(db_session, response.id)
    provider = SqlAlchemyAssessmentFeedbackContextProvider(db_session)
    cross_course = SubmissionContext.model_validate(
        {**submission.model_dump(), "course_id": "another-course"}
    )
    stale_task = SubmissionContext.model_validate(
        {**submission.model_dump(), "task_id": "another-task"}
    )

    assert (
        asyncio.run(provider.resolve(cross_course)).status is AssessmentContextStatus.ACCESS_DENIED
    )
    assert asyncio.run(provider.resolve(stale_task)).status is AssessmentContextStatus.ACCESS_DENIED

    missing_response = SubmissionAttempt(
        draft_id=response.draft_id,
        student_id=attempt.student_id,
        task_id=attempt.task_id,
        attempt_number=2,
        status=AttemptStatus.SUBMITTED,
        answer="A second immutable response without its assessment attempt.",
        feedback="Response recorded.",
        task_form_version_id=attempt.task_form_version_id,
        response_schema_version="assessment.response.v1",
        content_digest=f"sha256:{'b' * 64}",
        idempotency_key="missing-assessment-attempt",
        declared_conditions={},
    )
    db_session.add(missing_response)
    db_session.commit()

    missing_submission = _submission(db_session, missing_response.id)
    missing = asyncio.run(provider.resolve(missing_submission))
    assert missing.status is AssessmentContextStatus.MISSING
    assert missing.reason_code == "ASSESSMENT_ATTEMPT_MISSING"


def test_assessed_context_has_no_formal_result_or_numeric_score_authority(
    db_session: Session,
) -> None:
    _, response, _, _ = _approved_attempt(db_session)
    submission = _submission(db_session, response.id)
    resolution = asyncio.run(
        SqlAlchemyAssessmentFeedbackContextProvider(db_session).resolve(submission)
    )
    assert resolution.context is not None

    context_fields = set(AssessmentFeedbackContext.model_fields)
    assert {"result", "result_state", "reason_code", "score"}.isdisjoint(context_fields)
    payload = json.dumps(resolution.context.model_dump(mode="json"), sort_keys=True)
    assert '"score"' not in payload
    assert '"result"' not in payload

    service_root = Path(__file__).parents[1] / "app" / "services" / "feedback"
    forbidden_modules = {
        "app.models.assessment",
        "app.services.assessment.evaluation",
        "app.services.assessment.review",
    }
    offenders: list[Path] = []
    for path in service_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.ImportFrom) and node.module in forbidden_modules
            for node in ast.walk(tree)
        ):
            offenders.append(path)
    assert offenders == []


def test_pending_generation_gate_releases_no_assessed_classification(
    db_session: Session,
) -> None:
    _, response, _, _ = _approved_attempt(db_session)
    submission = _submission(db_session, response.id)
    collector = DefaultFeedbackContextCollector(
        SqlAlchemyTaskProvider(db_session),
        assessment_context_provider=SqlAlchemyAssessmentFeedbackContextProvider(db_session),
    )
    context = asyncio.run(collector.collect(submission, "00000000-0000-4000-8000-000000000002"))
    delegate = FakeFeedbackGenerator(None)  # type: ignore[arg-type]

    with pytest.raises(AssessedFeedbackNotReadyError):
        asyncio.run(PendingAssessmentFeedbackGenerator(delegate).generate(context))

    assert delegate.call_count == 0
    prompt_payload = feedback_context_payload(context)
    assert "assessment_context" in prompt_payload
    assert "score" not in prompt_payload["submission"]


def test_production_assessed_context_releases_safe_fallback_until_step4(
    db_session: Session,
) -> None:
    _, response, _, _ = _approved_attempt(db_session)
    delegate = FakeFeedbackGenerator(None)  # type: ignore[arg-type]
    collector = DefaultFeedbackContextCollector(
        SqlAlchemyTaskProvider(db_session),
        assessment_context_provider=SqlAlchemyAssessmentFeedbackContextProvider(db_session),
    )
    pipeline = FeedbackPipeline(
        LmsSubmissionProvider(db_session),
        collector,
        PendingAssessmentFeedbackGenerator(delegate),
        LocalFeedbackJudge(),
        SqlAlchemyFeedbackWorkflowRepository(db_session),
    )

    result = asyncio.run(pipeline.run(response.id))

    assert result.status is FeedbackPipelineStatus.FALLBACK
    assert result.safe_fallback is not None
    assert delegate.call_count == 0
