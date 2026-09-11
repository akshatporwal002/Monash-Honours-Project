"""Deterministic development adapters for a runnable, offline MVP.

Production can replace these through the existing provider interfaces. Keeping
the local behavior explicit makes demos and tests reproducible without pretending
that a network model was called.
"""

from __future__ import annotations

from decimal import Decimal

from app.models import JudgeDecision, JudgeEvaluationStatus
from app.schemas.feedback import (
    FeedbackContext,
    FeedbackRegenerationContext,
    FeedbackResponseClassification,
    FeedbackSourceAttribution,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    TokenUsage,
)
from app.schemas.generated_task_design import local_design
from app.services.feedback.quality_review import feedback_output, structural_review
from app.services.rag.contracts import (
    TaskGenerationRequest,
    TaskGenerationResponse,
)
from app.services.source_episode_generation import EPISODE_TYPES, source_episode
from app.services.structured_generation import grounded_structure


class LocalFeedbackGenerator:
    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        classification = FeedbackResponseClassification.NOT_EVALUATED
        summary = "Your response is saved for review."
        identified_error = None
        explanation = (
            "This local teaching template has not evaluated your answer. "
            "Compare your reasoning with the cited course evidence."
        )
        actions = ["State your prediction, check the evidence, and explain any difference."]
        next_step = "Revise your explanation or ask your educator to review it."

        if regeneration is not None:
            explanation = f"{explanation} This revision applies the quality-check guidance."

        source_references = [item.source_id for item in context.retrieval_context]
        simulation_references = (
            [context.simulation_context.simulation_id]
            if context.simulation_context is not None
            else []
        )
        content = {
            "response_classification": classification.value,
            "summary": summary,
            "identified_error": identified_error,
            "explanation": explanation,
            "improvement_actions": actions,
            "recommended_next_step": next_step,
            "source_references": source_references,
            "simulation_references": simulation_references,
            "ai_generated_notice": (
                "AI-generated feedback. Verify important details and report any concerns."
            ),
        }
        return GeneratedFeedback(
            feedback_content=content,
            provider="local-deterministic",
            model="quantumlearn-rules-v1",
            prompt_version="feedback-v2",
            source_references=source_references,
            source_attributions=[
                FeedbackSourceAttribution(source_id=item.source_id, label=item.source_label)
                for item in context.retrieval_context
            ],
            simulation_references=simulation_references,
            token_usage=TokenUsage(),
            estimated_cost=Decimal("0"),
            usage_complete=True,
        )


class LocalFeedbackJudge:
    async def evaluate(
        self,
        context: FeedbackContext,
        feedback: GeneratedFeedback,
    ) -> JudgeEvaluationOutcome:
        expected = await LocalFeedbackGenerator().generate(context)
        revised = expected.model_copy(deep=True)
        revised.feedback_content["explanation"] += (
            " This revision applies the quality-check guidance."
        )
        passed = feedback_output(feedback) in (feedback_output(expected), feedback_output(revised))
        decision = JudgeDecision.PASS if passed else JudgeDecision.FAIL
        result = JudgeResult(
            decision=decision,
            correctness_score=100 if passed else 0,
            relevance_score=100 if passed else 0,
            grounding_score=100 if passed else 0,
            actionability_score=100 if passed else 0,
            safety_score=100 if passed else 0,
            reason=(
                "Exact non-evaluative local template verified; structural checks only, "
                "not a semantic review or assessment of the learner's answer."
                if passed
                else "Candidate differs from the bounded local template."
            ),
            unsupported_claims=[] if passed else ["Content is outside the local template."],
            regeneration_instructions=[] if passed else ["Rebuild the exact local template."],
        )
        return JudgeEvaluationOutcome(
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=decision,
            judge_result=result,
            reason=result.reason,
            provider="local-deterministic",
            model="quantumlearn-judge-v1",
            prompt_version="quality-judge-v1",
            quality_policy_version="quality-policy-structural-v2",
            quality_review=structural_review(context, feedback, assessed=False, passed=passed),
            token_usage=TokenUsage(),
            estimated_cost=Decimal("0"),
            usage_complete=True,
        )


