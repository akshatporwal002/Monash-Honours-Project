"""Assertions shared by migration-history tests across additive heads."""

from pathlib import Path

from scripts.verify_sqlite_backup import TableVerification, database_manifest


def protected_history_manifest(database_path: Path) -> dict[str, TableVerification]:
    """Exclude migration bookkeeping and Task 20's safely removable empty table."""
    manifest = database_manifest(database_path)
    manifest.pop("alembic_version", None)
    manifest.pop("learner_preference_revisions", None)
    return manifest
