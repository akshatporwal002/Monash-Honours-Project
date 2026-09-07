import pytest
from test_assessment_definition_api import (
    _assign_assessor,
    _definition_payload,
    _draft_definition,
    _login,
    _publish,
)
from test_assessment_definition_api import assessment_api_context as assessment_api_context

from app.models import LearningTask
from app.models.assessment import CriterionVersion


def _circuit_definition(
    client, session, *, evaluator="rules", stage="supported", bloom="APPLY", qubits=1
):
    course, draft = _draft_definition(client)
    task_id = draft["task_forms"][0]["learning_task_id"]
    outcome_id = session.get(LearningTask, task_id).learning_outcome_id
    payload = _definition_payload(task_id)
    payload["bloom_process"] = bloom
    payload["task_forms"][0]["constraints"]["elicited_bloom_processes"] = [bloom]
    payload["criteria"][0]["evaluator_type"] = evaluator
    payload["criteria"][0]["critical_error_rules"] = {}
    payload["criteria"][0]["approved_anchors"] = {
        "kind": "circuit_v1",
        "stage": stage,
        "qubits": qubits,
        "operations": [{"gate": "h", "targets": [0]}],
    }
    updated = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{outcome_id}"
        f"/definitions/{draft['assessment_definition_id']}",
        json={**payload, "expected_version": draft["version"]},
    )
    assert updated.status_code == 200, updated.text
    return course, updated.json()


@pytest.mark.parametrize("evaluator", ["rules", "mixed"])
def test_approved_apply_structure_publishes_with_its_declared_evaluator(
    assessment_api_context,
    evaluator,
):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _circuit_definition(client, session, evaluator=evaluator)
    _assign_assessor(client, session, course["id"])
    published = _publish(client, course, draft)
    assert published.status_code == 200, published.text
    criterion = published.json()["criteria"][0]
    assert criterion["evaluator_type"] == evaluator
    assert session.get(CriterionVersion, criterion["id"]).approved_anchors["kind"] == "circuit_v1"
    assert published.json()["approval_state"] == "APPROVED"


@pytest.mark.parametrize(
    "settings",
    [{"stage": "transfer"}, {"bloom": "UNDERSTAND"}, {"qubits": 6}, {"evaluator": "validated_ai"}],
)
def test_invalid_circuit_scope_or_rules_do_not_pass_publication(assessment_api_context, settings):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _circuit_definition(client, session, **settings)
    _assign_assessor(client, session, course["id"])
    published = _publish(client, course, draft)
    assert published.status_code == 422
