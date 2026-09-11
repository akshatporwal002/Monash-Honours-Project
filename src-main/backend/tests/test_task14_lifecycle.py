"""Task 14 lifecycle against real task review and form publication."""

from dataclasses import replace

import pytest
from sqlalchemy import select
from support.alignment import next_action_contract
from support.task_review import approve_fixture_task, bootstrap_reviewed_demo
from test_assessment_definitions import _draft, _service, _setup

from app.domain.assessment import BloomProcess
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

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def setup_episode(
    session, task_type=TaskType.QUANTUM_CIRCUIT, *, prediction_required=True, support_modes=()
):
    course_id, outcome_id, owner_id, outcome_version_id = _setup(session)
    task = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    plan = EpisodePlanV1(
        support_representations=tuple(
            {
                "instructional_support_level": 4
                if mode == "worked_example"
                else 3
                if mode == "stepwise"
                else 2,
                "mode": mode,
                "title": f"Synthetic {mode} support",
                "text": "Use the supplied source to inspect the input and describe the operation.",
                "steps": ["Inspect the input", "Describe the operation"],
                "circuit": {"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]}
                if mode == "circuit"
                else None,
                "source_references": task.source_references,
                "equivalence_basis": "Synthetic test representation of the same approved conceptual support.",
            }
            for mode in support_modes
        ),
        prediction_required=prediction_required,
        transfer={
            "prompt": "SYNTHETIC PRIVATE fresh Hadamard application",
            "starter_circuit": {"qubits": 1, "operations": []},
            "solution": {"answer": "NEVER REVEAL solution"},
        },
        supported_hints=("Consider how H changes the input state.",),
        accessibility_support=("Text circuit and keyboard controls",),
    )
    task.task_type = task_type
    task.marking_criteria = {
        "required_gates": ["h"],
        "starter_circuit": {"qubits": 1, "operations": []},
        "episode_plan": plan.model_dump(mode="json"),
    }
    session.commit()
    approve_fixture_task(session, task)
    draft = replace(
        _draft(outcome_version_id=outcome_version_id, task_id=task.id, task_processes=["APPLY"]),
        formal_result_eligible=True,
        bloom_process=BloomProcess.APPLY,
        claim="Apply a Hadamard circuit through prediction, explanation, and fresh application.",
    )
    criteria = [
        replace(
            draft.criteria[0],
            stable_key=key,
            learner_description=description,
            evidence_description=description,
        )
        for key, description in (
            ("prediction", "Predict the circuit outcome."),
            ("explanation", "Explain the circuit outcome."),
            ("application", "Apply the circuit in a fresh context."),
        )
    ]
    draft = replace(
        draft,
        criteria=criteria,
        next_action_contract=next_action_contract(*(c.stable_key for c in criteria)),
        pass_rule_expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion": criterion.stable_key} for criterion in criteria],
        },
        instructional_support={"supported_stage": "unlimited approved conceptual hints"},
        transfer_rule={"required": True, "independence": "unaided fresh application"},
    )
    service = _service(session)
    definition = service.create_draft(
        course_id=course_id, learning_outcome_id=outcome_id, actor_user_id=owner_id, draft=draft
    )
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    assert form.constraints["episode_plan"] == plan.model_dump(mode="json")
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
    assert not hasattr(submitted, "score")
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("answer", "Changed answer"),
        ("code", "x(0)"),
        ("circuit", {"qubits": 1, "operations": [{"gate": "x", "targets": [0]}]}),
    ],
)
def test_checkpoint_rejects_changed_input_in_draft_entry_submit_and_reader(
    db_session, field, value
):
    from sqlalchemy.orm.attributes import set_committed_value

    from app.services.episode_contract import FrozenResponseInvalid
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    changed = payload.model_copy(update={field: value})
    for operation in (lms.save_draft, lms.episode_transfer):
        with pytest.raises(TaskReviewError, match="checkpoint input has changed"):
            operation(student, task.id, changed)
        db_session.rollback()
    with pytest.raises(TaskReviewError, match="checkpoint input has changed"):
        lms.submit(
            student, task.id, SubmissionCreate(**changed.model_dump(), idempotency_key="changed")
        )
    db_session.rollback()
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="valid")
    )
    reference = assessment_reference(db_session, first.id)
    response = db_session.get(SubmissionAttempt, first.id)
    set_committed_value(response, field, value)
    set_committed_value(
        response,
        "content_digest",
        canonical_response_digest(
            content=ResponseContent(
                answer=response.answer, code=response.code, circuit=response.circuit
            ),
            episode=payload.episode,
            schema_version=response.response_schema_version,
            assessment_work_start_id=response.assessment_work_start_id,
            task_form_version_id=response.task_form_version_id,
            declared_conditions=response.declared_conditions,
        ),
    )
    with pytest.raises(FrozenResponseInvalid, match="checkpoint input has changed"):
        SqlAlchemyFrozenResponseReader(db_session).read(assessment=reference)
    db_session.expire(response)
    raw = changed.episode.model_dump(mode="json")
    raw["supported"]["prediction_checkpoint_id"] = None
    raw["supported"]["simulation_references"] = []
    editable = changed.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    lms.save_draft(student, task.id, editable)
    replacement = lms.episode_checkpoint(student, task.id, editable, "supported", None)
    assert replacement["checkpoint_id"] != payload.episode.supported.prediction_checkpoint_id


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
    from support.migration_assertions import protected_history_manifest
    from test_migrations import migration_config

    path = tmp_path / "episodes.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with Session(engine) as session:
        lms, student, task, started = setup_episode(session)
        from app.schemas.episode import EpisodeHelpUseWrite

        lms.episode_help_use(
            student,
            task.id,
            EpisodeHelpUseWrite(
                assessment_work_start_id=started.assessment_work_start_id,
                kind="conceptual_hint",
                item_index=0,
                request_key="migrated-hint",
            ),
        )
        payload = complete(lms, student, task, started)
        lms.submit(
            student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="migrated")
        )
        original = list(session.execute(text("SELECT * FROM episode_checkpoints")).mappings())
        original_help = list(session.execute(text("SELECT * FROM episode_help_uses")).mappings())
    command.stamp(config, "20260907_0029")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            list(connection.execute(text("SELECT * FROM episode_checkpoints")).mappings())
            == original
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            list(connection.execute(text("SELECT * FROM episode_help_uses")).mappings())
            == original_help
        )
    for statement in (
        "UPDATE episode_checkpoints SET prediction='{}'",
        "DELETE FROM episode_stage_starts",
        "INSERT OR REPLACE INTO episode_checkpoints SELECT * FROM episode_checkpoints",
        "UPDATE episode_help_uses SET item_index=1",
        "DELETE FROM episode_help_uses",
        "INSERT OR REPLACE INTO episode_help_uses SELECT * FROM episode_help_uses",
    ):
        with pytest.raises(IntegrityError, match="protected"):
            with engine.begin() as connection:
                connection.execute(text(statement))
    before_downgrade = protected_history_manifest(path)
    with pytest.raises(RuntimeError, match="history is protected"):
        command.downgrade(config, "20260907_0029")
    assert protected_history_manifest(path) == before_downgrade
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "20260911_0054"
        )
        assert inspect(connection).has_table("episode_checkpoints")
        assert (
            list(connection.execute(text("SELECT * FROM episode_help_uses")).mappings())
            == original_help
        )
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


