"""Typed criterion evaluators that cannot create learner results on their own."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.assessment import BloomProcess, CriterionDecision
from app.models.assessment import CriterionEvaluatorType
from app.schemas.assessment import EvidenceReference


class EvaluatorFailure(RuntimeError):
    """An evaluator did not complete, so no criterion decision exists."""


@dataclass(frozen=True)
class CriterionEvaluationRequest:
    response_text: str
    bloom_process: BloomProcess
    approved_anchors: dict[str, Any] | list[Any]
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True)
class EvaluatorOutcome:
    decision: CriterionDecision
    reason: str
    evidence: tuple[EvidenceReference, ...]
    evaluator_type: CriterionEvaluatorType
    evaluator_reference: str
    model_version: str | None = None
    prompt_version: str | None = None
    retrieval_version: str | None = None
    confidence: float | None = None
    advisory: bool = False


@dataclass(frozen=True)
class HumanCriterionInput:
    decision: CriterionDecision
    reason: str


@dataclass(frozen=True)
class AiCriterionInput:
    decision: CriterionDecision
    reason: str
    model_version: str
    prompt_version: str
    retrieval_version: str | None
    confidence: float


class RuleCriterionEvaluator:
    """Evaluate only assessor-authored phrase and relationship anchors."""

    def evaluate(self, request: CriterionEvaluationRequest) -> EvaluatorOutcome:
        if not request.response_text.strip():
            return self._outcome(
                CriterionDecision.NOT_EVALUABLE,
                "The required learner response is missing.",
                request,
            )
        anchors = request.approved_anchors if isinstance(request.approved_anchors, dict) else {}
        required = _phrases(anchors.get("all_of"))
        alternatives = _phrases(anchors.get("any_of"))
        relations = _phrases(anchors.get("relation_markers"))
        text = request.response_text.casefold()
        missing_required = [phrase for phrase in required if phrase not in text]
        if missing_required or (
            alternatives and not any(phrase in text for phrase in alternatives)
        ):
            return self._outcome(
                CriterionDecision.NOT_MET,
                "The response does not show the approved criterion evidence.",
                request,
            )
        if request.bloom_process is BloomProcess.ANALYSE and (
            not relations or not any(phrase in text for phrase in relations)
        ):
            return self._outcome(
                CriterionDecision.NOT_MET,
                "The response recalls facts but does not show the required relationship or cause.",
                request,
            )
        return self._outcome(
            CriterionDecision.MET,
            "The response shows the approved criterion evidence.",
            request,
        )

    @staticmethod
    def _outcome(
        decision: CriterionDecision,
        reason: str,
        request: CriterionEvaluationRequest,
    ) -> EvaluatorOutcome:
        return EvaluatorOutcome(
            decision=decision,
            reason=reason,
            evidence=request.evidence,
            evaluator_type=CriterionEvaluatorType.RULES,
            evaluator_reference="rules.anchor.v1",
        )


class HumanCriterionEvaluator:
    """Preserve an authorised human's typed criterion decision."""

    def evaluate(
        self,
        request: CriterionEvaluationRequest,
        human: HumanCriterionInput,
    ) -> EvaluatorOutcome:
        _require_reason(human.reason)
        return EvaluatorOutcome(
            decision=human.decision,
            reason=human.reason,
            evidence=request.evidence,
            evaluator_type=CriterionEvaluatorType.HUMAN,
            evaluator_reference="human-assessor.v1",
        )


class ValidatedAiCriterionEvaluator:
    """Return AI analysis as advisory evidence until the release gate is approved."""

    def evaluate(
        self,
        request: CriterionEvaluationRequest,
        ai: AiCriterionInput,
        *,
        release_gate_approved: bool,
    ) -> EvaluatorOutcome:
        _require_reason(ai.reason)
        if not 0 <= ai.confidence <= 1:
            raise ValueError("evaluator confidence must be between zero and one")
        return EvaluatorOutcome(
            decision=ai.decision,
            reason=ai.reason,
            evidence=request.evidence,
            evaluator_type=CriterionEvaluatorType.VALIDATED_AI,
            evaluator_reference="validated-ai.v1",
            model_version=ai.model_version,
            prompt_version=ai.prompt_version,
            retrieval_version=ai.retrieval_version,
            confidence=ai.confidence,
            advisory=not release_gate_approved,
        )

    def evaluate_from_provider(
        self,
        request: CriterionEvaluationRequest,
        provider: Callable[[CriterionEvaluationRequest], AiCriterionInput],
        *,
        release_gate_approved: bool,
    ) -> EvaluatorOutcome:
        try:
            ai = provider(request)
        except TimeoutError as error:
            raise EvaluatorFailure("AI criterion evaluator timed out") from error
        return self.evaluate(request, ai, release_gate_approved=release_gate_approved)


class MixedCriterionEvaluator:
    """Keep both the deterministic rule result and human confirmation visible."""

    def evaluate(
        self,
        request: CriterionEvaluationRequest,
        human: HumanCriterionInput,
    ) -> EvaluatorOutcome:
        rule = RuleCriterionEvaluator().evaluate(request)
        confirmed = HumanCriterionEvaluator().evaluate(request, human)
        return EvaluatorOutcome(
            decision=confirmed.decision,
            reason=f"Rule check: {rule.reason} Human review: {confirmed.reason}",
            evidence=request.evidence,
            evaluator_type=CriterionEvaluatorType.MIXED,
            evaluator_reference="mixed.rules-human.v1",
        )


def _phrases(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        return ()
    return tuple(item.casefold() for item in value)


def _require_reason(value: str) -> None:
    if not value.strip() or len(value) > 500:
        raise ValueError("criterion evaluation requires a short reason")
