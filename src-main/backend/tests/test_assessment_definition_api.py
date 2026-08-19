from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.assessment_dependencies import (
    get_assessment_publication_policy,
    get_scoped_role_eligibility,
)
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory, get_db
from app.main import create_app
from app.models.assessment import AssessmentDefinition, OutcomeVersion
from app.models.lms import PlatformAuditEvent
from app.models.user import RoleAssignment, User, UserRole
from app.services.lms import DEMO_PASSWORD, bootstrap_demo


@pytest.fixture
def assessment_api_context(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'assessment-api.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    session = factory()
    bootstrap_demo(session)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_scoped_role_eligibility] = lambda: (
        lambda subject, role: subject.role is UserRole.EDUCATOR
    )
    app.dependency_overrides[get_assessment_publication_policy] = lambda: (
        lambda _actor, _course_id: True
    )
    try:
        with TestClient(app) as client:
            yield client, session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _login(client: TestClient, role: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"{role}@quantumlearn.demo", "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200


def _logout(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 204


def _definition_payload(task_id: str, *, eligible: bool = True) -> dict[str, object]:
    return {
        "claim": "The learner can analyse interference evidence to support a claim.",
        "supporting_evidence": {"observable": ["links evidence to the claim"]},
        "contradicting_evidence": {"observable": ["reverses the evidence relationship"]},
        "insufficient_evidence": {"observable": ["names evidence without analysis"]},
        "task_conditions": {"response_mode": "written"},
        "next_action_contract": {"when_incomplete": "offer reassessment when approved"},
        "purpose": "SUMMATIVE",
        "permitted_tools": {"allowed": ["course notes"]},
        "instructional_support": {"maximum_level": "approved"},
        "access_conditions": {"modes": [{"mode": "screen_reader", "preserves_construct": True}]},
        "transfer_rule": {"required": True, "new_context": "another quantum circuit"},
        "evidence_sufficiency": {"requires": ["criterion evidence"]},
        "formal_result_eligible": eligible,
        "bloom_process": "ANALYSE",
        "knowledge_dimension": "CONCEPTUAL",
        "criteria": [
            {
                "stable_key": "evidence_to_claim",
                "learner_description": "Explain how the evidence supports the claim.",
                "evidence_description": "Connects the observed pattern to the claim.",
                "mandatory": True,
                "evidence_source_types": ["learner_response"],
                "met_rule": "The response makes the relationship explicit.",
                "not_met_rule": "The response omits the relationship.",
                "not_evaluable_rule": "The response is unavailable or invalid.",
                "approved_anchors": {"met": ["valid explanation"]},
                "critical_error_rules": {"errors": ["reverses the relationship"]},
                "evaluator_type": "rules",
            }
        ],
        "pass_rule_expression": {
            "operator": "ALL_OF",
            "clauses": [{"criterion": "evidence_to_claim"}],
        },
        "task_forms": [
            {
                "learning_task_id": task_id,
                "source_version": "learning-task.v1",
                "source_digest": "sha256:assessment-definition-api-task",
                "task_family": "written_analysis",
                "context": {"scenario": "interference observation"},
                "constraints": {
                    "response_format": "text",
                    "elicited_bloom_processes": ["ANALYSE"],
                },
            }
        ],
    }


def _draft_definition(client: TestClient) -> tuple[dict[str, object], dict[str, object]]:
    course = client.post(
        "/api/v1/courses", json={"code": "ASM-701", "title": "Assessment API course"}
    ).json()
    module = client.post(
        f"/api/v1/courses/{course['id']}/modules",
        json={"title": "Quantum evidence", "description": "", "position": 1},
    ).json()
    outcome = client.post(
        f"/api/v1/modules/{module['id']}/outcomes",
        json={
            "title": "Analyse interference evidence",
            "statement": "Analyse how interference supports a quantum claim.",
            "kind": "topic",
            "position": 1,
        },
    ).json()
    task = client.post(
        f"/api/v1/courses/{course['id']}/tasks",
        json={
            "module_id": module["id"],
            "learning_outcome_id": outcome["id"],
            "title": "Interference analysis",
            "prompt": "Explain the evidence.",
            "instructions": "Use one evidence-to-claim explanation.",
            "task_type": "short_answer",
            "difficulty": "intermediate",
            "position": 1,
            "expected_answer": "evidence",
        },
    ).json()
    response = client.post(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{outcome['id']}/definitions",
        json=_definition_payload(task["id"]),
    )
    assert response.status_code == 201, response.text
    return course, response.json()


def _assign_assessor(client: TestClient, session: Session, course_id: str) -> None:
    _logout(client)
    _login(client, "admin")
    educator = session.scalar(select(User).where(User.email == "educator@quantumlearn.demo"))
    assert educator is not None
    response = client.post(
        f"/api/v1/assessment/admin/courses/{course_id}/assignments",
        json={
            "subject_user_id": educator.id,
            "role": "assessor",
            "reason": "Approved to assess the test course.",
        },
    )
    assert response.status_code == 201, response.text
    _logout(client)
    _login(client, "educator")


def _publish(client: TestClient, course: dict[str, object], definition: dict[str, object]):
    return client.post(
        f"/api/v1/assessment/courses/{course['id']}/definitions/"
        f"{definition['assessment_definition_id']}/publish",
        json={"expected_version": definition["version"], "reason": "Approved for formal use."},
    )


def test_educator_can_draft_but_cannot_approve_assessment(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, _ = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)

    response = _publish(client, course, definition)

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


def test_course_assessor_can_approve_complete_definition(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    _assign_assessor(client, session, str(course["id"]))

    response = _publish(client, course, definition)

    assert response.status_code == 200, response.text
    assert response.json()["approval_state"] == "APPROVED"
    assert response.json()["formal_result_eligible"] is True
    history = client.get(
        f"/api/v1/assessment/courses/{course['id']}/definitions/"
        f"{definition['assessment_definition_id']}/history"
    )
    assert history.status_code == 200
    assert history.json()[0]["criteria"][0]["stable_key"] == "evidence_to_claim"
    assert history.json()[0]["task_forms"][0]["learning_task_id"]
    assert "expected_answer" not in history.json()[0]


def test_educator_can_save_a_versioned_draft_revision(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    task_id = definition["task_forms"][0]["learning_task_id"]
    identity = session.get(AssessmentDefinition, definition["assessment_definition_id"])
    assert identity is not None
    outcome_id = identity.learning_outcome_id
    payload = _definition_payload(str(task_id))
    payload.update(
        {
            "expected_version": definition["version"],
            "claim": "The learner can analyse revised interference evidence.",
        }
    )

    response = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{outcome_id}/definitions/"
        f"{definition['assessment_definition_id']}",
        json=payload,
    )

    assert response.status_code == 200, response.text
    revised = response.json()
    assert revised["assessment_definition_id"] == definition["assessment_definition_id"]
    assert revised["version"] == 2
    assert revised["claim"] == "The learner can analyse revised interference evidence."

    stale = client.put(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{outcome_id}/definitions/"
        f"{definition['assessment_definition_id']}",
        json=payload,
    )
    assert stale.status_code == 409
    assert (
        session.scalar(
            select(func.count())
            .select_from(OutcomeVersion)
            .where(OutcomeVersion.learning_outcome_id == outcome_id)
        )
        == 2
    )


def test_student_admin_and_cross_course_users_are_denied(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    _logout(client)
    _login(client, "student")
    assert _publish(client, course, definition).status_code == 403
    assert (
        client.get(
            f"/api/v1/assessment/courses/{course['id']}/definitions/"
            f"{definition['assessment_definition_id']}/history"
        ).status_code
        == 404
    )
    _logout(client)
    _login(client, "admin")
    assert _publish(client, course, definition).status_code == 403

    _logout(client)
    _login(client, "educator")
    other_course = client.post(
        "/api/v1/courses", json={"code": "ASM-702", "title": "Other assessment course"}
    ).json()
    _assign_assessor(client, session, str(course["id"]))
    assert _publish(client, other_course, definition).status_code == 403


def test_publication_requires_bloom_criteria_pass_rule_and_approved_form(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course = client.post(
        "/api/v1/courses", json={"code": "ASM-703", "title": "Incomplete assessment course"}
    ).json()
    module = client.post(
        f"/api/v1/courses/{course['id']}/modules",
        json={"title": "Quantum evidence", "description": "", "position": 1},
    ).json()
    outcome = client.post(
        f"/api/v1/modules/{module['id']}/outcomes",
        json={
            "title": "Analyse interference evidence",
            "statement": "Analyse how interference supports a quantum claim.",
            "kind": "topic",
            "position": 1,
        },
    ).json()
    task = client.post(
        f"/api/v1/courses/{course['id']}/tasks",
        json={
            "module_id": module["id"],
            "learning_outcome_id": outcome["id"],
            "title": "Interference recall",
            "prompt": "Name the evidence.",
            "instructions": "Give one word.",
            "task_type": "short_answer",
            "difficulty": "beginner",
            "position": 1,
            "expected_answer": "interference",
        },
    ).json()
    payload = _definition_payload(task["id"])
    payload["task_forms"] = []
    definition = client.post(
        f"/api/v1/assessment/courses/{course['id']}/outcomes/{outcome['id']}/definitions",
        json=payload,
    ).json()
    _assign_assessor(client, session, str(course["id"]))

    response = _publish(client, course, definition)

    assert response.status_code == 422
    assert "approved task form" in response.json()["detail"]
    assert "assessment_definition.approval_rejected" in set(
        session.scalars(select(PlatformAuditEvent.action)).all()
    )


def test_stale_publication_returns_conflict(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    _assign_assessor(client, session, str(course["id"]))
    assert _publish(client, course, definition).status_code == 200

    response = _publish(client, course, definition)

    assert response.status_code == 409


def test_admin_can_revoke_scoped_assessor_access(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    _assign_assessor(client, session, str(course["id"]))
    assignment = session.scalar(
        select(RoleAssignment).where(RoleAssignment.course_id == course["id"])
    )
    assert assignment is not None
    _logout(client)
    _login(client, "admin")

    response = client.request(
        "DELETE",
        f"/api/v1/assessment/admin/assignments/{assignment.id}",
        json={"reason": "Assessment allocation ended."},
    )

    assert response.status_code == 200, response.text
    assert response.json()["revoked_at"] is not None
    _logout(client)
    _login(client, "educator")
    assert _publish(client, course, definition).status_code == 403


def test_assessment_setup_actions_are_audited(
    assessment_api_context: tuple[TestClient, Session],
) -> None:
    client, session = assessment_api_context
    _login(client, "educator")
    course, definition = _draft_definition(client)
    _assign_assessor(client, session, str(course["id"]))
    assert _publish(client, course, definition).status_code == 200

    actions = set(session.scalars(select(PlatformAuditEvent.action)).all())
    assert {
        "assessment.outcome_source_versioned",
        "assessment_definition.drafted",
        "role_assignment.assigned",
        "assessment_definition.approved",
    } <= actions
