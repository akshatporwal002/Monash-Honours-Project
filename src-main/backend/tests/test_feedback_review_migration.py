"""0055 replay preserves populated receipts and rejects incompatible schema drift."""

import asyncio

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_feedback_quality_review import reviewed_pipeline
from test_migrations import migration_config

from app.db.session import create_db_engine


def test_feedback_review_migration_preserves_receipts_and_restores_guards(tmp_path):
    url = f"sqlite:///{(tmp_path / 'feedback-review.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "20260911_0054")
    engine = create_db_engine(url)
    try:
        assert "quality_review" not in {
            column["name"] for column in inspect(engine).get_columns("judge_evaluations")
        }
        command.upgrade(config, "20260911_0055")
        with Session(engine) as session:
            pipeline, _, _ = reviewed_pipeline(session)
            result = asyncio.run(pipeline.run("submission-1"))
            assert result.judge_evaluations[-1].quality_review.decision.value == "APPROVED"
        with engine.begin() as connection:
            before = {
                table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
                for table in ("judge_evaluations", "feedback_records")
            }
            connection.execute(text("DROP TRIGGER feedback_review_output_no_update"))
        command.stamp(config, "20260911_0054")
        command.upgrade(config, "20260911_0055")
        with engine.connect() as connection:
            for table, rows in before.items():
                assert connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all() == rows
        for table in ("judge_evaluations", "feedback_records"):
            for mutation in (
                f"UPDATE {table} SET id=id",
                f"DELETE FROM {table}",
                f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}",
            ):
                with pytest.raises(IntegrityError, match="history is immutable"):
                    with engine.begin() as connection:
                        connection.execute(text(mutation))
        with pytest.raises(RuntimeError, match="history is protected"):
            command.downgrade(config, "20260911_0054")
        with engine.connect() as connection:
            for table, rows in before.items():
                assert connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all() == rows
    finally:
        engine.dispose()


@pytest.mark.parametrize("declaration", ["TEXT", "JSON NOT NULL", "JSON DEFAULT '{}' "])
def test_feedback_review_migration_rejects_incompatible_existing_column(tmp_path, declaration):
    url = f"sqlite:///{(tmp_path / 'incompatible-review.db').as_posix()}"
    config = migration_config(url)
    command.upgrade(config, "20260911_0054")
    engine = create_db_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(f"ALTER TABLE judge_evaluations ADD COLUMN quality_review {declaration}")
            )
        with pytest.raises(RuntimeError, match="quality_review has incompatible shape"):
            command.upgrade(config, "20260911_0055")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20260911_0054"
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'feedback_review_%'"
                    )
                )
                == 0
            )
    finally:
        engine.dispose()
