import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from support.task_review import approve_fixture_task
from test_assessment_definition_api import (
    _assign_assessor,
    _definition_payload,
    _draft_definition,
    _login,
    _logout,
    _publish,
)
from test_assessment_definition_api import (
    assessment_api_context as assessment_api_context,
)

from app.core.security import hash_password
from app.models import LearningTask, User, UserRole
from app.models.assessment import TaskApproval, TaskFormVersion
from app.models.source_history import SourcePassage, SourceRevision
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.schemas.lms import TaskUpdate
from app.services.assessment.access import ScopedRoleAccessDeniedError
from app.services.assessment.definitions import AssessmentDefinitionService
from app.services.assessment.publication import learner_task_available
from app.services.assessment.submissions import AssessmentSubmissionService
from app.services.lms import LmsService
from app.services.rag.source_history import record_approval
from app.services.task_review import TaskReviewError

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_publication_binds_exact_review_and_content_edit_needs_new_definition(
    assessment_api_context,
):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    assert not learner_task_available(session, task)
    with pytest.raises(TaskReviewError, match="not currently published"):
        AssessmentSubmissionService(session).declaration_for_task(task)
    _assign_assessor(client, session, course["id"])
    published = _publish(client, course, draft)
    assert published.status_code == 200, published.text
    form = session.get(TaskFormVersion, published.json()["task_forms"][0]["id"])
    revision = session.get(TaskRevision, form.task_revision_id)
    approval = session.scalar(
        select(TaskApproval).where(TaskApproval.task_form_version_id == form.id)
    )
    event = session.get(TaskReviewEvent, approval.task_review_event_id)
    assert revision.task_id == task.id
    assert event.task_revision_id == revision.id
    assert event.state == "APPROVED" and event.source_approvals
    assert form.source_digest == revision.content_digest
    assert form.source_version == f"task-revision:{revision.id}"
    assert learner_task_available(session, task)
    assert client.post(f"/api/v1/courses/{course['id']}/publish").status_code == 200
    owner = session.get(User, course["educator_id"])
    LmsService(session).update_task(
        owner, task.id, TaskUpdate(prompt="Explain a revised observation")
    )
    approve_fixture_task(session, task)
    assert not learner_task_available(session, task)
    with pytest.raises(TaskReviewError, match="save a new assessment definition"):
        AssessmentSubmissionService(session).declaration_for_task(task)
    assert client.post(f"/api/v1/courses/{course['id']}/publish").status_code == 409
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}/definitions/{draft['assessment_definition_id']}",
        json={**_definition_payload(task.id), "expected_version": 1},
    )
    assert revised.status_code == 200, revised.text
    assert _publish(client, course, revised.json()).status_code == 200
    assert learner_task_available(session, task)
    assert session.get(TaskApproval, approval.id).task_review_event_id == event.id
    assert session.get(TaskFormVersion, form.id).task_revision_id == revision.id


def test_assigned_nonowner_can_inspect_revise_and_publish_but_revocation_blocks_access(
    assessment_api_context,
):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    staff = User(
        email="assigned-author@example.edu",
        password_hash=hash_password("fixture-assessor-password"),
        full_name="Assigned Author",
        role=UserRole.EDUCATOR,
    )
    session.add(staff)
    session.commit()
    approved = client.post(
        f"/api/v1/assessment/courses/{course['id']}/assessor-eligibility",
        json={
            "subject_user_id": staff.id,
            "expected_version": 0,
            "state": "APPROVED",
            "reason": "Synthetic lead approval for the named test assessor",
        },
    )
    assert approved.status_code == 201, approved.text
    _logout(client)
    _login(client, "admin")
    grant = client.post(
        f"/api/v1/assessment/admin/courses/{course['id']}/assignments",
        json={
            "subject_user_id": staff.id,
            "role": "assessor",
            "reason": "Synthetic administrator appointment",
        },
    )
    assert grant.status_code == 201, grant.text
    _logout(client)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": staff.email, "password": "fixture-assessor-password"},
        ).status_code
        == 200
    )
    options_path = f"/api/v1/assessment/courses/{course['id']}/authoring-tasks"
    options = client.get(options_path)
    assert options.status_code == 200, options.text
    choice = options.json()[0]
    assert choice["reviewed"] is True and choice["source_materials"]
    assert "expected_answer" not in choice
    assert client.get(f"{options_path}?limit=1&offset=1").json() == []
    material_id = choice["source_materials"][0]["material_id"]
    assert (
        client.get(f"/api/v1/courses/{course['id']}/materials/{material_id}/revisions").status_code
        == 200
    )
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{choice['outcome_id']}/definitions/{draft['assessment_definition_id']}",
        json={**_definition_payload(choice["task_id"]), "expected_version": 1},
    )
    assert revised.status_code == 200, revised.text
    assert _publish(client, course, revised.json()).status_code == 200
    _logout(client)
    _login(client, "admin")
    assert (
        client.request(
            "DELETE",
            f"/api/v1/assessment/admin/assignments/{grant.json()['id']}",
            json={"reason": "Synthetic appointment ended"},
        ).status_code
        == 200
    )
    _logout(client)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": staff.email, "password": "fixture-assessor-password"},
        ).status_code
        == 200
    )
    assert client.get(options_path).status_code == 403
    assert _publish(client, course, revised.json()).status_code == 403
    assert (
        client.put(
            f"/api/v1/assessment/courses/{course['id']}/outcomes/{choice['outcome_id']}/definitions/{draft['assessment_definition_id']}",
            json={**_definition_payload(choice["task_id"]), "expected_version": 2},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("evaluator", ["validated_ai", "mixed"])
def test_unvalidated_ai_does_not_enter_formal_publication(assessment_api_context, evaluator):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    payload = _definition_payload(task.id)
    payload["criteria"][0]["evaluator_type"] = evaluator
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}/definitions/{draft['assessment_definition_id']}",
        json={**payload, "expected_version": 1},
    )
    assert revised.status_code == 200, revised.text
    rejected = _publish(client, course, revised.json())
    assert rejected.status_code == 422 and "separate validation gate" in rejected.text


