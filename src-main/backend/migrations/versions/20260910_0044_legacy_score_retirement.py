"""Archive original records, then retire numeric learner marks under D-10."""

import json
import re
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20260910_0044"
down_revision = "20260910_0043"
branch_labels = None
depends_on = None

TABLES = ("submission_attempts", "student_submissions")
SETTINGS = ("passing_score", "at_risk_threshold")
ARCHIVE = "legacy_numeric_history"
ARCHIVE_DDL = """
CREATE TABLE IF NOT EXISTS legacy_numeric_history (
    source_table VARCHAR(100) NOT NULL,
    source_record_id VARCHAR(255) NOT NULL,
    source_record JSON NOT NULL,
    migration_revision VARCHAR(32) NOT NULL,
    policy_version VARCHAR(100) NOT NULL,
    archived_at DATETIME NOT NULL,
    CONSTRAINT pk_legacy_numeric_history PRIMARY KEY (source_table, source_record_id)
)
"""


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _ddl(connection, table):
    return connection.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:table"),
        {"table": table},
    ).scalar_one()


def _without_score(ddl):
    revised, columns = re.subn(
        r"\bscore INTEGER(?: DEFAULT (?:'[^']*'|[-\d]+))?(?: NOT NULL)?\s*,\s*", "", ddl
    )
    revised, checks = re.subn(
        r",\s*CONSTRAINT \w+ CHECK \(score (?:IS NULL OR score )?BETWEEN 0 AND 100\)",
        "",
        revised,
    )
    if columns != 1 or checks != 1:
        raise RuntimeError("Cannot safely identify the retired score column and constraint")
    return revised


def _archive(connection, table, rows):
    now = datetime.now(UTC).isoformat()
    for row in rows:
        record = dict(row)
        connection.execute(
            sa.text(
                "INSERT INTO legacy_numeric_history VALUES "
                "(:table, :id, :record, :revision, 'legacy-retirement-v1', :now)"
            ),
            {
                "table": table,
                "id": str(record["id"]),
                "record": json.dumps(record, ensure_ascii=False, sort_keys=True),
                "revision": revision,
                "now": now,
            },
        )


