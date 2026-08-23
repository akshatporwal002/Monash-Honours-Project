import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from support.assessment import (
    build_assessment_attempt as _attempt_context,
)
from support.assessment import (
    build_assessment_blueprint as _blueprint,
)
from support.assessment import (
    build_external_criterion as _criterion_outside_frozen_rule,
)
from support.assessment import (
    build_provisional_decision as _provisional_decision,
)

from app.core.security import hash_password
from app.domain.assessment import (
    AssessmentAttemptState,
    AssessmentResult,
    QualityReviewDecision,
    ResultState,
)
from app.models import learning_evidence  # noqa: F401
from app.models.assessment import AssessmentAttempt, AssessmentDecision
from app.models.lms import AttemptStatus, SubmissionAttempt, SubmissionDraft
from app.models.user import User, UserRole
from app.schemas.assessment import legacy_judge_decision_to_quality_review
from scripts.verify_sqlite_backup import create_verified_backup, database_manifest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LEGACY_ASSESSMENT_FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "legacy_assessment.sql"
EXPECTED_TABLES = {
    "assessment_definition_versions",
    "assessment_definitions",
    "assessment_legacy_history",
    "evidence_artifacts",
    "evidence_links",
    "learner_model_evidence_links",
    "learner_model_annotations",
    "learner_model_correction_reviews",
    "learner_model_correction_snapshot_links",
    "learner_model_snapshots",
    "learner_outcome_estimates",
    "assessment_attempts",
    "assessment_decisions",
    "appeals_or_corrections",
    "assessor_reviews",
    "achievements",
    "alembic_version",
    "audit_events",
    "bloom_target_versions",
    "bloom_targets",
    "continuation_jobs",
    "course_modules",
    "criteria",
    "criterion_evaluations",
    "criterion_versions",
    "courses",
    "enrollments",
    "feedback_records",
    "feedback_reports",
    "judge_evaluations",
    "learning_events",
    "learning_evidence",
    "learning_materials",
    "learning_outcomes",
    "learning_tasks",
    "material_chunks",
    "outcome_versions",
    "pass_rule_versions",
    "pass_rules",
    "platform_audit_events",
    "recommendations",
    "role_assignments",
    "research_evaluations",
    "reassessment_links",
    "retrieval_audits",
    "student_achievements",
    "student_notifications",
    "student_profiles",
    "student_submissions",
    "submission_attempts",
    "submission_drafts",
    "system_settings",
    "task_point_awards",
    "task_approvals",
    "task_form_versions",
    "task_forms",
    "terminal_integration_outbox",
    "users",
    "worker_heartbeats",
    "workflow_runs",
    "reminders",
}


def migration_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _load_sql_fixture(engine: Engine, fixture_path: Path) -> None:
    """Apply a checked-in SQLite fixture without interpolating its contents."""

    raw_connection = engine.raw_connection()
    try:
        raw_connection.executescript(fixture_path.read_text(encoding="utf-8"))
        raw_connection.commit()
    finally:
        raw_connection.close()


def _prepare_legacy_assessment_database(tmp_path: Path) -> tuple[Path, Config]:
    database_path = tmp_path / "legacy-assessment.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260815_0017")
    engine = create_engine(database_url)
    try:
        _load_sql_fixture(engine, LEGACY_ASSESSMENT_FIXTURE)
    finally:
        engine.dispose()
    return database_path, config


def _legacy_history_rows(engine: Engine) -> list[dict[str, object]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT source_table, source_record_id, response_version_id, source_status, "
                "source_result, source_score, mapped_result, migration_revision, migration_actor, "
                "migration_reason "
                "FROM assessment_legacy_history ORDER BY source_table, source_record_id"
            )
        ).mappings()
        return [dict(row) for row in rows]


def _assert_cross_course_definition_link_is_rejected(engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="invalid assessment definition scope"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                    "VALUES ('assessment-owner@example.edu', 'hash', 'Assessment Owner', "
                    "'educator', 1)"
                )
            )
            owner_id = connection.execute(
                text("SELECT id FROM users WHERE email = 'assessment-owner@example.edu'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO courses "
                    "(id, educator_id, code, title, description, state, enrollment_open, "
                    "created_at, updated_at) "
                    "VALUES ('assessment-course-one', :owner, 'ASM101', 'First course', '', "
                    "'draft', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
                    "('assessment-course-two', :owner, 'ASM102', 'Second course', '', "
                    "'draft', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO course_modules "
                    "(id, course_id, title, description, position, created_at, updated_at) "
                    "VALUES ('assessment-module-one', 'assessment-course-one', 'Module', '', 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO learning_outcomes "
                    "(id, module_id, title, statement, kind, week_number, position, created_at, "
                    "updated_at) VALUES ('assessment-outcome-one', 'assessment-module-one', "
                    "'Outcome', 'Statement', 'weekly', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definitions "
                    "(id, course_id, learning_outcome_id, created_by_user_id, created_at) "
                    "VALUES ('invalid-assessment-definition', 'assessment-course-two', "
                    "'assessment-outcome-one', :owner, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )


def test_cross_course_definition_links_fail_at_database_layer(tmp_path: Path) -> None:
    database_path = tmp_path / "cross-course-definition.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        _assert_cross_course_definition_link_is_rejected(engine)
    finally:
        engine.dispose()


def test_migrated_versions_reject_renumbering_and_allow_safe_retirement(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "assessment-version-immutability.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                    "VALUES ('version-owner@example.edu', 'hash', 'Version Owner', 'educator', 1)"
                )
            )
            owner_id = connection.execute(
                text("SELECT id FROM users WHERE email = 'version-owner@example.edu'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO courses "
                    "(id, educator_id, code, title, description, state, enrollment_open, "
                    "created_at, updated_at) VALUES ('version-course', :owner, 'VER101', "
                    "'Version course', '', 'draft', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO course_modules "
                    "(id, course_id, title, description, position, created_at, updated_at) "
                    "VALUES ('version-module', 'version-course', 'Module', '', 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO learning_outcomes "
                    "(id, module_id, title, statement, kind, week_number, position, created_at, "
                    "updated_at) VALUES ('version-outcome', 'version-module', 'Outcome', "
                    "'Statement', 'weekly', 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO outcome_versions "
                    "(id, course_id, learning_outcome_id, version, owner_user_id, "
                    "created_by_user_id, created_at, approval_state, title, statement, source_version) "
                    "VALUES ('version-outcome-v1', 'version-course', 'version-outcome', 1, :owner, "
                    ":owner, CURRENT_TIMESTAMP, 'DRAFT', 'Outcome', 'Statement', 'source.v1')"
                ),
                {"owner": owner_id},
            )
        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE outcome_versions SET version = 2 WHERE id = 'version-outcome-v1'")
                )
        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE outcome_versions SET id = 'version-outcome-id-change' "
                        "WHERE id = 'version-outcome-v1'"
                    )
                )
        for invalid_state in ("APPROVED", "RETIRED"):
            with pytest.raises(IntegrityError, match="approval_shape"):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO outcome_versions "
                            "(id, course_id, learning_outcome_id, version, owner_user_id, "
                            "created_by_user_id, created_at, approval_state, title, statement, "
                            "source_version) VALUES (:id, 'version-course', 'version-outcome', 2, "
                            ":owner, :owner, CURRENT_TIMESTAMP, :state, 'Outcome', 'Statement', "
                            "'source.v2')"
                        ),
                        {
                            "id": f"invalid-{invalid_state.lower()}-outcome-v2",
                            "owner": owner_id,
                            "state": invalid_state,
                        },
                    )
        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE outcome_versions SET approval_state = 'RETIRED', "
                        "approved_at = CURRENT_TIMESTAMP, approved_by_user_id = :owner, "
                        "retired_at = CURRENT_TIMESTAMP, retired_by_user_id = :owner, "
                        "retirement_reason = 'Invalid direct transition.' "
                        "WHERE id = 'version-outcome-v1'"
                    ),
                    {"owner": owner_id},
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE outcome_versions SET approval_state = 'APPROVED', "
                    "approved_at = CURRENT_TIMESTAMP, approved_by_user_id = :owner "
                    "WHERE id = 'version-outcome-v1'"
                ),
                {"owner": owner_id},
            )
            approved_snapshot = (
                connection.execute(
                    text(
                        "SELECT title, statement, approval_state, approved_at, approved_by_user_id "
                        "FROM outcome_versions WHERE id = 'version-outcome-v1'"
                    )
                )
                .mappings()
                .one()
            )
            connection.execute(
                text(
                    "INSERT INTO outcome_versions "
                    "(id, course_id, learning_outcome_id, version, owner_user_id, "
                    "created_by_user_id, created_at, approval_state, title, statement, "
                    "source_version) VALUES ('version-outcome-v2', 'version-course', "
                    "'version-outcome', 2, :owner, :owner, CURRENT_TIMESTAMP, 'DRAFT', "
                    "'Revised outcome', 'Revised statement', 'source.v2')"
                ),
                {"owner": owner_id},
            )
            assert (
                connection.execute(
                    text(
                        "SELECT title, statement, approval_state, approved_at, approved_by_user_id "
                        "FROM outcome_versions WHERE id = 'version-outcome-v1'"
                    )
                )
                .mappings()
                .one()
                == approved_snapshot
            )
            connection.execute(
                text(
                    "UPDATE outcome_versions SET approval_state = 'RETIRED', "
                    "retired_at = CURRENT_TIMESTAMP, retired_by_user_id = :owner, "
                    "retirement_reason = 'Superseded by a later version.' "
                    "WHERE id = 'version-outcome-v1'"
                ),
                {"owner": owner_id},
            )
        with pytest.raises(IntegrityError, match="immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE outcome_versions SET title = 'Changed' WHERE id = 'version-outcome-v1'"
                    )
                )
    finally:
        engine.dispose()