class LocalTaskGenerationClient:
    """Create a predictable scaffold when an external model is not configured."""

    async def generate_structured(
        self,
        request: TaskGenerationRequest,
    ) -> TaskGenerationResponse:
        payload = request.payload
        outcome_id = str(payload["learning_outcome_id"])
        outcome = str(payload["learning_outcome_text"])
        task_count = int(payload["task_count"])
        types = [str(value) for value in payload["allowed_task_types"]]
        difficulties = [str(value) for value in payload["difficulty_levels"]]
        source_rows = [
            source
            for source in payload["sources"]
            if isinstance(source, dict) and source.get("chunk_id")
        ]
        sources = [str(source["chunk_id"]) for source in source_rows]
        evidence = " ".join(
            str(source.get("text", "")).replace("\n", " ").strip() for source in source_rows
        ).strip()
        evidence = " ".join(evidence.split())[:500]
        if not types or not difficulties or not sources or not evidence:
            raise ValueError("Task generation requires task types, difficulty levels, and sources.")
        tasks = []
        for index in range(task_count):
            task_type = types[index % len(types)]
            difficulty = difficulties[min(index, len(difficulties) - 1)]
            if payload.get("generation_mode") == "multipart":
                from app.services.multipart_generation import local_multipart

                if task_count != 1 or len(types) != 1:
                    raise ValueError("Multipart generation supports one episode at a time")
                item = local_multipart(source_rows, outcome, task_type)
                item["marking_criteria"]["generation_design"] = local_design(
                    task_type, outcome, difficulty, purpose="SUMMATIVE"
                )
                tasks.append(
                    {
                        **item,
                        "task_type": task_type,
                        "difficulty": difficulty,
                        "learning_outcome_id": outcome_id,
                    }
                )
                continue
            if task_type in EPISODE_TYPES:
                item = source_episode(source_rows, outcome, task_type, index)
                item["marking_criteria"]["generation_design"] = local_design(
                    task_type, outcome, difficulty
                )
                tasks.append(
                    {
                        **item,
                        "task_type": task_type,
                        "difficulty": difficulty,
                        "learning_outcome_id": outcome_id,
                    }
                )
                continue
            expected_answer, marking_criteria, starter_code = _task_scaffold(
                task_type,
                outcome,
                evidence,
            )
            if task_type in {"matching", "sequencing"}:
                expected_answer, marking_criteria = grounded_structure(task_type, source_rows)
            marking_criteria["generation_design"] = local_design(task_type, outcome, difficulty)
            tasks.append(
                {
                    "title": f"{outcome[:48]} · Step {index + 1}",
                    "prompt": (
                        f"Scaffold step {index + 1}: apply this learning outcome: {outcome}\n\n"
                        f"Use this course evidence: {evidence}"
                    ),
                    "instructions": _instructions(task_type, index),
                    "task_type": task_type,
                    "difficulty": difficulty,
                    "expected_answer": expected_answer,
                    "marking_criteria": marking_criteria,
                    "starter_code": starter_code,
                    "learning_outcome_id": outcome_id,
                    "source_references": sources,
                }
            )
        _condition_drafts(tasks, payload.get("generation_context"))
        return TaskGenerationResponse(
            tasks=tuple(tasks),
            provider="local-deterministic",
            model="quantumlearn-task-scaffold-v1",
        )


def _condition_drafts(tasks, context):
    if not context:
        return
    if context["kind"] == "variant":
        focus = "Use a contrasting example or starting condition and explain which relationship remains unchanged."
        label = "Variant"
    else:
        import json

        feedback = json.dumps(context["feedback"]).casefold()
        prior = context["prior_response"]
        if "code" in feedback and not prior.get("code"):
            focus = "Include the missing code step and explain how it implements the cited relationship."
        elif "prediction" in feedback:
            focus = "Make an explicit prediction before checking the evidence and justify it from the source."
        elif "reflection" in feedback or "revision" in feedback:
            focus = "Compare an initial claim with the evidence and explain a specific correction or retained relationship."
        else:
            focus = (
                "Make each reasoning step explicit and link it to evidence from the cited passage."
            )
        label = "Feedback follow-up"
    for task in tasks:
        task["title"] = f"{label}: {task['title']}"
        task["prompt"] += f"\n\n{focus}"
        task["marking_criteria"]["adaptation_review"] = {
            "kind": context["kind"],
            "focus": focus,
            "equivalence_review_required": True,
            "new_work_not_a_revision": True,
        }


