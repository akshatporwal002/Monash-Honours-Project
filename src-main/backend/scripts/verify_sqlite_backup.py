"""Create and verify a restorable SQLite backup without exposing record data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class TableVerification:
    row_count: int
    digest: str


@dataclass(frozen=True)
class BackupVerification:
    backup_path: Path
    manifest_path: Path
    table_count: int
    record_count: int
    dataset_digest: str


def _readonly_connection(database_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _digest_value(hasher: Any, value: object) -> None:
    if value is None:
        encoded = b"null:"
    elif isinstance(value, bytes):
        encoded = b"bytes:" + value
    else:
        encoded = f"{type(value).__name__}:{value}".encode()
    hasher.update(len(encoded).to_bytes(8, "big"))
    hasher.update(encoded)


def database_manifest(database_path: Path) -> dict[str, TableVerification]:
    """Return counts and content digests for every application table."""
    with closing(_readonly_connection(database_path)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchall()
        if integrity != [("ok",)]:
            raise RuntimeError("SQLite integrity_check failed")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError("SQLite foreign_key_check failed")

        table_names = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        manifest: dict[str, TableVerification] = {}
        for table_name in table_names:
            columns = list(connection.execute(f"PRAGMA table_info({_identifier(table_name)})"))
            column_names = [column[1] for column in columns]
            primary_key = [
                column[1] for column in sorted(columns, key=lambda column: column[5]) if column[5]
            ]
            order_columns = primary_key or column_names
            projection = ", ".join(_identifier(column) for column in column_names)
            order_by = ", ".join(_identifier(column) for column in order_columns)
            rows = connection.execute(
                f"SELECT {projection} FROM {_identifier(table_name)} ORDER BY {order_by}"
            )
            hasher = hashlib.sha256()
            row_count = 0
            for row in rows:
                row_count += 1
                for value in row:
                    _digest_value(hasher, value)
            manifest[table_name] = TableVerification(
                row_count=row_count,
                digest=hasher.hexdigest(),
            )
        return manifest


def _dataset_digest(manifest: dict[str, TableVerification]) -> str:
    serialized = json.dumps(
        {name: asdict(value) for name, value in manifest.items()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def create_verified_backup(
    database_path: Path,
    output_directory: Path,
) -> BackupVerification:
    """Back up SQLite, restore it separately, and verify every table record."""
    source = database_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {source}")

    destination = output_directory.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    suffix = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    backup_path = destination / f"quantumlearn-backup-{suffix}.sqlite3"
    partial_backup = destination / f".{backup_path.name}.partial"
    restored_path = destination / f".quantumlearn-restore-{suffix}.sqlite3"
    manifest_path = destination / f"{backup_path.name}.verification.json"

    try:
        with closing(_readonly_connection(source)) as source_connection:
            with closing(sqlite3.connect(partial_backup)) as backup_connection:
                source_connection.backup(backup_connection)
        os.replace(partial_backup, backup_path)
        try:
            backup_path.chmod(0o600)
        except OSError:
            pass

        backup_manifest = database_manifest(backup_path)
        with closing(_readonly_connection(backup_path)) as backup_connection:
            with closing(sqlite3.connect(restored_path)) as restored_connection:
                backup_connection.backup(restored_connection)
        restored_manifest = database_manifest(restored_path)
        if restored_manifest != backup_manifest:
            raise RuntimeError("Restored SQLite records do not match the backup")

        dataset_digest = _dataset_digest(backup_manifest)
        manifest_payload = {
            "verified_at": datetime.now(UTC).isoformat(),
            "backup_file": backup_path.name,
            "table_count": len(backup_manifest),
            "record_count": sum(item.row_count for item in backup_manifest.values()),
            "dataset_digest": dataset_digest,
            "tables": {name: asdict(value) for name, value in backup_manifest.items()},
        }
        manifest_path.write_text(
            json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return BackupVerification(
            backup_path=backup_path,
            manifest_path=manifest_path,
            table_count=manifest_payload["table_count"],
            record_count=manifest_payload["record_count"],
            dataset_digest=dataset_digest,
        )
    finally:
        partial_backup.unlink(missing_ok=True)
        restored_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create a consistent SQLite backup, restore it to an isolated candidate, "
            "and compare every application-table record by count and SHA-256 digest."
        )
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    result = create_verified_backup(arguments.database, arguments.output_dir)
    print(f"Verified backup: {result.backup_path}")
    print(f"Verification manifest: {result.manifest_path}")
    print(
        f"Matched {result.record_count} records across {result.table_count} tables "
        f"(dataset SHA-256: {result.dataset_digest})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
