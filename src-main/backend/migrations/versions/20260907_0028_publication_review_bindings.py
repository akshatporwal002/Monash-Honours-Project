"""Bind new formal task forms to exact teaching revisions and review events.

Revision ID: 20260907_0028
Revises: 20260907_0027
"""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0028"
down_revision = "20260907_0027"
branch_labels = None
depends_on = None

_REFERENCES = (
    ("task_form_versions", "task_revision_id", "task_revisions"),
    ("task_approvals", "task_review_event_id", "task_review_events"),
)


def upgrade() -> None:
    connection = op.get_bind()
    for table, column, target in _REFERENCES:
        if column in {item["name"] for item in sa.inspect(connection).get_columns(table)}:
            continue
        if connection.dialect.name == "sqlite":
            # Nullable references preserve legacy evidence without rebuilding protected tables.
            op.execute(
                sa.text(
                    f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(36) REFERENCES {target}(id)"
                )
            )
        else:
            op.add_column(table, sa.Column(column, sa.String(36), nullable=True))
            op.create_foreign_key(f"fk_{table}_{column}_{target}", table, target, [column], ["id"])

    if connection.dialect.name == "sqlite":
        for _, _, statement in binding_guards():
            op.execute(sa.text(statement))


def downgrade() -> None:
    _preflight_downgrade()
    connection = op.get_bind()
    # Check all newly affected tables before the first schema change.
    for table, _, _ in _REFERENCES:
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(
                "Formal publication history is protected; restore a verified backup instead"
            )
    if connection.dialect.name == "sqlite":
        for _, name, _ in binding_guards():
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    for table, column, target in reversed(_REFERENCES):
        if connection.dialect.name != "sqlite":
            op.drop_constraint(f"fk_{table}_{column}_{target}", table, type_="foreignkey")
        op.drop_column(table, column)


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
def binding_guards() -> list[tuple[str, str, str]]:
    guards = []
    for table, check in (
        (
            "task_form_versions",
            "NEW.task_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM task_revisions r WHERE r.id = NEW.task_revision_id AND r.course_id = NEW.course_id AND r.task_id = NEW.learning_task_id)",
        ),
        (
            "task_approvals",
            "NEW.task_review_event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM task_review_events e JOIN task_form_versions f ON f.task_revision_id = e.task_revision_id WHERE e.id = NEW.task_review_event_id AND e.state = 'APPROVED' AND e.course_id = NEW.course_id AND f.id = NEW.task_form_version_id AND f.course_id = NEW.course_id AND f.assessment_definition_version_id = NEW.assessment_definition_version_id)",
        ),
    ):
        for action in ("INSERT", "UPDATE"):
            name = f"publication_{table}_scope_{action.lower()}"
            guards.append(
                (
                    table,
                    name,
                    f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} WHEN {check} BEGIN SELECT RAISE(ABORT, 'Invalid publication review scope'); END",
                )
            )
    for table, column, condition in (
        (
            "task_form_versions",
            "task_revision_id",
            " AND (OLD.approval_state != 'DRAFT' OR NEW.approval_state != 'DRAFT')",
        ),
        ("task_approvals", "task_review_event_id", ""),
    ):
        name = f"publication_{table}_binding_immutable"
        guards.append(
            (
                table,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE UPDATE ON {table} WHEN NEW.{column} IS NOT OLD.{column}{condition} BEGIN SELECT RAISE(ABORT, 'Publication review bindings are immutable'); END",
            )
        )
    for table, unique in (
        ("task_form_versions", "task_form_id = NEW.task_form_id AND version = NEW.version"),
        (
            "task_approvals",
            "task_form_version_id = NEW.task_form_version_id AND approval_state = NEW.approval_state",
        ),
    ):
        name = f"publication_{table}_no_replace"
        guards.append(
            (
                table,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id OR ({unique})) BEGIN SELECT RAISE(ABORT, 'Publication review bindings are immutable'); END",
            )
        )
    return guards
