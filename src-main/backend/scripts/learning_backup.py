"""Bundle a SQLite snapshot with its immutable source files and verify an isolated restore."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import stat
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from scripts.verify_sqlite_backup import database_manifest


def file_digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def safe_file(root: Path, key: str) -> Path:
    """Reject traversal and links, including Windows junctions, before opening a file."""
    metadata = root.lstat()
    if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
        raise ValueError("Backup file roots cannot be symbolic links or reparse points")
    parts = PurePosixPath(key).parts
    if (
        not parts
        or key != "/".join(parts)
        or any(part in {".", ".."} or ":" in part or "\\" in part for part in parts)
        or PurePosixPath(key).is_absolute()
    ):
        raise ValueError("Invalid backup file path")
    candidate = root
    for part in parts:
        candidate = candidate / part
        metadata = candidate.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError("Backup files cannot be symbolic links or reparse points")
    if not candidate.resolve().is_relative_to(root.resolve()) or not candidate.is_file():
        raise ValueError("Backup file must be a regular file within its root")
    return candidate


def database_details(path: Path) -> dict:
    tables = {name: asdict(value) for name, value in database_manifest(path).items()}
    with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
        heads = connection.execute("SELECT version_num FROM alembic_version").fetchall()
        if len(heads) != 1:
            raise ValueError("Backup requires one recorded migration head")
        schema = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_schema "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        references = []
        for table in ("learning_materials", "source_revisions"):
            if table in tables:
                references.extend(
                    connection.execute(
                        f"SELECT storage_key, content_hash FROM {table} WHERE storage_key IS NOT NULL"
                    ).fetchall()
                )
    return {
        "tables": tables,
        "migration_head": heads[0][0],
        "schema_sha256": hashlib.sha256(json.dumps(schema).encode()).hexdigest(),
        "references": [list(row) for row in references],
    }


def verify_bundle(bundle: Path) -> dict:
    manifest = json.loads(safe_file(bundle, "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1:
        raise ValueError("Unsupported backup format")
    database = safe_file(bundle, "database.sqlite3")
    if file_digest(database) != manifest["database_sha256"]:
        raise ValueError("Database checksum mismatch")
    details = database_details(database)
    if details != manifest["database"]:
        raise ValueError("Database verification does not match the manifest")
    uploads = bundle / "uploads"
    for key, expected in manifest["uploads"].items():
        path = safe_file(uploads, key)
        if path.stat().st_size != expected["size"] or file_digest(path) != expected["sha256"]:
            raise ValueError("Uploaded file checksum mismatch")
    for key, content_hash in details["references"]:
        if key not in manifest["uploads"]:
            raise ValueError("A referenced source file is missing from the backup")
        if content_hash and content_hash.startswith("sha256:"):
            if manifest["uploads"][key]["sha256"] != content_hash.removeprefix("sha256:"):
                raise ValueError("Source file does not match its recorded content hash")
    return manifest


def create_bundle(database: Path, uploads: Path, output_directory: Path) -> Path:
    database, uploads, output_directory = (
        database.resolve(),
        uploads.resolve(),
        output_directory.resolve(),
    )
    if not database.is_file() or not uploads.is_dir():
        raise ValueError("Database and upload directory must exist")
    if output_directory.is_relative_to(uploads):
        raise ValueError("Backup output must be outside the upload directory")
    output_directory.mkdir(parents=True, exist_ok=True)
    bundle = output_directory / f"learnlens-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}"
    bundle.mkdir(mode=0o700)
    try:
        snapshot = bundle / "database.sqlite3"
        with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
        details = database_details(snapshot)
        files = {}
        (bundle / "uploads").mkdir()
        # File keys are immutable. Copy the files referenced by this exact database snapshot,
        # including historical revisions; orphaned and in-flight uploads are not part of it.
        for key, _ in details["references"]:
            if key in files:
                continue
            source_file = safe_file(uploads, key)
            target_file = bundle / "uploads" / key
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, target_file)
            files[key] = {"size": target_file.stat().st_size, "sha256": file_digest(target_file)}
        manifest = {
            "format": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "database_sha256": file_digest(snapshot),
            "database": details,
            "uploads": files,
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        verify_bundle(bundle)
        restored = restore_bundle(bundle, bundle / "restore-check")
        if database_details(restored / "database.sqlite3") != details:
            raise ValueError("Isolated restore did not preserve database contents")
        shutil.rmtree(restored)
        return bundle
    except BaseException:
        # This UUID directory was exclusively created above; never remove an existing target.
        shutil.rmtree(bundle)
        raise


def restore_bundle(bundle: Path, destination: Path) -> Path:
    bundle, destination = bundle.resolve(), destination.absolute()
    manifest = verify_bundle(bundle)
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    try:
        shutil.copyfile(safe_file(bundle, "database.sqlite3"), destination / "database.sqlite3")
        (destination / "uploads").mkdir()
        for key in manifest["uploads"]:
            target = destination / "uploads" / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(safe_file(bundle / "uploads", key), target)
        shutil.copyfile(safe_file(bundle, "manifest.json"), destination / "manifest.json")
        verify_bundle(destination)
        return destination
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--database", type=Path, required=True)
    create.add_argument("--uploads", type=Path, required=True)
    create.add_argument("--output-dir", type=Path, required=True)
    restore = commands.add_parser("restore")
    restore.add_argument("--bundle", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = (
        create_bundle(args.database, args.uploads, args.output_dir)
        if args.command == "create"
        else restore_bundle(args.bundle, args.destination)
    )
    print(f"Verified: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
