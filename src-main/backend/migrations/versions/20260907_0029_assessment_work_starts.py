"""Freeze the approved standard when assessed work begins.

Revision ID: 20260907_0029
Revises: 20260907_0028
"""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0029"
down_revision = "20260907_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if not sa.inspect(connection).has_table("assessment_work_starts"):
        references = [
            ("student_id", "users", sa.Integer()),
            ("task_id", "learning_tasks", sa.String(36)),
            ("course_id", "courses", sa.String(36)),
            ("assessment_definition_version_id", "assessment_definition_versions", sa.String(36)),
            ("task_form_version_id", "task_form_versions", sa.String(36)),
            ("bloom_target_version_id", "bloom_target_versions", sa.String(36)),
            ("pass_rule_version_id", "pass_rule_versions", sa.String(36)),
            ("task_approval_id", "task_approvals", sa.String(36)),
        ]
        op.create_table(
            "assessment_work_starts",
            sa.Column("id", sa.String(36), primary_key=True),
            *[
                sa.Column(
                    name, kind, sa.ForeignKey(f"{target}.id", ondelete="RESTRICT"), nullable=False
                )
                for name, target, kind in references
            ],
            sa.Column("declared_conditions", sa.JSON(), nullable=False),
            sa.Column("source_references", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("student_id", "task_id", name="uq_assessment_work_student_task"),
        )
    for table in ("submission_drafts", "submission_attempts"):
        if "assessment_work_start_id" in {
            c["name"] for c in sa.inspect(connection).get_columns(table)
        }:
            continue
        if connection.dialect.name == "sqlite":
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} ADD COLUMN assessment_work_start_id VARCHAR(36) REFERENCES assessment_work_starts(id)"
                )
            )
        else:
            op.add_column(
                table, sa.Column("assessment_work_start_id", sa.String(36), nullable=True)
            )
            op.create_foreign_key(
                f"fk_{table}_work_start",
                table,
                "assessment_work_starts",
                ["assessment_work_start_id"],
                ["id"],
            )
    if connection.dialect.name == "sqlite":
        for _, _, statement in work_guards():
            op.execute(sa.text(statement))


def downgrade() -> None:
    _preflight_downgrade()
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessment_work_starts")).scalar_one():
        raise RuntimeError(
            "Assessment work history is protected; restore a verified backup instead"
        )
    if connection.dialect.name == "sqlite":
        for _, name, _ in work_guards():
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    for table in ("submission_attempts", "submission_drafts"):
        if connection.dialect.name != "sqlite":
            op.drop_constraint(f"fk_{table}_work_start", table, type_="foreignkey")
        op.drop_column(table, "assessment_work_start_id")
    op.drop_table("assessment_work_starts")


