"""Task 14 lifecycle against real task review and form publication."""

from dataclasses import replace

import pytest
from sqlalchemy import select
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo
from test_assessment_definitions import _draft, _service, _setup

from app.models.assessment import TaskFormVersion
from app.models.enums import TaskType
from app.models.lms import Course, CourseState, Enrollment, SubmissionAttempt
from app.models.persistence import LearningTask
from app.models.user import UserRole
from app.schemas.episode import EpisodePayloadV1, EpisodePlanV1, ResponseContent
from app.schemas.lms import DraftWrite, SubmissionCreate
from app.schemas.student import SimulationRequest
from app.services.episode_evidence import canonical_response_digest
from app.services.lms import LmsService
from app.services.task_review import TaskReviewError


def setup_episode(session):
    course_id, outcome_id, owner_id, outcome_version_id = _setup(session)
    task = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    plan = EpisodePlanV1(
        transfer={
            "prompt": "SYNTHETIC PRIVATE fresh Hadamard application",
            "starter_circuit": {"qubits": 1, "operations": []},
            "solution": {"answer": "NEVER REVEAL solution"},
        },
        supported_hints=("Consider how H changes the input state.",),
        accessibility_support=("Text circuit and keyboard controls",),
    )
    task.task_type = TaskType.QUANTUM_CIRCUIT
    task.marking_criteria = {
        "required_gates": ["h"],
        "starter_circuit": {"qubits": 1, "operations": []},
        "episode_plan": plan.model_dump(mode="json"),
    }
    session.commit()
    approve_fixture_task(session, task)
    draft = replace(
        _draft(outcome_version_id=outcome_version_id, task_id=task.id), formal_result_eligible=True
    )
    service = _service(session)
    definition = service.create_draft(
        course_id=course_id, learning_outcome_id=outcome_id, actor_user_id=owner_id, draft=draft
    )
    # Until shared publication wiring lands, explicitly freeze the reviewed plan before approval.
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    if "episode_plan" not in form.constraints:
        form.constraints = {**form.constraints, "episode_plan": plan.model_dump(mode="json")}
        session.commit()
    service.approve(
        course_id=course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="Synthetic episode approved for this test",
    )
    users, _ = bootstrap_reviewed_demo(session)
    student = next(u for u in users if u.role is UserRole.STUDENT)
    session.get(Course, course_id).state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course_id, student_id=student.id))
    session.commit()
    lms = LmsService(session)
    started = lms.start_assessment_work(student, task.id, form.id)
    return lms, student, task, started


def supported(started):
    return DraftWrite(
        assessment_work_start_id=started.assessment_work_start_id,
        answer="  Supported answer\n",
        circuit={"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]},
        episode=EpisodePayloadV1(
            supported={
                "prediction": {"answer": "  Half zero, half one\n"},
                "reasoning": "  H changes amplitudes\n",
                "explanation": "  Equal outcome probabilities\n",
                "reflection": "  My first prediction held\n",
            }
        ),
    )


def complete(lms, student, task, started):
    payload = supported(started)
    checkpoint = lms.episode_checkpoint(student, task.id, payload, "supported", None)
    payload = DraftWrite.model_validate(
        checkpoint["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    )
    state = lms.episode_transfer(student, task.id, payload)
    assert "NEVER REVEAL" not in str(state)
    transfer = state["transfer"]
    raw = payload.episode.model_dump(mode="json")
    raw["transfer"] = {
        "stage_start_id": transfer["stage_start_id"],
        "part_id": transfer["part_id"],
        "content": {
            "answer": "  Fresh application\n",
            "code": "  h(0)\n",
            "circuit": {"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]},
        },
        "process": {
            "reasoning": " Fresh reasoning\n",
            "explanation": " Fresh explanation\n",
            "reflection": " Fresh reflection\n",
        },
    }
    return payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})


def test_episode_full_roundtrip_and_retry(db_session):
    lms, student, task, started = setup_episode(db_session)
    assert "PRIVATE" not in str(lms.episode_state(student, task.id))
    payload = complete(lms, student, task, started)
    lms.save_draft(student, task.id, payload)
    assert lms.get_draft(student, task.id).episode == payload.episode
    submitted = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="episode-response"),
    )
    assert submitted.episode == payload.episode
    assert submitted.score is None
    assert (
        lms.submit(
            student,
            task.id,
            SubmissionCreate(**payload.model_dump(), idempotency_key="episode-response"),
        ).id
        == submitted.id
    )
    response = db_session.get(SubmissionAttempt, submitted.id)
    assert response.response_schema_version == "assessment.response.v2"


