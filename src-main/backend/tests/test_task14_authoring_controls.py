from copy import deepcopy

import pytest
from sqlalchemy import func, select
from support.task_review import approve_fixture_task
from test_assessment_definition_api import (
    _assign_assessor,
    _definition_payload,
    _draft_definition,
    _login,
    _publish,
)
from test_assessment_definition_api import assessment_api_context as assessment_api_context
from test_assessment_work_starts import setup_work

from app.models import LearningTask, User
from app.models.assessment import TaskFormVersion
from app.models.assessment_work import AssessmentWorkStart
from app.models.lms import SubmissionDraft
from app.models.task_review import TaskRevision
from app.schemas.episode import EpisodePlanV1
from app.schemas.lms import TaskUpdate
from app.services.assessment.publication import current_form_review, learner_task_available
from app.services.lms import LmsService
from app.services.task_review import TaskReviewError, TaskReviewService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def _plan():
    return {
        "transfer": {
            "prompt": "Explain a fresh Hadamard example.",
            "solution": {"answer": "PRIVATE TRANSFER GUIDANCE"},
        },
        "supported_hints": ["Consider how the gate changes the state."],
        "accessibility_support": ["Equivalent circuit text"],
    }


def test_episode_only_legacy_draft_keeps_its_original_unversioned_work(db_session):
    student, task, form, _, _, _ = setup_work(db_session)
    episode = {"supported": {"prediction": {"answer": "Earlier prediction"}}}
    draft = SubmissionDraft(student_id=student.id, task_id=task.id, answer="", episode=episode)
    db_session.add(draft)
    db_session.commit()
    with pytest.raises(TaskReviewError, match="predates"):
        LmsService(db_session).start_assessment_work(student, task.id, form.id)
    db_session.rollback()
    saved = LmsService(db_session).get_draft(student, task.id)
    assert saved.episode.supported.prediction.answer == "Earlier prediction"
    assert saved.assessment_work_start_id is None
    assert db_session.scalar(select(func.count()).select_from(AssessmentWorkStart)) == 0


def _saved_episode(client, session):
    _login(client, "educator")
    course, draft = _draft_definition(client)
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    owner = session.get(User, course["educator_id"])
    criteria = {**task.marking_criteria, "episode_plan": _plan()}
    LmsService(session).update_task(owner, task.id, TaskUpdate(marking_criteria=criteria))
    approve_fixture_task(session, task)
    return course, draft, task


def _update(client, course, draft, task, payload):
    return client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}"
        f"/definitions/{draft['assessment_definition_id']}",
        json={**payload, "expected_version": draft["version"]},
    )


def test_definition_freezes_reviewed_private_plan_and_changed_prompt_invalidates_publication(
    assessment_api_context,
):
    client, session = assessment_api_context
    course, draft, task = _saved_episode(client, session)
    updated = _update(client, course, draft, task, _definition_payload(task.id))
    assert updated.status_code == 200, updated.text
    canonical = EpisodePlanV1.model_validate(_plan()).model_dump(mode="json")
    assert updated.json()["task_forms"][0]["constraints"]["episode_plan"] == canonical
    _assign_assessor(client, session, course["id"])
    published = _publish(client, course, updated.json())
    assert published.status_code == 200, published.text
    form = session.get(TaskFormVersion, published.json()["task_forms"][0]["id"])
    revision = session.get(TaskRevision, form.task_revision_id)
    assert revision.snapshot["marking_criteria"]["episode_plan"] == _plan()
    assert current_form_review(session, form).task_revision_id == revision.id
    owner = session.get(User, course["educator_id"])
    changed = deepcopy(task.marking_criteria)
    changed["episode_plan"]["transfer"]["prompt"] = "A different fresh task."
    LmsService(session).update_task(owner, task.id, TaskUpdate(marking_criteria=changed))
    assert not learner_task_available(session, task)
    assert form.constraints["episode_plan"] == canonical
    assert revision.snapshot["marking_criteria"]["episode_plan"] == _plan()


def test_definition_rejects_unreviewed_private_plan_copy(assessment_api_context):
    client, session = assessment_api_context
    course, draft, task = _saved_episode(client, session)
    payload = _definition_payload(task.id)
    altered = _plan()
    altered["transfer"]["prompt"] = "UNREVIEWED PRIVATE PROMPT"
    payload["task_forms"][0]["constraints"]["episode_plan"] = altered
    response = _update(client, course, draft, task, payload)
    assert response.status_code == 422
    assert "UNREVIEWED PRIVATE PROMPT" not in response.text
    assert "PRIVATE TRANSFER GUIDANCE" not in response.text


@pytest.mark.parametrize(
    "circuit",
    [
        {"qubits": 1, "operations": [{"gate": "unsupported", "targets": [0]}]},
        {"qubits": 1, "operations": [{"gate": "h", "targets": [0], "angle": 1}]},
        {"qubits": 1, "operations": [{"gate": "cx", "targets": [0, 0]}]},
    ],
)
def test_teaching_review_rejects_invalid_private_starter_circuit(assessment_api_context, circuit):
    client, session = assessment_api_context
    course, _, task = _saved_episode(client, session)
    changed = deepcopy(task.marking_criteria)
    changed["episode_plan"]["transfer"]["starter_circuit"] = circuit
    owner = session.get(User, course["educator_id"])
    LmsService(session).update_task(owner, task.id, TaskUpdate(marking_criteria=changed))
    with pytest.raises(TaskReviewError, match="unsupported circuit"):
        TaskReviewService(session).validate_ready(task, require_sources=True)
