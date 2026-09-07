"""Immutable episode checkpoints and transfer starts, with lossless responses."""

import sqlalchemy as sa
from alembic import op

revision = "20260907_0030"
down_revision = "20260907_0029"
branch_labels = None
depends_on = None


def upgrade():
    _expand_task_type_check()
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
                        f"ALTER TABLE simulation_runs ADD COLUMN {name} VARCHAR(36) REFERENCES {target}(id) ON DELETE RESTRICT"
                    )
                )
            else:
                op.add_column("simulation_runs", sa.Column(name, sa.String(36)))
                op.create_foreign_key(
                    f"fk_simulation_{name}",
                    "simulation_runs",
                    target,
                    [name],
                    ["id"],
                    ondelete="RESTRICT",
                )
    if connection.dialect.name == "sqlite":
        _normalize_simulation_foreign_keys()
        for _, _, statement in episode_guards():
            op.execute(sa.text(statement))


def downgrade():
    _preflight_downgrade()
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM learning_tasks WHERE task_type IN ('prediction','reasoning','explanation','revision','reflection','transfer')"
        )
    ).scalar_one():
        raise RuntimeError("Episode task types are protected; restore a verified backup instead")
    for table in ("episode_checkpoints", "episode_stage_starts"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError("Episode history is protected; restore a verified backup instead")
    for table in ("submission_drafts", "submission_attempts"):
        if connection.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} WHERE episode IS NOT NULL AND CAST(episode AS TEXT) != 'null'"
            )
        ).scalar_one():
            raise RuntimeError("Episode responses are protected; restore a verified backup instead")
    _expand_task_type_check(include_episode=False)
    if connection.dialect.name == "sqlite":
        for _, name, _ in episode_guards():
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {name}"))
    if connection.dialect.name == "sqlite":
        _normalize_simulation_foreign_keys(remove=True)
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


_LEGACY_TASK_TYPES = (
    "quiz",
    "code",
    "circuit",
    "multiple_choice",
    "multiple_answer",
    "short_answer",
    "code_explanation",
    "code_completion",
    "quantum_circuit",
)
_EPISODE_TASK_TYPES = (
    "prediction",
    "reasoning",
    "explanation",
    "revision",
    "reflection",
    "transfer",
)


def _expand_task_type_check(include_episode=True):
    """Rebuild only the SQLite task table atomically, retaining every dependent trigger."""
    import re

    connection = op.get_bind()
    allowed = ", ".join(
        repr(kind)
        for kind in (*_LEGACY_TASK_TYPES, *(_EPISODE_TASK_TYPES if include_episode else ()))
    )
    if connection.dialect.name != "sqlite":
        checks = sa.inspect(connection).get_check_constraints("learning_tasks")
        prior = next(item for item in checks if "task_type" in item["sqltext"])
        op.drop_constraint(op.f(prior["name"]), "learning_tasks", type_="check")
        op.create_check_constraint(
            op.f(prior["name"]), "learning_tasks", f"task_type IN ({allowed})"
        )
        return
    ddl = connection.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='learning_tasks'")
    ).scalar_one()
    if (
        all(repr(kind) in ddl for kind in _EPISODE_TASK_TYPES)
        if include_episode
        else not any(repr(kind) in ddl for kind in _EPISODE_TASK_TYPES)
    ):
        return
    revised, count = re.subn(
        r"CHECK\s*\(\s*task_type\s+IN\s*\([^)]*\)\s*\)",
        f"CHECK (task_type IN ({allowed}))",
        ddl,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise RuntimeError("Task type constraint could not be identified safely")
    _rebuild_sqlite_table("learning_tasks", revised)


def _rebuild_sqlite_table(table, revised, excluded_columns=()):
    import re

    connection = op.get_bind()
    if table not in {"learning_tasks", "simulation_runs"}:
        raise RuntimeError("Unexpected episode migration table")
    temporary = "_task14_" + table
    revised = re.sub(
        r'CREATE TABLE\s+["`\[]?' + table + r'["`\]]?',
        "CREATE TABLE " + temporary,
        revised,
        count=1,
        flags=re.IGNORECASE,
    )
    triggers = list(
        connection.execute(
            sa.text("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL")
        )
    )
    indexes = list(
        connection.execute(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:table AND sql IS NOT NULL"
            ),
            {"table": table},
        ).scalars()
    )
    columns = ", ".join(
        '"' + item["name"].replace('"', '""') + '"'
        for item in sa.inspect(connection).get_columns(table)
        if item["name"] not in excluded_columns
    )
    with op.get_context().autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            for name, _ in triggers:
                connection.exec_driver_sql('DROP TRIGGER "' + name.replace('"', '""') + '"')
            connection.exec_driver_sql(revised)
            connection.exec_driver_sql(
                f"INSERT INTO {temporary} ({columns}) SELECT {columns} FROM {table}"
            )
            connection.exec_driver_sql(f"DROP TABLE {table}")
            connection.exec_driver_sql(f"ALTER TABLE {temporary} RENAME TO {table}")
            for sql in indexes:
                connection.exec_driver_sql(sql)
            for _, sql in triggers:
                connection.exec_driver_sql(sql)
            if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Episode migration foreign key validation failed")
            connection.exec_driver_sql("COMMIT")
        except BaseException:
            connection.exec_driver_sql("ROLLBACK")
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _normalize_simulation_foreign_keys(remove=False):
    import re

    connection = op.get_bind()
    ddl = connection.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE name='simulation_runs' AND type='table'")
    ).scalar_one()
    revised = ddl
    names = ("prediction_checkpoint_id", "episode_stage_start_id")
    for name, target in zip(names, ("episode_checkpoints", "episode_stage_starts")):
        fkname = f"fk_simulation_runs_{name}_{target}"
        if remove:
            revised = re.sub(
                r"\b"
                + name
                + r" VARCHAR\(36\)(?: REFERENCES "
                + target
                + r"\(id\)(?: ON DELETE RESTRICT)?)?,\s*",
                "",
                revised,
            )
            revised = re.sub(
                r",\s*CONSTRAINT "
                + fkname
                + r" FOREIGN KEY\("
                + name
                + r"\) REFERENCES "
                + target
                + r" \(id\) ON DELETE RESTRICT",
                "",
                revised,
            )
        elif fkname not in revised:
            revised = revised.replace(
                f"{name} VARCHAR(36) REFERENCES {target}(id) ON DELETE RESTRICT",
                f"{name} VARCHAR(36)",
            )
            revised = (
                revised.rsplit(")", 1)[0]
                + f", CONSTRAINT {fkname} FOREIGN KEY({name}) REFERENCES {target} (id) ON DELETE RESTRICT)"
            )
    if revised != ddl:
        _rebuild_sqlite_table("simulation_runs", revised, names if remove else ())


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
