from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "achievements",
    "alembic_version",
    "feedback_records",
    "judge_evaluations",
    "learning_events",
    "learning_tasks",
    "research_evaluations",
    "student_achievements",
    "student_notifications",
    "student_profiles",
    "student_submissions",
    "workflow_runs",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "migrations.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    assert inspector.get_foreign_keys("feedback_records")[0]["referred_table"] == "workflow_runs"
    assert inspector.get_foreign_keys("judge_evaluations")[0]["referred_table"] == (
        "feedback_records"
    )
    engine.dispose()
    command.check(config)

    command.downgrade(config, "base")
    downgraded_engine = create_engine(database_url)
    assert inspect(downgraded_engine).get_table_names() == ["alembic_version"]
    downgraded_engine.dispose()