def test_checkpoint_reveal_and_changed_circuit(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = supported(started)
    with pytest.raises(TaskReviewError, match="prediction"):
        lms.simulate_student_circuit(
            student,
            SimulationRequest(
                task_id=task.id, qubits=1, operations=[{"gate": "h", "targets": [0]}]
            ),
        )
    db_session.rollback()
    saved = lms.episode_checkpoint(student, task.id, payload, "supported", None)
    with pytest.raises(TaskReviewError, match="exact circuit"):
        lms.simulate_student_circuit(
            student,
            SimulationRequest(
                task_id=task.id,
                qubits=1,
                operations=[{"gate": "x", "targets": [0]}],
                prediction_checkpoint_id=saved["checkpoint_id"],
            ),
        )
    db_session.rollback()
    assert lms.get_draft(student, task.id).answer == payload.answer
    assert db_session.scalar(select(SubmissionAttempt)) is None


def test_invalid_revision_keeps_saved_work(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    lms.save_draft(student, task.id, payload)
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["revision"] = {"previous_response_version_id": "unknown", "reason": "Reason"}
    with pytest.raises(TaskReviewError, match="earlier response"):
        lms.save_draft(
            student,
            task.id,
            payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)}),
        )
    db_session.rollback()
    assert lms.get_draft(student, task.id).episode == payload.episode


@pytest.mark.parametrize("change", ["episode", "work", "form", "conditions"])
def test_digest_binds_episode_and_frozen_references(change):
    args = dict(
        content=ResponseContent(answer=" text\n"),
        episode=EpisodePayloadV1(supported={"reasoning": "reason"}),
        schema_version="assessment.response.v2",
        assessment_work_start_id="work",
        task_form_version_id="form",
        declared_conditions={"tools": []},
    )
    first = canonical_response_digest(**args)
    if change == "episode":
        args["episode"] = EpisodePayloadV1(supported={"reasoning": "changed"})
    elif change == "work":
        args["assessment_work_start_id"] = "other"
    elif change == "form":
        args["task_form_version_id"] = "other"
    else:
        args["declared_conditions"] = {"tools": ["other"]}
    assert canonical_response_digest(**args) != first


def assessment_reference(session, response_id):
    from app.models.assessment import (
        AssessmentAttempt,
        AssessmentDefinitionVersion,
        BloomTargetVersion,
        OutcomeVersion,
        PassRuleVersion,
    )
    from app.schemas.assessment import AssessmentVersionReference

    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response_id)
    )
    definition = session.get(AssessmentDefinitionVersion, attempt.assessment_definition_version_id)
    form = session.get(TaskFormVersion, attempt.task_form_version_id)
    bloom = session.get(BloomTargetVersion, attempt.bloom_target_version_id)
    rule = session.get(PassRuleVersion, attempt.pass_rule_version_id)
    outcome = session.get(OutcomeVersion, definition.outcome_version_id)
    return AssessmentVersionReference(
        course_id=attempt.course_id,
        assessment_definition_id=definition.assessment_definition_id,
        assessment_definition_version=definition.version,
        outcome_id=outcome.learning_outcome_id,
        outcome_version=outcome.version,
        bloom_target_id=bloom.bloom_target_id,
        bloom_target_version=bloom.version,
        criterion_set_id=definition.assessment_definition_id,
        criterion_set_version=definition.version,
        pass_rule_id=rule.pass_rule_id,
        pass_rule_version=rule.version,
        task_id=attempt.task_id,
        task_form_version=form.version,
        assessment_attempt_id=attempt.id,
        response_version_id=response_id,
    )