def test_reader_contract_preserves_historical_condition_list(db_session):
    from app.schemas.episode import FrozenResponseRead
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    attempt = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="condition-list")
    )
    frozen = SqlAlchemyFrozenResponseReader(db_session).read(
        assessment=assessment_reference(db_session, attempt.id)
    )
    historical = frozen.model_copy(update={"declared_conditions": [{"access": "  preserved\n"}]})
    assert FrozenResponseRead.model_validate_json(
        historical.model_dump_json()
    ).declared_conditions == [{"access": "  preserved\n"}]


def test_migration_accepts_every_new_type_and_preserves_reviewed_history(tmp_path):
    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from support.assessment import build_assessment_blueprint
    from test_migrations import migration_config

    from app.models.task_review import TaskReviewEvent, TaskRevision
    from app.services.task_review import snapshot_digest, task_snapshot

    path = tmp_path / "preexisting.db"
    url = f"sqlite:///{path.as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "20260907_0029")
    engine = create_engine(url)
    with Session(engine) as session:
        _, _, _, _, form, owner = build_assessment_blueprint(session)
        task = session.get(LearningTask, form.learning_task_id)
        course_id, outcome_id, owner_id = task.course_id, task.learning_outcome_id, owner.id
        snapshot = task_snapshot(session, task)
        revision = TaskRevision(
            task_id=task.id,
            course_id=course_id,
            version=1,
            snapshot=snapshot,
            content_digest=snapshot_digest(snapshot),
            provenance="AUTHORED",
            actor_user_id=owner_id,
        )
        session.add(revision)
        session.flush()
        for version, state in enumerate(("SUBMITTED", "APPROVED"), start=1):
            session.add(
                TaskReviewEvent(
                    task_revision_id=revision.id,
                    course_id=course_id,
                    version=version,
                    state=state,
                    actor_user_id=owner_id,
                    reason="Historical migration fixture review",
                )
            )
            session.flush()
        session.commit()
        task_id = task.id
        before = dict(
            session.execute(text("SELECT * FROM learning_tasks WHERE id=:id"), {"id": task_id})
            .mappings()
            .one()
        )
        review = list(session.execute(text("SELECT * FROM task_revisions")).mappings())
        triggers = list(
            session.execute(
                text("SELECT name,sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
            )
        )
    command.upgrade(config, "20260907_0030")
    with engine.begin() as connection:
        assert (
            dict(
                connection.execute(
                    text("SELECT * FROM learning_tasks WHERE id=:id"), {"id": task_id}
                )
                .mappings()
                .one()
            )
            == before
        )
        assert list(connection.execute(text("SELECT * FROM task_revisions")).mappings()) == review
        for kind in (
            "prediction",
            "reasoning",
            "explanation",
            "revision",
            "reflection",
            "transfer",
        ):
            connection.execute(
                text(
                    "INSERT INTO learning_tasks (id,slug,title,module,description,instructions,expected_answer,task_type,difficulty,points,position,source_references,prerequisite_task_ids,course_id,module_id,learning_outcome_id) VALUES (:kind,:kind,'Typed task','Module','Prompt','Instructions','Answer',:kind,'beginner',0,:position,'[]','[]',:course_id,:module_id,:learning_outcome_id)"
                ),
                {
                    "kind": kind,
                    "position": 10 + len(kind),
                    "course_id": course_id,
                    "module_id": before["module_id"],
                    "learning_outcome_id": outcome_id,
                },
            )
        after = dict(
            connection.execute(
                text("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
            ).all()
        )
        assert all(after[name] == sql for name, sql in triggers)
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    with pytest.raises(RuntimeError, match="protected"):
        command.downgrade(config, "20260907_0029")
    engine.dispose()


@pytest.mark.parametrize(
    "task_type",
    [
        TaskType.PREDICTION,
        TaskType.REASONING,
        TaskType.EXPLANATION,
        TaskType.REVISION,
        TaskType.REFLECTION,
        TaskType.TRANSFER,
    ],
)
def test_every_supported_type_roundtrips_and_revises(db_session, task_type):
    lms, student, task, started = setup_episode(db_session, task_type)
    payload = complete(lms, student, task, started)
    saved = lms.save_draft(student, task.id, payload)
    assert lms.get_draft(student, task.id).episode == saved.episode
    first = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key="first-typed")
    )
    changed = payload.episode.model_dump(mode="json")
    changed["supported"]["revision"] = {
        "previous_response_version_id": first.id,
        "reason": "  Refined my reasoning\n",
    }
    changed["supported"]["reflection"] = "  Reflection after submitting\n"
    revised = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(changed)})
    second = lms.submit(
        student, task.id, SubmissionCreate(**revised.model_dump(), idempotency_key="second-typed")
    )
    assert second.episode == revised.episode
    assert not hasattr(second, "score")
    assert db_session.get(SubmissionAttempt, first.id).episode == payload.episode.model_dump(
        mode="json"
    )