def test_pass_rule_database_trigger_rejects_bypass_writes(tmp_path: Path) -> None:
    database_path = tmp_path / "pass-rule-database-guard.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                    "VALUES ('rule-owner@example.edu', 'hash', 'Rule Owner', 'educator', 1)"
                )
            )
            owner_id = connection.execute(
                text("SELECT id FROM users WHERE email = 'rule-owner@example.edu'")
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO courses (id, educator_id, code, title, description, state, "
                    "enrollment_open, created_at, updated_at) VALUES "
                    "('rule-course', :owner, 'RUL101', 'Rule course', '', 'draft', 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO course_modules (id, course_id, title, description, position, "
                    "created_at, updated_at) VALUES ('rule-module', 'rule-course', 'Module', '', 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO learning_outcomes (id, module_id, title, statement, kind, "
                    "week_number, position, created_at, updated_at) VALUES ('rule-outcome', "
                    "'rule-module', 'Outcome', 'Statement', 'weekly', 1, 1, CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO outcome_versions (id, course_id, learning_outcome_id, version, "
                    "owner_user_id, created_by_user_id, created_at, approval_state, title, statement, "
                    "source_version) VALUES ('rule-outcome-v1', 'rule-course', 'rule-outcome', 1, "
                    ":owner, :owner, CURRENT_TIMESTAMP, 'DRAFT', 'Outcome', 'Statement', 'source.v1')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definitions (id, course_id, learning_outcome_id, "
                    "created_by_user_id, created_at) VALUES ('rule-definition', 'rule-course', "
                    "'rule-outcome', :owner, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definition_versions "
                    "(id, course_id, assessment_definition_id, version, owner_user_id, "
                    "created_by_user_id, created_at, approval_state, outcome_version_id, claim, "
                    "supporting_evidence, contradicting_evidence, insufficient_evidence, "
                    "task_conditions, next_action_contract, purpose, permitted_tools, "
                    "instructional_support, access_conditions, transfer_rule, evidence_sufficiency) "
                    "VALUES ('rule-definition-v1', 'rule-course', 'rule-definition', 1, :owner, "
                    ":owner, CURRENT_TIMESTAMP, 'DRAFT', 'rule-outcome-v1', 'Claim', '[]', '[]', "
                    "'[]', '[]', '[]', 'SUMMATIVE', '[]', '[]', '[]', '[]', '[]')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO criteria (id, assessment_definition_id, stable_key) VALUES "
                    "('rule-criterion', 'rule-definition', 'criterion')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO criterion_versions "
                    "(id, course_id, criterion_id, version, owner_user_id, created_by_user_id, "
                    "created_at, approval_state, assessment_definition_version_id, learner_description, "
                    "evidence_description, mandatory, evidence_source_types, met_rule, not_met_rule, "
                    "not_evaluable_rule, approved_anchors, critical_error_rules, evaluator_type) "
                    "VALUES ('rule-criterion-v1', 'rule-course', 'rule-criterion', 1, :owner, :owner, "
                    "CURRENT_TIMESTAMP, 'DRAFT', 'rule-definition-v1', 'Learner', 'Evidence', 1, '[]', "
                    "'Met', 'Not met', 'Not evaluable', '[]', '[]', 'rules')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO courses (id, educator_id, code, title, description, state, "
                    "enrollment_open, created_at, updated_at) VALUES "
                    "('other-rule-course', :owner, 'RUL102', 'Other rule course', '', 'draft', 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO course_modules (id, course_id, title, description, position, "
                    "created_at, updated_at) VALUES ('other-rule-module', 'other-rule-course', "
                    "'Module', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO learning_outcomes (id, module_id, title, statement, kind, "
                    "week_number, position, created_at, updated_at) VALUES ('other-rule-outcome', "
                    "'other-rule-module', 'Outcome', 'Statement', 'weekly', 1, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO outcome_versions (id, course_id, learning_outcome_id, version, "
                    "owner_user_id, created_by_user_id, created_at, approval_state, title, statement, "
                    "source_version) VALUES ('other-rule-outcome-v1', 'other-rule-course', "
                    "'other-rule-outcome', 1, :owner, :owner, CURRENT_TIMESTAMP, 'DRAFT', "
                    "'Outcome', 'Statement', 'source.v1')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definitions (id, course_id, learning_outcome_id, "
                    "created_by_user_id, created_at) VALUES ('other-rule-definition', "
                    "'other-rule-course', 'other-rule-outcome', :owner, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definition_versions "
                    "(id, course_id, assessment_definition_id, version, owner_user_id, "
                    "created_by_user_id, created_at, approval_state, outcome_version_id, claim, "
                    "supporting_evidence, contradicting_evidence, insufficient_evidence, "
                    "task_conditions, next_action_contract, purpose, permitted_tools, "
                    "instructional_support, access_conditions, transfer_rule, evidence_sufficiency) "
                    "VALUES ('other-rule-definition-v1', 'other-rule-course', "
                    "'other-rule-definition', 1, :owner, :owner, CURRENT_TIMESTAMP, 'DRAFT', "
                    "'other-rule-outcome-v1', 'Claim', '[]', '[]', '[]', '[]', '[]', "
                    "'SUMMATIVE', '[]', '[]', '[]', '[]', '[]')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO criteria (id, assessment_definition_id, stable_key) VALUES "
                    "('other-rule-criterion', 'other-rule-definition', 'criterion')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO criterion_versions "
                    "(id, course_id, criterion_id, version, owner_user_id, created_by_user_id, "
                    "created_at, approval_state, assessment_definition_version_id, learner_description, "
                    "evidence_description, mandatory, evidence_source_types, met_rule, not_met_rule, "
                    "not_evaluable_rule, approved_anchors, critical_error_rules, evaluator_type) "
                    "VALUES ('other-rule-criterion-v1', 'other-rule-course', "
                    "'other-rule-criterion', 1, :owner, :owner, CURRENT_TIMESTAMP, 'DRAFT', "
                    "'other-rule-definition-v1', 'Learner', 'Evidence', 1, '[]', 'Met', "
                    "'Not met', 'Not evaluable', '[]', '[]', 'rules')"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO pass_rules (id, assessment_definition_id) VALUES "
                    "('rule-pass-rule', 'rule-definition')"
                )
            )

        def insert_rule(rule_id: str, expression: str) -> None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO pass_rule_versions "
                        "(id, course_id, pass_rule_id, version, owner_user_id, created_by_user_id, "
                        "created_at, approval_state, assessment_definition_version_id, expression) "
                        "VALUES (:id, 'rule-course', 'rule-pass-rule', 1, :owner, :owner, "
                        "CURRENT_TIMESTAMP, 'DRAFT', 'rule-definition-v1', :expression)"
                    ),
                    {"id": rule_id, "owner": owner_id, "expression": expression},
                )

        with pytest.raises(IntegrityError, match="invalid pass rule expression"):
            insert_rule("rule-invalid-operator", '{"operator":"SCORE","clauses":[]}')
        with pytest.raises(IntegrityError, match="invalid pass rule expression"):
            insert_rule(
                "rule-invalid-score",
                '{"operator":"ALL_OF","clauses":[{"criterion_version_id":"rule-criterion-v1","score":1}]}',
            )
        with pytest.raises(IntegrityError, match="invalid pass rule expression"):
            insert_rule(
                "rule-missing-criterion",
                '{"operator":"ALL_OF","clauses":[{"criterion_version_id":"missing"}]}',
            )
        with pytest.raises(IntegrityError, match="invalid pass rule expression"):
            insert_rule(
                "rule-cross-course-criterion",
                '{"operator":"ALL_OF","clauses":[{"criterion_version_id":"other-rule-criterion-v1"}]}',
            )
        for rule_id, expression in (
            (
                "rule-root-array",
                '["invalid scalar", {"criterion_version_id":"rule-criterion-v1"}]',
            ),
            (
                "rule-scalar-clause",
                '{"operator":"ALL_OF","clauses":["invalid scalar", {"criterion_version_id":"rule-criterion-v1"}]}',
            ),
            (
                "rule-mixed-leaf-operator",
                '{"operator":"ALL_OF","criterion_version_id":"rule-criterion-v1","clauses":[{"criterion_version_id":"rule-criterion-v1"}]}',
            ),
            (
                "rule-empty-nested-operator",
                '{"operator":"ALL_OF","clauses":[{"operator":"ANY_OF","clauses":[]}]}',
            ),
            (
                "rule-duplicate-operator",
                '{"operator":"ALL_OF","operator":"ANY_OF","clauses":[{"criterion_version_id":"rule-criterion-v1"}]}',
            ),
            (
                "rule-duplicate-clauses",
                '{"operator":"ALL_OF","clauses":[{"criterion_version_id":"rule-criterion-v1"}],"clauses":[{"criterion_version_id":"rule-criterion-v1"}]}',
            ),
        ):
            with pytest.raises(IntegrityError, match="invalid pass rule expression"):
                insert_rule(rule_id, expression)
        insert_rule(
            "rule-valid",
            '{"operator":"NOT","clauses":[{"operator":"ANY_OF","clauses":[{"criterion_version_id":"rule-criterion-v1"}]}]}',
        )
        with pytest.raises(IntegrityError, match="referenced criterion version"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE criterion_versions SET course_id = 'other-rule-course' "
                        "WHERE id = 'rule-criterion-v1'"
                    )
                )
        with pytest.raises(IntegrityError, match="referenced criterion version"):
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM criterion_versions WHERE id = 'rule-criterion-v1'")
                )
    finally:
        engine.dispose()


