"""A restore must recover database history and every referenced source byte."""

import hashlib
import json
import sqlite3
from contextlib import closing

import pytest

from scripts.learning_backup import create_bundle, restore_bundle, safe_file, verify_bundle


@pytest.fixture
def source(tmp_path):
    uploads = tmp_path / "uploads"
    (uploads / "material").mkdir(parents=True)
    database = tmp_path / "source.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(
            "CREATE TABLE alembic_version(version_num TEXT PRIMARY KEY);"
            "INSERT INTO alembic_version VALUES ('test-head');"
            "CREATE TABLE learning_materials(id TEXT PRIMARY KEY, storage_key TEXT, content_hash TEXT);"
            "CREATE TABLE source_revisions(id TEXT PRIMARY KEY, storage_key TEXT, content_hash TEXT);"
            "CREATE TRIGGER protect_history BEFORE DELETE ON source_revisions "
            "BEGIN SELECT RAISE(ABORT, 'immutable'); END;"
        )
        for table, name, data in (
            ("learning_materials", "current.txt", b"current source"),
            ("source_revisions", "historical.txt", b"original source"),
        ):
            key = f"material/{name}"
            (uploads / key).write_bytes(data)
            connection.execute(
                f"INSERT INTO {table} VALUES (?, ?, ?)",
                (name, key, f"sha256:{hashlib.sha256(data).hexdigest()}"),
            )
        connection.commit()
    (uploads / ".staging").mkdir()
    (uploads / ".staging" / "partial").write_bytes(b"in-flight")
    return database, uploads, tmp_path / "backups"


def test_backup_restores_current_and_historical_sources_and_guards(source, tmp_path):
    bundle = create_bundle(*source)
    manifest = verify_bundle(bundle)
    assert manifest["database"]["migration_head"] == "test-head"
    restored = restore_bundle(bundle, tmp_path / "restored")
    assert (restored / "uploads/material/historical.txt").read_bytes() == b"original source"
    assert (restored / "uploads/material/current.txt").read_bytes() == b"current source"
    assert not (restored / "uploads/.staging").exists()
    with closing(sqlite3.connect(restored / "database.sqlite3")) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM source_revisions")


@pytest.mark.parametrize("target", ["database.sqlite3", "uploads/material/historical.txt"])
def test_corruption_is_rejected_before_restore_creates_destination(source, tmp_path, target):
    bundle = create_bundle(*source)
    (bundle / target).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        restore_bundle(bundle, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_existing_restore_directory_is_preserved(source, tmp_path):
    bundle = create_bundle(*source)
    destination = tmp_path / "existing"
    destination.mkdir()
    (destination / "keep").write_text("keep")
    with pytest.raises(FileExistsError):
        restore_bundle(bundle, destination)
    assert (destination / "keep").read_text() == "keep"


def test_missing_or_changed_referenced_source_fails_capture(source):
    database, uploads, output = source
    (uploads / "material/historical.txt").write_bytes(b"wrong bytes")
    with pytest.raises(ValueError, match="recorded content hash"):
        create_bundle(database, uploads, output)
    assert list(output.iterdir()) == []
    (uploads / "material/historical.txt").unlink()
    with pytest.raises(FileNotFoundError):
        create_bundle(database, uploads, output)
    assert list(output.iterdir()) == []


@pytest.mark.parametrize(
    "key", ["../outside", "/outside", "C:/outside", "a\\outside", "a/../outside", "a//outside"]
)
def test_manifest_paths_cannot_escape_upload_root(tmp_path, key):
    with pytest.raises(ValueError, match="Invalid"):
        safe_file(tmp_path, key)


def test_manifest_cannot_omit_historical_source(source):
    bundle = create_bundle(*source)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    del manifest["uploads"]["material/historical.txt"]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="referenced source file is missing"):
        verify_bundle(bundle)


def test_capture_output_cannot_be_nested_in_uploads(source):
    database, uploads, _ = source
    with pytest.raises(ValueError, match="outside"):
        create_bundle(database, uploads, uploads / "backups")
