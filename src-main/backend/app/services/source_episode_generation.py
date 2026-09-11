"""Source-led episode drafts without claiming a semantic answer has been verified."""

from app.schemas.episode import EpisodePlanV1
from app.schemas.multipart_generation import STAGES, MultipartCandidate, SourceAnchor

EPISODE_TYPES = {"prediction", "reasoning", "explanation", "reflection", "transfer"}


def source_episode(sources, outcome, task_type, index=0, *, assessed=False):
    usable = [row for row in sources if len(str(row.get("text", "")).strip()) >= 20]
    if not usable:
        raise ValueError("Episode generation needs a substantive cited passage")
    source = usable[index % len(usable)]
    quote = str(source["text"]).strip()[:2000]
    reference = str(source["chunk_id"])
    circuit = task_type == "quantum_circuit"
    if circuit and not any(word in quote.casefold() for word in ("circuit", "gate", "qubit")):
        raise ValueError("Circuit episode generation needs circuit or gate source material")
    demands = {
        "prediction": "State a testable prediction from the cited relationship, including the conditions under which it should hold.",
        "reasoning": "Choose a claim in the passage and explain the steps connecting its assumptions to its conclusion.",
        "explanation": "Explain a relationship in the passage in your own words and illustrate it with a worked example.",
        "reflection": "Record an initial prediction, check it against the passage, and explain what you retain or revise and why.",
        "transfer": "Work through an example of the cited relationship before attempting the separate new-context application.",
        "quantum_circuit": "Construct a small circuit illustrating a relationship stated in the passage. Record its predicted outcome before running it and explain the observed result.",
    }
    if task_type not in demands:
        raise ValueError("Unsupported source episode response type")
    plan = EpisodePlanV1.model_validate(
        {
            "prediction_required": True,
            "required_responses": list(STAGES[:-1]),
            "transfer": {
                "prompt": (
                    "Fresh application: change one gate or input of your supported circuit. "
                    "Identify the change, predict its effect and justify the result from the underlying relationship."
                    if circuit
                    else "Fresh application: construct a different example in which one assumption of your supported example changes. "
                    "State the changed assumption, predict its consequence, and explain whether the original relationship still applies."
                ),
                "instructions": "Use your own reasoning without instructional hints. Make the new example and changed condition explicit.",
                **({"starter_circuit": {"qubits": 1, "operations": []}} if circuit else {}),
            },
        }
    )
    guidance = {
        "prediction": "Records a prediction with explicit conditions before checking the result.",
        "reasoning": "Connects the cited relationship and assumptions to the prediction through explicit steps.",
        "explanation": "Explains the worked example and its evidence consistently with the cited relationship.",
        "reflection": "Compares the actual initial prediction and subsequent evidence and justifies what is retained or changed.",
        "transfer": "Independently applies the relationship to a distinct example with a changed condition and explains its consequence.",
    }
    criteria = {
        "response_review": "human",
        "episode_plan": plan.model_dump(mode="json"),
        "source_episode": {"source_reference": reference, "quote": quote},
        "mandatory_response_features": guidance,
        **({"starter_circuit": {"qubits": 1, "operations": []}} if circuit else {}),
    }
    if assessed:
        candidate = MultipartCandidate.model_validate(
            {
                "family": "source_application_transfer",
                "prior_work_policy": "revision_after_real_same_work_response",
                "source_anchors": [{"source_reference": reference, "quote": quote}],
                "criterion_sources": {stage: [reference] for stage in STAGES},
                "episode_plan": plan.model_dump(mode="json"),
                "assessment_design": {
                    "claim": f"Apply a source-grounded relationship and justify its use: {outcome[:1000]}",
                    "purpose": "SUMMATIVE",
                    "bloom_process": "APPLY",
                    "knowledge_dimension": "PROCEDURAL",
                    "supporting_evidence": {"required_stages": list(STAGES)},
                    "contradicting_evidence": {
                        "review": "Identify contradictions with the cited relationship and its stated assumptions."
                    },
                    "insufficient_evidence": {
                        "review": "A missing stage or an unsupported claim does not establish the criterion."
                    },
                    "task_conditions": {
                        "review_required": True,
                        "context_and_demand_review_required": True,
                    },
                    "next_action_contract": {
                        "incomplete": "Identify missing evidence and review reassessment conditions."
                    },
                    "permitted_tools": {
                        "allowed": [
                            "Reviewed course source",
                            *(["Circuit editor and simulator"] if circuit else []),
                        ]
                    },
                    "instructional_support": {"allowed": [], "transfer": "unaided"},
                    "access_conditions": {"review_required": True},
                    "transfer_rule": {"required": True, "independence": "unaided fresh input"},
                    "evidence_sufficiency": {
                        "required": "All five stage criteria with real response provenance."
                    },
                    "formal_result_eligible": False,
                    "criteria": [
                        {
                            "stable_key": stage,
                            "learner_description": description,
                            "evidence_description": description,
                            "mandatory": True,
                            "evidence_source_types": ["learner_response"],
                            "met_rule": description,
                            "not_met_rule": "The response omits or contradicts this relationship.",
                            "not_evaluable_rule": "The required response or its provenance is missing.",
                            "approved_anchors": {
                                "met": [description],
                                "not_met": [
                                    "A claim without the required reasoning or comparison."
                                ],
                            },
                            "critical_error_rules": {
                                "review": "Educator must specify subject-specific critical errors before assessment approval."
                            },
                            "evaluator_type": "human",
                        }
                        for stage, description in guidance.items()
                    ],
                    "pass_rule_expression": {
                        "operator": "ALL_OF",
                        "clauses": [{"criterion": stage} for stage in STAGES],
                    },
                    "task_forms": [],
                },
            }
        )
        criteria["multipart_candidate"] = candidate.model_dump(mode="json")
    else:
        criteria.pop("episode_plan")
        criteria["mandatory_response_features"] = {task_type: guidance[task_type]}
        if task_type == "transfer":
            demands[task_type] = (
                "Apply the cited relationship to a new example. State one changed assumption, predict its consequence, and explain whether the relationship still holds."
            )
    return {
        "title": f"{task_type.replace('_', ' ').title()}: {outcome[:48]} · {index + 1}",
        "prompt": f"Activity {index + 1}: {demands[task_type]}\n\nCited passage:\n{quote}",
        "instructions": (
            "Complete prediction, reasoning, explanation and reflection, then enter the fresh application. Explain the evidence for each claim. Any later revision must reference your actual earlier response from this work."
            if assessed
            else f"Complete the {task_type.replace('_', ' ')} response using the cited passage. Explain the evidence for your claim. This is supported practice; later revisions must reference your actual earlier response to this task."
        ),
        "expected_answer": None,
        "marking_criteria": criteria,
        "source_references": [reference],
    }


def validate_source_episode(criteria, source_texts):
    anchor = SourceAnchor.model_validate(criteria.get("source_episode"))
    quote = anchor.quote
    if (
        not isinstance(quote, str)
        or len(quote.strip()) < 20
        or quote not in source_texts.get(anchor.source_reference, "")
    ):
        raise ValueError("The episode source anchor is not in the supplied course evidence")
    if "episode_plan" in criteria:
        EpisodePlanV1.model_validate(criteria["episode_plan"])