def test_assessment_attempt_database_triggers_reject_direct_bypass_writes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "assessment-attempt-database-guard.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    command.upgrade(migration_config(database_url), "head")
    engine = create_engine(database_url)
    session = Session(engine)
    try:
        definition, bloom, criterion, rule, form, owner = _blueprint(session)
        student = User(
            email="migration-attempt-student@example.edu",
            password_hash=hash_password("migration-attempt-test-password"),
            full_name="Migration Attempt Student",
            role=UserRole.STUDENT,
        )
        session.add(student)
        session.flush()
        draft = SubmissionDraft(student_id=student.id, task_id=form.learning_task_id)
        session.add(draft)
        session.flush()
        response = SubmissionAttempt(
            draft_id=draft.id,
            student_id=student.id,
            task_id=form.learning_task_id,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            answer="A formal response version.",
            score=None,
            feedback="Recorded.",
            task_form_version_id=form.id,
            response_schema_version="assessment.response.v1",
            content_digest="sha256:" + "a" * 64,
            idempotency_key="migration-response-key",
            declared_conditions={"tools": []},
        )
        session.add(response)
        session.flush()
        attempt = AssessmentAttempt(
            course_id=definition.course_id,
            student_id=student.id,
            task_id=form.learning_task_id,
            response_version_id=response.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            bloom_target_version_id=bloom.id,
            pass_rule_version_id=rule.id,
            state=AssessmentAttemptState.PENDING,
        )
        session.add(attempt)
        session.commit()

        outside_criterion = _criterion_outside_frozen_rule(session, attempt, criterion, owner)
        with pytest.raises(IntegrityError, match="invalid criterion evaluation scope"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO criterion_evaluations "
                        "(id, assessment_attempt_id, criterion_version_id, decision, "
                        "evidence_references, evaluator_reference, reason, evaluated_at) "
                        "VALUES ('invalid-evaluation', :attempt, :criterion, 'MET', "
                        "'{}', 'rules.v1', 'Invalid scope.', CURRENT_TIMESTAMP)"
                    ),
                    {"attempt": attempt.id, "criterion": outside_criterion.id},
                )
        with pytest.raises(IntegrityError, match="invalid assessment decision version bundle"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO assessment_decisions "
                        "(id, assessment_attempt_id, bloom_target_version_id, pass_rule_version_id, "
                        "evaluation_idempotency_key, result, result_state, evidence_references, "
                        "system_reason, created_at) VALUES ('invalid-decision', :attempt, "
                        "'missing-bloom', :rule, 'invalid-evaluation-key', 'PASS', 'PROVISIONAL', "
                        "'{}', 'TARGET_EVIDENCE_MET', CURRENT_TIMESTAMP)"
                    ),
                    {"attempt": attempt.id, "rule": rule.id},
                )

        decision = AssessmentDecision(
            assessment_attempt_id=attempt.id,
            bloom_target_version_id=bloom.id,
            pass_rule_version_id=rule.id,
            evaluation_idempotency_key="migration-evaluation-key",
            result=AssessmentResult.PASS,
            result_state=ResultState.PROVISIONAL,
            evidence_references={"criterion_evaluations": []},
            system_reason="TARGET_EVIDENCE_MET",
        )
        session.add(decision)
        session.commit()
        with pytest.raises(
            IntegrityError,
            match="assessment decision transitions require a matching assessor review",
        ):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE assessment_decisions SET result_state = 'CONFIRMED', "
                        "assessor_user_id = :owner, reviewed_at = CURRENT_TIMESTAMP "
                        "WHERE id = :decision"
                    ),
                    {"decision": decision.id, "owner": owner.id},
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO assessor_reviews "
                    "(id, assessment_decision_id, review_revision, assessor_user_id, action, prior_result, "
                    "new_result, reason, reviewed_at) VALUES ('wrong-override-review', :decision, "
                    "1, :owner, 'OVERRIDE', 'INCOMPLETE', 'PASS', 'Wrong reason.', CURRENT_TIMESTAMP)"
                ),
                {"decision": decision.id, "owner": owner.id},
            )
        with pytest.raises(
            IntegrityError,
            match="assessment decision transitions require a matching assessor review",
        ):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE assessment_decisions SET result_state = 'OVERRIDDEN', "
                        "prior_result = 'INCOMPLETE', result = 'PASS', assessor_user_id = :owner, "
                        "reviewed_at = CURRENT_TIMESTAMP, override_reason = 'Different reason.' "
                        "WHERE id = :decision"
                    ),
                    {"decision": decision.id, "owner": owner.id},
                )
        replacement_response = SubmissionAttempt(
            draft_id=draft.id,
            student_id=student.id,
            task_id=form.learning_task_id,
            attempt_number=2,
            status=AttemptStatus.SUBMITTED,
            answer="A later valid response version.",
            score=None,
            feedback="Recorded.",
            task_form_version_id=form.id,
            response_schema_version="assessment.response.v1",
            content_digest="sha256:" + "b" * 64,
            idempotency_key="migration-response-key-2",
            declared_conditions={"tools": []},
        )
        session.add(replacement_response)
        session.commit()
        replacement_attempt = AssessmentAttempt(
            course_id=definition.course_id,
            student_id=student.id,
            task_id=form.learning_task_id,
            response_version_id=replacement_response.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            bloom_target_version_id=bloom.id,
            pass_rule_version_id=rule.id,
            state=AssessmentAttemptState.PENDING,
        )
        other_student = User(
            email="migration-other-student@example.edu",
            password_hash=hash_password("migration-other-student-password"),
            full_name="Migration Other Student",
            role=UserRole.STUDENT,
        )
        session.add_all([replacement_attempt, other_student])
        session.flush()
        other_draft = SubmissionDraft(student_id=other_student.id, task_id=form.learning_task_id)
        session.add(other_draft)
        session.flush()
        other_response = SubmissionAttempt(
            draft_id=other_draft.id,
            student_id=other_student.id,
            task_id=form.learning_task_id,
            attempt_number=1,
            status=AttemptStatus.SUBMITTED,
            answer="A different learner's valid response version.",
            score=None,
            feedback="Recorded.",
            task_form_version_id=form.id,
            response_schema_version="assessment.response.v1",
            content_digest="sha256:" + "c" * 64,
            idempotency_key="migration-other-response-key",
            declared_conditions={"tools": []},
        )
        session.add(other_response)
        session.flush()
        other_attempt = AssessmentAttempt(
            course_id=definition.course_id,
            student_id=other_student.id,
            task_id=form.learning_task_id,
            response_version_id=other_response.id,
            assessment_definition_version_id=definition.id,
            task_form_version_id=form.id,
            bloom_target_version_id=bloom.id,
            pass_rule_version_id=rule.id,
            state=AssessmentAttemptState.PENDING,
        )
        session.add(other_attempt)
        session.commit()
        with pytest.raises(IntegrityError, match="version anchors are immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE assessment_attempts SET response_version_id = :replacement "
                        "WHERE id = :attempt"
                    ),
                    {"attempt": attempt.id, "replacement": replacement_response.id},
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO criterion_evaluations "
                    "(id, assessment_attempt_id, criterion_version_id, decision, "
                    "evidence_references, evaluator_reference, reason, evaluated_at) "
                    "VALUES ('stored-evaluation', :attempt, :criterion, 'MET', '{}', "
                    "'rules.v1', 'Stored evidence.', CURRENT_TIMESTAMP)"
                ),
                {"attempt": attempt.id, "criterion": criterion.id},
            )
            connection.execute(
                text(
                    "INSERT INTO assessor_reviews "
                    "(id, assessment_decision_id, review_revision, assessor_user_id, action, prior_result, "
                    "new_result, reason, reviewed_at) VALUES ('stored-review', :decision, "
                    "2, :owner, 'RETURN', NULL, NULL, 'Return for clarification.', CURRENT_TIMESTAMP)"
                ),
                {"decision": decision.id, "owner": owner.id},
            )
        with pytest.raises(IntegrityError, match="assessment records are append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE criterion_evaluations SET reason = 'changed' WHERE id = 'stored-evaluation'"
                    )
                )
        with pytest.raises(IntegrityError, match="assessment records are append-only"):
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM assessor_reviews WHERE id = 'stored-review'"))
        with pytest.raises(IntegrityError, match="evidence and anchors are immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE assessment_decisions SET result_state = 'CONFIRMED', "
                        "assessor_user_id = :owner, reviewed_at = CURRENT_TIMESTAMP, "
                        "evidence_references = '{\"rewritten\": true}' WHERE id = :decision"
                    ),
                    {"decision": decision.id, "owner": owner.id},
                )
        with pytest.raises(IntegrityError, match="assessment records are append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM assessment_decisions WHERE id = :decision"),
                    {"decision": decision.id},
                )
        with pytest.raises(IntegrityError, match="invalid reassessment link scope"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO reassessment_links "
                        "(id, prior_assessment_attempt_id, replacement_assessment_attempt_id, "
                        "approved_by_user_id, reason, created_at) VALUES ('invalid-reassessment', "
                        ":attempt, :other_attempt, :owner, 'Different learner.', CURRENT_TIMESTAMP)"
                    ),
                    {
                        "attempt": attempt.id,
                        "other_attempt": other_attempt.id,
                        "owner": owner.id,
                    },
                )
        with pytest.raises(IntegrityError, match="invalid appeal or correction scope"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO appeals_or_corrections "
                        "(id, assessment_attempt_id, assessment_decision_id, requested_by_user_id, "
                        "request_kind, request_reason, state, created_at) VALUES ('invalid-appeal', "
                        ":replacement_attempt, :decision, :student, 'appeal', 'Wrong attempt.', "
                        "'PENDING', CURRENT_TIMESTAMP)"
                    ),
                    {
                        "replacement_attempt": replacement_attempt.id,
                        "decision": decision.id,
                        "student": student.id,
                    },
                )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO appeals_or_corrections "
                    "(id, assessment_attempt_id, assessment_decision_id, requested_by_user_id, "
                    "request_kind, request_reason, state, created_at) VALUES ('stored-appeal', "
                    ":attempt, :decision, :student, 'appeal', 'Stored request.', 'PENDING', "
                    "CURRENT_TIMESTAMP)"
                ),
                {"attempt": attempt.id, "decision": decision.id, "student": student.id},
            )
        with pytest.raises(IntegrityError, match="assessment records are append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM appeals_or_corrections WHERE id = 'stored-appeal'")
                )
        with pytest.raises(IntegrityError, match="assessment records are append-only"):
            with engine.begin() as connection:
                connection.execute(
                    text("DELETE FROM assessment_attempts WHERE id = :attempt"),
                    {"attempt": attempt.id},
                )
        with pytest.raises(
            IntegrityError, match="decided assessment attempts cannot become faulted"
        ):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE assessment_attempts SET state = 'FAULTED', "
                        "fault_reason = 'Invalid after decision.' WHERE id = :attempt"
                    ),
                    {"attempt": attempt.id},
                )
        with pytest.raises(IntegrityError, match="submission attempts are immutable"):
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE submission_attempts SET answer = 'changed' WHERE id = :response"),
                    {"response": response.id},
                )
        assert criterion.id
        assert owner.id
    finally:
        session.close()
        engine.dispose()