def _rebuild(connection, table, ddl, columns):
    temporary = "_task29_" + table
    indexes = list(
        connection.execute(
            sa.text(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=:table AND sql IS NOT NULL"
            ),
            {"table": table},
        ).scalars()
    )
    revised, count = re.subn(
        r'CREATE TABLE\s+["`\[]?' + table + r'["`\]]?',
        "CREATE TABLE " + temporary,
        ddl,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise RuntimeError("Cannot safely identify the retired score table")
    names = ", ".join(map(_quote, columns))
    connection.exec_driver_sql(revised)
    connection.exec_driver_sql(f"INSERT INTO {temporary} ({names}) SELECT {names} FROM {table}")
    connection.exec_driver_sql(f"DROP TABLE {table}")
    connection.exec_driver_sql(f"ALTER TABLE {temporary} RENAME TO {table}")
    for statement in indexes:
        connection.exec_driver_sql(statement)


def _verify(connection, *, allow_new_records=False):
    for table in TABLES:
        saved = {
            key: json.loads(value)
            for key, value in connection.execute(
                sa.text(
                    "SELECT source_record_id, source_record FROM legacy_numeric_history WHERE source_table=:table"
                ),
                {"table": table},
            )
        }
        current = {
            str(row["id"]): dict(row)
            for row in connection.exec_driver_sql(f"SELECT * FROM {table}").mappings()
        }
        for value in saved.values():
            value.pop("score", None)
        original_rows = {key: current.get(key) for key in saved}
        if original_rows != saved or (not allow_new_records and current != saved):
            raise RuntimeError("Legacy retirement changed original response records")
    if connection.exec_driver_sql(
        "SELECT COUNT(*) FROM system_settings WHERE key IN ('passing_score','at_risk_threshold')"
    ).scalar_one():
        raise RuntimeError("Retired numeric settings remain active")
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Legacy retirement foreign key validation failed")


def _guards(connection):
    for action in ("INSERT", "UPDATE", "DELETE"):
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS legacy_numeric_history_no_{action.lower()} "
            f"BEFORE {action} ON legacy_numeric_history BEGIN SELECT RAISE(ABORT, "
            "'Legacy numeric history is migration-only and immutable'); END"
        )


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        raise RuntimeError("Legacy retirement requires the supported SQLite deployment")
    columns = {
        table: [column["name"] for column in sa.inspect(connection).get_columns(table)]
        for table in TABLES
    }
    if all("score" not in names for names in columns.values()):
        # Recover a completed schema transaction interrupted before Alembic stamped it.
        _verify(connection, allow_new_records=True)
        _guards(connection)
        return
    if any("score" not in names for names in columns.values()):
        raise RuntimeError("Partial legacy retirement requires a verified backup")
    revised = {table: _without_score(_ddl(connection, table)) for table in TABLES}
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("Repair existing foreign key errors before legacy retirement")
    with op.get_context().autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            triggers = list(
                connection.exec_driver_sql(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL"
                )
            )
            for name, _ in triggers:
                connection.exec_driver_sql("DROP TRIGGER " + _quote(name))
            connection.exec_driver_sql(ARCHIVE_DDL)
            for table in TABLES:
                _archive(
                    connection,
                    table,
                    connection.exec_driver_sql(f"SELECT * FROM {table}").mappings().all(),
                )
                _rebuild(
                    connection,
                    table,
                    revised[table],
                    [name for name in columns[table] if name != "score"],
                )
            settings = (
                connection.exec_driver_sql(
                    "SELECT * FROM system_settings WHERE key IN ('passing_score','at_risk_threshold')"
                )
                .mappings()
                .all()
            )
            _archive(connection, "system_settings", settings)
            connection.exec_driver_sql(
                "DELETE FROM system_settings WHERE key IN ('passing_score','at_risk_threshold')"
            )
            for _, statement in triggers:
                connection.exec_driver_sql(statement)
            _guards(connection)
            _verify(connection)
            connection.exec_driver_sql("COMMIT")
        except BaseException:
            connection.exec_driver_sql("ROLLBACK")
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade():
    connection = op.get_bind()
    protected = (
        set(
            connection.exec_driver_sql(
                "SELECT DISTINCT tbl_name FROM sqlite_master WHERE type='trigger' AND upper(sql) LIKE '%BEFORE DELETE%'"
            ).scalars()
        )
        | set(TABLES)
        | {ARCHIVE}
    )
    for table in sorted(protected):
        if connection.exec_driver_sql("SELECT COUNT(*) FROM " + _quote(table)).scalar_one():
            raise RuntimeError(
                "cannot downgrade populated history. Recorded history is protected; restore a verified backup"
            )
    # An empty database can return to the prior package. Populated rollback uses backup.
    # Rebuild only the empty tables so their original check constraints are restored.
    with op.get_context().autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            connection.exec_driver_sql("ALTER TABLE submission_attempts ADD COLUMN score INTEGER")
            connection.exec_driver_sql(
                "ALTER TABLE student_submissions ADD COLUMN score INTEGER DEFAULT '0' NOT NULL"
            )
            triggers = list(
                connection.exec_driver_sql(
                    "SELECT name,sql FROM sqlite_master WHERE type='trigger' AND sql IS NOT NULL"
                )
            )
            for name, _ in triggers:
                connection.exec_driver_sql("DROP TRIGGER " + _quote(name))
            for table in TABLES:
                condition = (
                    "score IS NULL OR score BETWEEN 0 AND 100"
                    if table == "submission_attempts"
                    else "score BETWEEN 0 AND 100"
                )
                constraint = (
                    "ck_submission_attempts_submission_attempt_legacy_score"
                    if table == "submission_attempts"
                    else "ck_student_submissions_student_submission_score"
                )
                ddl = _ddl(connection, table).rstrip()
                ddl = ddl[:-1] + f", CONSTRAINT {constraint} CHECK ({condition}))"
                names = [column["name"] for column in sa.inspect(connection).get_columns(table)]
                _rebuild(connection, table, ddl, names)
            connection.exec_driver_sql("DROP TABLE legacy_numeric_history")
            for name, statement in triggers:
                if not name.startswith("legacy_numeric_history_no_"):
                    connection.exec_driver_sql(statement)
            if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("Legacy rollback foreign key validation failed")
            connection.exec_driver_sql("COMMIT")
        except BaseException:
            connection.exec_driver_sql("ROLLBACK")
            raise
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
