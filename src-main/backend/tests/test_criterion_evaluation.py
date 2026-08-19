"""Tests for the typed, fail-closed criterion evaluator layer."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.assessment import BloomProcess, CriterionDecision
from app.schemas.assessment import (
    AssessmentVersionReference,
    EvidenceReference,
    EvidenceReferenceResolution,
    ResolvedEvidenceReference,
    StaleEvidenceReference,
)
from app.services.assessment.evaluators import (
    AiCriterionInput,
    CriterionEvaluationRequest,
    EvaluatorFailure,
    HumanCriterionEvaluator,
    HumanCriterionInput,
    MixedCriterionEvaluator,
    RuleCriterionEvaluator,
    ValidatedAiCriterionEvaluator,
)
from app.services.assessment.evidence import EvidenceValidationError, FrozenEvidenceValidator
from app.services.evidence.assessment_port import AssessmentEvidencePort


@pytest.fixture
def cases() -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / "assessment_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assessment(cases: dict[str, object]) -> AssessmentVersionReference:
    return AssessmentVersionReference.model_validate(cases["assessment"])


def _resolved(cases: dict[str, object]) -> ResolvedEvidenceReference:
    reference = EvidenceReference.model_validate(
        {"assessment": cases["assessment"], **dict(cases["evidence"])}
    )
    return ResolvedEvidenceReference(reference=reference)


class StubResolver:
    def __init__(self, resolutions: dict[str, EvidenceReferenceResolution]) -> None:
        self.resolutions = resolutions
        self.calls: list[tuple[AssessmentVersionReference, str]] = []

    def resolve(
        self,
        *,
        assessment: AssessmentVersionReference,
        evidence_id: str,
    ) -> EvidenceReferenceResolution:
        self.calls.append((assessment, evidence_id))
        return self.resolutions[evidence_id]


def _port(
    cases: dict[str, object],
    resolution: EvidenceReferenceResolution | None = None,
) -> tuple[AssessmentEvidencePort, StubResolver]:
    resolved = resolution or _resolved(cases)
    resolver = StubResolver({"evidence-1": resolved})
    return AssessmentEvidencePort(resolver), resolver


def _request(cases: dict[str, object], response: str) -> CriterionEvaluationRequest:
    port, _ = _port(cases)
    evidence = FrozenEvidenceValidator().resolve_and_validate(
        port,
        assessment=_assessment(cases),
        evidence_ids=("evidence-1",),
        allowed_types=("learner_response",),
    )
    return CriterionEvaluationRequest(
        response_text=response,
        bloom_process=BloomProcess.ANALYSE,
        approved_anchors=dict(cases["anchors"]),
        evidence=evidence,
    )


def test_validator_resolves_every_evidence_id_through_person_b_port(
    cases: dict[str, object],
) -> None:
    assessment = _assessment(cases)
    port, resolver = _port(cases)

    evidence = FrozenEvidenceValidator().resolve_and_validate(
        port,
        assessment=assessment,
        evidence_ids=("evidence-1",),
        allowed_types=("learner_response",),
    )

    assert evidence == (_resolved(cases).reference,)
    assert resolver.calls == [(assessment, "evidence-1")]


def test_each_criterion_decision_keeps_exact_evidence_and_reason(cases: dict[str, object]) -> None:
    request = _request(cases, list(cases["valid_responses"])[0])
    outcomes = (
        RuleCriterionEvaluator().evaluate(request),
        HumanCriterionEvaluator().evaluate(
            request,
            HumanCriterionInput(CriterionDecision.MET, "The relation is explicit."),
        ),
        MixedCriterionEvaluator().evaluate(
            request,
            HumanCriterionInput(CriterionDecision.MET, "Human review confirms the evidence."),
        ),
    )

    assert {outcome.decision for outcome in outcomes} == {CriterionDecision.MET}
    assert all(outcome.evidence == request.evidence and outcome.reason for outcome in outcomes)


def test_stale_and_cross_course_evidence_is_rejected(cases: dict[str, object]) -> None:
    validator = FrozenEvidenceValidator()
    assessment = _assessment(cases)
    stale: EvidenceReferenceResolution = StaleEvidenceReference(
        reference=_resolved(cases).reference,
        mismatched_fields=("record_version",),
        reason_code="VERSION_MISMATCH",
    )
    stale_port, _ = _port(cases, stale)
    with pytest.raises(EvidenceValidationError, match="stale"):
        validator.resolve_and_validate(
            stale_port,
            assessment=assessment,
            evidence_ids=("evidence-1",),
            allowed_types=("learner_response",),
        )

    cross_course = _resolved(cases).reference.model_copy(
        update={"assessment": assessment.model_copy(update={"course_id": "course-2"})}
    )
    cross_course_port, _ = _port(
        cases,
        ResolvedEvidenceReference(reference=cross_course),
    )
    with pytest.raises(EvidenceValidationError, match="access is denied"):
        validator.resolve_and_validate(
            cross_course_port,
            assessment=assessment,
            evidence_ids=("evidence-1",),
            allowed_types=("learner_response",),
        )


def test_provider_failure_is_not_not_evaluable_or_incomplete(cases: dict[str, object]) -> None:
    request = _request(cases, list(cases["valid_responses"])[0])

    def timeout(_: CriterionEvaluationRequest) -> AiCriterionInput:
        raise TimeoutError

    provider: Callable[[CriterionEvaluationRequest], AiCriterionInput] = timeout
    with pytest.raises(EvaluatorFailure, match="timed out"):
        ValidatedAiCriterionEvaluator().evaluate_from_provider(
            request,
            provider,
            release_gate_approved=False,
        )


def test_recall_only_response_does_not_meet_analyse_criterion(cases: dict[str, object]) -> None:
    outcome = RuleCriterionEvaluator().evaluate(_request(cases, str(cases["recall_only_response"])))

    assert outcome.decision is CriterionDecision.NOT_MET
    assert "relationship" in outcome.reason


def test_missing_learner_response_is_not_evaluable_after_valid_resolution(
    cases: dict[str, object],
) -> None:
    outcome = RuleCriterionEvaluator().evaluate(_request(cases, ""))

    assert outcome.decision is CriterionDecision.NOT_EVALUABLE


def test_concise_unusual_and_accessible_valid_answers_are_supported(
    cases: dict[str, object],
) -> None:
    outcomes = [
        RuleCriterionEvaluator().evaluate(_request(cases, response))
        for response in list(cases["valid_responses"])
    ]

    assert [outcome.decision for outcome in outcomes] == [CriterionDecision.MET] * 3


def test_ai_criterion_decision_remains_advisory_before_release_gate(
    cases: dict[str, object],
) -> None:
    request = _request(cases, list(cases["valid_responses"])[0])
    outcome = ValidatedAiCriterionEvaluator().evaluate(
        request,
        AiCriterionInput(
            decision=CriterionDecision.MET,
            reason="The response links phase and interference.",
            model_version="criterion-model.v1",
            prompt_version="criterion-prompt.v1",
            retrieval_version="retrieval.v1",
            confidence=0.91,
        ),
        release_gate_approved=False,
    )

    assert outcome.advisory is True
    assert outcome.confidence == 0.91
    assert outcome.decision is CriterionDecision.MET


def test_forbidden_evidence_fields_are_rejected_before_evaluation(cases: dict[str, object]) -> None:
    payload = {"assessment": cases["assessment"], **dict(cases["evidence"]), "score": 100}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceReference.model_validate(payload)
