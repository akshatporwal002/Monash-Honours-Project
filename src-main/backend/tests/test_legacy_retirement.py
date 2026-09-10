"""Real populated migration and failure recovery for D-10 retirement."""

import importlib
import json

import pytest
from alembic import command
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from support.assessment import build_assessment_attempt
from support.migration_assertions import protected_history_manifest
from test_migrations import _prepare_legacy_assessment_database, migration_config

from scripts.verify_sqlite_backup import database_manifest


def _populated(tmp_path):
    path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "20260910_0043")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with Session(engine) as session:
        build_assessment_attempt(session, suffix="-retirement")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO student_profiles (id,display_name,points,streak_days) VALUES ('retire-profile','Archived learner',0,0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO student_submissions (id,student_id,task_id,answer,status,score,attempts) VALUES ('retire-response','retire-profile',(SELECT id FROM learning_tasks ORDER BY id LIMIT 1),'Original practice answer','completed',0,1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO system_settings (id,key,value,description,updated_at) VALUES ('retired-passing','passing_score','70','Legacy threshold',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO system_settings (id,key,value,description,updated_at) VALUES ('retired-risk','at_risk_threshold','60','Legacy threshold',CURRENT_TIMESTAMP)"
            )
        )
    return path, config, engine


def test_populated_retirement_preserves_every_original_row_and_guards_history(tmp_path):
    path, config, engine = _populated(tmp_path)
    before = database_manifest(path)
    with engine.connect() as connection:
        originals = {
            table: [
                dict(row) for row in connection.exec_driver_sql(f"SELECT * FROM {table}").mappings()
            ]
            for table in ("submission_attempts", "student_submissions", "system_settings")
        }
    command.upgrade(config, "head")
    after = database_manifest(path)
    for table in before.keys() - {
        "alembic_version",
        "submission_attempts",
        "student_submissions",
        "system_settings",
        "legacy_numeric_history",
    }:
        assert before[table] == after[table], table
    with engine.connect() as connection:
        for table, records in originals.items():
            archived = {
                key: json.loads(record)
                for key, record in connection.execute(
                    text(
                        "SELECT source_record_id,source_record FROM legacy_numeric_history WHERE source_table=:table"
                    ),
                    {"table": table},
                )
            }
            assert archived == {str(record["id"]): record for record in records}
        assert not connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        for table in ("submission_attempts", "student_submissions"):
            assert "score" not in {
                column["name"] for column in inspect(connection).get_columns(table)
            }
        assert (
            connection.exec_driver_sql(
                "SELECT COUNT(*) FROM system_settings WHERE key IN ('passing_score','at_risk_threshold')"
            ).scalar_one()
            == 0
        )
        for statement in (
            "DELETE FROM legacy_numeric_history",
            "UPDATE legacy_numeric_history SET policy_version='changed'",
            "INSERT OR REPLACE INTO legacy_numeric_history SELECT * FROM legacy_numeric_history",
            "DELETE FROM submission_attempts",
            "UPDATE submission_attempts SET answer='changed'",
        ):
            with pytest.raises(Exception, match="immutable|protected|modified|append-only"):
                connection.exec_driver_sql(statement)
            connection.rollback()
    snapshot = database_manifest(path)
    command.upgrade(config, "head")
    assert database_manifest(path) == snapshot
    command.stamp(config, "20260910_0043")
    command.upgrade(config, "head")
    assert database_manifest(path) == snapshot
    protected_snapshot = protected_history_manifest(path)
    with pytest.raises(RuntimeError, match="history is protected"):
        command.downgrade(config, "20260910_0043")
    # Additive empty extensions may downgrade before the older protected step refuses.
    # Verify every retained record immediately, then restore the exact head manifest.
    assert protected_history_manifest(path) == protected_snapshot
    command.upgrade(config, "head")
    assert database_manifest(path) == snapshot
    engine.dispose()


def test_replay_keeps_new_unscored_work_and_original_archive(tmp_path):
    path, config, engine = _populated(tmp_path)
    command.upgrade(config, "head")
    with Session(engine) as session:
        build_assessment_attempt(session, suffix="-after-retirement")
    before = database_manifest(path)
    command.stamp(config, "20260910_0043")
    command.upgrade(config, "head")
    assert database_manifest(path) == before
    engine.dispose()


def test_failure_after_first_rebuild_rolls_back_schema_archive_and_triggers(tmp_path, monkeypatch):
    path, _, engine = _populated(tmp_path)
    before = database_manifest(path)
    migration = importlib.import_module("migrations.versions.20260910_0044_legacy_score_retirement")
    rebuild = migration._rebuild

    def interrupted(connection, table, ddl, columns):
        if table == "student_submissions":
            raise RuntimeError("Injected migration interruption")
        return rebuild(connection, table, ddl, columns)

    monkeypatch.setattr(migration, "_rebuild", interrupted)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"transactional_ddl": True})
        with context.begin_transaction():
            with Operations.context(context), pytest.raises(RuntimeError, match="Injected"):
                migration.upgrade()
    assert database_manifest(path) == before
    with engine.connect() as connection:
        assert "score" in {
            column["name"] for column in inspect(connection).get_columns("submission_attempts")
        }
        with pytest.raises(Exception, match="immutable|protected|modified|append-only"):
            connection.exec_driver_sql("DELETE FROM submission_attempts")
    engine.dispose()


def test_empty_retirement_round_trip_keeps_one_head(tmp_path):
    config = migration_config(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    command.upgrade(config, "head")
    command.downgrade(config, "20260910_0043")
    command.upgrade(config, "head")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all() == ["20260910_0046"]
    engine.dispose()
