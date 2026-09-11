"""Bounded extractive feedback and a deterministic release boundary.

Assessment correctness remains with the assessment workflow. This boundary permits
only objective field-presence statements, approved hints and exact source quotes.
It does not forward private rubric rules, pending decisions or solutions.
"""

import hashlib
import json
import re

from app.models.enums import JudgeDecision, JudgeEvaluationStatus
from app.schemas.assessed_feedback import (
    AssessedFeedbackView,
    CriterionFeedback,
    GroundedSourceClaim,
    ResponseFieldEvidence,
    SimulationProvenance,
)
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackRegenerationContext,
    FeedbackSourceAttribution,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
)
from app.services.episode_evidence import canonical_response_digest, extract_response_evidence
from app.services.feedback.contracts import FeedbackGenerator, FeedbackJudge
from app.services.feedback.quality_review import structural_review

MODEL_VERSION = "bounded-extractive-v1"
PROMPT_VERSION = "assessed-feedback-template-v1"
RULE_POLICY_VERSION = "assessed-grounding-policy-v1"
REFLECTION = "Which recorded evidence supports your explanation, and what would you revise next?"
NEXT_ACTION = "Reflect on this feedback before requesting a new permitted attempt."
GUIDANCE = (
    "Link your explanation to recorded evidence for this criterion when a new attempt is permitted."
)
INSTRUCTION_PATTERN = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|system)|system\s*prompt|"
    r"developer\s*message|(?:reveal|print|expose)\s+(?:the\s+)?(?:secret|solution|prompt)|"
    r"(?:assistant|system)\s*:|<\|(?:im_start|system)|"
    r"(?:transfer|hidden|private)\s+(?:task\s+)?(?:solution|answer)",
    re.IGNORECASE,
)


class GroundingUnavailable(ValueError):
    """Context cannot support a learner-safe candidate."""


def _is_assessed(context: FeedbackContext) -> bool:
    return context.task.assessed or context.assessment_context is not None