def test_assessment_attempt_downgrade_restores_prior_audit_actions(tmp_path: Path) -> None:
    database_path = tmp_path / "assessment-attempt-downgrade.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "20260815_0016")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            audit_table_sql = connection.execute(
                text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'audit_events'")
            ).scalar_one()
        assert "assessment_attempt_created" not in audit_table_sql
        assert "feedback_generation_started" in audit_table_sql
    finally:
        engine.dispose()


def test_populated_role_assignment_downgrade_is_refused_before_schema_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "populated-role-assignment.db"
    config = migration_config(f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260815_0015")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            owner_id = connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                    "VALUES ('role-history@example.edu', 'hash', 'Role History', 'educator', 1) "
                    "RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO courses "
                    "(id, educator_id, code, title, description, state, enrollment_open, "
                    "created_at, updated_at) VALUES ('role-history-course', :owner, 'ROL101', "
                    "'Role history', '', 'draft', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO role_assignments "
                    "(id, subject_user_id, course_id, role, version, assigned_by_user_id, "
                    "reason, assigned_at, valid_from) VALUES "
                    "('role-history-1', :owner, 'role-history-course', 'assessor', 1, :owner, "
                    "'Approved assessor assignment.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
    finally:
        engine.dispose()

    before = database_manifest(database_path)
    with pytest.raises(RuntimeError, match="cannot downgrade populated role assignment"):
        command.downgrade(config, "20260726_0014")
    assert database_manifest(database_path) == before


def test_populated_definition_downgrade_is_refused_before_schema_changes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "populated-definition.db"
    config = migration_config(f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260815_0016")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            owner_id = connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role, is_active) "
                    "VALUES ('definition-history@example.edu', 'hash', 'Definition History', "
                    "'educator', 1) RETURNING id"
                )
            ).scalar_one()
            connection.execute(
                text(
                    "INSERT INTO courses "
                    "(id, educator_id, code, title, description, state, enrollment_open, "
                    "created_at, updated_at) VALUES ('definition-history-course', :owner, "
                    "'DEF101', 'Definition history', '', 'draft', 1, CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
            connection.execute(
                text(
                    "INSERT INTO course_modules "
                    "(id, course_id, title, description, position, created_at, updated_at) "
                    "VALUES ('definition-history-module', 'definition-history-course', "
                    "'Module', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO learning_outcomes "
                    "(id, module_id, title, statement, kind, week_number, position, created_at, "
                    "updated_at) VALUES ('definition-history-outcome', "
                    "'definition-history-module', 'Outcome', 'Statement', 'weekly', 1, 1, "
                    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_definitions "
                    "(id, course_id, learning_outcome_id, created_by_user_id, created_at) "
                    "VALUES ('definition-history-1', 'definition-history-course', "
                    "'definition-history-outcome', :owner, CURRENT_TIMESTAMP)"
                ),
                {"owner": owner_id},
            )
    finally:
        engine.dispose()

    before = database_manifest(database_path)
    with pytest.raises(RuntimeError, match="cannot downgrade populated assessment definition"):
        command.downgrade(config, "20260815_0015")
    assert database_manifest(database_path) == before


def test_populated_attempt_downgrade_is_refused_before_schema_changes(tmp_path: Path) -> None:
    database_path = tmp_path / "populated-attempt.db"
    config = migration_config(f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260815_0017")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    session = Session(engine)
    try:
        _attempt_context(session)
    finally:
        session.close()
        engine.dispose()

    before = database_manifest(database_path)
    with pytest.raises(RuntimeError, match="cannot downgrade populated assessment attempt"):
        command.downgrade(config, "20260815_0016")
    assert database_manifest(database_path) == before


def test_assessment_migration_upgrades_clean_and_legacy_databases(tmp_path: Path) -> None:
    clean_path = tmp_path / "clean-assessment.db"
    clean_config = migration_config(f"sqlite:///{clean_path.as_posix()}")
    command.upgrade(clean_config, "head")
    clean_engine = create_engine(f"sqlite:///{clean_path.as_posix()}")
    try:
        assert "assessment_legacy_history" in inspect(clean_engine).get_table_names()
        with clean_engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM assessment_legacy_history")
                ).scalar_one()
                == 0
            )
    finally:
        clean_engine.dispose()

    legacy_path, legacy_config = _prepare_legacy_assessment_database(tmp_path)
    before_manifest = database_manifest(legacy_path)
    command.upgrade(legacy_config, "head")
    legacy_engine = create_engine(f"sqlite:///{legacy_path.as_posix()}")
    try:
        history = _legacy_history_rows(legacy_engine)
        assert len(history) == 5
        assert {row["source_table"] for row in history} == {
            "legacy_learner_results",
            "submission_attempts",
        }
        assert all(row["mapped_result"] != "PASS" for row in history)
        assert {
            row["source_record_id"]: (row["source_status"], row["source_score"])
            for row in history
            if row["source_table"] == "submission_attempts"
        } == {
            "00000000-0000-4000-8000-000000000521": ("completed", 92),
            "00000000-0000-4000-8000-000000000522": ("submitted", 15),
        }
        legacy_pass = next(
            row for row in history if row["source_record_id"] == "legacy-learner-pass"
        )
        assert legacy_pass["source_result"] == "PASS"
        assert legacy_pass["mapped_result"] is None
        assert legacy_pass["migration_reason"] == "LEGACY_PUBLIC_RESULT_UNMAPPED"
        inspector = inspect(legacy_engine)
        assert "ck_assessment_legacy_history_assessment_legacy_history_mapped_result" in {
            constraint["name"]
            for constraint in inspector.get_check_constraints("assessment_legacy_history")
        }
        assert "uq_assessment_legacy_history_source_record" in {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("assessment_legacy_history")
        }
        assert "ix_assessment_legacy_history_response" in {
            index["name"] for index in inspector.get_indexes("assessment_legacy_history")
        }
        assert any(
            foreign_key["constrained_columns"] == ["response_version_id"]
            and foreign_key["referred_table"] == "submission_attempts"
            for foreign_key in inspector.get_foreign_keys("assessment_legacy_history")
        )
        with legacy_engine.connect() as connection:
            trigger_names = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                        "AND tbl_name = 'assessment_legacy_history'"
                    )
                ).scalars()
            )
            assert trigger_names >= {
                "trg_assessment_legacy_history_immutable_delete",
                "trg_assessment_legacy_history_immutable_update",
                "trg_assessment_legacy_history_migration_only_insert",
            }
        with legacy_engine.connect() as connection:
            invalid_links = connection.execute(
                text(
                    "SELECT COUNT(*) FROM assessment_legacy_history AS history "
                    "LEFT JOIN submission_attempts AS attempt "
                    "ON attempt.id = history.response_version_id "
                    "WHERE history.response_version_id IS NOT NULL AND attempt.id IS NULL"
                )
            ).scalar_one()
            assert invalid_links == 0
        with legacy_engine.begin() as connection:
            with pytest.raises(IntegrityError, match="immutable"):
                connection.execute(
                    text(
                        "UPDATE assessment_legacy_history SET source_score = 0 "
                        "WHERE source_table = 'submission_attempts'"
                    )
                )
    finally:
        legacy_engine.dispose()

    after_manifest = database_manifest(legacy_path)
    for table_name in {
        "submission_attempts",
        "legacy_learner_results",
        "legacy_quality_judge_results",
    }:
        assert after_manifest[table_name] == before_manifest[table_name]


