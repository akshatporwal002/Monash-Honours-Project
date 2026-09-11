"""Forward/replay/restore tests use only fresh synthetic databases."""

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_migrations import migration_config
from test_research_governance import governed as governed

from app.models.research_governance import ResearchGovernanceEvent
from app.models.user import User, UserRole
from scripts.verify_sqlite_backup import create_verified_backup, database_manifest


def test_governance_forward_replay_and_populated_downgrade(tmp_path):
    path = tmp_path / "synthetic-forward.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    assert ScriptDirectory.from_config(config).get_heads() == ["20260911_0055"]
    command.upgrade(config, "20260910_0044")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with Session(engine) as session:
        user = User(
            email="synthetic-migration@example.invalid",
            full_name="Synthetic only",
            password_hash="unused",
            role=UserRole.ADMINISTRATOR,
        )
        session.add(user)
        session.commit()
        user_id = user.id
    before = database_manifest(path)
    command.upgrade(config, "20260910_0045")
    after = database_manifest(path)
    for name, manifest in before.items():
        if name != "alembic_version":
            assert after[name] == manifest
    assert after["research_governance_events"].row_count == 0
    with Session(engine) as session:
        session.add(
            ResearchGovernanceEvent(
                study_id="synthetic-history",
                revision=1,
                actor_user_id=user_id,
                request_key="synthetic-history-only",
                kind="scope",
                command={"synthetic_migration_sentinel": True},
            )
        )
        session.commit()
    populated = database_manifest(path)
    command.stamp(config, "20260910_0044")
    command.upgrade(config, "20260910_0045")
    assert database_manifest(path) == populated
    # Exercise the original populated 0045 guard before later irreversible steps.
    populated = database_manifest(path)
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(config, "20260910_0044")
    assert database_manifest(path) == populated
    with engine.begin() as connection:
        for sql in (
            "DELETE FROM research_governance_events",
            "UPDATE research_governance_events SET revision=2",
            "INSERT OR REPLACE INTO research_governance_events SELECT * FROM research_governance_events",
        ):
            with pytest.raises(IntegrityError):
                connection.execute(text(sql))
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert set(inspect(connection).get_table_names()) >= {
            "research_governance_events",
            "research_case_governance",
            "research_export_eligibility",
        }
    engine.dispose()
    command.upgrade(config, "head")
    command.check(config)


def test_restore_preserves_withdrawal_and_revocation(governed, tmp_path):
    from test_research_governed_paths import export_fixture

    from app.services.research.governance import GovernanceDenied, ResearchGovernanceService

    g = governed
    row = export_fixture(g)
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    g.record(g.grant.model_copy(update={"revoked": True}))
    source = g.session.get_bind().url.database
    restored = tmp_path / "restored-synthetic.db"
    g.session.commit()
    from pathlib import Path

    restored = create_verified_backup(Path(source), restored).backup_path
    engine = create_engine(f"sqlite:///{restored.as_posix()}")
    with Session(engine) as session:
        service = ResearchGovernanceService(session)
        with pytest.raises(GovernanceDenied, match="consent_inactive"):
            service.require_case(row.case_id)
        with pytest.raises(GovernanceDenied, match="grant_inactive"):
            service.grant(g.study, g.course.id, g.educator.id, {"case_id"})
        assert session.scalars(select(ResearchGovernanceEvent)).all()
    engine.dispose()
