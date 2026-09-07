"""Task 15 deterministic dispatch consumes real frozen stage content."""

from types import SimpleNamespace

import pytest
from test_task14_lifecycle import assessment_reference, complete, setup_episode

from app.domain.assessment import BloomProcess, CriterionDecision
from app.models.assessment import CriterionEvaluatorType
from app.schemas.episode import EpisodePayloadV1
from app.schemas.lms import SubmissionCreate
from app.services.assessment.evaluation import CriterionEvaluationUnavailableError
from app.services.assessment.runtime import SqlAlchemyRuleCriterionEvaluationPort


def stage_response(session, *, circuit):
    lms, student, task, started = setup_episode(session)
    payload = complete(lms, student, task, started)
    raw = payload.episode.model_dump(mode="json")
    raw["transfer"]["content"]["circuit"] = circuit
    payload = payload.model_copy(update={"episode": EpisodePayloadV1.model_validate(raw)})
    response = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="circuit-dispatch"),
    )
    return assessment_reference(session, response.id), response.answer


def criterion(stage="supported", evaluator=CriterionEvaluatorType.RULES):
    # Approved settings are exercised through real publication in the separate
    # coordinator-owned authoring API tests. This port test isolates dispatch.
    return SimpleNamespace(
        evaluator_type=evaluator,
        critical_error_rules={},
        evidence_source_types=["learner_response"],
        approved_anchors={
            "kind": "circuit_v1",
            "stage": stage,
            "qubits": 1,
            "operations": [{"gate": "h", "targets": [0]}],
        },
    )


def test_dispatch_uses_the_declared_supported_or_fresh_stage(db_session):
    reference, answer = stage_response(
        db_session,
        circuit={
            "qubits": 1,
            "operations": [{"gate": "x", "targets": [0]}],
            "shots": 64,
            "seed": 1,
        },
    )
    port = SqlAlchemyRuleCriterionEvaluationPort(db_session)
    supported = port.evaluate(
        assessment=reference,
        response_text=answer,
        bloom_process=BloomProcess.APPLY,
        criterion=criterion(),
    )
    transfer = port.evaluate(
        assessment=reference,
        response_text=answer,
        bloom_process=BloomProcess.APPLY,
        criterion=criterion("transfer"),
    )
    assert supported.decision is CriterionDecision.MET
    assert transfer.decision is CriterionDecision.NOT_MET
    assert supported.evidence[0].assessment == reference
    assert supported.evaluator_reference == "rules.circuit-structure.v1"


@pytest.mark.parametrize(
    "circuit", [None, {"qubits": 1, "operations": [{"gate": "z", "targets": [0]}]}]
)
def test_missing_or_unsupported_fresh_circuit_goes_to_human(db_session, circuit):
    reference, answer = stage_response(db_session, circuit=circuit)
    with pytest.raises(CriterionEvaluationUnavailableError):
        SqlAlchemyRuleCriterionEvaluationPort(db_session).evaluate(
            assessment=reference,
            response_text=answer,
            bloom_process=BloomProcess.APPLY,
            criterion=criterion("transfer"),
        )


@pytest.mark.parametrize(
    "evaluator",
    [
        CriterionEvaluatorType.MIXED,
        CriterionEvaluatorType.HUMAN,
        CriterionEvaluatorType.VALIDATED_AI,
    ],
)
def test_human_mixed_and_ai_criteria_never_become_automatic_decisions(db_session, evaluator):
    reference, answer = stage_response(db_session, circuit=None)
    with pytest.raises(CriterionEvaluationUnavailableError, match="human or validated"):
        SqlAlchemyRuleCriterionEvaluationPort(db_session).evaluate(
            assessment=reference,
            response_text=answer,
            bloom_process=BloomProcess.APPLY,
            criterion=criterion(evaluator=evaluator),
        )
