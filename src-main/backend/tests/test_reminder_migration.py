import importlib
from datetime import timedelta

import pytest
from alembic import command
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_migrations import migration_config
from test_reminder_controls import NOW, context

from app.core.readiness import MIGRATION_HEAD
from app.schemas.reminders import DeadlineArrangementWrite, ReminderPreferenceWrite
from app.services.reminders import ReminderService
from scripts.learning_backup import create_bundle, restore_bundle, verify_bundle


def test_migrated_controls_restore_with_history_and_refuse_destructive_rollback(tmp_path):
    database = tmp_path / "migrated.db"
    config = migration_config(f"sqlite:///{database.as_posix()}")
    command.upgrade(config, "head")
    command.check(config)
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    try:
        with Session(engine) as session:
            student, task, owner = context(session)
            service = ReminderService(session, now=NOW)
            service.save_preference(
                student.id,
                ReminderPreferenceWrite(
                    expected_revision=0,
                    idempotency_key="preference",
                    enabled=False,
                ),
            )
            service.save_arrangement(
                owner,
                student.id,
                task.id,
                DeadlineArrangementWrite(
                    expected_revision=0,
                    idempotency_key="extension",
                    kind="EXTENSION",
                    time_zone="UTC",
                    local_due_at=(NOW + timedelta(days=3)).replace(tzinfo=None),
                    reason="Approved scheduling change",
                    learner_notice="Your deadline has been extended.",
                ),
            )
        # Demo URL materials have no stored upload bytes. The complete database, including
        # assessment/task history and the new controls, must still survive isolated restoration.
        uploads = tmp_path / "uploads"
        uploads.mkdir()
        bundle = create_bundle(database, uploads, tmp_path / "backups")
        assert verify_bundle(bundle)["database"]["migration_head"] == MIGRATION_HEAD
        restored = restore_bundle(bundle, tmp_path / "restored")
        restored_engine = create_engine(f"sqlite:///{(restored / 'database.sqlite3').as_posix()}")
        try:
            with restored_engine.begin() as connection:
                assert connection.scalar(text("SELECT count(*) FROM deadline_arrangements")) == 1
                with pytest.raises(IntegrityError, match="immutable"):
                    connection.execute(text("UPDATE deadline_arrangements SET reason='changed'"))
        finally:
            restored_engine.dispose()
        # Isolate the reminder guard before testing the current release's refusal.
        migration = importlib.import_module("migrations.versions.20260909_0039_reminder_controls")
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            with Operations.context(migration_context):
                with pytest.raises(
                    RuntimeError, match="cannot downgrade populated deadline_arrangements"
                ):
                    migration.downgrade()
        with pytest.raises(RuntimeError, match="Intake history is protected"):
            command.downgrade(config, "20260909_0038")
        command.upgrade(config, "head")
        command.check(config)
        with engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version")) == MIGRATION_HEAD
            )
            assert connection.scalar(text("SELECT count(*) FROM deadline_arrangements")) == 1
            with pytest.raises(IntegrityError, match="immutable"):
                connection.execute(text("UPDATE deadline_arrangements SET reason='changed'"))
    finally:
        engine.dispose()


def test_empty_reminder_migration_round_trip_preserves_prior_schema_data(tmp_path):
    config = migration_config(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    command.upgrade(config, "20260909_0039")
    command.downgrade(config, "20260909_0038")
    command.upgrade(config, "head")
    command.check(config)