def test_reader_lossless_read_only_revision_history_and_digest(db_session):
    from sqlalchemy import event

    from app.services.episode_contract import FrozenResponseInvalid, FrozenResponseStale
    from app.services.episode_evidence import export_response_snapshot, extract_response_evidence
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="reader-first")
    )
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["revision"] = {
        "previous_response_version_id": first.id,
        "reason": "  More precise explanation\n",
    }
    raw["supported"]["reflection"] = "  Reflection after submission\n"
    second_payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    second = lms.submit(
        student,
        task.id,
        SubmissionCreate(**second_payload.model_dump(), idempotency_key="reader-second"),
    )
    reference = assessment_reference(db_session, first.id)
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(db_session.get_bind(), "before_cursor_execute", observe)
    try:
        frozen = SqlAlchemyFrozenResponseReader(db_session).read(assessment=reference)
        second_frozen = SqlAlchemyFrozenResponseReader(db_session).read(
            assessment=assessment_reference(db_session, second.id)
        )
    finally:
        event.remove(db_session.get_bind(), "before_cursor_execute", observe)
    assert set(statements) <= {"SELECT"}
    assert frozen.episode == payload.episode
    assert second_frozen.episode.supported.revision.previous_response_version_id == first.id
    assert extract_response_evidence(frozen) == export_response_snapshot(frozen)
    assert export_response_snapshot(frozen)["content"]["answer"] == "  Supported answer\n"
    with pytest.raises(FrozenResponseStale):
        SqlAlchemyFrozenResponseReader(db_session).read(
            assessment=reference.model_copy(update={"task_form_version": 99})
        )
    response = db_session.get(SubmissionAttempt, first.id)
    from sqlalchemy.orm.attributes import set_committed_value

    set_committed_value(response, "answer", "tampered")
    with pytest.raises(FrozenResponseInvalid, match="digest"):
        SqlAlchemyFrozenResponseReader(db_session).read(assessment=reference)
    db_session.expire(response)


def test_reader_preserves_historical_v1(db_session):
    from test_assessment_work_starts import setup_work

    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    student, task, form, *_ = setup_work(db_session)
    lms = LmsService(db_session)
    started = lms.start_assessment_work(student, task.id, form.id)
    attempt = lms.submit(
        student,
        task.id,
        SubmissionCreate(
            answer="  historical response\n",
            assessment_work_start_id=started.assessment_work_start_id,
            idempotency_key="v1",
        ),
    )
    frozen = SqlAlchemyFrozenResponseReader(db_session).read(
        assessment=assessment_reference(db_session, attempt.id)
    )
    assert frozen.episode is None
    assert frozen.content.answer == "  historical response\n"
    assert frozen.reference.schema_version == "assessment.response.v1"


def test_real_migration_history_replay_and_rollback(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from test_migrations import migration_config

    path = tmp_path / "episodes.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with Session(engine) as session:
        lms, student, task, started = setup_episode(session)
        payload = complete(lms, student, task, started)
        lms.submit(
            student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="migrated")
        )
        original = list(session.execute(text("SELECT * FROM episode_checkpoints")).mappings())
    command.stamp(config, "20260907_0029")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            list(connection.execute(text("SELECT * FROM episode_checkpoints")).mappings())
            == original
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    for statement in (
        "UPDATE episode_checkpoints SET prediction='{}'",
        "DELETE FROM episode_stage_starts",
        "INSERT OR REPLACE INTO episode_checkpoints SELECT * FROM episode_checkpoints",
    ):
        with pytest.raises(IntegrityError, match="protected"):
            with engine.begin() as connection:
                connection.execute(text(statement))
    with pytest.raises(RuntimeError, match="protected"):
        command.downgrade(config, "20260907_0029")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260907_0030"
        )
        assert inspect(connection).has_table("episode_checkpoints")
    engine.dispose()


@pytest.mark.parametrize("error_code", ["simulation_timeout", "simulation_failed"])
def test_controlled_failure_preserves_prediction_and_work(db_session, error_code):
    from app.services.quantum import CircuitOperation, QuantumSimulationError
    from app.services.simulation_evidence import SimulationEvidenceService

    lms, student, task, started = setup_episode(db_session)
    payload = supported(started)
    checkpoint = lms.episode_checkpoint(student, task.id, payload, "supported", None)

    def fails(**kwargs):
        raise QuantumSimulationError("Controlled technical fault", code=error_code)

    run = SimulationEvidenceService(db_session, executor=fails).execute(
        owner_id=student.id,
        task_id=task.id,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        prediction_checkpoint_id=checkpoint["checkpoint_id"],
    )
    assert run["status"] in {"failed", "timed_out"}
    assert lms.read_simulation(student, run["run_id"])["result"] is None
    assert lms.list_student_simulations(student, task.id, 10)[0]["run_id"] == run["run_id"]
    assert (
        lms.get_draft(student, task.id).episode.supported.prediction
        == payload.episode.supported.prediction
    )
    assert db_session.scalar(select(SubmissionAttempt)) is None
