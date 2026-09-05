"""Service and route-contract tests for provisional assessment evaluation."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt as _attempt_context

from app.domain.assessment import (
    AssessmentAttemptState,
    CriterionDecision,
    QualityReviewDecision,
    ResultState,
)
from app.main import create_app
from app.models.assessment import (
    AssessmentApprovalState,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    CriterionEvaluation,
    PassRuleVersion,
    TaskApproval,
)
from app.models.lms import PlatformAuditEvent
from app.schemas.assessment import EvidenceReference
from app.services.assessment.evaluation import (
    AssessmentEvaluationConflictError,
    AssessmentEvaluationFaultError,
    AssessmentEvaluationService,
)
from app.services.assessment.evaluators import EvaluatorOutcome


class StaticCriterionPort:
    def __init__(
        self, decision: CriterionDecision = CriterionDecision.MET, *, fails: bool = False
    ) -> None:
        self.decision = decision
        self.fails = fails

    def evaluate(self, *, assessment, response_text, bloom_process, criterion) -> EvaluatorOutcome:
        if self.fails:
            raise TimeoutError("provider unavailable")
        evidence = EvidenceReference(
            assessment=assessment,
            evidence_id=f"evidence-{criterion.id}",
            evidence_type="learner_response",
            schema_version="learner-response.v1",
            record_version=1,
            content_digest="sha256:" + "a" * 64,
            source_record_id=assessment.response_version_id,
            source_record_version=1,
            occurred_at=datetime(2026, 8, 16, tzinfo=UTC),
        )
        return EvaluatorOutcome(
            decision=self.decision,
            reason="The response contains the approved criterion evidence.",
            evidence=(evidence,),
            evaluator_type=criterion.evaluator_type,
            evaluator_reference="test.evaluator.v1",
        )


class StaticQualityPort:
    def __init__(
        self,
        decision: QualityReviewDecision | None = QualityReviewDecision.APPROVED,
        *,
        fails: bool = False,
    ) -> None:
        self.decision = decision
        self.fails = fails
        self.calls: list[dict[str, object]] = []

    def review(self, *, assessment, reason_code, evidence):
        if self.fails:
            raise RuntimeError("quality provider unavailable")
        self.calls.append(
            {"assessment": assessment, "reason_code": reason_code, "evidence": evidence}
        )
        return self.decision


def _ready_attempt(session: Session):
    attempt, response, _, rule, owner = _attempt_context(session)
    definition = session.get(AssessmentDefinitionVersion, attempt.assessment_definition_version_id)
    form = response.task_form_version
    assert definition is not None and form is not None
    definition.formal_result_eligible = True
    definition.result_eligibility_declared_at = datetime(2026, 8, 16, tzinfo=UTC)
    session.commit()
    definition.approval_state = AssessmentApprovalState.APPROVED
    definition.approved_at = datetime(2026, 8, 16, tzinfo=UTC)
    definition.approved_by_user_id = owner.id
    session.add(
        TaskApproval(
            course_id=attempt.course_id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            actor_user_id=owner.id,
            approval_reason="The frozen task form is approved for this assessment.",
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=datetime(2026, 8, 16, tzinfo=UTC),
            approved_by_user_id=owner.id,
        )
    )
    session.commit()
    return attempt, response, definition, rule, owner


def _service(session: Session, criterion=None, quality=None) -> AssessmentEvaluationService:
    return AssessmentEvaluationService(
        session,
        criterion_port=criterion or StaticCriterionPort(),
        quality_port=quality or StaticQualityPort(),
        correlation_id="00000000-0000-4000-8000-000000000012",
    )


def test_complete_valid_evaluation_creates_one_provisional_decision(db_session: Session) -> None:
    attempt, _, _, _, _ = _ready_attempt(db_session)
    quality = StaticQualityPort()

    result = _service(db_session, quality=quality).evaluate(
        assessment_attempt_id=attempt.id,
        evaluation_idempotency_key="evaluation-key-1",
    )

    decision = db_session.get(AssessmentDecision, result.decision_id)
    assert decision is not None
    assert result.result.value == "PASS"
    assert result.result_state is ResultState.PROVISIONAL
    assert attempt.state is AssessmentAttemptState.EVALUATED
    assert len(db_session.scalars(select(CriterionEvaluation)).all()) == 1
    assert quality.calls and "result" not in quality.calls[0]


def test_duplicate_evaluation_request_replays_one_decision(db_session: Session) -> None:
    attempt, _, _, _, _ = _ready_attempt(db_session)
    service = _service(db_session)

    first = service.evaluate(
        assessment_attempt_id=attempt.id, evaluation_idempotency_key="repeat-key"
    )
    replay = service.evaluate(
        assessment_attempt_id=attempt.id, evaluation_idempotency_key="repeat-key"
    )

    assert replay.decision_id == first.decision_id
    assert replay.replayed is True
    assert len(db_session.scalars(select(AssessmentDecision)).all()) == 1


def test_stale_rule_or_response_version_returns_conflict(db_session: Session) -> None:
    attempt, _, definition, rule, owner = _ready_attempt(db_session)
    later_rule = PassRuleVersion(
        course_id=attempt.course_id,
        pass_rule_id=rule.pass_rule_id,
        assessment_definition_version_id=definition.id,
        version=rule.version + 1,
        owner_user_id=owner.id,
        created_by_user_id=owner.id,
        expression=rule.expression,
        approval_state=AssessmentApprovalState.APPROVED,
        approved_at=datetime(2026, 8, 17, tzinfo=UTC),
        approved_by_user_id=owner.id,
    )
    db_session.add(later_rule)
    db_session.commit()

    with pytest.raises(AssessmentEvaluationConflictError, match="pass rule changed"):
        _service(db_session).evaluate(
            assessment_attempt_id=attempt.id,
            evaluation_idempotency_key="stale-key",
        )

    assert db_session.scalar(select(AssessmentDecision)) is None
    assert attempt.state is AssessmentAttemptState.PENDING


@pytest.mark.parametrize("criterion_fault,quality_fault", [(True, False), (False, True)])
def test_task_evaluator_and_quality_faults_create_no_formal_result(
    db_session: Session,
    criterion_fault: bool,
    quality_fault: bool,
) -> None:
    attempt, _, _, _, _ = _ready_attempt(db_session)

    with pytest.raises(AssessmentEvaluationFaultError):
        _service(
            db_session,
            criterion=StaticCriterionPort(fails=criterion_fault),
            quality=StaticQualityPort(fails=quality_fault),
        ).evaluate(assessment_attempt_id=attempt.id, evaluation_idempotency_key="fault-key")

    assert db_session.scalar(select(AssessmentDecision)) is None
    assert attempt.state is AssessmentAttemptState.FAULTED


def test_quality_rejection_stays_separate_from_learner_result(db_session: Session) -> None:
    attempt, _, _, _, _ = _ready_attempt(db_session)
    quality = StaticQualityPort(QualityReviewDecision.REJECTED)

    result = _service(db_session, quality=quality).evaluate(
        assessment_attempt_id=attempt.id,
        evaluation_idempotency_key="rejected-quality-key",
    )

    audit = db_session.scalar(
        select(PlatformAuditEvent).where(
            PlatformAuditEvent.action == "assessment_evaluation.provisional"
        )
    )
    assert result.result.value == "PASS"
    assert result.reason_code == "TARGET_EVIDENCE_MET"
    assert audit is not None and audit.details["quality_review_status"] == "REJECTED"


def test_research_permutations_do_not_change_result(db_session: Session) -> None:
    attempt, _, _, _, _ = _ready_attempt(db_session)
    parameter_names = set(inspect.signature(AssessmentEvaluationService.evaluate).parameters)

    result = _service(db_session).evaluate(
        assessment_attempt_id=attempt.id,
        evaluation_idempotency_key="research-isolation-key",
    )

    assert {"research_condition", "consent", "confidence", "time_taken"}.isdisjoint(parameter_names)
    assert result.result.value == "PASS"


def test_result_audit_excludes_direct_id_and_full_answer_text(db_session: Session) -> None:
    attempt, response, _, _, _ = _ready_attempt(db_session)
    _service(db_session).evaluate(
        assessment_attempt_id=attempt.id,
        evaluation_idempotency_key="audit-key",
    )

    details = [
        json.dumps(event.details) for event in db_session.scalars(select(PlatformAuditEvent)).all()
    ]
    assert all(response.id not in item and response.answer not in item for item in details)
    assert all("student_id" not in item and "response_version_id" not in item for item in details)


def test_learner_direct_evaluation_route_is_not_published() -> None:
    schema = create_app().openapi()
    assert "/api/v1/assessment/attempts/{assessment_attempt_id}/evaluate" not in schema["paths"]