def test_source_reapproval_requires_new_teaching_review_and_form(assessment_api_context):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    assert _publish(client, course, draft).status_code == 200
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    passage = session.get(SourcePassage, task.source_references[0])
    revision = session.get(SourceRevision, passage.revision_id)
    for sequence, state in [(1, "REVOKED"), (2, "APPROVED")]:
        record_approval(
            session,
            course_id=course["id"],
            material_id=revision.material_id,
            revision_id=revision.id,
            actor_id=str(course["educator_id"]),
            expected_sequence=sequence,
            state=state,
            reason="Synthetic source review change",
        )
        assert not learner_task_available(session, task)
        with pytest.raises(TaskReviewError):
            AssessmentSubmissionService(session).declaration_for_task(task)
    approve_fixture_task(session, task)
    with pytest.raises(TaskReviewError, match="no longer matches educator review"):
        AssessmentSubmissionService(session).declaration_for_task(task)
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}/definitions/{draft['assessment_definition_id']}",
        json={**_definition_payload(task.id), "expected_version": 1},
    )
    assert revised.status_code == 200, revised.text
    assert _publish(client, course, revised.json()).status_code == 200
    assert learner_task_available(session, task)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE task_form_versions SET task_revision_id = NULL WHERE id = :form",
        "UPDATE task_approvals SET task_review_event_id = NULL WHERE task_form_version_id = :form",
        "INSERT OR REPLACE INTO task_form_versions SELECT * FROM task_form_versions WHERE id = :form",
        "INSERT OR REPLACE INTO task_approvals SELECT * FROM task_approvals WHERE task_form_version_id = :form",
    ],
)
def test_publication_bindings_reject_direct_rewrite(assessment_api_context, statement):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    assert _publish(client, course, draft).status_code == 200
    with pytest.raises(IntegrityError, match="immutable"):
        session.execute(text(statement), {"form": draft["task_forms"][0]["id"]})
    session.rollback()


@pytest.mark.parametrize("actor_kind", ["student", "withdrawn"])
def test_service_publication_requires_current_assessor(assessment_api_context, actor_kind):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    actor_id = course["educator_id"]
    if actor_kind == "student":
        actor_id = session.scalar(select(User.id).where(User.role == UserRole.STUDENT))
    else:
        withdrawn = client.post(
            f"/api/v1/assessment/courses/{course['id']}/assessor-eligibility",
            json={
                "subject_user_id": actor_id,
                "expected_version": 1,
                "state": "WITHDRAWN",
                "reason": "Synthetic direct service denial test",
            },
        )
        assert withdrawn.status_code == 201, withdrawn.text
    with pytest.raises(ScopedRoleAccessDeniedError):
        AssessmentDefinitionService(session).approve(
            course_id=course["id"],
            assessment_definition_id=draft["assessment_definition_id"],
            expected_version=1,
            actor_user_id=actor_id,
            approval_reason="Direct service attempt",
        )
    assert session.scalar(select(TaskApproval.id)) is None


@pytest.mark.parametrize(
    "field, value",
    [
        ("instructional_support", {"allowed": ["   "]}),
        ("transfer_rule", {"rule": "   "}),
        ("task_conditions", {"source": ""}),
        ("permitted_tools", {"allowed": [""]}),
    ],
)
def test_blank_nested_conditions_block_publication(assessment_api_context, field, value):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    payload = {**_definition_payload(task.id), field: value, "expected_version": 1}
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}/definitions/{draft['assessment_definition_id']}",
        json=payload,
    )
    assert revised.status_code == 200, revised.text
    rejected = _publish(client, course, revised.json())
    assert rejected.status_code == 422 and field in rejected.text


def test_explicit_no_tools_support_or_transfer_is_a_complete_declaration(assessment_api_context):
    client, session = assessment_api_context
    _login(client, "educator")
    course, draft = _draft_definition(client)
    _assign_assessor(client, session, course["id"])
    task = session.get(LearningTask, draft["task_forms"][0]["learning_task_id"])
    payload = {
        **_definition_payload(task.id),
        "permitted_tools": {"allowed": []},
        "instructional_support": {"allowed": []},
        "transfer_rule": {"required": False},
        "expected_version": 1,
    }
    revised = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{task.learning_outcome_id}/definitions/{draft['assessment_definition_id']}",
        json=payload,
    )
    assert revised.status_code == 200, revised.text
    published = _publish(client, course, revised.json())
    assert published.status_code == 200, published.text
