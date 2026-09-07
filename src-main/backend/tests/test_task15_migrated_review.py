"""Task 15 acceptance through real episode persistence and migrated constraints."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from alembic import command
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session
from test_migrations import migration_config
from test_task14_lifecycle import complete, setup_episode

from app.domain.assessment import CriterionDecision
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentEvaluationJob,
    AssessmentEvaluationJobState,
    CriterionEvaluation,
)
from app.models.human_assessment import HumanAssessmentAction
from app.models.user import User
from app.schemas.episode import EpisodePayloadV1
from app.schemas.lms import SubmissionCreate
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.human_review import (
    HumanAssessmentRequest,
    HumanAssessmentService,
    HumanCriterionInput,
)
from app.services.assessment.jobs import SqlAlchemyAssessmentEvaluationJobRepository
from app.services.assessment.review import AssessmentReviewConflictError
from app.services.episode_responses import SqlAlchemyFrozenResponseReader


@pytest.fixture
def migrated(tmp_path):
    url = f"sqlite:///{(tmp_path / 'human.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_engine(url, connect_args={"timeout": 10})
    with Session(engine) as session:
        yield session, config
    engine.dispose()


def setup_human(session, *, revision=False, simulation_status=None):
    from support.assessment import assign_assessor

    from app.models.lms import Course

    lms, student, task, started = setup_episode(session)
    payload = complete(lms, student, task, started)
    if simulation_status:
        from app.models.simulation import SimulationRun
        from app.services.quantum import CircuitOperation
        from app.services.simulation_evidence import SimulationEvidenceService

        simulations = SimulationEvidenceService(session)
        run_id, _ = simulations.prepare(
            owner_id=student.id,
            task_id=task.id,
            qubits=1,
            operations=[CircuitOperation("h", (0,))],
            shots=1024,
            seed=42,
            prediction_checkpoint_id=payload.episode.supported.prediction_checkpoint_id,
        )
        if simulation_status == "completed":
            simulations.finish(run_id, status="completed", result={"counts": {"0": 512, "1": 512}})
        elif simulation_status == "timed_out":
            simulations.finish(run_id, status="timed_out", error_code="simulation_timeout")
        run = session.get(SimulationRun, run_id)
        raw = payload.episode.model_dump(mode="json")
        raw["supported"]["simulation_references"] = [
            {"run_id": run_id, "circuit_version_id": run.circuit_version_id}
        ]
        payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    first = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="human-episode-first"),
    )
    response_id = first.id
    if revision:
        raw = payload.episode.model_dump(mode="json")
        raw["supported"]["revision"] = {
            "previous_response_version_id": first.id,
            "reason": "A clearer explanation",
        }
        raw["supported"]["simulation_references"] = []
        revised = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
        response_id = lms.submit(
            student,
            task.id,
            SubmissionCreate(**revised.model_dump(), idempotency_key="human-episode-second"),
        ).id
    owner = session.get(User, session.get(Course, task.course_id).educator_id)
    if not RoleAssignmentService(session).list_active_assignments(owner.id):
        assign_assessor(session, owner, task.course_id, owner)
    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response_id)
    )
    service = make_service(session)
    return service, owner, attempt, first.id


def make_service(session):
    return HumanAssessmentService(
        session,
        assignments=RoleAssignmentService(session),
        reader=SqlAlchemyFrozenResponseReader(session),
    )


def request(service, actor, attempt_id, *, key="human-record", decision=CriterionDecision.MET):
    detail = service.detail(actor, assessment_attempt_id=attempt_id)
    return HumanAssessmentRequest(
        idempotency_key=key,
        expected_token=detail["expected_token"],
        reason="Inspected supported and independent work against each approved criterion.",
        criteria=tuple(
            HumanCriterionInput(
                row["criterion_version_id"],
                decision,
                "Evidence is present in the supported explanation and fresh transfer response.",
                (detail["response"].reference.evidence_id,),
            )
            for row in detail["criteria"]
        ),
    )


def test_real_episode_review_is_lossless_read_only_and_confirmed(migrated):
    session, config = migrated
    service, actor, attempt, original_id = setup_human(session, revision=True)
    statements = []

    def observe(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(session.get_bind(), "before_cursor_execute", observe)
    try:
        detail = service.detail(actor, assessment_attempt_id=attempt.id)
    finally:
        event.remove(session.get_bind(), "before_cursor_execute", observe)
    assert set(statements) == {"SELECT"}
    assert detail["response"].episode.supported.prediction.answer == "  Half zero, half one\n"
    assert detail["response"].episode.transfer.content.code == "  h(0)\n"
    assert detail["response_history"][0].reference.evidence_id == original_id
    assert detail["response_history"][0].reference.assessment.response_version_id == original_id
    action = service.finalise(
        actor, assessment_attempt_id=attempt.id, request=request(service, actor, attempt.id)
    )
    assert action["result_state"] == "CONFIRMED" and action["result"] == "PASS"
    before = list(session.execute(text("SELECT * FROM human_criterion_decisions")).mappings())
    session.commit()
    command.stamp(config, "20260907_0030")
    command.upgrade(config, "head")
    assert (
        list(session.execute(text("SELECT * FROM human_criterion_decisions")).mappings()) == before
    )
    for statement in [
        "UPDATE human_criterion_decisions SET reason='changed'",
        "DELETE FROM human_assessment_actions",
        "INSERT OR REPLACE INTO human_assessment_actions SELECT * FROM human_assessment_actions",
    ]:
        with pytest.raises(Exception, match="append-only|Invalid human assessment action scope"):
            session.execute(text(statement))
        session.rollback()
    with pytest.raises(RuntimeError, match="protected"):
        command.downgrade(config, "20260907_0030")
    assert (
        session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        == "20260907_0031"
    )
    assert session.execute(text("PRAGMA foreign_key_check")).all() == []


def test_two_assessor_actions_use_one_migrated_revision(migrated):
    session, _ = migrated
    service, actor, attempt, _ = setup_human(session)
    payload = request(service, actor, attempt.id)
    actor_id, attempt_id = actor.id, attempt.id
    session.commit()
    barrier = Barrier(2)

    def run(key):
        with Session(session.get_bind()) as other:
            human = make_service(other)
            user = other.get(User, actor_id)
            barrier.wait(timeout=10)
            try:
                return human.finalise(
                    user,
                    assessment_attempt_id=attempt_id,
                    request=replace(payload, idempotency_key=key),
                )
            except AssessmentReviewConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ["assessor-race-a", "assessor-race-b"]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("conflict") == 1
    assert len(session.scalars(select(HumanAssessmentAction)).all()) == 1
    assert len(session.scalars(select(AssessmentDecision)).all()) == 1


def test_human_claim_fences_an_expired_worker(migrated):
    session, _ = migrated
    service, actor, attempt, response_id = setup_human(session)
    repo = SqlAlchemyAssessmentEvaluationJobRepository(session)
    claim = repo.claim_for_response(
        response_id,
        now=datetime.now(UTC) - timedelta(minutes=10),
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=5),
        execution_token="00000000-0000-4000-8000-000000000321",
    )
    assert claim is not None
    service.finalise(
        actor, assessment_attempt_id=attempt.id, request=request(service, actor, attempt.id)
    )
    assert not repo.complete(claim, completed_at=datetime.now(UTC))
    assert (
        session.get(AssessmentEvaluationJob, attempt.id).state
        is AssessmentEvaluationJobState.COMPLETED
    )
    assert len(session.scalars(select(AssessmentDecision)).all()) == 1
    assert session.scalar(select(CriterionEvaluation)) is None


@pytest.mark.parametrize("status", ["completed", "pending", "timed_out"])
def test_real_simulation_inputs_and_faults_are_read_without_recovery_writes(migrated, status):
    from support.assessment import assign_assessor

    from app.models.lms import Course
    from app.models.simulation import SimulationOutcome
    from app.services.quantum import CircuitOperation
    from app.services.simulation_evidence import SimulationEvidenceService

    session, _ = migrated
    lms, student, task, started = setup_episode(session)
    payload = complete(lms, student, task, started)
    simulations = SimulationEvidenceService(session)
    run_id, _ = simulations.prepare(
        owner_id=student.id,
        task_id=task.id,
        qubits=1,
        operations=[CircuitOperation("h", (0,))],
        shots=1024,
        seed=42,
        prediction_checkpoint_id=payload.episode.supported.prediction_checkpoint_id,
    )
    if status == "completed":
        simulations.finish(
            run_id,
            status="completed",
            result={"counts": {"0": 32, "1": 32}, "probabilities": {"0": 0.5, "1": 0.5}},
        )
    elif status == "timed_out":
        simulations.finish(run_id, status="timed_out", error_code="simulation_timeout")
    from app.models.simulation import SimulationRun

    run = session.get(SimulationRun, run_id)
    raw = payload.episode.model_dump(mode="json")
    raw["supported"]["simulation_references"] = [
        {"run_id": run_id, "circuit_version_id": run.circuit_version_id}
    ]
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    response = lms.submit(
        student, task.id, SubmissionCreate(**payload.model_dump(), idempotency_key=f"sim-{status}")
    )
    actor = session.get(User, session.get(Course, task.course_id).educator_id)
    if not RoleAssignmentService(session).list_active_assignments(actor.id):
        assign_assessor(session, actor, task.course_id, actor)
    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response.id)
    )
    human = make_service(session)
    detail = human.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["simulations"][0]["shots"] == 1024
    assert detail["simulations"][0]["seed"] == 42
    assert detail["simulations"][0]["status"] == status
    assert (
        detail["simulations"][0]["prediction_checkpoint_id"]
        == payload.episode.supported.prediction_checkpoint_id
    )
    assert bool(session.get(SimulationOutcome, run_id)) == (status != "pending")
    if status == "completed":
        assert detail["can_finalise"]
    else:
        assert not detail["can_finalise"]
        with pytest.raises(AssessmentReviewConflictError, match="technical fault"):
            human.finalise(
                actor, assessment_attempt_id=attempt.id, request=request(human, actor, attempt.id)
            )
    assert session.scalar(select(AssessmentDecision)) is None


def test_authorised_review_uses_intact_submitted_standard_after_new_rule(migrated):
    from app.models.assessment import AssessmentApprovalState, PassRuleVersion
    from app.services.assessment.evaluation import AssessmentEvaluationConflictError
    from app.services.assessment.runtime import build_assessment_evaluation_service

    session, _ = migrated
    human, actor, attempt, _ = setup_human(session)
    rule = session.get(PassRuleVersion, attempt.pass_rule_version_id)
    session.add(
        PassRuleVersion(
            course_id=rule.course_id,
            pass_rule_id=rule.pass_rule_id,
            assessment_definition_version_id=rule.assessment_definition_version_id,
            version=rule.version + 1,
            owner_user_id=actor.id,
            created_by_user_id=actor.id,
            expression=rule.expression,
            approval_state=AssessmentApprovalState.APPROVED,
            approved_at=datetime.now(UTC),
            approved_by_user_id=actor.id,
        )
    )
    session.commit()
    with pytest.raises(AssessmentEvaluationConflictError, match="pass rule changed"):
        build_assessment_evaluation_service(session, attempt.id).evaluate(
            assessment_attempt_id=attempt.id, evaluation_idempotency_key="newer-rule-auto"
        )
    detail = human.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["response"].reference.assessment.pass_rule_version == rule.version
    receipt = human.finalise(
        actor, assessment_attempt_id=attempt.id, request=request(human, actor, attempt.id)
    )
    decision = session.get(AssessmentDecision, receipt["decision_id"])
    assert decision.pass_rule_version_id == rule.id
    assert decision.result == "PASS"


@pytest.mark.parametrize("status", ["completed", "pending", "timed_out"])
def test_earlier_response_keeps_its_own_simulation_evidence(migrated, status):
    session, _ = migrated
    human, actor, attempt, original_id = setup_human(
        session, revision=True, simulation_status=status
    )
    detail = human.detail(actor, assessment_attempt_id=attempt.id)
    assert detail["simulations"] == ()
    earlier = detail["historical_evidence"][0]
    assert earlier.response_version_id == original_id
    assert earlier.response.reference.assessment.response_version_id == original_id
    run = earlier.simulations[0]
    assert run["shots"] == 1024 and run["seed"] == 42
    assert run["circuit"] == {"qubits": 1, "operations": [{"gate": "h", "targets": [0]}]}
    assert run["status"] == status
    assert bool(earlier.issues) == (status != "completed")
    assert detail["can_finalise"]
    if status == "completed":
        assert run["result"]["counts"] == {"0": 512, "1": 512}
        human.finalise(
            actor, assessment_attempt_id=attempt.id, request=request(human, actor, attempt.id)
        )
        from app.services.assessment.review import AssessmentReviewService

        review = AssessmentReviewService(
            session,
            assignments=RoleAssignmentService(session),
            reader=SqlAlchemyFrozenResponseReader(session),
        )
        detail_after = review.get_detail(
            actor, decision_id=session.scalar(select(AssessmentDecision)).id
        )
        assert detail_after.historical_evidence[0].simulations[0]["run_id"] == run["run_id"]


def test_assessor_context_uses_reviewed_revision_and_frozen_outcome(migrated):
    from app.models.assessment import (
        AssessmentDefinitionVersion,
        OutcomeVersion,
        PassRuleVersion,
        TaskFormVersion,
    )
    from app.models.lms import LearningOutcome
    from app.models.persistence import LearningTask
    from app.models.task_review import TaskRevision

    session, _ = migrated
    human, actor, attempt, _ = setup_human(session)
    form = session.get(TaskFormVersion, attempt.task_form_version_id)
    revision = session.get(TaskRevision, form.task_revision_id)
    definition = session.get(AssessmentDefinitionVersion, attempt.assessment_definition_version_id)
    outcome = session.get(OutcomeVersion, definition.outcome_version_id)
    session.get(
        LearningTask, attempt.task_id
    ).description = "Later mutable question that must not replace frozen evidence"
    session.get(LearningOutcome, outcome.learning_outcome_id).statement = "Later mutable outcome"
    session.commit()
    context = human.detail(actor, assessment_attempt_id=attempt.id)["frozen_context"]
    assert context.task_revision_id == revision.id
    assert context.supported_prompt == revision.snapshot["description"]
    assert context.supported_instructions == revision.snapshot["instructions"]
    assert context.transfer_prompt == "SYNTHETIC PRIVATE fresh Hadamard application"
    assert context.outcome_statement == outcome.statement
    assert context.bloom_process and context.knowledge_dimension
    assert (
        context.pass_rule_expression
        == session.get(PassRuleVersion, attempt.pass_rule_version_id).expression
    )
