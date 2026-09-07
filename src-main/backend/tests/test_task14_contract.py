import pytest
from pydantic import ValidationError

from app.schemas.episode import EpisodePayloadV1, EpisodePlanV1, ResponseContent
from app.services.episode_contract import learner_episode_plan, validate_reviewed_episode_plan


def test_lossless_all_episode_fields():
    content = {
        "answer": "  answer\n",
        "code": "  h(0)\n",
        "circuit": {"operations": [{"gate": "h", "targets": [0]}]},
    }
    stage = {
        "prediction": content,
        "reasoning": " why\n",
        "explanation": " because\n",
        "reflection": " learned\n",
        "revision": {"previous_response_version_id": "old", "reason": " changed\n"},
        "prediction_checkpoint_id": "checkpoint",
        "simulation_references": [{"run_id": "run", "circuit_version_id": "circuit"}],
    }
    value = EpisodePayloadV1(
        supported=stage,
        transfer={
            "stage_start_id": "start",
            "part_id": "fresh",
            "content": content,
            "process": stage,
        },
    )
    restored = EpisodePayloadV1.model_validate_json(value.model_dump_json())
    assert restored == value
    assert restored.supported.prediction.answer == "  answer\n"
    assert restored.transfer.process.revision.reason == " changed\n"


@pytest.mark.parametrize(
    "value",
    [
        {"answer": 42},
        {"answer": "x" * 100001},
        {"unknown": "text"},
        {"circuit": {"data": "x" * 100001}},
    ],
)
def test_content_rejects_invalid_or_unbounded_values(value):
    with pytest.raises(ValidationError):
        ResponseContent.model_validate(value)


def test_reviewed_plan_and_learner_projection():
    plan = EpisodePlanV1(
        transfer={"prompt": "PRIVATE fresh prompt", "solution": {"answer": "PRIVATE solution"}}
    )
    criteria = {"episode_plan": plan.model_dump(mode="json")}
    assert validate_reviewed_episode_plan(criteria, plan) == plan
    assert "PRIVATE" not in str(learner_episode_plan(plan))
    changed = plan.model_dump(mode="json")
    changed["transfer"]["prompt"] = "different"
    with pytest.raises(ValueError, match="differs"):
        validate_reviewed_episode_plan(criteria, changed)
    with pytest.raises(ValueError, match="not part"):
        validate_reviewed_episode_plan({}, plan)
    assert validate_reviewed_episode_plan({}) is None
