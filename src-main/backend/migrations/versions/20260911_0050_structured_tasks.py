"""Allow matching and sequencing without changing protected response history."""

import re

import sqlalchemy as sa
from alembic import op

revision = "20260911_0050"
down_revision = "20260910_0046"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        ddl = connection.execute(
            sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='learning_tasks'")
        ).scalar_one()
        if "'matching'" in ddl and "'sequencing'" in ddl:
            return
        revised, count = re.subn(
            r"(CHECK\s*\(\s*task_type\s+IN\s*\()([^)]*)(\)\s*\))",
            r"\1\2, 'matching', 'sequencing'\3",
            ddl,
            flags=re.I,
        )
        if count != 1:
            raise RuntimeError("Task type constraint could not be identified safely")
        _rebuild_sqlite_table("learning_tasks", revised)
    else:
        checks = sa.inspect(connection).get_check_constraints("learning_tasks")
        prior = next(item for item in checks if "task_type" in item["sqltext"])
        revised = prior["sqltext"].replace(")", ", 'matching', 'sequencing')", 1)
        op.drop_constraint(op.f(prior["name"]), "learning_tasks", type_="check")
        op.create_check_constraint(op.f(prior["name"]), "learning_tasks", revised)


def downgrade():
    raise RuntimeError("Structured task history is protected; restore a verified backup instead")


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
