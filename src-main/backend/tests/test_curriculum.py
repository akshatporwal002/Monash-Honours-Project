"""Real approved task graph, evidence transactions, and practice-only bypass."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from support.task_review import approve_sourced_fixture_task

from app.models import LearningTask, User, UserRole
from app.models.assessment import AssessmentDecision
from app.models.curriculum import (
    DiagnosticConfirmation,
    DiagnosticResponse,
    DiagnosticSession,
    PathwayVersion,
)
from app.models.learning_evidence import LearningEvidence
from app.schemas.curriculum import (
    DiagnosticConfirm,
    DiagnosticStart,
    DiagnosticSubmit,
    PathwayPublish,
)
from app.services.assessment.eligibility import AssessorEligibilityService
from app.services.curriculum import CurriculumService, pathway_progress


@pytest.fixture
def curriculum(db_session):
    from support.curriculum import setup_curriculum

    return setup_curriculum(db_session)


def start_and_submit(context, *, independent=True):
    service, _, student, _, tasks, _, path = context
    start = DiagnosticStart(
        request_key="start",
        pathway_id=path.id,
        purpose="prior_mastery",
        target_task_id=tasks[-1].id,
    )
    row = service.start(student, start)
    payload = DiagnosticSubmit(
        request_key="response",
        prior_knowledge="H applied twice is identity.",
        reasoning="The second H reverses the first transformation.",
        confidence="sure",
        concept_uncertainty="none_reported",
        requested_support="none",
        independent_conditions_met=independent,
    )
    return service.submit(student, row.id, payload), start, payload


def confirmation(**changes):
    return DiagnosticConfirm(
        **dict(
            request_key="confirm",
            decision="advance",
            independent_verified=True,
            reason="Independent reasoning checked against the approved criteria",
        )
        | changes
    )


def test_diagnostic_evidence_and_confirmed_practice_bypass(curriculum, db_session):
    service, teacher, student, _, tasks, _, _ = curriculum
    row, _, _ = start_and_submit(curriculum)
    assert row.state == "needs_review"
    assert pathway_progress(db_session, student.id, tasks[-1])[0] == set()
    result = service.confirm(teacher, row.id, confirmation())
    assert result.state == "advance" and result.reason
    assert pathway_progress(db_session, student.id, tasks[-1]) == (
        {task.id for task in tasks[:2]},
        {tasks[1].id},
        "independent",
    )
    evidence = db_session.get(LearningEvidence, result.evidence_id)
    assert evidence.evidence_type.value == "DIAGNOSTIC"
    assert evidence.observation_type.value == "SELF_REPORTED"
    assert db_session.scalar(select(func.count()).select_from(AssessmentDecision)) == 0


def test_exact_replay_and_payload_conflicts(curriculum, db_session):
    service, teacher, student, _, tasks, publish, path = curriculum
    assert service.publish(teacher, tasks[0].learning_outcome_id, publish).id == path.id
    row, start, response = start_and_submit(curriculum)
    assert service.start(student, start).id == row.id
    assert service.submit(student, row.id, response).evidence_id == row.evidence_id
    service.confirm(teacher, row.id, confirmation())
    assert service.confirm(teacher, row.id, confirmation()).state == "advance"
    for operation in (
        lambda: service.submit(
            student, row.id, response.model_copy(update={"reasoning": "Changed response"})
        ),
        lambda: service.confirm(teacher, row.id, confirmation(decision="retain")),
        lambda: service.publish(
            teacher, tasks[0].learning_outcome_id, publish.model_copy(update={"title": "Changed"})
        ),
    ):
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(DiagnosticResponse)) == 1


def test_no_independent_claim_or_learner_self_confirmation(curriculum):
    service, teacher, student, *_ = curriculum
    row, _, _ = start_and_submit(curriculum, independent=False)
    with pytest.raises(HTTPException) as error:
        service.confirm(student, row.id, confirmation())
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        service.confirm(teacher, row.id, confirmation())
    assert error.value.status_code == 422
    assert (
        service.confirm(
            teacher, row.id, confirmation(decision="retain", independent_verified=False)
        ).state
        == "retain"
    )


def test_scope_and_revoked_assessor(curriculum, db_session):
    service, teacher, student, course, *_ = curriculum
    row, _, _ = start_and_submit(curriculum)
    other = User(
        email="other@curriculum.test",
        password_hash="unused",
        full_name="Other",
        role=UserRole.STUDENT,
    )
    db_session.add(other)
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        service.read(other, row.id)
    assert error.value.status_code == 404
    AssessorEligibilityService(db_session).record(
        teacher,
        course_id=course.id,
        subject_user_id=teacher.id,
        expected_version=1,
        state="WITHDRAWN",
        reason="Assessor duties ended",
    )
    with pytest.raises(HTTPException) as error:
        service.confirm(teacher, row.id, confirmation())
    assert error.value.status_code == 403
    assert service.read(student, row.id).state == "needs_review"


def test_changed_task_or_pathway_cannot_grant_stale_bypass(curriculum, db_session):
    service, teacher, student, _, tasks, publish, path = curriculum
    row, _, _ = start_and_submit(curriculum)
    newer = service.publish(
        teacher,
        tasks[0].learning_outcome_id,
        publish.model_copy(update={"expected_version": 1, "request_key": "publish2"}),
    )
    assert newer.version == 2
    with pytest.raises(HTTPException):
        service.confirm(teacher, row.id, confirmation())
    assert service.read(student, row.id).pathway_id == path.id
    tasks[0].instructions += " Changed after approval."
    db_session.commit()
    with pytest.raises(Exception, match="changed|Changed|unavailable"):
        service.start(
            student,
            DiagnosticStart(
                request_key="new",
                pathway_id=newer.id,
                purpose="initial",
                target_task_id=tasks[0].id,
            ),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"diagnosis": "forbidden"},
        {"learner_id": 44},
        {"expected_version": True},
        {"steps": []},
    ],
)
def test_strict_publication_contract(curriculum, change):
    with pytest.raises(ValidationError):
        PathwayPublish.model_validate(curriculum[5].model_dump() | change)


def test_graph_rejects_cycles_duplicates_and_cross_outcome(curriculum):
    service, teacher, _, _, tasks, publish, _ = curriculum
    data = publish.model_dump()
    data["steps"][0]["prerequisites"] = [tasks[-1].id]
    with pytest.raises(ValidationError):
        PathwayPublish.model_validate(data)
    data = publish.model_dump()
    data["steps"][1]["task_id"] = data["steps"][0]["task_id"]
    with pytest.raises(ValidationError):
        PathwayPublish.model_validate(data)
    data = publish.model_dump()
    data.update(expected_version=1, request_key="invalid")
    data["steps"][-1]["task_id"] = "other-course-task"
    with pytest.raises(HTTPException) as error:
        service.publish(teacher, tasks[0].learning_outcome_id, PathwayPublish.model_validate(data))
    assert error.value.status_code == 422


def test_history_cannot_be_replaced_updated_or_deleted(curriculum, db_session):
    row, _, _ = start_and_submit(curriculum)
    curriculum[0].confirm(curriculum[1], row.id, confirmation())
    for model in (PathwayVersion, DiagnosticSession, DiagnosticResponse, DiagnosticConfirmation):
        for action in (
            f"UPDATE {model.__tablename__} SET id=id",
            f"DELETE FROM {model.__tablename__}",
            f"INSERT OR REPLACE INTO {model.__tablename__} SELECT * FROM {model.__tablename__}",
        ):
            with pytest.raises(IntegrityError):
                db_session.execute(text(action))
            db_session.rollback()


def test_evidence_and_response_roll_back_together(curriculum, db_session, monkeypatch):
    service, _, student, _, tasks, _, path = curriculum
    row = service.start(
        student,
        DiagnosticStart(
            request_key="start", pathway_id=path.id, purpose="initial", target_task_id=tasks[0].id
        ),
    )

    def fail():
        raise RuntimeError("Injected final commit failure")

    monkeypatch.setattr(service, "_commit", fail)
    payload = DiagnosticSubmit(
        request_key="reply",
        prior_knowledge="H",
        reasoning="H twice restores input",
        confidence="unsure",
        concept_uncertainty="unsure",
        requested_support="guided",
        independent_conditions_met=False,
    )
    with pytest.raises(RuntimeError, match="Injected"):
        service.submit(student, row.id, payload)
    assert db_session.scalar(select(func.count()).select_from(DiagnosticResponse)) == 0
    assert db_session.scalar(select(func.count()).select_from(LearningEvidence)) == 0


def test_mounted_api_csrf_history_and_actual_task_unlock(curriculum, db_session):
    from fastapi.testclient import TestClient
    from test_lms_core_api import login

    from app.db.session import get_db
    from app.main import create_app
    from app.schemas.learner_preferences import PreferenceUpdate, PreferenceValues
    from app.services.learner_preferences import LearnerPreferenceService
    from app.services.lms import LmsService

    service, teacher, student, course, tasks, _, path = curriculum
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        endpoint = "/api/v1/curriculum/diagnostics"
        assert client.get(f"/api/v1/curriculum/courses/{course.id}/pathways").status_code == 401
        login(client, "student")
        headers = {"X-CSRF-Token": client.cookies.get("ql_csrf"), "Origin": "http://localhost:5173"}
        payload = dict(
            request_key="api-start",
            pathway_id=path.id,
            purpose="prior_mastery",
            target_task_id=tasks[-1].id,
        )
        assert client.post(endpoint, json=payload).status_code == 403
        result = client.post(endpoint, json=payload, headers=headers)
        assert result.status_code == 200, result.text
        assert result.headers["cache-control"] == "no-store"
        identity = result.json()["id"]
        assert client.get(endpoint + "/" + identity + "?learner_id=100").status_code == 422
        assert (
            client.get(f"/api/v1/curriculum/courses/{course.id}/diagnostics?limit=101").status_code
            == 422
        )
        response = dict(
            request_key="reply",
            prior_knowledge="H twice restores input",
            reasoning="H is self inverse",
            confidence="sure",
            concept_uncertainty="none_reported",
            requested_support="none",
            independent_conditions_met=True,
        )
        assert (
            client.post(
                endpoint + f"/{identity}/response",
                json=response | {"formal_result": "PASS"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint + f"/{identity}/response", json=response, headers=headers
            ).status_code
            == 200
        )
        assert (
            LmsService(db_session).get_student_task(student, tasks[-1].id).access_status == "locked"
        )
        service.confirm(teacher, identity, confirmation())
        lms = LmsService(db_session)
        assert lms.get_student_task(student, tasks[-1].id).access_status == "available"
        lms._require_unlocked(student, tasks[-1])
        assert (
            lms.effective_preferences(student, tasks[-1].id).pathway_support_level == "independent"
        )
        LearnerPreferenceService(db_session).save(
            student,
            PreferenceUpdate(
                expected_version=0,
                request_key="off",
                values=PreferenceValues(personalisation_enabled=False),
            ),
        )
        assert lms.effective_preferences(student, tasks[-1].id).pathway_support_level is None
        history = client.get(f"/api/v1/curriculum/courses/{course.id}/diagnostics").json()
        assert history[0]["state"] == "advance"


def test_formal_tasks_cannot_be_diagnostic_or_bypassed(db_session):
    from copy import copy

    from test_assessment_work_starts import setup_work

    from app.models.lms import new_uuid
    from app.services.task_review import TaskReviewError

    student, formal, _, _, _, owner_id = setup_work(db_session)
    teacher = db_session.get(User, owner_id)
    tasks = []
    for index in range(2):
        task = LearningTask(
            id=new_uuid(),
            slug=f"practice-{index}",
            title="Practice",
            module=formal.module,
            description=formal.description,
            instructions=formal.instructions,
            task_type=formal.task_type,
            difficulty="introductory",
            points=0,
            position=index + 1,
            course_id=formal.course_id,
            module_id=formal.module_id,
            learning_outcome_id=formal.learning_outcome_id,
            expected_answer=formal.expected_answer,
            marking_criteria=copy(formal.marking_criteria),
            prerequisite_task_ids=[],
        )
        db_session.add(task)
        db_session.commit()
        approve_sourced_fixture_task(db_session, task)
        tasks.append(task)
    tasks.append(formal)
    payload = PathwayPublish(
        expected_version=0,
        request_key="formal-path",
        title="Practice and unchanged assessment",
        steps=[
            dict(
                task_id=task.id,
                concept="Hadamard",
                prerequisites=[],
                support_level="guided",
                faded_support_level="concept_cue",
                evidence_rule="Approved evidence",
            )
            for task in tasks
        ],
        diagnostic_task_id=formal.id,
        diagnostic_prompt="Prior knowledge",
        independent_conditions="Unaided with access support",
        reason="Teaching review",
    )
    service = CurriculumService(db_session)
    with pytest.raises((HTTPException, TaskReviewError)):
        service.publish(teacher, formal.learning_outcome_id, payload)
    valid = payload.model_copy(update={"diagnostic_task_id": tasks[0].id})
    path = service.publish(teacher, formal.learning_outcome_id, valid)
    with pytest.raises(HTTPException) as error:
        service.start(
            student,
            DiagnosticStart(
                request_key="formal-bypass",
                pathway_id=path.id,
                purpose="prior_mastery",
                target_task_id=formal.id,
            ),
        )
    assert error.value.status_code == 422
    assert pathway_progress(db_session, student.id, formal)[0] == set()


def test_new_migration_matches_metadata_and_replays_guards(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, inspect
    from test_migrations import migration_config

    url = f"sqlite:///{(tmp_path / 'curriculum.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.begin() as connection:
        assert inspect(connection).has_table("curriculum_diagnostic_responses")
        connection.execute(text("DROP TRIGGER curriculum_diagnostic_responses_no_delete"))
    command.stamp(config, "20260908_0033")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name='curriculum_diagnostic_responses_no_delete'"
                )
            ).scalar_one()
            == 1
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(config, "20260908_0033")
    assert not inspect(engine).has_table("curriculum_pathway_versions")
    command.upgrade(config, "head")
    from sqlalchemy.orm import Session
    from support.curriculum import setup_curriculum

    with Session(engine) as session:
        context = setup_curriculum(session)
        diagnostic, _, _ = start_and_submit(context)
        context[0].confirm(context[1], diagnostic.id, confirmation())
    with pytest.raises(RuntimeError, match="history is protected"):
        command.downgrade(config, "20260908_0033")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260910_0044"
        )
        assert (
            connection.execute(
                text("SELECT COUNT(*) FROM curriculum_diagnostic_confirmations")
            ).scalar_one()
            == 1
        )
    engine.dispose()


def test_simultaneous_identical_starts_return_one_receipt(curriculum, db_session):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import Session

    _, _, student, _, tasks, _, path = curriculum
    identity = student.id
    barrier = Barrier(2)
    payload = DiagnosticStart(
        request_key="concurrent", pathway_id=path.id, purpose="initial", target_task_id=tasks[0].id
    )
    db_session.rollback()

    def save():
        with Session(db_session.get_bind()) as session:
            actor = session.get(User, identity)
            barrier.wait(timeout=10)
            return CurriculumService(session).start(actor, payload).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(save) for _ in range(2)]
        receipts = [future.result(timeout=40) for future in futures]
    assert receipts[0] == receipts[1]
    assert db_session.scalar(select(func.count()).select_from(DiagnosticSession)) == 1
