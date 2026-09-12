"""Bound the model hydration work used inside continuation writer transactions."""

import pytest
from sqlalchemy import delete, event, select, update
from test_learner_model import _seed_scope, _service, _store_evidence, _update_command

from app.domain.platform_enums import EvidenceLinkRelation, EvidenceType
from app.models.learner_model import LearnerModelEvidenceLink, LearnerOutcomeEstimate
from app.models.learning_evidence import LearningEvidence
from app.services.learner_model.contracts import LearnerModelEvidenceSignal
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_model.safety import LearnerModelSafetyError


@pytest.mark.parametrize("operation", ["current", "timeline"])
def test_model_view_joins_evidence_scope_without_loading_unused_metadata(db_session, operation):
    scope = _seed_scope(db_session)
    for identity, kind in (
        ("prediction", EvidenceType.PREDICTION),
        ("reason", EvidenceType.REASONING),
    ):
        _store_evidence(db_session, scope, evidence_id=identity, evidence_type=kind)
        _service(db_session).update(
            _update_command(
                scope,
                (
                    LearnerModelEvidenceSignal(
                        evidence_id=identity, relation=EvidenceLinkRelation.SUPPORTS
                    ),
                ),
            )
        )
    repository = SqlAlchemyLearnerModelRepository(db_session)
    arguments = dict(
        course_id=scope["course_one"],
        learner_id=scope["learner_id"],
        outcome_id=scope["outcome_one"],
    )
    expected = getattr(repository, operation)(**arguments)
    db_session.expunge_all()
    statements = []

    def observe(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", observe)
    try:
        actual = getattr(repository, operation)(**arguments)
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    assert actual == expected
    views = (actual,) if operation == "current" else actual
    assert views[-1].record_version == 2
    assert {
        identity for estimate in views[-1].estimates for identity, _ in estimate.evidence_links
    } == {"prediction", "reason"}
    assert len(statements) <= 3, f"Model hydration executed {len(statements)} statements"
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert not any("learning_evidence.content_digest" in statement for statement in statements)


@pytest.mark.parametrize("operation", ["current", "timeline"])
@pytest.mark.parametrize("corruption", ["missing_link", "missing_evidence", "wrong_scope"])
def test_model_view_preserves_invalid_join_rows_for_rejection(db_session, operation, corruption):
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session, scope, evidence_id="prediction", evidence_type=EvidenceType.PREDICTION
    )
    _service(db_session).update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    if corruption == "missing_link":
        estimate_id = db_session.scalar(select(LearnerOutcomeEstimate.id))
        db_session.execute(
            delete(LearnerModelEvidenceLink).where(
                LearnerModelEvidenceLink.estimate_id == estimate_id
            )
        )
        message = "estimate is incomplete"
    elif corruption == "wrong_scope":
        db_session.execute(update(LearningEvidence).values(course_id=scope["course_two"]))
        message = "evidence link is out of scope"
    else:
        # This isolated synthetic database deliberately models a damaged import.
        db_session.commit()
        with db_session.get_bind().connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.execute(delete(LearningEvidence))
            connection.commit()
        message = "evidence link is out of scope"
    db_session.commit()
    db_session.expunge_all()
    with pytest.raises(LearnerModelSafetyError, match=message):
        getattr(SqlAlchemyLearnerModelRepository(db_session), operation)(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )


@pytest.mark.parametrize("operation", ["current", "timeline"])
@pytest.mark.parametrize("column", ["evidence_type", "occurred_at"])
def test_model_view_still_rejects_invalid_typed_evidence_metadata(db_session, operation, column):
    scope = _seed_scope(db_session)
    _store_evidence(
        db_session, scope, evidence_id="prediction", evidence_type=EvidenceType.PREDICTION
    )
    _service(db_session).update(
        _update_command(
            scope,
            (
                LearnerModelEvidenceSignal(
                    evidence_id="prediction", relation=EvidenceLinkRelation.SUPPORTS
                ),
            ),
        )
    )
    db_session.commit()
    with db_session.get_bind().connect() as connection:
        connection.exec_driver_sql("PRAGMA ignore_check_constraints=ON")
        connection.exec_driver_sql(f"UPDATE learning_evidence SET {column} = 'invalid'")
        connection.commit()
    db_session.expunge_all()
    with pytest.raises((LookupError, ValueError)):
        getattr(SqlAlchemyLearnerModelRepository(db_session), operation)(
            course_id=scope["course_one"],
            learner_id=scope["learner_id"],
            outcome_id=scope["outcome_one"],
        )