def test_assessor_review_migration_backfills_history_and_blocks_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "assessor-review-history.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260816_0020")
    engine = create_engine(database_url)
    session = Session(engine)
    try:
        attempt, _, _, _, owner = _attempt_context(session)
        decision = _provisional_decision(session, attempt)
        session.commit()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO assessor_reviews "
                    "(id, assessment_decision_id, assessor_user_id, action, prior_result, "
                    "new_result, reason, reviewed_at) VALUES "
                    "('review-history-1', :decision, :owner, 'RETURN', NULL, NULL, "
                    "'First retained review.', '2026-08-16T09:00:00+00:00'), "
                    "('review-history-2', :decision, :owner, 'RETURN', NULL, NULL, "
                    "'Second retained review.', '2026-08-16T09:01:00+00:00')"
                ),
                {"decision": decision.id, "owner": owner.id},
            )
    finally:
        session.close()
        engine.dispose()

    command.upgrade(config, "head")
    upgraded = create_engine(database_url)
    try:
        with upgraded.connect() as connection:
            rows = connection.execute(
                text("SELECT id, review_revision FROM assessor_reviews ORDER BY review_revision")
            ).all()
        assert rows == [("review-history-1", 1), ("review-history-2", 2)]
        with pytest.raises(
            RuntimeError, match="cannot downgrade populated assessor review history"
        ):
            command.downgrade(config, "20260816_0020")
    finally:
        upgraded.dispose()


