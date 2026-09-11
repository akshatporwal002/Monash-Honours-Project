import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt, build_provisional_decision
from test_migrations import migration_config

from scripts.verify_sqlite_backup import database_manifest


def test_structured_type_upgrade_preserves_reviewed_history_and_rejects_unknown_types(tmp_path):
    path = tmp_path / "structured.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "20260910_0046")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with Session(engine) as session:
        # Seed actual pre-scanner schema without invoking today's publication API.
        attempt, _, _, _, owner = build_assessment_attempt(session)
        decision = build_provisional_decision(session, attempt)
        session.execute(
            text(
                "INSERT INTO assessor_reviews "
                "(id, assessment_decision_id, review_revision, assessor_user_id, action, "
                "prior_result, new_result, reason, reviewed_at) VALUES "
                "('structured-history-review', :decision, 1, :owner, 'RETURN', NULL, NULL, "
                "'Retained synthetic human review.', CURRENT_TIMESTAMP)"
            ),
            {"decision": decision.id, "owner": owner.id},
        )
        session.commit()
    historical = database_manifest(path)
    command.upgrade(config, "20260911_0049")
    before = database_manifest(path)
    assert all(
        before[key] == value for key, value in historical.items() if key != "alembic_version"
    )
    assert before["assessment_attempts"].row_count == 1
    assert before["assessor_reviews"].row_count == 1
    with engine.connect() as connection:
        triggers = connection.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
        ).all()
    engine.dispose()
    command.upgrade(config, "20260911_0050")
    after = database_manifest(path)
    assert all(after[key] == value for key, value in before.items() if key != "alembic_version")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert (
            connection.execute(
                text("SELECT name, sql FROM sqlite_master WHERE type='trigger' ORDER BY name")
            ).all()
            == triggers
        )
        for kind in ("matching", "sequencing"):
            connection.execute(text("UPDATE learning_tasks SET task_type=:kind"), {"kind": kind})
            assert (
                connection.execute(text("SELECT task_type FROM learning_tasks")).scalar_one()
                == kind
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                text("UPDATE learning_tasks SET task_type='unsupported_future_type'")
            )
        connection.rollback()
    command.stamp(config, "20260911_0049")
    command.upgrade(config, "20260911_0050")
    assert database_manifest(path) == after
    with pytest.raises(RuntimeError, match="protected"):
        command.downgrade(config, "20260910_0046")
    assert database_manifest(path) == after
    engine.dispose()
