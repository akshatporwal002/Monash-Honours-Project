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
from app.services.rag.contracts import (
    TaskGenerationRequest,
    TaskGenerationResponse,
)


class LocalFeedbackGenerator:
    async def generate(
        self,
        context: FeedbackContext,
        regeneration: FeedbackRegenerationContext | None = None,
    ) -> GeneratedFeedback:
        score = context.submission.score
        if score is not None and score >= 80:
            classification = FeedbackResponseClassification.CORRECT
            summary = "Your response meets the learning outcome."
            identified_error = None
            explanation = (
                "The key idea is present and consistent with the supplied course evidence."
            )
            actions: list[str] = []
            next_step = "Continue to the next unlocked activity."
        elif score is not None and score >= 50:
            classification = FeedbackResponseClassification.PARTIALLY_CORRECT
            summary = "Your response shows the right direction but needs one clearer connection."
            identified_error = (
                "The explanation does not fully connect the result to the task criteria."
            )
            explanation = "Compare each claim with the expected behavior and the supplied source."
            actions = ["Add the missing reasoning step and name the expected circuit outcome."]
            next_step = "Revise once, then compare your answer with the course source."
        else:
            classification = FeedbackResponseClassification.INCORRECT
            summary = "This attempt does not yet meet the learning outcome."
            identified_error = "The submitted result does not match the expected quantum behavior."
            explanation = (
                "Use the retrieved source and simulation result to check the gate sequence."
            )
            actions = [
                "Trace the circuit one gate at a time and state the measurement distribution."
            ]
            next_step = "Review the prerequisite concept before resubmitting."

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
        content = feedback.feedback_content
        allowed_sources = {item.source_id for item in context.retrieval_context}
        grounded = set(feedback.source_references).issubset(allowed_sources)
        actionable = bool(
            content.get("recommended_next_step") or content.get("improvement_actions")
        )
        passed = grounded and actionable and bool(content.get("explanation"))
        decision = JudgeDecision.PASS if passed else JudgeDecision.FAIL
        result = JudgeResult(
            decision=decision,
            correctness_score=90 if passed else 60,
            relevance_score=90 if passed else 60,
            grounding_score=90 if grounded else 40,
            actionability_score=90 if actionable else 40,
            safety_score=100,
            reason=(
                "The feedback is grounded, relevant, actionable, and safe."
                if passed
                else "The feedback needs stronger grounding or an actionable next step."
            ),
            unsupported_claims=[] if grounded else ["An unavailable source was referenced."],
            regeneration_instructions=(
                [] if passed else ["Use only supplied evidence and add one concrete action."]
            ),
        )
        return JudgeEvaluationOutcome(
            evaluation_status=JudgeEvaluationStatus.VALID,
            reported_decision=decision,
            judge_result=result,
            reason=result.reason,
            provider="local-deterministic",
            model="quantumlearn-judge-v1",
            prompt_version="quality-judge-v1",
            quality_policy_version="quality-policy-v1",
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
            expected_answer, marking_criteria, starter_code = _task_scaffold(
                task_type,
                outcome,
                evidence,
            )
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
                    "source_references": [sources[index % len(sources)]],
                }
            )
        return TaskGenerationResponse(
            tasks=tuple(tasks),
            provider="local-deterministic",
            model="quantumlearn-task-scaffold-v1",
        )


def _instructions(task_type: str, index: int) -> str:
    if task_type == "quantum_circuit":
        return "Build the circuit, run it with Qiskit Aer, and explain the measurement counts."
    if task_type in {"code_explanation", "code_completion"}:
        return "Read the formatted Qiskit code and explain or complete the missing operation."
    if task_type in {"multiple_choice", "multiple_answer"}:
        return "Select the best supported answer and justify the choice."
    return f"Explain the concept in a concise response for scaffold step {index + 1}."


def _task_scaffold(
    task_type: str,
    outcome: str,
    evidence: str,
) -> tuple[str | None, dict[str, object], str | None]:
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
        return (
            '["a","c"]',
            {
                "choices": [
                    {"id": "a", "text": "Use the supplied course evidence."},
                    {"id": "b", "text": "Ignore measurement behavior."},
                    {"id": "c", "text": f"Address the outcome: {outcome[:180]}"},
                    {"id": "d", "text": "Invent a source that was not supplied."},
                ],
                "correct_answers": ["a", "c"],
            },
            None,
        )
    if task_type == "code_explanation":
        return (
            "measurement",
            {"required_terms": ["measurement", "superposition"]},
            (
                "from qiskit import QuantumCircuit\n\n"
                "circuit = QuantumCircuit(1, 1)\n"
                "circuit.h(0)\n"
                "circuit.measure(0, 0)\n"
            ),
        )
    if task_type in {"code_completion", "code"}:
        return (
            "circuit.h",
            {"required_code_fragments": ["circuit.h"]},
            (
                "from qiskit import QuantumCircuit\n\n"
                "circuit = QuantumCircuit(1, 1)\n"
                "# Add the required gate here\n"
                "circuit.measure(0, 0)\n"
            ),
        )
    if task_type in {"quantum_circuit", "circuit"}:
        return (
            None,
            {
                "required_gates": ["h"],
                "starter_circuit": {"qubits": 1, "operations": []},
            },
            None,
        )
    keyword = max(
        (word.strip(".,:;!?()[]").casefold() for word in outcome.split()),
        key=len,
        default="quantum",
    )
    return keyword, {"required_keywords": [keyword]}, None
