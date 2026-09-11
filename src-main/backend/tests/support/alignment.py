"""Explicit synthetic assessor declarations used by approval fixtures only."""


def next_action_contract(*criterion_keys: str) -> dict:
    return {
        "when_incomplete": "offer reassessment when approved",
        "alignment": {
            "schema_version": 1,
            "criterion_feedback": [
                {
                    "criterion_key": key,
                    "evidence_source_types": ["learner_response"],
                    "met": "Explain how the response meets this criterion's evidence rule.",
                    "not_met": "Identify the missing relationship required by this criterion.",
                    "not_evaluable": "Explain why the response cannot be evaluated against the rule.",
                }
                for key in criterion_keys
            ],
            "result_adaptation": {
                "PASS": {
                    "feedback": "Explain how the criterion decisions satisfy the pass rule.",
                    "adaptation": "Retain the result; no further task is required by this fixture.",
                },
                "INCOMPLETE": {
                    "feedback": "Explain which criterion decisions prevent the pass rule being met.",
                    "adaptation": "Offer a fresh approved reassessment after reviewing the missing evidence.",
                },
            },
        },
    }