def test_assessment_migration_is_repeat_safe(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        first_rows = _legacy_history_rows(engine)
        with engine.connect() as connection:
            first_audit_count = connection.execute(
                text(
                    "SELECT COUNT(*) FROM audit_events "
                    "WHERE action = 'assessment_legacy_result_migrated'"
                )
            ).scalar_one()
        assert first_audit_count == 1
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '20260815_0017'"))
    finally:
        engine.dispose()

    # This represents a process that committed the archived rows but was not
    # able to mark the revision complete.  Re-running must not duplicate data.
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert _legacy_history_rows(engine) == first_rows
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE action = 'assessment_legacy_result_migrated'"
                    )
                ).scalar_one()
                == first_audit_count
            )
        with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="migration-only"):
                connection.execute(
                    text(
                        "INSERT INTO assessment_legacy_history "
                        "(id, source_table, source_record_id, migration_revision, migration_actor, "
                        "migration_reason, archived_at) "
                        "VALUES ('duplicate-history', 'submission_attempts', "
                        "'00000000-0000-4000-8000-000000000521', '20260815_0018', "
                        "'untrusted', 'DUPLICATE', CURRENT_TIMESTAMP)"
                    )
                )
    finally:
        engine.dispose()


def test_assessment_migration_replaces_stale_insert_guard_on_rerun(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text("DROP TRIGGER trg_assessment_legacy_history_migration_only_insert")
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_assessment_legacy_history_migration_only_insert "
                    "BEFORE INSERT ON assessment_legacy_history BEGIN SELECT 1; END"
                )
            )
            connection.execute(text("UPDATE alembic_version SET version_num = '20260815_0017'"))
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            with pytest.raises(IntegrityError, match="migration-only"):
                connection.execute(
                    text(
                        "INSERT INTO assessment_legacy_history "
                        "(id, source_table, source_record_id, migration_revision, migration_actor, "
                        "migration_reason, archived_at) "
                        "VALUES ('forged-history', 'submission_attempts', 'forged-source', "
                        "'20260815_0018', 'untrusted', 'FORGED', CURRENT_TIMESTAMP)"
                    )
                )
    finally:
        engine.dispose()


def test_assessment_migration_rejects_partial_history_schema_for_recovery(tmp_path: Path) -> None:
    database_path = tmp_path / "partial-assessment-history.db"
    config = migration_config(f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260815_0017")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE assessment_legacy_history "
                    "(id TEXT PRIMARY KEY, source_table TEXT, source_record_id TEXT)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO assessment_legacy_history "
                    "(id, source_table, source_record_id) "
                    "VALUES ('partial-history', 'submission_attempts', 'partial-row')"
                )
            )
        partial_manifest = database_manifest(database_path)
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="exists but is incomplete"):
        command.upgrade(config, "head")

    assert database_manifest(database_path) == partial_manifest
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("20260815_0017")
    finally:
        engine.dispose()


