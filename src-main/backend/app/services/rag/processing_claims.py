"""Durable material claims and publication fencing shared by both processors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models import LearningMaterial, MaterialIndexStatus
from app.services.rag.errors import (
    InvalidMaterialStateError,
    MaterialAlreadyProcessingError,
    RagError,
)
from app.services.rag.source_history import preserve_current_source


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class LostMaterialClaim(RagError):
    def __init__(self) -> None:
        super().__init__(
            "material_processing_claim_expired",
            "Processing ownership changed. Reload the material's current status.",
            409,
        )


class MaterialRetryRequired(RagError):
    def __init__(self) -> None:
        super().__init__(
            "material_processing_retry_required",
            "Automatic processing stopped. Review the error, then request a fresh processing run.",
            409,
        )


@dataclass(frozen=True)
class MaterialClaim:
    material_id: str
    token: str
    revision: int
    content_hash: str
    storage_key: str
    attempts: int
    backend: str


class MaterialProcessingClaims:
    def __init__(
        self,
        session: Session,
        *,
        now: Callable[[], datetime] = utc_now,
        configured_settings: Settings = settings,
    ) -> None:
        self.session = session
        self.now = now
        self.config = configured_settings

    def claim(
        self,
        material: LearningMaterial,
        *,
        backend: str,
        force: bool = False,
        recover: bool = False,
    ) -> MaterialClaim:
        self.session.refresh(material)
        observed = self.now()
        if material.retired_at is not None or not material.storage_key:
            raise InvalidMaterialStateError()
        if backend not in {"offline", "semantic"}:
            raise ValueError("Unknown material processor")
        running = material.indexing_status is MaterialIndexStatus.PROCESSING
        if running and (
            (material.processing_lease_expires_at is None and not recover)
            or (
                material.processing_lease_expires_at is not None
                and utc(material.processing_lease_expires_at) > observed
            )
        ):
            raise MaterialAlreadyProcessingError()
        if material.processing_attempts and material.processing_backend != backend:
            raise RagError(
                "material_processing_backend_mismatch",
                "Restore the saved processing adapter before retrying this material.",
                409,
            )
        reset = force and not running
        if not reset:
            if material.processing_attempts >= self.config.max_infrastructure_attempts:
                raise MaterialRetryRequired()
            if material.indexing_status is MaterialIndexStatus.INDEXED:
                raise InvalidMaterialStateError()
            if material.processing_retry_at and utc(material.processing_retry_at) > observed:
                raise MaterialAlreadyProcessingError()
            if (
                material.indexing_status is MaterialIndexStatus.FAILED
                and material.processing_retry_at is None
                and material.processing_attempts
            ):
                raise MaterialRetryRequired()
        token = str(uuid4())
        revision = material.processing_revision + int(reset)
        attempts = 1 if reset else material.processing_attempts + 1
        matched = self.session.execute(
            update(LearningMaterial)
            .where(
                LearningMaterial.id == material.id,
                LearningMaterial.retired_at.is_(None),
                LearningMaterial.processing_revision == material.processing_revision,
                LearningMaterial.processing_token == material.processing_token,
                LearningMaterial.processing_attempts == material.processing_attempts,
                LearningMaterial.indexing_status == material.indexing_status,
                LearningMaterial.content_hash == material.content_hash,
                LearningMaterial.storage_key == material.storage_key,
            )
            .values(
                indexing_status=MaterialIndexStatus.PROCESSING,
                processing_token=token,
                processing_revision=revision,
                processing_attempts=attempts,
                processing_backend=backend,
                processing_lease_expires_at=observed
                + timedelta(seconds=self.config.material_processing_lease_seconds),
                processing_retry_at=None,
                error_code=None,
                extraction_error=None,
                failure_stage=None,
            )
            .execution_options(synchronize_session=False)
        )
        if matched.rowcount != 1:
            self.session.rollback()
            raise MaterialAlreadyProcessingError()
        self.session.refresh(material)
        preserve_current_source(self.session, material)
        claim = MaterialClaim(
            material.id,
            token,
            revision,
            material.content_hash,
            material.storage_key,
            attempts,
            backend,
        )
        self.session.commit()
        return claim

    def _owned(self, claim: MaterialClaim):
        return and_(
            LearningMaterial.id == claim.material_id,
            LearningMaterial.retired_at.is_(None),
            LearningMaterial.processing_token == claim.token,
            LearningMaterial.processing_revision == claim.revision,
            LearningMaterial.content_hash == claim.content_hash,
            LearningMaterial.storage_key == claim.storage_key,
        )

    def guard_publication(self, claim: MaterialClaim) -> None:
        # This write takes SQLite's writer lock before changing the current index.
        # Keep that transaction open through the revision and completion writes.
        result = self.session.execute(
            update(LearningMaterial)
            .where(self._owned(claim), LearningMaterial.processing_lease_expires_at > self.now())
            .values(processing_token=claim.token)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise LostMaterialClaim()

    def complete(self, claim: MaterialClaim) -> None:
        self.session.flush()
        result = self.session.execute(
            update(LearningMaterial)
            .where(self._owned(claim), LearningMaterial.processing_lease_expires_at > self.now())
            .values(
                indexing_status=MaterialIndexStatus.INDEXED,
                processing_token=None,
                processing_lease_expires_at=None,
                processing_retry_at=None,
                error_code=None,
                failure_stage=None,
                extraction_error=None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise LostMaterialClaim()
        self.session.commit()

    def fail(self, claim: MaterialClaim, error: Exception) -> bool:
        self.session.rollback()
        retryable = not isinstance(error, RagError) or error.http_status >= 500
        retryable = retryable and claim.attempts < self.config.max_infrastructure_attempts
        code = error.code if isinstance(error, RagError) else "material_processing_failed"
        message = (
            error.safe_message
            if isinstance(error, RagError)
            else "The saved material could not be processed."
        )
        result = self.session.execute(
            update(LearningMaterial)
            .where(self._owned(claim))
            .values(
                indexing_status=MaterialIndexStatus.FAILED,
                processing_token=None,
                processing_lease_expires_at=None,
                processing_retry_at=self.now()
                + timedelta(seconds=self.config.material_processing_retry_seconds)
                if retryable
                else None,
                failure_stage="processing",
                error_code=code,
                extraction_error=message,
            )
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        return result.rowcount == 1

    def next_recoverable(self) -> LearningMaterial | None:
        observed = self.now()
        due = or_(
            LearningMaterial.indexing_status.in_(
                [MaterialIndexStatus.PENDING, MaterialIndexStatus.EXTRACTED]
            ),
            and_(
                LearningMaterial.indexing_status == MaterialIndexStatus.FAILED,
                or_(
                    LearningMaterial.processing_retry_at <= observed,
                    LearningMaterial.processing_attempts == 0,
                ),
            ),
            and_(
                LearningMaterial.indexing_status == MaterialIndexStatus.PROCESSING,
                or_(
                    LearningMaterial.processing_lease_expires_at <= observed,
                    LearningMaterial.processing_lease_expires_at.is_(None),
                ),
            ),
        )
        return self.session.scalar(
            select(LearningMaterial)
            .where(
                LearningMaterial.retired_at.is_(None),
                LearningMaterial.storage_key.is_not(None),
                due,
            )
            .order_by(LearningMaterial.created_at, LearningMaterial.id)
            .limit(1)
        )

    def exhaust(self, material: LearningMaterial) -> bool:
        """Finish a final interrupted execution without deleting its saved upload."""
        result = self.session.execute(
            update(LearningMaterial)
            .where(
                LearningMaterial.id == material.id,
                LearningMaterial.processing_token == material.processing_token,
                LearningMaterial.processing_attempts >= self.config.max_infrastructure_attempts,
                LearningMaterial.retired_at.is_(None),
                or_(
                    LearningMaterial.processing_lease_expires_at <= self.now(),
                    LearningMaterial.processing_lease_expires_at.is_(None),
                ),
                LearningMaterial.indexing_status != MaterialIndexStatus.INDEXED,
            )
            .values(
                indexing_status=MaterialIndexStatus.FAILED,
                processing_token=None,
                processing_lease_expires_at=None,
                processing_retry_at=None,
                failure_stage="processing",
                error_code="material_processing_attempts_exhausted",
                extraction_error="Processing was interrupted repeatedly. Review the saved upload and request a fresh processing run.",
            )
            .execution_options(synchronize_session=False)
        )
        self.session.commit()
        return result.rowcount == 1
