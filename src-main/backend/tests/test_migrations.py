from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "achievements",
    "alembic_version",
    "feedback_records",
    "judge_evaluations",
    "learning_events",
    "learning_materials",
    "learning_tasks",
    "material_chunks",
    "research_evaluations",
    "retrieval_audits",
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
    feedback_columns = {column["name"] for column in inspector.get_columns("feedback_records")}
    assert {
        "provider",
        "prompt_version",
        "simulation_references",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost",
    } <= feedback_columns
    task_columns = {column["name"] for column in inspector.get_columns("learning_tasks")}
    assert {
        "course_id", "learning_outcome_id", "marking_criteria", "source_references",
        "prerequisite_task_ids", "generation_provider", "generation_total_tokens",
    } <= task_columns
    assert inspector.get_foreign_keys("material_chunks")[0]["referred_table"] == "learning_materials"
    material_columns = {column["name"] for column in inspector.get_columns("learning_materials")}
    assert {
        "storage_key", "file_size_bytes", "failure_stage", "error_code", "processing_revision",
    } <= material_columns
    engine.dispose()
    command.check(config)

    command.downgrade(config, "base")
    downgraded_engine = create_engine(database_url)
    assert inspect(downgraded_engine).get_table_names() == ["alembic_version"]
    downgraded_engine.dispose()


def test_feedback_metadata_migration_backfills_legacy_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260713_0001")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workflow_runs "
                "(id, submission_id, current_stage, regeneration_count, started_at) "
                "VALUES (:id, :submission_id, 'pending', 0, CURRENT_TIMESTAMP)"
            ),
            {"id": "00000000-0000-4000-8000-000000000001", "submission_id": "legacy"},
        )
        connection.execute(
            text(
                "INSERT INTO feedback_records "
                "(id, submission_id, workflow_run_id, feedback_content, status, "
                "generation_attempt, model, source_references, created_at) "
                "VALUES (:id, 'legacy', :workflow_id, :content, 'accepted', 1, "
                "'legacy-model', :references, CURRENT_TIMESTAMP)"
            ),
            {
                "id": "00000000-0000-4000-8000-000000000002",
                "workflow_id": "00000000-0000-4000-8000-000000000001",
                "content": '{"summary": "Legacy feedback"}',
                "references": "[]",
            },
        )
    engine.dispose()

    command.upgrade(config, "head")
    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT provider, prompt_version, simulation_references, input_tokens, "
                "output_tokens, total_tokens, estimated_cost FROM feedback_records"
            )
        ).mappings().one()

    assert row["provider"] == "legacy"
    assert row["prompt_version"] == "feedback-v0"
    assert row["simulation_references"] == "[]"
    assert row["input_tokens"] == 0
    assert row["output_tokens"] == 0
    assert row["total_tokens"] == 0
    assert row["estimated_cost"] == 0
    upgraded_engine.dispose()
