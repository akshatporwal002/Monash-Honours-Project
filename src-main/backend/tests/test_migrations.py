from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TABLES = {
    "achievements",
    "alembic_version",
    "audit_events",
    "continuation_jobs",
    "feedback_records",
    "feedback_reports",
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
    "terminal_integration_outbox",
    "worker_heartbeats",
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
    assert inspector.get_foreign_keys("feedback_records")[0]["constrained_columns"] == [
        "workflow_run_id",
        "submission_id",
    ]
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
        "source_attributions",
        "usage_complete",
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
    workflow_columns = {column["name"] for column in inspector.get_columns("workflow_runs")}
    assert {
        "course_id",
        "execution_attempt_count",
        "execution_token",
        "failure_category",
        "latency_ms",
        "lease_expires_at",
        "next_retry_at",
        "task_id",
    } <= workflow_columns
    judge_columns = {column["name"] for column in inspector.get_columns("judge_evaluations")}
    assert {
        "reported_decision",
        "provider",
        "model",
        "prompt_version",
        "quality_policy_version",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost",
        "usage_complete",
    } <= judge_columns
    report_columns = {column["name"] for column in inspector.get_columns("feedback_reports")}
    assert {
        "id",
        "feedback_id",
        "reporter_reference",
        "category",
        "note",
        "created_at",
    } == report_columns
    assert inspector.get_foreign_keys("feedback_reports")[0]["referred_table"] == (
        "feedback_records"
    )
    research_columns = {column["name"] for column in inspector.get_columns("research_evaluations")}
    assert {
        "task_type",
        "measurement_schema_version",
        "execution_token",
        "lease_expires_at",
        "processing_attempts",
        "failure_category",
        "fallback_used",
        "comparable",
        "usage_complete",
        "retrieval_request_count",
        "retrieval_hit_count",
        "first_judge_status",
        "first_judge_decision",
        "final_judge_status",
        "final_judge_decision",
        "quality_policy_version",
        "evaluation_latency_ms",
        "evaluation_total_tokens",
        "evaluation_estimated_cost",
        "correlation_id",
    } <= research_columns
    assert {index["name"] for index in inspector.get_indexes("research_evaluations")} >= {
        "ix_research_evaluations_course_condition_created",
        "ix_research_evaluations_task_type",
        "ix_research_evaluations_provider_model",
        "ix_research_evaluations_decision",
        "ix_research_evaluations_correlation",
    }
    research_checks = {
        constraint["name"]: constraint["sqltext"]
        for constraint in inspector.get_check_constraints("research_evaluations")
    }
    assert (
        "processing_attempts BETWEEN 0 AND 3"
        in research_checks["ck_research_evaluations_research_processing_attempts"]
    )
    assert {index["name"] for index in inspector.get_indexes("audit_events")} == {
        "ix_audit_events_action_time",
        "ix_audit_events_actor_time",
        "ix_audit_events_correlation_time",
    }
    continuation_columns = {column["name"] for column in inspector.get_columns("continuation_jobs")}
    assert {
        "workflow_run_id",
        "pseudonymous_actor_reference",
        "course_reference",
        "completed_task_reference",
        "correlation_id",
        "state",
        "progress_recorded",
        "processing_attempts",
        "execution_token",
        "lease_expires_at",
        "next_retry_at",
        "next_task_reference",
        "failure_category",
        "created_at",
        "updated_at",
        "completed_at",
    } == continuation_columns
    assert {index["name"] for index in inspector.get_indexes("continuation_jobs")} == {
        "ix_continuation_jobs_claim",
        "ix_continuation_jobs_course_state",
    }
    continuation_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("continuation_jobs")
    }
    assert {
        "ck_continuation_jobs_continuation_processing_attempts",
        "ck_continuation_jobs_continuation_state_shape",
    } <= continuation_checks
    continuation_foreign_key = inspector.get_foreign_keys("continuation_jobs")[0]
    assert continuation_foreign_key["referred_table"] == "workflow_runs"
    assert continuation_foreign_key["constrained_columns"] == ["workflow_run_id"]
    assert {column["name"] for column in inspector.get_columns("worker_heartbeats")} == {
        "slot",
        "worker_id",
        "last_heartbeat_at",
    }
    assert {
        constraint["name"] for constraint in inspector.get_check_constraints("worker_heartbeats")
    } >= {"ck_worker_heartbeats_worker_heartbeat_singleton"}
    learning_columns = {column["name"] for column in inspector.get_columns("learning_events")}
    assert "workflow_reference" in learning_columns
    assert {index["name"] for index in inspector.get_indexes("learning_events")} >= {
        "ix_learning_events_event_workflow"
    }
    learning_foreign_keys = inspector.get_foreign_keys("learning_events")
    assert any(
        key["constrained_columns"] == ["workflow_reference"]
        and key["referred_table"] == "workflow_runs"
        for key in learning_foreign_keys
    )
    outbox_columns = {
        column["name"] for column in inspector.get_columns("terminal_integration_outbox")
    }
    assert {
        "id",
        "workflow_run_id",
        "integration_type",
        "correlation_id",
        "payload",
        "state",
        "processing_attempts",
        "execution_token",
        "lease_expires_at",
        "next_retry_at",
        "failure_category",
        "created_at",
        "updated_at",
        "completed_at",
    } == outbox_columns
    assert {index["name"] for index in inspector.get_indexes("terminal_integration_outbox")} == {
        "ix_terminal_integration_outbox_claim",
        "ix_terminal_integration_outbox_correlation",
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("terminal_integration_outbox")
    } >= {
        "ck_terminal_integration_outbox_terminal_integration_processing_attempts",
        "ck_terminal_integration_outbox_terminal_integration_state_shape",
    }
    outbox_foreign_key = inspector.get_foreign_keys("terminal_integration_outbox")[0]
    assert outbox_foreign_key["referred_table"] == "workflow_runs"
    assert outbox_foreign_key["constrained_columns"] == ["workflow_run_id"]
    workflow_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("workflow_runs")
    }
    assert "ck_workflow_runs_workflow_failure_shape" in workflow_checks
    assert {
        index["name"] for index in inspector.get_indexes("feedback_records") if index["unique"]
    } >= {"uq_feedback_records_workflow_released"}
    engine.dispose()
    command.check(config)

    command.downgrade(config, "base")
    downgraded_engine = create_engine(database_url)
    assert inspect(downgraded_engine).get_table_names() == ["alembic_version"]
    downgraded_engine.dispose()

    # Prove the downgrade is reversible, rather than merely destructive.
    command.upgrade(config, "head")
    round_trip_engine = create_engine(database_url)
    round_trip_inspector = inspect(round_trip_engine)
    assert set(round_trip_inspector.get_table_names()) == EXPECTED_TABLES
    assert {
        "usage_complete",
        "source_attributions",
    } <= {column["name"] for column in round_trip_inspector.get_columns("feedback_records")}
    assert {
        "correlation_id",
        "processing_attempts",
    } <= {column["name"] for column in round_trip_inspector.get_columns("research_evaluations")}
    assert {
        index["name"] for index in round_trip_inspector.get_indexes("terminal_integration_outbox")
    } == {
        "ix_terminal_integration_outbox_claim",
        "ix_terminal_integration_outbox_correlation",
    }
    round_trip_engine.dispose()
    command.check(config)


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
        row = (
            connection.execute(
                text(
                    "SELECT provider, prompt_version, simulation_references, input_tokens, "
                    "output_tokens, total_tokens, estimated_cost, source_attributions "
                    "FROM feedback_records"
                )
            )
            .mappings()
            .one()
        )

    assert row["provider"] == "legacy"
    assert row["prompt_version"] == "feedback-v0"
    assert row["simulation_references"] == "[]"
    assert row["input_tokens"] == 0
    assert row["output_tokens"] == 0
    assert row["total_tokens"] == 0
    assert row["estimated_cost"] == 0
    assert row["source_attributions"] == "[]"
    upgraded_engine.dispose()


