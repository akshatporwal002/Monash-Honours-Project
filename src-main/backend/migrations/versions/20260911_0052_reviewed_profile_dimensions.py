"""Extend reviewed profile dimensions while preserving every snapshot and trigger."""

import re

import sqlalchemy as sa
from alembic import op

revision = "20260911_0052"
down_revision = "20260911_0051"
branch_labels = None
depends_on = None

_ADDED = (
    "USEFUL_EXPLANATION_FORM",
    "SUCCESSFUL_STRATEGY",
    "UNSUCCESSFUL_STRATEGY",
    "SUPPORT_NEEDS",
)


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        ddl = connection.execute(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='learner_outcome_estimates'"
            )
        ).scalar_one()
        missing = [value for value in _ADDED if "'" + value + "'" not in ddl]
        if not missing and re.search(r"\bdimension\s+VARCHAR\(23\)", ddl, re.I):
            return
        added = ", " + ", ".join("'" + value + "'" for value in missing) if missing else ""
        revised, count = re.subn(
            r"(CHECK\s*\(\s*dimension\s+IN\s*\()([^)]*)(\)\s*\))",
            lambda match: match[1] + match[2] + added + match[3],
            ddl,
            flags=re.I,
        )
        if count != 1:
            raise RuntimeError(
                "Learner profile dimension constraint could not be identified safely"
            )
        revised, width_count = re.subn(
            r"(\bdimension\s+VARCHAR)\(\d+\)", r"\1(23)", revised, flags=re.I
        )
        if width_count != 1:
            raise RuntimeError("Learner profile dimension width could not be identified safely")
        _rebuild_sqlite_table("learner_outcome_estimates", revised)
    else:
        checks = sa.inspect(connection).get_check_constraints("learner_outcome_estimates")
        prior = next(item for item in checks if "dimension IN" in item["sqltext"])
        op.alter_column(
            "learner_outcome_estimates", "dimension", type_=sa.String(23), existing_nullable=False
        )
        if all("'" + value + "'" in prior["sqltext"] for value in _ADDED):
            return
        revised = prior["sqltext"].replace(
            ")", ", " + ", ".join("'" + value + "'" for value in _ADDED) + ")", 1
        )
        op.drop_constraint(op.f(prior["name"]), "learner_outcome_estimates", type_="check")
        op.create_check_constraint(op.f(prior["name"]), "learner_outcome_estimates", revised)


def downgrade():
    raise RuntimeError("Learner profile history is protected; restore a verified backup instead")


def _rebuild_sqlite_table(table, revised, excluded_columns=()):
    import re

    connection = op.get_bind()
    if table not in {"learner_outcome_estimates"}:
        raise RuntimeError("Unexpected episode migration table")
    temporary = "_profile_" + table
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
                raise RuntimeError("Learner profile migration foreign key validation failed")
            connection.exec_driver_sql("COMMIT")
        except BaseException:
            connection.exec_driver_sql("ROLLBACK")
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