def _recorded(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_recorded(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_recorded(item) for item in value)
    return True


def _field_label(path: str) -> str:
    name = path.rsplit(".", 1)[-1]
    if path.startswith("content."):
        return f"Submitted {name}"
    if path.startswith("episode.supported."):
        return f"Supported {name}"
    return f"Fresh application {name}"


def _trusted_view(context: FeedbackContext) -> AssessedFeedbackView:
    assessed = context.assessment_context
    if assessed is None or assessed.frozen_response is None:
        raise GroundingUnavailable("FROZEN_RESPONSE_MISSING")
    if not assessed.feedback_release_allowed or assessed.active_transfer:
        raise GroundingUnavailable("HELP_POLICY_RESTRICTED")
    if assessed.context_warnings or not assessed.task_revision_id:
        raise GroundingUnavailable("FROZEN_CONTEXT_UNAVAILABLE")
    response = assessed.frozen_response
    reference = assessed.assessment
    digest = canonical_response_digest(
        content=response.content,
        episode=response.episode,
        schema_version=response.reference.schema_version,
        assessment_work_start_id=response.assessment_work_start_id,
        task_form_version_id=response.task_form_version_id,
        declared_conditions=response.declared_conditions,
    )
    if (
        response.reference.assessment != reference
        or digest != response.reference.content_digest
        or digest != assessed.response_content_digest
        or context.submission.submission_id != reference.response_version_id
        or context.task.task_id != reference.task_id
        or context.task.course_id != reference.course_id
    ):
        raise GroundingUnavailable("FROZEN_RESPONSE_MISMATCH")
    if not context.retrieval_context:
        raise GroundingUnavailable("APPROVED_SOURCE_MISSING")
    claims = []
    for source in context.retrieval_context[:3]:
        actual_digest = hashlib.sha256(source.chunk_text.encode("utf-8")).hexdigest()
        if (
            source.task_id != reference.task_id
            or source.course_id != reference.course_id
            or not source.source_revision_id
            or not source.source_digest
            or not source.approval_id
            or not source.retrieval_version
            or source.passage_digest not in (actual_digest, f"sha256:{actual_digest}")
        ):
            raise GroundingUnavailable("APPROVED_SOURCE_INVALID")
        if INSTRUCTION_PATTERN.search(source.chunk_text) or INSTRUCTION_PATTERN.search(
            source.source_label
        ):
            raise GroundingUnavailable("SOURCE_INSTRUCTION_PAYLOAD")
        quote = source.chunk_text[:320]
        claims.append(
            GroundedSourceClaim(
                source_id=source.source_id,
                source_label=source.source_label,
                document_id=source.document_id,
                chunk_id=source.chunk_id,
                source_revision_id=source.source_revision_id,
                source_digest=source.source_digest,
                passage_digest=source.passage_digest,
                approval_id=source.approval_id,
                retrieval_request_id=source.retrieval_request_id,
                retrieval_version=source.retrieval_version,
                support_quote=quote,
                start_offset=0,
                end_offset=len(quote),
                claim=quote,
            )
        )
    snapshot = extract_response_evidence(response)
    fields = {f"content.{key}": value for key, value in snapshot["content"].items()}
    if snapshot["episode"]:
        for stage in ("supported", "transfer"):
            process = snapshot["episode"].get(stage)
            if process is None:
                continue
            prefix = f"episode.{stage}"
            if stage == "transfer":
                process = process["process"]
                prefix += ".process"
            for field in ("prediction", "reasoning", "explanation", "reflection"):
                fields[f"{prefix}.{field}"] = process[field]
    evidence = [
        ResponseFieldEvidence(
            response_version_id=reference.response_version_id,
            content_digest=digest,
            path=path,
            recorded=_recorded(value),
            statement=f"{_field_label(path)} is {'recorded' if _recorded(value) else 'not recorded'}.",
        )
        for path, value in fields.items()
    ]
    # Durable runs are resolved against the exact response upstream. Retain their
    # provenance without copying large counts or inventing observed outcomes.
    runs = assessed.simulation_evidence
    frozen_runs = {}
    if response.episode:
        stages = [(response.episode.supported, None)]
        if response.episode.transfer:
            stages.append(
                (response.episode.transfer.process, response.episode.transfer.stage_start_id)
            )
        for stage, stage_start_id in stages:
            for item in stage.simulation_references:
                expected = (item.circuit_version_id, stage.prediction_checkpoint_id, stage_start_id)
                if item.run_id in frozen_runs and frozen_runs[item.run_id] != expected:
                    raise GroundingUnavailable("SIMULATION_SCOPE_MISMATCH")
                frozen_runs[item.run_id] = expected
    if (
        len(runs) > 20
        or len({item.get("run_id") for item in runs}) != len(runs)
        or {item.get("run_id") for item in runs} != set(frozen_runs)
        or any(
            frozen_runs.get(item.get("run_id"))
            != (
                item.get("circuit_version_id"),
                item.get("prediction_checkpoint_id"),
                item.get("episode_stage_start_id"),
            )
            for item in runs
        )
    ):
        raise GroundingUnavailable("SIMULATION_SCOPE_MISMATCH")
    simulations = [
        SimulationProvenance(
            run_id=item["run_id"],
            circuit_version_id=item["circuit_version_id"],
            prediction_checkpoint_id=item.get("prediction_checkpoint_id"),
            episode_stage_start_id=item.get("episode_stage_start_id"),
            status=item["status"],
            result_digest="sha256:"
            + hashlib.sha256(
                json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode()
            ).hexdigest(),
            policy_version=item["policy_version"],
            engine_versions=item["engine_versions"],
        )
        for item in runs
    ]
    criteria = []
    for criterion in assessed.criteria:
        kinds = set(criterion.evidence_source_types)
        selected = [
            item
            for item in evidence
            if (
                "learner_response" in kinds
                or any(item.path.endswith("." + kind) for kind in kinds)
                or ("written_response" in kinds and item.path == "content.answer")
                or ("code_response" in kinds and item.path == "content.code")
                or ("circuit_response" in kinds and item.path == "content.circuit")
            )
        ]
        guidance = GUIDANCE
        if assessed.current_human_action_id and criterion.evaluation:
            outcome = criterion.evaluation.decision.value
            if outcome == "NOT_EVALUABLE":
                guidance = "The assessor needs more evidence for this criterion. " + GUIDANCE
            elif outcome == "NOT_MET":
                guidance = "The assessor identified this criterion for revision. " + GUIDANCE
        criteria.append(
            CriterionFeedback(
                criterion_id=criterion.criterion_id,
                criterion_version_id=criterion.criterion_version_id,
                criterion_version=criterion.criterion_version,
                learner_description=criterion.learner_description,
                evidence=selected,
                guidance=guidance,
                simulation_references=[item.run_id for item in simulations]
                if "simulation_output" in kinds
                else [],
            )
        )
    return AssessedFeedbackView(
        assessment=reference,
        assessment_attempt_id=reference.assessment_attempt_id,
        response_version_id=reference.response_version_id,
        content_digest=digest,
        task_revision_id=assessed.task_revision_id,
        task_form_id=assessed.task_form_id,
        task_form_version=reference.task_form_version,
        task_form_version_id=response.task_form_version_id,
        current_human_action_id=assessed.current_human_action_id,
        summary="Review the recorded response fields and source excerpts alongside each criterion.",
        criteria=criteria,
        simulation_evidence=simulations,
        source_claims=claims,
        approved_hints=list(assessed.approved_hints),
        reflection_prompt=REFLECTION,
        permitted_next_action=NEXT_ACTION,
        help_use_ids=list(assessed.help_use_ids),
        rule_policy_version=RULE_POLICY_VERSION,
        prompt_version=PROMPT_VERSION,
        model_version=MODEL_VERSION,
    )


class AssessedFeedbackGenerator:
    def __init__(self, delegate: FeedbackGenerator) -> None:
        self.delegate = delegate

    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        if not _is_assessed(context):
            return await self.delegate.generate(context, regeneration)
        try:
            view = _trusted_view(context)
            content = {"assessed": view.model_dump(mode="json")}
            if len(json.dumps(content, ensure_ascii=False, separators=(",", ":"))) > 65_536:
                raise GroundingUnavailable("FEEDBACK_SIZE_LIMIT")
            references = list(dict.fromkeys(item.source_id for item in view.source_claims))
        except (ValueError, KeyError, TypeError) as error:
            content = {
                "assessed_generation_error": "GROUNDING_UNAVAILABLE",
                "reason_code": str(error)
                if isinstance(error, GroundingUnavailable)
                else "FROZEN_CONTEXT_INVALID",
                "rule_policy_version": RULE_POLICY_VERSION,
                "assessment_reference": context.assessment_context.assessment.model_dump(
                    mode="json"
                )
                if context.assessment_context
                else None,
                "response_content_digest": context.assessment_context.response_content_digest
                if context.assessment_context
                else None,
                "task_source_version": context.assessment_context.task_source_version
                if context.assessment_context
                else None,
                "task_source_digest": context.assessment_context.task_source_digest
                if context.assessment_context
                else None,
                "approved_source_references": list(context.task.source_references),
                "source_versions": [
                    item.model_dump(
                        mode="json",
                        include={
                            "source_id",
                            "document_id",
                            "chunk_id",
                            "source_revision_id",
                            "source_digest",
                            "passage_digest",
                            "approval_id",
                            "retrieval_version",
                            "retrieval_request_id",
                        },
                    )
                    for item in context.retrieval_context[:3]
                ],
            }
            references = []
        return GeneratedFeedback(
            feedback_content=content,
            provider="local",
            model=MODEL_VERSION,
            prompt_version=PROMPT_VERSION,
            source_references=references,
            source_attributions=_attributions(view) if "assessed" in content else [],
            usage_complete=True,
            simulation_references=[item.run_id for item in view.simulation_evidence]
            if "assessed" in content
            else [],
        )


def _attributions(view: AssessedFeedbackView) -> list[FeedbackSourceAttribution]:
    labels = {item.source_id: item.source_label for item in view.source_claims}
    return [FeedbackSourceAttribution(source_id=key, label=value) for key, value in labels.items()]


class AssessedFeedbackJudge:
    def __init__(self, delegate: FeedbackJudge) -> None:
        self.delegate = delegate

    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        if not _is_assessed(context):
            return await self.delegate.evaluate(context, feedback)
        reason_code = "UNSUPPORTED_CONTENT"
        try:
            expected = _trusted_view(context)
            proposed = feedback.feedback_content.get("assessed", {})
            if isinstance(proposed, dict):
                if proposed.get("reflection_prompt") != REFLECTION:
                    reason_code = "REFLECTION_REQUIRED"
                elif proposed.get("source_claims") != [
                    item.model_dump(mode="json") for item in expected.source_claims
                ]:
                    reason_code = "SOURCE_QUOTE_MISMATCH"
                elif proposed.get("approved_hints") != expected.approved_hints:
                    reason_code = "HELP_POLICY_VIOLATION"
            valid = (
                feedback.feedback_content == {"assessed": expected.model_dump(mode="json")}
                and feedback.source_references
                == list(dict.fromkeys(item.source_id for item in expected.source_claims))
                and feedback.source_attributions == _attributions(expected)
                and feedback.simulation_references
                == [item.run_id for item in expected.simulation_evidence]
                and feedback.provider == "local"
                and feedback.model == MODEL_VERSION
                and feedback.prompt_version == PROMPT_VERSION
            )
        except (ValueError, KeyError, TypeError) as error:
            valid = False
            reason_code = (
                str(error) if isinstance(error, GroundingUnavailable) else "FROZEN_CONTEXT_INVALID"
            )
        decision = JudgeDecision.PASS if valid else JudgeDecision.FAIL
        reason = (
            "Exact frozen approved-content selection and structural checks passed; "
            "no fresh semantic quality review or assessment decision was performed."
            if valid
            else f"Assessed feedback rejected: {reason_code}."
        )
        result = JudgeResult(
            decision=decision,
            correctness_score=100 if valid else 0,
            relevance_score=100 if valid else 0,
            grounding_score=100 if valid else 0,
            actionability_score=100 if valid else 0,
            safety_score=100 if valid else 0,
            reason=reason,
            unsupported_claims=[] if valid else ["Unverified assessed content."],
            regeneration_instructions=[]
            if valid
            else ["Rebuild from the frozen approved context."],
        )
        return JudgeEvaluationOutcome(
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=decision,
            judge_result=result,
            reason=reason,
            provider="local",
            model=MODEL_VERSION,
            prompt_version=RULE_POLICY_VERSION,
            quality_policy_version="quality-policy-structural-v2",
            quality_review=structural_review(context, feedback, assessed=True, passed=valid),
            usage_complete=True,
        )