def test_interrupted_run_recovery_and_invalid_input_keep_work(db_session):
    from datetime import UTC, datetime, timedelta

    from pydantic import ValidationError

    from app.services.quantum import CircuitOperation
    from app.services.simulation_evidence import SimulationEvidenceService

    lms, student, task, started = setup_episode(db_session)
    checkpoint = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    before = lms.get_draft(student, task.id)
    with pytest.raises(ValidationError):
        SimulationRequest(task_id=task.id, qubits=1, operations=[{"gate": "h", "targets": [3]}])
    now = datetime.now(UTC)
    service = SimulationEvidenceService(db_session, now=lambda: now)
    run_id, _ = service.prepare(
        owner_id=student.id,
        task_id=task.id,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        prediction_checkpoint_id=checkpoint["checkpoint_id"],
    )
    recovered = SimulationEvidenceService(db_session, now=lambda: now + timedelta(minutes=2))
    assert recovered.recover_expired() == 1
    assert recovered.read(run_id)["status"] == "interrupted"
    assert recovered.recover_expired() == 0
    assert lms.get_draft(student, task.id) == before
    assert db_session.scalar(select(SubmissionAttempt)) is None


def test_uncheckpointed_run_is_not_revealed_through_direct_or_list_reads(db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.simulation import SimulationRun
    from app.services.quantum import CircuitOperation
    from app.services.simulation_evidence import SimulationEvidenceService

    lms, student, task, started = setup_episode(db_session)
    checkpoint = lms.episode_checkpoint(student, task.id, supported(started), "supported", None)
    run_id, _ = SimulationEvidenceService(db_session).prepare(
        owner_id=student.id,
        task_id=task.id,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        prediction_checkpoint_id=checkpoint["checkpoint_id"],
    )
    actual = db_session.get(SimulationRun, run_id)
    old = SimulationRun(
        id="old-run",
        owner_id=student.id,
        request_key="old-key",
        circuit_version_id=actual.circuit_version_id,
        purpose="task",
        shots=1024,
        seed=42,
        policy_version=actual.policy_version,
        engine_versions=actual.engine_versions,
        created_at=datetime.now(UTC),
        deadline_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    db_session.add(old)
    db_session.commit()
    with pytest.raises(TaskReviewError, match="prediction"):
        lms.read_simulation(student, old.id)
    with pytest.raises(TaskReviewError, match="prediction"):
        lms.list_student_simulations(student, task.id, 10)
    from fastapi import HTTPException

    from app.domain.platform_enums import EvidenceType
    from app.services.evidence.live import LiveEvidenceCapture
    from app.services.progress_evidence import read_progress_evidence

    evidence_id = LiveEvidenceCapture(db_session)._write(
        task=task,
        learner_id=student.id,
        source=old.id,
        field="simulation",
        kind=EvidenceType.SIMULATION,
        value={"result": {"probabilities": {"0": 0.5, "1": 0.5}}},
        occurred_at=old.created_at,
    )
    db_session.commit()
    with pytest.raises(HTTPException, match="prediction"):
        read_progress_evidence(db_session, student, task.course_id, evidence_id)


def test_checkpoint_history_preserves_changed_prediction_and_denies_wrong_shots(db_session):

    lms, student, task, started = setup_episode(db_session)
    payload = supported(started)
    first = lms.episode_checkpoint(student, task.id, payload, "supported", None)
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["prediction"] = {"answer": "  A changed prediction for changed input\n"}
    changed = payload.model_copy(
        update={
            "episode": EpisodePayloadV1.model_validate(raw),
            "circuit": {"qubits": 1, "operations": [{"gate": "x", "targets": [0]}]},
        }
    )
    second = lms.episode_checkpoint(student, task.id, changed, "supported", None)
    assert first["checkpoint_id"] != second["checkpoint_id"]
    history = lms.episode_checkpoint_history(student, task.id)
    assert [item["prediction"]["answer"] for item in history["items"]] == [
        "  A changed prediction for changed input\n",
        "  Half zero, half one\n",
    ]
    from app.schemas.episode import EpisodeCheckpointPage
    from app.schemas.lms import EpisodeCheckpointReceipt
    from app.services.lms import LmsServiceError

    assert EpisodeCheckpointReceipt.model_validate(second).draft.episode == second["draft"].episode
    page = EpisodeCheckpointPage.model_validate(
        lms.episode_checkpoint_history(student, task.id, limit=1)
    )
    assert page.next_offset == 1
    older = EpisodeCheckpointPage.model_validate(
        lms.episode_checkpoint_history(student, task.id, limit=1, offset=page.next_offset)
    )
    assert older.next_offset is None
    assert older.items[0].prediction.answer == "  Half zero, half one\n"
    for limit, offset in ((0, 0), (101, 0), (20, -1)):
        with pytest.raises(LmsServiceError, match="Invalid prediction history"):
            lms.episode_checkpoint_history(student, task.id, limit=limit, offset=offset)
    with pytest.raises(TaskReviewError, match="exact circuit"):
        lms.simulate_student_circuit(
            student,
            SimulationRequest(
                task_id=task.id,
                qubits=1,
                operations=[{"gate": "x", "targets": [0]}],
                prediction_checkpoint_id=second["checkpoint_id"],
                shots=512,
            ),
        )
    db_session.rollback()
    assert (
        lms.get_draft(student, task.id).episode.supported.prediction_checkpoint_id
        == second["checkpoint_id"]
    )


def test_episode_routes_have_safe_typed_responses_and_bounded_history(db_session):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies.roles import require_student
    from app.api.routes.lms import get_lms_service, router

    lms, student, task, started = setup_episode(db_session)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_student] = lambda: student
    app.dependency_overrides[get_lms_service] = lambda: lms
    with TestClient(app) as client:
        base = f"/students/me/tasks/{task.id}/episode"
        initial = client.get(base)
        assert initial.status_code == 200
        assert "PRIVATE" not in initial.text
        payload = supported(started)
        receipt = client.post(
            base + "/checkpoints",
            json={"response": payload.model_dump(mode="json"), "part_id": "supported"},
        )
        assert receipt.status_code == 200
        assert (
            receipt.json()["draft"]["episode"]["supported"]["prediction"]["answer"]
            == "  Half zero, half one\n"
        )
        assert client.get(base + "/checkpoints?limit=1").json()["next_offset"] is None
        for query in ("limit=0", "limit=101", "offset=-1"):
            assert client.get(base + "/checkpoints?" + query).status_code == 422
        schema = app.openapi()
        for path, method in (
            ("", "get"),
            ("/checkpoints", "get"),
            ("/checkpoints", "post"),
            ("/transfer", "post"),
        ):
            response = schema["paths"]["/students/me/tasks/{task_id}/episode" + path][method][
                "responses"
            ]["200"]["content"]["application/json"]["schema"]
            assert response
        transfer_schema = schema["components"]["schemas"]["EpisodeTransferRead"]
        assert "solution" not in transfer_schema["properties"]


@pytest.mark.parametrize(
    "task_type",
    [
        TaskType.PREDICTION,
        TaskType.REASONING,
        TaskType.EXPLANATION,
        TaskType.REVISION,
        TaskType.REFLECTION,
        TaskType.TRANSFER,
    ],
)
def test_every_typed_episode_can_run_its_approved_fresh_circuit(db_session, task_type):
    lms, student, task, started = setup_episode(db_session, task_type)
    payload = complete(lms, student, task, started)
    raw = payload.episode.model_dump(mode="json")
    raw["transfer"]["process"]["prediction"] = {"answer": "Half each"}
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    transfer = payload.episode.transfer
    checkpoint = lms.episode_checkpoint(
        student, task.id, payload, transfer.part_id, transfer.stage_start_id
    )
    request = SimulationRequest(
        task_id=task.id,
        qubits=1,
        operations=[{"gate": "h", "targets": [0]}],
        prediction_checkpoint_id=checkpoint["checkpoint_id"],
        episode_stage_start_id=transfer.stage_start_id,
        episode_part_id=transfer.part_id,
    )
    result = lms.simulate_student_circuit(student, request)
    assert result["result"]["probabilities"] == pytest.approx({"0": 0.5, "1": 0.5})
    changed = checkpoint["draft"].model_dump(exclude={"id", "task_id", "updated_at"})
    changed["episode"]["transfer"]["content"]["circuit"]["operations"] = [
        {"gate": "x", "targets": [0]}
    ]
    with pytest.raises(TaskReviewError, match="checkpoint input has changed"):
        lms.save_draft(student, task.id, DraftWrite.model_validate(changed))
    db_session.rollback()
    with pytest.raises(TaskReviewError):
        lms.simulate_student_circuit(
            student, request.model_copy(update={"episode_stage_start_id": "foreign"})
        )


def test_foreign_revision_simulation_and_transfer_references_are_denied(db_session):
    lms, student, task, started = setup_episode(db_session)
    payload = complete(lms, student, task, started)
    lms.save_draft(student, task.id, payload)
    for field in ("stage", "simulation", "checkpoint"):
        raw = payload.episode.model_dump(mode="json")
        if field == "stage":
            raw["transfer"]["stage_start_id"] = "foreign"
        elif field == "simulation":
            raw["supported"]["simulation_references"] = [
                {"run_id": "foreign", "circuit_version_id": "foreign"}
            ]
        else:
            raw["supported"]["prediction_checkpoint_id"] = "foreign"
        with pytest.raises(TaskReviewError):
            lms.save_draft(
                student,
                task.id,
                payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)}),
            )
        db_session.rollback()
        assert lms.get_draft(student, task.id).episode == payload.episode
