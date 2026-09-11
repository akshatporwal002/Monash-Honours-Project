"""Explicit synthetic malware-control fixtures; never scanner effectiveness evidence."""

from contextlib import contextmanager

from app.core.config import settings
from app.services.material_scanning import ScanVerdict


class SyntheticCleanScanner:
    def scan(self, content: bytes) -> ScanVerdict:
        return ScanVerdict("CLEAN", "synthetic-test-only", "fixture-v1", "synthetic_clean")


def enable_synthetic_scanning(monkeypatch):
    monkeypatch.setattr(settings, "material_scan_policy", "required")
    monkeypatch.setattr(settings, "material_scan_policy_version", "synthetic-policy-v1")
    monkeypatch.setattr(
        "app.services.material_scanning.configured_scanner", lambda config: SyntheticCleanScanner()
    )


@contextmanager
def synthetic_scanning_scope():
    """Restore the real configuration when a disposable test/app lifecycle ends."""
    from pytest import MonkeyPatch

    with MonkeyPatch.context() as patch:
        enable_synthetic_scanning(patch)
        yield


def record_synthetic_scan(session, material):
    """Only for synthetic source fixtures; caller separately enables test policy."""
    from uuid import uuid4

    from app.models.intake_history import MaterialScan

    receipt = MaterialScan(
        material_id=material.id,
        content_hash=material.content_hash,
        processing_revision=material.processing_revision,
        claim_token=str(uuid4()),
        policy_version="synthetic-policy-v1",
        scanner="synthetic-test-only",
        scanner_version="fixture-v1",
        status="CLEAN",
        code="synthetic_clean",
    )
    session.add(receipt)
    session.flush()
    material.scan_status = "CLEAN"
    material.current_scan_id = receipt.id
    return receipt
