"""Immutable episode checkpoints and transfer starts, with lossless responses."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0030"
down_revision = "20260907_0029"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table in ("submission_drafts", "submission_attempts"):
        if "episode" not in {c["name"] for c in sa.inspect(connection).get_columns(table)}:
            op.add_column(table, sa.Column("episode", sa.JSON(), nullable=True))
    for table in ("episode_stage_starts", "episode_checkpoints"):
        if sa.inspect(connection).has_table(table):
            continue
        refs = [
            ("student_id", "users", sa.Integer()),
            ("task_id", "learning_tasks", sa.String(36)),
            ("assessment_work_start_id", "assessment_work_starts", sa.String(36)),
            ("task_form_version_id", "task_form_versions", sa.String(36)),
        ]
        extra = (
            [
                sa.Column("supported_snapshot", sa.JSON(), nullable=False),
                sa.UniqueConstraint(
                    "assessment_work_start_id", "part_id", name="uq_episode_transfer_start"
                ),
            ]
            if table == "episode_stage_starts"
            else [
                sa.Column(
                    "stage_start_id",
                    sa.String(36),
                    sa.ForeignKey("episode_stage_starts.id", ondelete="RESTRICT"),
                ),
                *[
                    sa.Column(name, sa.JSON(), nullable=False)
                    for name in ("prediction", "input_content", "snapshot")
                ],
            ]
        )
        op.create_table(
            table,
            sa.Column("id", sa.String(36), primary_key=True),
            *[
                sa.Column(
                    name, kind, sa.ForeignKey(f"{target}.id", ondelete="RESTRICT"), nullable=False
                )
                for name, target, kind in refs
            ],
            sa.Column("part_id", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            *extra,
        )
    for name, target in (
        ("prediction_checkpoint_id", "episode_checkpoints"),
        ("episode_stage_start_id", "episode_stage_starts"),
    ):
        if name not in {c["name"] for c in sa.inspect(connection).get_columns("simulation_runs")}:
            if connection.dialect.name == "sqlite":
                op.execute(
                    sa.text(
                        f"ALTER TABLE simulation_runs ADD COLUMN {name} VARCHAR(36) REFERENCES {target}(id)"
                    )
                )
            else:
                op.add_column("simulation_runs", sa.Column(name, sa.String(36)))
                op.create_foreign_key(
                    f"fk_simulation_{name}", "simulation_runs", target, [name], ["id"]
                )
    if connection.dialect.name == "sqlite":
        for _, _, statement in episode_guards():
            op.execute(sa.text(statement))


def downgrade():
    connection = op.get_bind()
    for table in ("episode_checkpoints", "episode_stage_starts"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("Episode history is protected; restore a verified backup instead")
    for table in ("submission_drafts", "submission_attempts"):
        if connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE episode IS NOT NULL AND episode != 'null'")
        ).scalar_one():
            raise RuntimeError("Episode responses are protected; restore a verified backup instead")
    if connection.dialect.name == "sqlite":
        for _, name, _ in episode_guards():
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    for name in ("prediction_checkpoint_id", "episode_stage_start_id"):
        if connection.dialect.name != "sqlite":
            op.drop_constraint(f"fk_simulation_{name}", "simulation_runs", type_="foreignkey")
        op.drop_column("simulation_runs", name)
    op.drop_table("episode_checkpoints")
    op.drop_table("episode_stage_starts")
    for table in ("submission_drafts", "submission_attempts"):
        op.drop_column(table, "episode")


# Frozen migration guards. No live application imports.
def episode_guards():
    clauses = []
    for table in ("episode_checkpoints", "episode_stage_starts"):
        for action in ("UPDATE", "DELETE"):
            clauses.append((table, f"{table}_no_{action.lower()}", action, "1"))
        clauses.append(
            (
                table,
                f"{table}_no_replace",
                "INSERT",
                f"EXISTS(SELECT 1 FROM {table} WHERE id=NEW.id)",
            )
        )
        clauses.append(
            (
                table,
                f"{table}_scope",
                "INSERT",
                "NOT EXISTS(SELECT 1 FROM assessment_work_starts w WHERE w.id=NEW.assessment_work_start_id AND w.task_id=NEW.task_id AND w.student_id=NEW.student_id AND w.task_form_version_id=NEW.task_form_version_id)",
            )
        )
    clauses.append(
        (
            "episode_checkpoints",
            "episode_checkpoint_stage_scope",
            "INSERT",
            "NEW.stage_start_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM episode_stage_starts s WHERE s.id=NEW.stage_start_id AND s.assessment_work_start_id=NEW.assessment_work_start_id AND s.part_id=NEW.part_id)",
        )
    )
    clauses.append(
        (
            "episode_stage_starts",
            "episode_stage_no_scope_replace",
            "INSERT",
            "EXISTS(SELECT 1 FROM episode_stage_starts WHERE assessment_work_start_id=NEW.assessment_work_start_id AND part_id=NEW.part_id)",
        )
    )
    return [
        (
            table,
            name,
            f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Episode history or scope is protected'); END",
        )
        for table, name, action, condition in clauses
    ]
