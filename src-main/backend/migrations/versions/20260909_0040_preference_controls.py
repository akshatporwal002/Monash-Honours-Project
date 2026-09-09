"""Connect support controls to the published preference history without replacing it."""

import sqlalchemy as sa
from alembic import op

revision = "20260909_0040"
down_revision = "20260909_0039"
branch_labels = None
depends_on = None


def upgrade():
    table = "learner_preference_revisions"
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
    for name, default in (
        ("support_amount", "standard"),
        ("feedback_form", "inline"),
        ("action", "save"),
    ):
        if name not in columns:
            op.add_column(
                table,
                sa.Column(
                    name,
                    sa.String(10 if name == "action" else 20),
                    nullable=False,
                    server_default=default,
                ),
            )
    for operation in ("update", "delete"):
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {table}_no_{operation}"))
        op.execute(
            sa.text(
                f"CREATE TRIGGER {table}_no_{operation} BEFORE {operation.upper()} ON {table} BEGIN SELECT RAISE(ABORT, 'Preference history is protected; learner preference revisions are append-only'); END"
            )
        )
    op.execute(
        sa.text(
            "CREATE TRIGGER IF NOT EXISTS learner_preference_revisions_append BEFORE INSERT ON learner_preference_revisions WHEN NEW.revision != COALESCE((SELECT MAX(revision) FROM learner_preference_revisions WHERE learner_id=NEW.learner_id), 0) + 1 OR EXISTS(SELECT 1 FROM learner_preference_revisions WHERE id=NEW.id OR (learner_id=NEW.learner_id AND idempotency_key=NEW.idempotency_key)) BEGIN SELECT RAISE(ABORT, 'Preference history is protected; learner preference revisions are append-only'); END"
        )
    )


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM learner_preference_revisions"))
        .scalar_one()
    ):
        raise RuntimeError("Preference history is protected; restore a verified backup")
    # Retain additive default columns so historical metadata fixtures remain readable.
    op.execute(sa.text("DROP TRIGGER IF EXISTS learner_preference_revisions_append"))
