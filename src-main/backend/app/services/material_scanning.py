"""Fail-closed local malware adapter and byte-bound scan receipts.

Type/signature validation is separate. No unscanned-content bypass is supported.
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import select, update

from app.core.config import Settings, settings
from app.models import LearningMaterial
from app.models.intake_history import MaterialScan
from app.services.rag.errors import RagError


@dataclass(frozen=True)
class ScanVerdict:
    status: str
    scanner: str
    version: str
    code: str


class MalwareScanner(Protocol):
    def scan(self, content: bytes) -> ScanVerdict: ...


class ClamAvScanner:
    """Run an operator-provisioned clamscan, never a shell or remote service."""

    def __init__(self, config: Settings):
        self.config = config

    def scan(self, content: bytes) -> ScanVerdict:
        executable = Path(self.config.material_clamscan_path)
        if not executable.is_absolute() or not executable.is_file():
            return ScanVerdict("UNAVAILABLE", "clamav", "unknown", "scanner_unavailable")
        try:
            version = subprocess.run(
                [str(executable), "--version"],
                capture_output=True,
                timeout=self.config.material_scan_timeout_seconds,
                check=False,
            )
            identity = version.stdout.decode(errors="replace").strip()
            if version.returncode or not identity.startswith("ClamAV ") or len(identity) > 255:
                return ScanVerdict(
                    "UNAVAILABLE", "clamav", "unknown", "scanner_version_unavailable"
                )
            with tempfile.TemporaryDirectory(prefix="llscan-") as directory:
                target = Path(directory) / "source"
                target.write_bytes(content)
                result = subprocess.run(
                    [
                        str(executable),
                        "--stdout",
                        "--no-summary",
                        "--alert-exceeds-max=yes",
                        "--alert-encrypted=yes",
                        "--alert-broken=yes",
                        "--scan-archive=yes",
                        "--scan-pdf=yes",
                        "--scan-ole2=yes",
                        "--scan-xmldocs=yes",
                        "--max-filesize=25M",
                        "--max-scansize=100M",
                        f"--fail-if-cvd-older-than={self.config.material_scan_database_max_age_days}",
                        "--",
                        str(target),
                    ],
                    capture_output=True,
                    timeout=self.config.material_scan_timeout_seconds,
                    check=False,
                )
                # A zero exit alone must not accept a skipped or incomplete scan.
                output = result.stdout.decode(errors="replace").strip()
                if (
                    result.returncode == 0
                    and output == f"{target}: OK"
                    and not result.stderr.strip()
                ):
                    return ScanVerdict("CLEAN", "clamav", identity, "scanner_clean")
                if result.returncode == 1:
                    return ScanVerdict("REJECTED", "clamav", identity, "scanner_rejected")
                return ScanVerdict("UNAVAILABLE", "clamav", identity, "scanner_incomplete")
        except (OSError, subprocess.TimeoutExpired):
            return ScanVerdict("UNAVAILABLE", "clamav", "unknown", "scanner_unavailable")


def configured_scanner(config: Settings) -> MalwareScanner | None:
    if config.material_scan_policy == "required" and config.material_scan_policy_version.strip():
        return ClamAvScanner(config)
    return None


def scan_for_extraction(
    claims, claim, storage, scanner: MalwareScanner | None = None
) -> io.BytesIO:
    """Extract from exactly the bytes scanned; publish only under the same live claim."""
    config = claims.config
    content = b""
    try:
        with storage.open_read(claim.storage_key) as source:
            content = source.read(config.rag_max_file_bytes + 1)
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        if len(content) > config.rag_max_file_bytes or digest != claim.content_hash:
            verdict = ScanVerdict("REJECTED", "integrity", "v1", "source_integrity_mismatch")
        elif (
            config.material_scan_policy != "required"
            or not config.material_scan_policy_version.strip()
        ):
            verdict = ScanVerdict("DISABLED", "none", "none", "scanner_policy_disabled")
        else:
            adapter = scanner or configured_scanner(config)
            verdict = adapter.scan(content)
            if verdict.status not in {"CLEAN", "REJECTED", "UNAVAILABLE"} or not verdict.version:
                verdict = ScanVerdict(
                    "UNAVAILABLE", "unknown", "unknown", "scanner_invalid_response"
                )
    except Exception:
        verdict = ScanVerdict("UNAVAILABLE", "unknown", "unknown", "scanner_unavailable")
    claims.guard_publication(claim, require_scan=False)
    receipt = MaterialScan(
        material_id=claim.material_id,
        content_hash=claim.content_hash,
        processing_revision=claim.revision,
        claim_token=claim.token,
        policy_version=config.material_scan_policy_version,
        scanner=verdict.scanner,
        scanner_version=verdict.version,
        status=verdict.status,
        code=verdict.code,
    )
    claims.session.add(receipt)
    claims.session.flush()
    claims.session.execute(
        update(LearningMaterial)
        .where(claims._owned(claim))
        .values(scan_status=verdict.status, current_scan_id=receipt.id)
    )
    claims.session.commit()
    if verdict.status != "CLEAN":
        raise RagError(
            verdict.code,
            "Material remains quarantined. Malware scanning " + verdict.status.lower() + ".",
            503 if verdict.status == "UNAVAILABLE" else 409,
        )
    return io.BytesIO(content)


def require_clean_material(session, material, config: Settings = settings) -> None:
    receipt = (
        session.get(MaterialScan, material.current_scan_id) if material.current_scan_id else None
    )
    if (
        config.material_scan_policy != "required"
        or not config.material_scan_policy_version.strip()
        or receipt is None
        or receipt.status != "CLEAN"
        or material.scan_status != "CLEAN"
        or receipt.material_id != material.id
        or receipt.content_hash != material.content_hash
        or receipt.policy_version != config.material_scan_policy_version
    ):
        raise RagError(
            "material_quarantined", "Material is quarantined until malware scanning succeeds.", 409
        )


def require_claim_scan(claims, claim):
    material = claims.session.get(LearningMaterial, claim.material_id, populate_existing=True)
    require_clean_material(claims.session, material, claims.config)
    receipt = claims.session.scalar(
        select(MaterialScan).where(MaterialScan.id == material.current_scan_id)
    )
    if receipt.claim_token != claim.token or receipt.processing_revision != claim.revision:
        raise RagError(
            "material_scan_stale", "A fresh scan is required for this processing run.", 409
        )


def revision_scan_is_clean(session, revision, config: Settings = settings) -> bool:
    """Replacement bytes never lend their receipt to an older approved passage."""
    if config.material_scan_policy != "required" or not config.material_scan_policy_version.strip():
        return False
    receipt = session.scalar(
        select(MaterialScan)
        .where(
            MaterialScan.material_id == revision.material_id,
            MaterialScan.content_hash == revision.content_hash,
            MaterialScan.policy_version == config.material_scan_policy_version,
        )
        .order_by(MaterialScan.created_at.desc(), MaterialScan.id.desc())
        .limit(1)
    )
    return receipt is not None and receipt.status == "CLEAN"
