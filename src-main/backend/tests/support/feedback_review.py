"""Explicit synthetic model-review replies for transport fixtures only."""

from app.schemas.category_review import ReviewDimension


def synthetic_model_assessment(prompt_payload: dict) -> dict:
    request = prompt_payload["category_review"]
    return {
        "request_digest": request["request_digest"],
        "reviewer": {
            "kind": "model",
            "reference": "synthetic-transport",
            "version": "synthetic-test-only-v1",
            "model_version": "synthetic-model",
            "prompt_version": "synthetic-prompt",
        },
        "findings": [
            {
                "dimension": dimension.value,
                "outcome": "SATISFIED",
                "basis": "model",
                "reason": "Explicit synthetic fixture finding; not real semantic quality evidence.",
                "evidence_references": [item["reference"] for item in request["evidence"]],
            }
            for dimension in ReviewDimension
        ],
    }
