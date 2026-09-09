"""Assertions shared by migration-history tests across additive heads."""

from pathlib import Path

from scripts.verify_sqlite_backup import TableVerification, database_manifest


def protected_history_manifest(database_path: Path) -> dict[str, TableVerification]:
    """Exclude bookkeeping and safely removable empty extension tables."""
    manifest = database_manifest(database_path)
    manifest.pop("alembic_version", None)
    for name in (
        "learner_preference_revisions",
        "tutor_turns",
        "appeal_resolutions",
        "outcome_result_policies",
        "reassessment_authorisations",
        "escalation_queue_revisions",
        "escalation_cases",
        "escalation_events",
        "gamification_preferences",
        "participation_recognitions",
    ):
        if name in manifest and manifest[name].row_count == 0:
            manifest.pop(name)
    return manifest
