import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_assessment_definitions import _setup
from test_migrations import migration_config

from scripts.verify_sqlite_backup import database_manifest


def test_structured_type_upgrade_preserves_reviewed_history_and_rejects_unknown_types(tmp_path):
    path = tmp_path / "structured.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    command.upgrade(config, "20260910_0046")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with Session(engine) as session:
        _setup(session)
    before = database_manifest(path)
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
    command.stamp(config, "20260910_0046")
    command.upgrade(config, "20260911_0050")
    assert database_manifest(path) == after
    with pytest.raises(RuntimeError, match="protected"):
        command.downgrade(config, "20260910_0046")
    assert database_manifest(path) == after
    engine.dispose()
