"""New history survives additive upgrades and blocks destructive downgrades."""

import importlib

import pytest
from alembic import command
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.orm import Session
from support.migration_assertions import protected_history_manifest
from test_learner_results import context
from test_migrations import migration_config
from test_task14_lifecycle import setup_episode
from test_tutor import send

from app.db.session import create_db_engine
from app.schemas.learner_results import AppealResolutionWrite, LearnerAppealWrite
from app.services.tutor import TutorService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.mark.parametrize("history", ["tutor", "appeal"])
def test_populated_history_blocks_downgrade_without_losing_records(tmp_path, history):
    path = tmp_path / f"{history}.db"
    url = f"sqlite:///{path.as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "head")
    engine = create_db_engine(url)
    try:
        with Session(engine) as session:
            if history == "tutor":
                _, student, task, _ = setup_episode(session)
                send(TutorService(session), student, task, "migration")
            else:
                results, _, student, owner, response, _ = context(session)
                appeal = results.request_review(
                    student,
                    response.id,
                    LearnerAppealWrite(
                        reason="Explain the evidence",
                        idempotency_key="migration",
                    ),
                )
                results.resolve(
                    owner,
                    appeal.id,
                    AppealResolutionWrite(
                        expected_decision_revision=0,
                        reason="Review recorded",
                        learner_notice="Your request has been reviewed.",
                    ),
                )
        before = protected_history_manifest(path)
        # Runtime fixtures require today's schema. Probe each historical guard directly
        # so a newer unconditional downgrade refusal cannot hide a regression in it.
        revision = (
            "20260909_0035_tutor_dialogue"
            if history == "tutor"
            else "20260909_0034_appeal_resolutions"
        )
        migration = importlib.import_module(f"migrations.versions.{revision}")
        with engine.connect() as connection:
            migration_context = MigrationContext.configure(connection)
            with Operations.context(migration_context):
                with pytest.raises(RuntimeError, match="cannot downgrade populated"):
                    migration.downgrade()
        assert protected_history_manifest(path) == before
        with pytest.raises(RuntimeError, match="Feedback review history is protected"):
            command.downgrade(config, "20260908_0033")
        assert protected_history_manifest(path) == before
        command.upgrade(config, "head")
        assert protected_history_manifest(path) == before
    finally:
        engine.dispose()
