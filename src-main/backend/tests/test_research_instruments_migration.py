"""Forward migration, immutable history, and withdrawal restore with synthetic data."""

from pathlib import Path

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from test_migrations import migration_config
from test_research_governance import governed as governed
from test_research_instruments import collect
from test_research_instruments import instruments as instruments

from app.services.research.governance import GovernanceDenied
from app.services.research.instruments import ResearchInstrumentService
from scripts.verify_sqlite_backup import create_verified_backup, database_manifest


def test_instrument_forward_replay_and_guarded_downgrade(tmp_path):
    path = tmp_path / "synthetic-instruments.db"
    config = migration_config(f"sqlite:///{path.as_posix()}")
    assert ScriptDirectory.from_config(config).get_heads() == ["20260911_0055"]
    command.upgrade(config, "20260910_0045")
    before = database_manifest(path)
    command.upgrade(config, "20260910_0046")
    after = database_manifest(path)
    assert all(after[key] == value for key, value in before.items() if key != "alembic_version")
    command.stamp(config, "20260910_0045")
    command.upgrade(config, "20260910_0046")
    assert database_manifest(path) == after
    command.downgrade(config, "20260910_0045")
    command.upgrade(config, "20260910_0046")
    engine = create_engine(config.get_main_option("sqlalchemy.url"))
    with engine.begin() as connection:
        # Sentinel rows test append-only persistence, not an instrument approval.
        connection.execute(
            text(
                "INSERT INTO users (id,email,password_hash,full_name,role) VALUES (100,'synthetic@example.invalid','unused','Synthetic','administrator')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO courses (id,code,title,description,educator_id,state,enrollment_open,created_at,updated_at,time_zone) VALUES ('synthetic-course','synthetic','Synthetic','',100,'draft',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'UTC')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO research_governance_events (id,study_id,revision,actor_user_id,request_key,kind,command,recorded_at) VALUES ('synthetic-scope','synthetic',1,100,'synthetic','scope','{}',CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO research_instrument_forms (id,study_id,course_id,scope_id,instrument_key,version,definition,content_digest,actor_user_id,request_key,request_digest,recorded_at) VALUES ('synthetic-form','synthetic','synthetic-course','synthetic-scope','synthetic',1,'{}','synthetic-sentinel',100,'synthetic','synthetic-sentinel',CURRENT_TIMESTAMP)"
            )
        )
    populated = database_manifest(path)
    with pytest.raises(RuntimeError, match="populated"):
        command.downgrade(config, "20260910_0045")
    assert database_manifest(path) == populated
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert "research_instrument_records" in inspect(connection).get_table_names()
    engine.dispose()
    command.upgrade(config, "head")
    command.check(config)


def test_restore_preserves_instrument_withdrawal_and_no_operational_changes(instruments, tmp_path):
    g = instruments
    path = Path(g.session.get_bind().url.database)
    before = database_manifest(path)
    receipt = collect(g)
    g.record(
        g.consent.model_copy(update={"decision": "withdrawn", "fields": [], "purposes": []}),
        g.student.id,
    )
    after = database_manifest(path)
    excluded = {"restricted_instrument_evidence"}
    for table in before:
        if not table.startswith("research_") and table not in excluded:
            assert before[table] == after[table]
    restored = create_verified_backup(path, tmp_path / "restored.db").backup_path
    engine = create_engine(f"sqlite:///{restored.as_posix()}")
    with Session(engine) as session:
        service = ResearchInstrumentService(session, now=lambda: g.now)
        with pytest.raises(GovernanceDenied, match="consent_inactive"):
            service.read(g.educator.id, g.study, g.course.id, receipt.id, ["instrument.stage"])
    engine.dispose()
