"""Schema and migration proof for Person B append-only evidence storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app import models  # noqa: F401
from app.db.base import Base
from app.models.learning_evidence import EvidenceArtifact, EvidenceLink, LearningEvidence
from scripts.verify_sqlite_backup import create_verified_backup, database_manifest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
NEW_TABLES = {"evidence_artifacts", "learning_evidence", "evidence_links"}


def migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _seed_evidence_scope(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                "VALUES ('evidence-owner@example.edu', 'hash', 'Evidence Owner', 'educator', 1), "
                "('evidence-learner@example.edu', 'hash', 'Evidence Learner', 'student', 1)"
            )
        )
        owner_id = connection.execute(
            text("SELECT id FROM users WHERE email = 'evidence-owner@example.edu'")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO courses (id, educator_id, code, title, description, state, "
                "enrollment_open, created_at, updated_at) VALUES "
                "('evidence-course', :owner, 'EVD101', 'Evidence course', '', 'draft', 1, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"owner": owner_id},
        )
        connection.execute(
            text(
                "INSERT INTO course_modules (id, course_id, title, description, position, created_at, updated_at) "
                "VALUES ('evidence-module', 'evidence-course', 'Evidence module', '', 1, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO learning_outcomes (id, module_id, title, statement, kind, week_number, position, created_at, updated_at) "
                "VALUES ('evidence-outcome', 'evidence-module', 'Evidence outcome', 'Explain evidence.', "
                "'weekly', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO learning_tasks (id, slug, title, module, description, instructions, task_type, difficulty, points, position, course_id, module_id, learning_outcome_id) "
                "VALUES ('evidence-task', 'evidence-task', 'Evidence task', 'Evidence module', '', '', "
                "'short_answer', 'introductory', 0, 1, 'evidence-course', 'evidence-module', 'evidence-outcome')"
            )
        )


def _insert_evidence_rows(engine: Engine) -> None:
    digest = "sha256:" + "a" * 64
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        learner_id = connection.execute(
            text("SELECT id FROM users WHERE email = 'evidence-learner@example.edu'")
        ).scalar_one()
        values = {"learner_id": learner_id, "digest": digest}
        connection.execute(
            text(
                "INSERT INTO evidence_artifacts "
                "(id, course_id, learner_id, content, content_digest, content_format, schema_version, "
                "record_version, actor_reference, agent_reference, correlation_id, occurred_at) "
                "VALUES ('evidence-artifact', 'evidence-course', :learner_id, 'protected answer', :digest, "
                "'plain-text.v1', 'evidence-artifact.v1', 1, 'learner', NULL, 'corr-1', CURRENT_TIMESTAMP)"
            ),
            values,
        )
        connection.execute(
            text(
                "INSERT INTO learning_evidence "
                "(id, artifact_id, course_id, learner_id, outcome_id, activity_id, task_id, response_version_id, "
                "source_interaction_id, source_version, task_conditions_version, evidence_type, provenance, "
                "observation_type, instructional_support_level, access_support_state, content_digest, actor_reference, "
                "agent_reference, correlation_id, schema_version, record_version, idempotency_key, occurred_at) "
                "VALUES ('evidence-one', 'evidence-artifact', 'evidence-course', :learner_id, 'evidence-outcome', "
                "'activity-1', 'evidence-task', 'response-1', 'source-1', 'source.v1', 1, 'REASONING', "
                "'LEARNER', 'DIRECT', 0, 'PROVIDED', :digest, 'learner', NULL, 'corr-1', 'evidence-record.v1', "
                "1, 'evidence-key-1', CURRENT_TIMESTAMP), "
                "('evidence-two', NULL, 'evidence-course', :learner_id, 'evidence-outcome', 'activity-1', "
                "'evidence-task', NULL, NULL, NULL, NULL, 'REFLECTION', 'LEARNER', 'SELF_REPORTED', 1, "
                "'NOT_DECLARED', :digest, 'learner', NULL, 'corr-1', 'evidence-record.v1', 1, 'evidence-key-2', "
                "CURRENT_TIMESTAMP)"
            ),
            values,
        )
        connection.execute(
            text(
                "INSERT INTO evidence_links "
                "(id, evidence_id, linked_evidence_id, relation, actor_reference, correlation_id, occurred_at) "
                "VALUES ('evidence-link', 'evidence-one', 'evidence-two', 'SUPPORTS', 'learner', 'corr-1', CURRENT_TIMESTAMP)"
            )
        )


def test_evidence_models_define_only_platform_evidence_records() -> None:
    tables = Base.metadata.tables

    assert NEW_TABLES.issubset(tables)
    assert {"score", "grade", "result"}.isdisjoint(tables["learning_evidence"].columns.keys())
    assert "content" not in tables["learning_evidence"].columns
    assert "learner_id" in tables["learning_evidence"].columns
    assert "content" in tables["evidence_artifacts"].columns
    assert EvidenceArtifact.__tablename__ == "evidence_artifacts"
    assert LearningEvidence.__tablename__ == "learning_evidence"
    assert EvidenceLink.__tablename__ == "evidence_links"


def test_evidence_migration_is_append_only_and_preserves_legacy_records(tmp_path: Path) -> None:
    database_path = tmp_path / "evidence-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260815_0018")
    engine = create_engine(database_url)
    try:
        _seed_evidence_scope(engine)
    finally:
        engine.dispose()

    before_manifest = database_manifest(database_path)
    legacy_manifest = {
        name: verification
        for name, verification in before_manifest.items()
        if name != "alembic_version"
    }
    backup = create_verified_backup(database_path, tmp_path / "backup")
    assert backup.record_count == sum(item.row_count for item in before_manifest.values())

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    clean_head_backup = create_verified_backup(database_path, tmp_path / "clean-head-backup")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert NEW_TABLES.issubset(inspector.get_table_names())
        assert {
            name: database_manifest(database_path)[name] for name in legacy_manifest
        } == legacy_manifest
        _insert_evidence_rows(engine)
        with engine.connect() as connection:
            trigger_names = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                        "AND tbl_name IN ('evidence_artifacts', 'learning_evidence', 'evidence_links')"
                    )
                ).scalars()
            )
        assert trigger_names == {
            "trg_evidence_artifacts_append_only_update",
            "trg_evidence_artifacts_append_only_delete",
            "trg_learning_evidence_append_only_update",
            "trg_learning_evidence_append_only_delete",
            "trg_evidence_links_append_only_update",
            "trg_evidence_links_append_only_delete",
        }
        append_only_operations = (
            "UPDATE evidence_artifacts SET content = 'changed' WHERE id = 'evidence-artifact'",
            "UPDATE learning_evidence SET activity_id = 'changed' WHERE id = 'evidence-one'",
            "UPDATE evidence_links SET correlation_id = 'changed' WHERE id = 'evidence-link'",
            "DELETE FROM evidence_artifacts WHERE id = 'evidence-artifact'",
            "DELETE FROM learning_evidence WHERE id = 'evidence-one'",
            "DELETE FROM evidence_links WHERE id = 'evidence-link'",
        )
        for statement in append_only_operations:
            with pytest.raises(IntegrityError, match="append-only"):
                with engine.begin() as connection:
                    connection.execute(text(statement))
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys=ON"))
                connection.execute(
                    text(
                        "INSERT INTO learning_evidence "
                        "(id, course_id, learner_id, outcome_id, activity_id, task_id, evidence_type, provenance, "
                        "observation_type, instructional_support_level, access_support_state, content_digest, "
                        "actor_reference, correlation_id, schema_version, record_version, idempotency_key, occurred_at) "
                        "SELECT 'duplicate-evidence', course_id, learner_id, outcome_id, activity_id, task_id, "
                        "evidence_type, provenance, observation_type, instructional_support_level, access_support_state, "
                        "content_digest, actor_reference, correlation_id, schema_version, record_version, "
                        "idempotency_key, CURRENT_TIMESTAMP FROM learning_evidence WHERE id = 'evidence-one'"
                    )
                )
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO learning_evidence "
                        "(id, course_id, learner_id, outcome_id, activity_id, task_id, evidence_type, provenance, "
                        "observation_type, instructional_support_level, access_support_state, content_digest, "
                        "actor_reference, correlation_id, schema_version, record_version, idempotency_key, occurred_at) "
                        "VALUES ('broken-fk', 'missing-course', 1, 'evidence-outcome', 'activity', 'evidence-task', "
                        "'REASONING', 'LEARNER', 'DIRECT', 0, 'NOT_DECLARED', 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
                        "'learner', 'corr', 'evidence-record.v1', 1, 'broken-key', CURRENT_TIMESTAMP)"
                    )
                )
        before_failed_downgrade = database_manifest(database_path)
        with pytest.raises(RuntimeError, match="cannot downgrade populated"):
            command.downgrade(config, "20260815_0018")
        assert database_manifest(database_path) == before_failed_downgrade
    finally:
        engine.dispose()

    with sqlite3.connect(clean_head_backup.backup_path) as source_connection:
        with sqlite3.connect(database_path) as restored_connection:
            source_connection.backup(restored_connection)
    command.downgrade(config, "20260815_0018")
    downgraded_engine = create_engine(database_url)
    try:
        assert NEW_TABLES.isdisjoint(inspect(downgraded_engine).get_table_names())
        after_downgrade = database_manifest(database_path)
        assert {name: after_downgrade[name] for name in legacy_manifest} == legacy_manifest
    finally:
        downgraded_engine.dispose()