def work_guards() -> list[tuple[str, str, str]]:
    guards = []
    table = "assessment_work_starts"
    scope = """NOT EXISTS (
        SELECT 1 FROM task_form_versions f
        JOIN assessment_definition_versions d ON d.id = f.assessment_definition_version_id
        JOIN bloom_target_versions b ON b.assessment_definition_version_id = d.id
        JOIN pass_rule_versions r ON r.assessment_definition_version_id = d.id
        JOIN task_approvals a ON a.task_form_version_id = f.id
        WHERE f.id = NEW.task_form_version_id AND f.learning_task_id = NEW.task_id
        AND f.course_id = NEW.course_id AND d.id = NEW.assessment_definition_version_id
        AND b.id = NEW.bloom_target_version_id AND r.id = NEW.pass_rule_version_id
        AND a.id = NEW.task_approval_id AND a.assessment_definition_version_id = d.id
        AND f.approval_state = 'APPROVED' AND d.approval_state = 'APPROVED'
        AND a.approval_state = 'APPROVED' AND f.task_revision_id IS NOT NULL
        AND a.task_review_event_id IS NOT NULL)"""
    clauses = [
        (table, "scope", "INSERT", scope),
        (table, "no_update", "UPDATE", "1"),
        (table, "no_delete", "DELETE", "1"),
        (
            table,
            "no_replace",
            "INSERT",
            "EXISTS (SELECT 1 FROM assessment_work_starts WHERE id = NEW.id OR (student_id = NEW.student_id AND task_id = NEW.task_id))",
        ),
    ]
    for target in ("submission_drafts", "submission_attempts"):
        for action in ("INSERT", "UPDATE"):
            clauses.append(
                (
                    target,
                    "work_scope_" + action.lower(),
                    action,
                    "NEW.assessment_work_start_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assessment_work_starts w WHERE w.id = NEW.assessment_work_start_id AND w.student_id = NEW.student_id AND w.task_id = NEW.task_id"
                    + (
                        " AND w.task_form_version_id = NEW.task_form_version_id AND EXISTS (SELECT 1 FROM submission_drafts d WHERE d.id = NEW.draft_id AND d.assessment_work_start_id = w.id)"
                        if target == "submission_attempts"
                        else ""
                    )
                    + ")",
                )
            )
        clauses.append(
            (
                target,
                "work_binding",
                "UPDATE",
                "OLD.assessment_work_start_id IS NOT NULL AND NEW.assessment_work_start_id IS NOT OLD.assessment_work_start_id",
            )
        )
        clauses.append(
            (
                target,
                "work_replace",
                "INSERT",
                f"EXISTS (SELECT 1 FROM {target} WHERE (id = NEW.id"
                + (
                    " OR (student_id = NEW.student_id AND task_id = NEW.task_id)"
                    if target == "submission_drafts"
                    else ""
                )
                + ") AND assessment_work_start_id IS NOT NULL)",
            )
        )
    for target, suffix, action, condition in clauses:
        name = f"{target}_{suffix}"
        guards.append(
            (
                target,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {target} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Assessment work history or scope is protected'); END",
            )
        )
    return guards


_PROTECTED_DOWNGRADE_TABLES = (
    "role_assignments",
    "assessment_definitions",
    "outcome_versions",
    "assessment_definition_versions",
    "bloom_targets",
    "bloom_target_versions",
    "criteria",
    "criterion_versions",
    "pass_rules",
    "pass_rule_versions",
    "task_forms",
    "task_form_versions",
    "task_approvals",
    "assessment_attempts",
    "criterion_evaluations",
    "assessment_decisions",
    "assessor_reviews",
    "reassessment_links",
    "appeals_or_corrections",
    "learner_model_snapshots",
    "learner_outcome_estimates",
    "learner_model_evidence_links",
    "evidence_artifacts",
    "learning_evidence",
    "evidence_links",
    "assessment_legacy_history",
)


def _preflight_downgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if connection.execute(
        sa.text("SELECT COUNT(*) FROM assessor_eligibility_approvals")
    ).scalar_one():
        raise RuntimeError(
            "Assessor eligibility history is protected; restore a verified backup instead"
        )
    for table in ("circuit_versions", "simulation_runs", "simulation_outcomes"):
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "Simulation evidence is protected; restore a verified backup instead"
            )
    for table in ("source_revisions", "source_passages", "source_approvals", "source_uses"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("Source history is protected; restore a verified backup instead")
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessor_reviews")).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated assessor review history; restore a verified backup instead"
        )
    if connection.execute(sa.text("SELECT COUNT(*) FROM assessment_evaluation_jobs")).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated assessment evaluation jobs; restore a verified backup instead"
        )
    for table in _PROTECTED_DOWNGRADE_TABLES:
        if (
            inspector.has_table(table)
            and connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        ):
            raise RuntimeError(
                "cannot downgrade populated protected learner-model, evidence, or assessment history; restore a verified backup instead"
            )
    if connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM learning_materials WHERE processing_attempts > 0 OR indexing_status = 'processing'"
        )
    ).scalar_one():
        raise RuntimeError(
            "cannot downgrade populated material processing claims; restore a verified backup instead"
        )

    for table in ("task_revisions", "task_review_events"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(
                "Task review history is protected; restore a verified backup instead"
            )


# Frozen migration SQL; do not import live application models.