def test_quality_judge_migration_backfills_and_converts_legacy_rejection(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy-judge-migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260720_0002")

    workflow_id = "00000000-0000-4000-8000-000000000011"
    feedback_id = "00000000-0000-4000-8000-000000000012"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO workflow_runs "
                "(id, submission_id, current_stage, regeneration_count, final_outcome, "
                "started_at, completed_at) VALUES "
                "(:id, 'legacy-rejected', 'failed', 1, 'workflow_failed', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": workflow_id},
        )
        connection.execute(
            text(
                "INSERT INTO feedback_records "
                "(id, submission_id, workflow_run_id, feedback_content, status, "
                "generation_attempt, provider, model, prompt_version, source_references, "
                "simulation_references, input_tokens, output_tokens, total_tokens, "
                "estimated_cost, created_at) VALUES "
                "(:id, 'legacy-rejected', :workflow_id, :content, 'rejected', 1, "
                "'legacy-feedback-provider', 'legacy-feedback-model', 'feedback-v1', "
                ":references, :references, 2, 1, 3, 0.1, CURRENT_TIMESTAMP)"
            ),
            {
                "id": feedback_id,
                "workflow_id": workflow_id,
                "content": '{"summary": "Rejected legacy feedback"}',
                "references": "[]",
            },
        )
        connection.execute(
            text(
                "INSERT INTO judge_evaluations "
                "(id, feedback_id, evaluation_status, decision, correctness_score, "
                "relevance_score, grounding_score, actionability_score, safety_score, "
                "reason, unsupported_claims, regeneration_instructions, error_category, "
                "created_at) VALUES "
                "('00000000-0000-4000-8000-000000000013', :feedback_id, 'valid', "
                "'fail', 50, 60, 70, 80, 100, 'Needs revision.', :items, :items, NULL, "
                "CURRENT_TIMESTAMP)"
            ),
            {"feedback_id": feedback_id, "items": "[]"},
        )
    engine.dispose()

    command.upgrade(config, "head")
    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        workflow = (
            connection.execute(
                text(
                    "SELECT current_stage, final_outcome, execution_attempt_count, latency_ms "
                    "FROM workflow_runs "
                    "WHERE id = :workflow_id"
                ),
                {"workflow_id": workflow_id},
            )
            .mappings()
            .one()
        )
        feedback_rows = (
            connection.execute(
                text(
                    "SELECT status, generation_attempt, provider, model, prompt_version "
                    "FROM feedback_records WHERE workflow_run_id = :workflow_id "
                    "ORDER BY generation_attempt"
                ),
                {"workflow_id": workflow_id},
            )
            .mappings()
            .all()
        )
        judge = (
            connection.execute(
                text(
                    "SELECT reported_decision, provider, model, prompt_version, "
                    "quality_policy_version, input_tokens, output_tokens, total_tokens, "
                    "estimated_cost FROM judge_evaluations "
                    "WHERE feedback_id = :feedback_id"
                ),
                {"feedback_id": feedback_id},
            )
            .mappings()
            .one()
        )

    assert workflow == {
        "current_stage": "completed",
        "final_outcome": "safe_fallback",
        "execution_attempt_count": 1,
        "latency_ms": 0,
    }
    assert [row["status"] for row in feedback_rows] == ["safe_fallback", "rejected"]
    fallback = feedback_rows[0]
    assert fallback["generation_attempt"] is None
    assert fallback["provider"] is None
    assert fallback["model"] is None
    assert fallback["prompt_version"] is None
    assert judge["reported_decision"] == "fail"
    assert judge["provider"] == "legacy"
    assert judge["model"] == "legacy-feedback-model"
    assert judge["prompt_version"] == "quality-judge-v0"
    assert judge["quality_policy_version"] == "quality-policy-v0"
    assert judge["input_tokens"] == 0
    assert judge["output_tokens"] == 0
    assert judge["total_tokens"] == 0
    assert judge["estimated_cost"] == 0

    with pytest.raises(IntegrityError):
        with upgraded_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE judge_evaluations SET reported_decision = 'invalid' "
                    "WHERE feedback_id = :feedback_id"
                ),
                {"feedback_id": feedback_id},
            )
    with pytest.raises(IntegrityError):
        with upgraded_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE judge_evaluations SET total_tokens = 1 WHERE feedback_id = :feedback_id"
                ),
                {"feedback_id": feedback_id},
            )
    upgraded_engine.dispose()

    command.downgrade(config, "20260720_0003")
    downgraded_engine = create_engine(database_url)
    downgraded_inspector = inspect(downgraded_engine)
    assert "feedback_reports" not in downgraded_inspector.get_table_names()
    assert "source_attributions" not in {
        column["name"] for column in downgraded_inspector.get_columns("feedback_records")
    }
    assert {"lease_expires_at", "failure_category"}.isdisjoint(
        column["name"] for column in downgraded_inspector.get_columns("workflow_runs")
    )
    with downgraded_engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM feedback_records")).scalar_one() == 2
    downgraded_engine.dispose()