def test_assessment_migration_rejects_stale_same_name_history_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "stale-assessment-history.db"
    config = migration_config(f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260815_0017")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE assessment_legacy_history ("
                    "id VARCHAR(255) NOT NULL PRIMARY KEY, "
                    "source_table VARCHAR(100) NOT NULL, "
                    "source_record_id VARCHAR(255) NOT NULL, "
                    "response_version_id VARCHAR(36), "
                    "source_status VARCHAR(100), source_result VARCHAR(100), "
                    "source_score TEXT, mapped_result VARCHAR(20), "
                    "migration_revision VARCHAR(32) NOT NULL, "
                    "migration_actor VARCHAR(255) NOT NULL, "
                    "migration_reason VARCHAR(255) NOT NULL, archived_at DATETIME NOT NULL, "
                    "CONSTRAINT ck_assessment_legacy_history_assessment_legacy_history_mapped_result "
                    "CHECK (mapped_result IS NULL OR mapped_result = 'INCOMPLETE'), "
                    "CONSTRAINT uq_assessment_legacy_history_source_record "
                    "UNIQUE (source_table, source_record_id), "
                    "CONSTRAINT fk_assessment_legacy_history_response_version_id_submission_attempts "
                    "FOREIGN KEY(response_version_id) REFERENCES submission_attempts(id) ON DELETE CASCADE)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_assessment_legacy_history_response "
                    "ON assessment_legacy_history(response_version_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_assessment_legacy_history_immutable_update "
                    "BEFORE UPDATE ON assessment_legacy_history BEGIN SELECT 1; END"
                )
            )
            connection.execute(
                text(
                    "CREATE TRIGGER trg_assessment_legacy_history_immutable_delete "
                    "BEFORE DELETE ON assessment_legacy_history BEGIN SELECT 1; END"
                )
            )
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="exists but is incomplete"):
        command.upgrade(config, "head")


def test_numeric_scores_are_preserved_but_never_mapped_to_pass(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        rows = _legacy_history_rows(engine)
        numeric_rows = [row for row in rows if row["source_table"] == "submission_attempts"]
        assert {row["source_score"] for row in numeric_rows} == {15, 92}
        assert all(row["mapped_result"] is None for row in numeric_rows)
        assert all(row["mapped_result"] != "PASS" for row in rows)
    finally:
        engine.dispose()


def test_legacy_fail_mapping_keeps_source_and_reason(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        rows = _legacy_history_rows(engine)
        fail_row = next(row for row in rows if row["source_record_id"] == "legacy-learner-fail")
        assert fail_row == {
            "source_table": "legacy_learner_results",
            "source_record_id": "legacy-learner-fail",
            "response_version_id": "00000000-0000-4000-8000-000000000522",
            "source_status": None,
            "source_result": "FAIL",
            "source_score": 15,
            "mapped_result": "INCOMPLETE",
            "migration_revision": "20260815_0018",
            "migration_actor": "alembic:20260815_0018",
            "migration_reason": "LEGACY_PUBLIC_FAIL_TO_INCOMPLETE",
        }
        unknown_row = next(
            row for row in rows if row["source_record_id"] == "legacy-learner-unknown"
        )
        assert unknown_row["mapped_result"] is None
        assert unknown_row["migration_reason"] == "LEGACY_PUBLIC_RESULT_UNMAPPED"
        with engine.connect() as connection:
            audit_row = (
                connection.execute(
                    text(
                        "SELECT actor_reference, action, outcome, resource_type, resource_id, "
                        "deduplication_key FROM audit_events "
                        "WHERE action = 'assessment_legacy_result_migrated'"
                    )
                )
                .mappings()
                .one()
            )
        assert dict(audit_row) == {
            "actor_reference": "alembic:20260815_0018",
            "action": "assessment_legacy_result_migrated",
            "outcome": "success",
            "resource_type": "assessment_legacy_history",
            "resource_id": "legacy_learner_results:legacy-learner-fail",
            "deduplication_key": "assessment-legacy-result:legacy-learner-fail",
        }
    finally:
        engine.dispose()


def test_legacy_learner_result_ids_that_could_collide_in_audit_are_rejected(
    tmp_path: Path,
) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    shared_prefix = "legacy-id-" + ("x" * 221)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO legacy_learner_results (id, response_version_id, result, score) "
                    "VALUES (:first, '00000000-0000-4000-8000-000000000521', 'FAIL', 92), "
                    "(:second, '00000000-0000-4000-8000-000000000522', 'FAIL', 15)"
                ),
                {"first": shared_prefix + "a", "second": shared_prefix + "b"},
            )
        before_manifest = database_manifest(database_path)
    finally:
        engine.dispose()

    with pytest.raises(RuntimeError, match="maximum safe audit source ID length"):
        command.upgrade(config, "head")

    assert database_manifest(database_path) == before_manifest