def _instructions(task_type: str, index: int) -> str:
    if task_type == "matching":
        return "Match each excerpt opening to its complete source excerpt. Use each option once."
    if task_type == "sequencing":
        return (
            "Reconstruct the cited passage by placing its fragments in the original reading order."
        )

    if task_type == "quantum_circuit":
        return "Build the circuit, run it with Qiskit Aer, and explain the measurement counts."
    if task_type in {"code_explanation", "code_completion"}:
        return "Read the formatted Qiskit code and explain or complete the missing operation."
    if task_type == "multiple_answer":
        return "Select every excerpt that occurs in the supplied course evidence."
    if task_type == "multiple_choice":
        return "Select the best supported answer and justify the choice."
    return f"Explain the concept in a concise response for scaffold step {index + 1}."


def _task_scaffold(
    task_type: str,
    outcome: str,
    evidence: str,
) -> tuple[str | None, dict[str, object], str | None]:
    if task_type in {"matching", "sequencing"}:
        return None, {}, None
    if task_type in {"multiple_choice", "quiz"}:
        return (
            "b",
            {
                "choices": [
                    {"id": "a", "text": "A claim not supported by the course evidence."},
                    {"id": "b", "text": evidence[:240]},
                    {"id": "c", "text": "A classical-only interpretation of the concept."},
                ]
            },
            None,
        )
    if task_type == "multiple_answer":
        words = evidence.split()
        if len(words) < 4:
            raise ValueError("Multiple-answer generation requires a substantive source passage")
        midpoint = len(words) // 2
        return (
            '["a","c"]',
            {
                "choices": [
                    {"id": "a", "text": " ".join(words[:midpoint])},
                    {"id": "b", "text": "No course evidence is needed for this conclusion."},
                    {"id": "c", "text": " ".join(words[midpoint:])},
                    {
                        "id": "d",
                        "text": "Every assumption can be ignored without changing the conclusion.",
                    },
                ],
                "correct_answers": ["a", "c"],
            },
            None,
        )
    if task_type in {"code_explanation", "code_completion", "code", "quantum_circuit", "circuit"}:
        import re

        mentions = [
            (match.start(), gate)
            for gate, pattern in (
                ("h", r"\bhadamard\b|\bh\s+gate\b|\b(?:circuit|qc)\.h\("),
                ("x", r"\bpauli[- ]?x\b|\bx\s+gate\b|\b(?:circuit|qc)\.x\("),
                (
                    "cx",
                    r"\bcnot\b|\bcontrolled[- ](?:not|x)\b|\bcx\s+gate\b|\b(?:circuit|qc)\.cx\(",
                ),
            )
            if (match := re.search(pattern, evidence, re.IGNORECASE))
        ]
        if not mentions:
            raise ValueError(
                "Local code and circuit drafts require a source naming a supported H, X or CX gate"
            )
        gate = min(mentions)[1]
        qubits = 2 if gate == "cx" else 1
        operation = f"circuit.{gate}({'0, 1' if qubits == 2 else '0'})"
        preamble = (
            f"from qiskit import QuantumCircuit\n\ncircuit = QuantumCircuit({qubits}, {qubits})\n"
        )
        measurement = f"circuit.measure(range({qubits}), range({qubits}))\n"
    if task_type == "code_explanation":
        return (
            None,
            {
                "response_review": "human",
                "expected_response_features": [
                    f"Explain {operation} using the cited relationship",
                    "Explain the measurement operation and its limits",
                ],
            },
            preamble + operation + "\n" + measurement,
        )
    if task_type in {"code_completion", "code"}:
        return (
            operation,
            {"required_code_fragments": [operation], "response_review": "human"},
            preamble + f"# Add the source's {gate.upper()} operation here\n" + measurement,
        )
    if task_type in {"quantum_circuit", "circuit"}:
        return (
            None,
            {
                "required_gates": [gate],
                "starter_circuit": {"qubits": qubits, "operations": []},
            },
            None,
        )
    if task_type != "short_answer":
        from app.services.task_types import UnsupportedTaskTypeError

        raise UnsupportedTaskTypeError(
            f"Local generation is unavailable for {task_type}; author a reviewed episode instead"
        )
    return (
        None,
        {
            "response_review": "human",
            "expected_response_features": [
                "Explain the cited relationship in your own words",
                "State its conditions and cite the supporting passage",
            ],
        },
        None,
    )
