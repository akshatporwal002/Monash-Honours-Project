"""Bounded offline candidates and validation before any teaching revision is saved."""

from app.schemas.multipart_generation import STAGES, MultipartCandidate

SOURCE_FACT = "Hadamard maps |0> to (|0> + |1>)/sqrt(2) and |1> to (|0> - |1>)/sqrt(2)."
SUPPORTED = {"qubits": 1, "operations": []}
TRANSFER = {"qubits": 1, "operations": [{"gate": "x", "targets": [0]}]}


def local_multipart(sources, outcome):
    source = next((row for row in sources if SOURCE_FACT in row.get("text", "")), None)
    if source is None:
        raise ValueError(
            "This local multipart family requires a source explicitly stating both Hadamard basis transformations; author unsupported content manually"
        )
    reference = source["chunk_id"]
    descriptions = {
        "prediction": "Predict the computational-basis probabilities before running the supported circuit.",
        "reasoning": "Explain how the supplied Hadamard transformation produces your prediction.",
        "explanation": "Relate the circuit and exact probabilities to the sampled counts without treating counts as exact.",
        "reflection": "Compare your initial prediction with the result and explain what you would retain or change.",
        "transfer": "Apply the Hadamard transformation to the input disclosed at the fresh stage without instructional help.",
    }
    met_anchors = {
        "prediction": "Before the run: I predict P(0)=P(1)=1/2 for H applied to |0>.",
        "reasoning": "H maps |0> to equal amplitudes 1/sqrt(2); squaring their magnitudes gives equal probabilities.",
        "explanation": "The exact probabilities are one half each; finite sampled counts can differ from an exact half.",
        "reflection": "I compare my recorded pre-run prediction with the saved outcome and identify a specific retained or corrected relationship.",
        "transfer": "For H applied to |1>, the |1> amplitude is negative; both measurement probabilities remain one half. I distinguish relative phase from measurement probability.",
    }
    criteria = [
        {
            "stable_key": key,
            "learner_description": description,
            "evidence_description": description,
            "mandatory": True,
            "evidence_source_types": ["learner_response"],
            "met_rule": description,
            "not_met_rule": "The response omits or contradicts the required relationship.",
            "not_evaluable_rule": "The required response or its provenance is missing or invalid.",
            "approved_anchors": {
                "met": [met_anchors[key]],
                "not_met": ["A bare answer with no required explanation or evidence relationship."],
            },
            "critical_error_rules": {
                "review": "Distinguish relative phase, exact probability and sampled frequency."
            },
            "evaluator_type": "human",
        }
        for key, description in descriptions.items()
    ]
    candidate = MultipartCandidate.model_validate(
        {
            "family": "hadamard_basis_transfer",
            "prior_work_policy": "revision_after_real_same_work_response",
            "source_anchors": [{"source_reference": reference, "quote": SOURCE_FACT}],
            "criterion_sources": {key: [reference] for key in STAGES},
            "episode_plan": {
                "prediction_required": True,
                "required_responses": list(STAGES[:-1]),
                "transfer": {
                    "prompt": "Fresh input: the supplied X prepares |1>. Add H, predict its result, then explain the probabilities and relative phase using your own reasoning.",
                    "starter_circuit": TRANSFER,
                },
            },
            "assessment_design": {
                "claim": "Apply the Hadamard transformation and explain its effects in supported and fresh contexts.",
                "purpose": "SUMMATIVE",
                "bloom_process": "APPLY",
                "knowledge_dimension": "PROCEDURAL",
                "supporting_evidence": {"required_stages": list(STAGES)},
                "contradicting_evidence": {
                    "review": "Confuses amplitudes with probabilities or denies relative phase."
                },
                "insufficient_evidence": {
                    "review": "Missing prediction, reasoning, explanation, reflection or fresh application."
                },
                "task_conditions": {
                    "supported_input": "|0>",
                    "transfer_input_disclosure": "The fresh input is disclosed on entry to the transfer stage.",
                    "review_required": True,
                },
                "next_action_contract": {
                    "incomplete": "Assessor identifies missing evidence and reviews reassessment conditions."
                },
                "permitted_tools": {"allowed": ["Reviewed source", "Circuit editor and simulator"]},
                "instructional_support": {"allowed": [], "transfer": "unaided"},
                "access_conditions": {"review_required": True},
                "transfer_rule": {"required": True, "independence": "unaided fresh input"},
                "evidence_sufficiency": {
                    "required": "All five stage criteria; references resolved from actual learner work."
                },
                "formal_result_eligible": False,
                "criteria": criteria,
                "pass_rule_expression": {
                    "operator": "ALL_OF",
                    "clauses": [{"criterion": key} for key in STAGES],
                },
                "task_forms": [],
            },
        }
    )
    return {
        "title": "Hadamard: predict, explain and transfer",
        "prompt": "Supported input: start with |0>, add H, record your prediction before running, and explain the result.",
        "instructions": "Complete prediction, reasoning, explanation and reflection, then the separate fresh input. On a later response, use the actual earlier response reference to explain a revision. This draft requires teaching and assessment review before assessed use.",
        "expected_answer": None,
        "marking_criteria": {
            "multipart_candidate": candidate.model_dump(mode="json"),
            "episode_plan": candidate.episode_plan.model_dump(mode="json"),
            "starter_circuit": SUPPORTED,
            "response_review": "human",
        },
        "source_references": [reference],
    }


def validate_multipart(criteria, task_type, source_texts):
    if not isinstance(criteria, dict) or "multipart_candidate" not in criteria:
        raise ValueError("This task has no typed multipart assessment candidate")
    candidate = MultipartCandidate.model_validate(criteria.get("multipart_candidate"))
    if "generation_design" in criteria and (
        not isinstance(criteria["generation_design"], dict)
        or criteria["generation_design"].get("assessment_purpose")
        != candidate.assessment_design.purpose.value
    ):
        raise ValueError(
            "Generation metadata and the proposed assessment must declare the same purpose"
        )
    if task_type != "quantum_circuit":
        raise ValueError("This multipart family requires the existing circuit episode renderer")
    if criteria.get("episode_plan") != candidate.episode_plan.model_dump(mode="json"):
        raise ValueError("The executable episode plan must match the proposed multipart design")
    if (
        criteria.get("starter_circuit") != SUPPORTED
        or candidate.episode_plan.transfer.starter_circuit != TRANSFER
    ):
        raise ValueError("This family requires distinct supported |0> and fresh |1> inputs")
    for anchor in candidate.source_anchors:
        if (
            anchor.source_reference not in source_texts
            or anchor.quote != SOURCE_FACT
            or anchor.quote not in source_texts[anchor.source_reference]
        ):
            raise ValueError(
                "Multipart source anchors must exactly match the supplied Hadamard passage"
            )
    return candidate