def test_quality_judge_fail_never_becomes_incomplete(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            decision = connection.execute(
                text(
                    "SELECT decision FROM legacy_quality_judge_results "
                    "WHERE id = 'legacy-quality-judge-fail'"
                )
            ).scalar_one()
            assert (
                connection.execute(text("SELECT COUNT(*) FROM assessment_decisions")).scalar_one()
                == 0
            )
        assert legacy_judge_decision_to_quality_review(decision) is QualityReviewDecision.REJECTED
        assert all(
            row["source_table"] != "legacy_quality_judge_results"
            for row in _legacy_history_rows(engine)
        )
    finally:
        engine.dispose()


def test_assessment_backup_restore_preserves_counts_links_and_digests(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    source_manifest = database_manifest(database_path)

    result = create_verified_backup(database_path, tmp_path / "verified-backups")

    assert result.backup_path.is_file()
    assert result.manifest_path.is_file()
    assert database_manifest(result.backup_path) == source_manifest
    assert result.table_count == len(source_manifest)
    assert result.record_count == sum(table.row_count for table in source_manifest.values())


def test_assessment_populated_downgrade_restores_verified_backup(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    command.upgrade(config, "head")
    before_downgrade = database_manifest(database_path)
    backup = create_verified_backup(database_path, tmp_path / "downgrade-backups")

    with pytest.raises(RuntimeError, match="cannot downgrade populated"):
        command.downgrade(config, "20260815_0017")
    assert database_manifest(database_path) == before_downgrade

    with sqlite3.connect(backup.backup_path) as source_connection:
        with sqlite3.connect(database_path) as restored_connection:
            source_connection.backup(restored_connection)

    assert database_manifest(database_path) == before_downgrade


def test_numeric_only_populated_history_blocks_downgrade(tmp_path: Path) -> None:
    database_path, config = _prepare_legacy_assessment_database(tmp_path)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE legacy_learner_results"))
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT COUNT(*) FROM assessment_legacy_history")
                ).scalar_one()
                == 2
            )
            assert (
                connection.execute(
                    text(
                        "SELECT COUNT(*) FROM audit_events "
                        "WHERE action = 'assessment_legacy_result_migrated'"
                    )
                ).scalar_one()
                == 0
            )
    finally:
        engine.dispose()

    before_downgrade = database_manifest(database_path)
    with pytest.raises(RuntimeError, match="cannot downgrade populated"):
        command.downgrade(config, "20260815_0017")
    assert database_manifest(database_path) == before_downgrade


def test_definition_migration_upgrades_clean_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migrations.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    with engine.connect() as connection:
        achievement_rows = (
            connection.execute(
                text("SELECT id, code, name, description, icon FROM achievements ORDER BY code")
            )
            .mappings()
            .all()
        )
    assert [dict(row) for row in achievement_rows] == [
        {
            "id": "00000000-0000-4000-9000-000000000102",
            "code": "circuit-maker",
            "name": "Circuit Maker",
            "description": "Complete a circuit activity.",
            "icon": "⌁",
        },
        {
            "id": "00000000-0000-4000-9000-000000000101",
            "code": "first-step",
            "name": "First Step",
            "description": "Complete your first learning activity.",
            "icon": "✦",
        },
        {
            "id": "00000000-0000-4000-9000-000000000103",
            "code": "perfect-score",
            "name": "Quantum Ace",
            "description": "Earn a perfect task score.",
            "icon": "★",
        },
    ]
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
        "course_id",
        "learning_outcome_id",
        "marking_criteria",
        "source_references",
        "prerequisite_task_ids",
        "generation_provider",
        "generation_total_tokens",
    } <= task_columns
    assert (
        inspector.get_foreign_keys("material_chunks")[0]["referred_table"] == "learning_materials"
    )
    material_columns = {column["name"] for column in inspector.get_columns("learning_materials")}
    assert {
        "storage_key",
        "file_size_bytes",
        "failure_stage",
        "error_code",
        "processing_revision",
    } <= material_columns
    with engine.connect() as connection:
        scope_triggers = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND name LIKE 'trg_learning_%_scope_%'"
                )
            ).scalars()
        )
    assert scope_triggers == {
        "trg_learning_materials_scope_insert",
        "trg_learning_materials_scope_update",
        "trg_learning_tasks_scope_insert",
        "trg_learning_tasks_scope_update",
    }
    with pytest.raises(IntegrityError, match="invalid learning material scope"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO learning_materials "
                    "(id, course_id, module_id, original_filename, source_url, mime_type, "
                    "content_hash, indexing_status, processing_revision, created_at) "
                    "VALUES ('invalid-material', 'missing-course', NULL, 'notes.pdf', NULL, "
                    "'application/pdf', 'sha256:invalid', 'pending', 0, CURRENT_TIMESTAMP)"
                )
            )
    with pytest.raises(IntegrityError, match="invalid learning task scope"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO learning_tasks "
                    "(id, slug, title, module, description, instructions, task_type, "
                    "difficulty, points, position, course_id, module_id, "
                    "learning_outcome_id, source_references, prerequisite_task_ids, "
                    "generation_input_tokens, generation_output_tokens, "
                    "generation_total_tokens, generation_estimated_cost) "
                    "VALUES ('invalid-task', 'invalid-task', 'Invalid', 'Missing', "
                    "'Invalid', 'Invalid', 'quiz', 'beginner', 10, 1, "
                    "'missing-course', 'missing-module', 'missing-outcome', '[]', '[]', "
                    "0, 0, 0, 0)"
                )
            )
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
    role_assignment_columns = {
        column["name"] for column in inspector.get_columns("role_assignments")
    }
    assert {
        "id",
        "subject_user_id",
        "course_id",
        "role",
        "version",
        "assigned_by_user_id",
        "reason",
        "assigned_at",
        "valid_from",
        "valid_until",
        "revoked_at",
        "revoked_by_user_id",
        "revocation_reason",
        "supersedes_assignment_id",
    } == role_assignment_columns
    assert {index["name"] for index in inspector.get_indexes("role_assignments")} >= {
        "ix_role_assignments_subject_course_role_active"
    }
    role_assignment_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("role_assignments")
    }
    assert {
        "ck_role_assignments_role_assignment_reason",
        "ck_role_assignments_role_assignment_revocation_shape",
        "ck_role_assignments_role_assignment_valid_window",
        "ck_role_assignments_role_assignment_version",
        "ck_role_assignments_scoped_role",
    } <= role_assignment_checks
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM role_assignments")).scalar_one() == 0
        assessment_triggers = set(
            connection.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' "
                    "AND name LIKE 'trg_assessment_%'"
                )
            ).scalars()
        )
    assert assessment_triggers >= {
        "trg_assessment_definitions_scope_insert",
        "trg_assessment_definition_versions_scope_insert",
        "trg_assessment_definition_versions_immutable_update",
    }
    definition_columns = {
        column["name"] for column in inspector.get_columns("assessment_definition_versions")
    }
    assert {
        "claim",
        "supporting_evidence",
        "contradicting_evidence",
        "insufficient_evidence",
        "task_conditions",
        "next_action_contract",
        "permitted_tools",
        "instructional_support",
        "access_conditions",
        "transfer_rule",
        "evidence_sufficiency",
        "formal_result_eligible",
        "result_eligibility_declared_at",
    } <= definition_columns
    assert (
        not {
            "score",
            "mark",
            "percentage",
            "grade_band",
        }
        & definition_columns
    )
    assert "ck_task_approvals_task_approval_reason" in {
        constraint["name"] for constraint in inspector.get_check_constraints("task_approvals")
    }
    _assert_cross_course_definition_link_is_rejected(engine)
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


def test_default_achievement_seed_preserves_existing_codes_and_fills_missing(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "existing-achievements.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260726_0012")
    legacy_id = "00000000-0000-4000-8000-000000000999"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO achievements (id, code, name, description, icon) "
                "VALUES (:id, 'first-step', 'Existing First Step', "
                "'Existing deployment definition.', '!')"
            ),
            {"id": legacy_id},
        )
    engine.dispose()

    command.upgrade(config, "head")

    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        rows = connection.execute(text("SELECT id, code FROM achievements ORDER BY code")).all()
    upgraded_engine.dispose()
    assert rows == [
        ("00000000-0000-4000-9000-000000000102", "circuit-maker"),
        (legacy_id, "first-step"),
        ("00000000-0000-4000-9000-000000000103", "perfect-score"),
    ]


def test_role_assignment_migration_does_not_grant_existing_educators(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "existing-educator.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = migration_config(database_url)
    command.upgrade(config, "20260726_0014")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        educator_id = connection.execute(
            text(
                "INSERT INTO users "
                "(email, password_hash, full_name, role, is_active) "
                "VALUES ('educator@example.edu', 'not-a-real-hash', "
                "'Existing Educator', 'educator', 1) RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO courses "
                "(id, educator_id, code, title, description, state, enrollment_open, "
                "created_at, updated_at) VALUES "
                "('00000000-0000-4000-8000-000000000301', :educator_id, 'QNT301', "
                "'Existing Course', '', 'draft', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"educator_id": educator_id},
        )
    engine.dispose()

    command.upgrade(config, "head")

    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM role_assignments")).scalar_one() == 0
    upgraded_engine.dispose()


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
