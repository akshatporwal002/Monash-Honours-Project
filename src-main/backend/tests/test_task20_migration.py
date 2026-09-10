"""Migration boundaries for learner-owned preference history."""

from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from test_migrations import migration_config


def test_empty_learner_preference_history_can_downgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'empty-preferences.db').as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")

    command.downgrade(config, "20260908_0032")

    engine = create_engine(database_url)
    try:
        assert "learner_preference_revisions" not in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "20260908_0032"
            )
    finally:
        engine.dispose()


def test_populated_learner_preference_history_blocks_downgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'populated-preferences.db').as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            learner_id = connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) VALUES ('preference-migration@example.test', 'unused', 'Preference Learner', 'student', 1) RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO learner_preference_revisions (id, learner_id, revision, pace, format, explanation_detail, optional_breaks_enabled, repeat_practice_enabled, personalisation_enabled, schema_version, actor_reference, correlation_id, idempotency_key, occurred_at, created_at) VALUES ('preference-revision-1', :learner_id, 1, 'DEFAULT', 'NO_PREFERENCE', 'STANDARD', 0, 0, 1, 'learnlens.learner-preferences.v1', :actor, 'migration-correlation', 'migration-key', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"learner_id": learner_id, "actor": str(learner_id)},
            )

        with pytest.raises(RuntimeError, match="history is protected"):
            command.downgrade(config, "20260908_0032")

        assert "learner_preference_revisions" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "20260910_0044"
            )
    finally:
        engine.dispose()
