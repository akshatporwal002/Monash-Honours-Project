"""Recover saved material work in the existing database worker."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.models import LearningMaterial
from app.services.material_indexing import OfflineMaterialProcessor
from app.services.rag.errors import RagError
from app.services.rag.processing_claims import LostMaterialClaim, MaterialProcessingClaims, utc_now
from app.services.rag.storage import LocalFileStorage


class RecoverableMaterialProcessor(Protocol):
    def process(
        self, material: LearningMaterial, force: bool = False, *, recover: bool = False
    ) -> tuple[int, int]: ...


MaterialProcessorFactory = Callable[[Session, str], RecoverableMaterialProcessor]


class MaterialRecoveryWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        now: Callable[[], datetime] = utc_now,
        configured_settings: Settings = settings,
        processor_factory: MaterialProcessorFactory | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.now = now
        self.config = configured_settings
        self.processor_factory = processor_factory

    async def run_once(self) -> bool:
        # Extraction runs outside the event loop, allowing ownership heartbeats.
        return await asyncio.to_thread(self._run_once)

    def _run_once(self) -> bool:
        with self.session_factory() as session:
            claims = MaterialProcessingClaims(
                session, now=self.now, configured_settings=self.config
            )
            material = claims.next_recoverable()
            if material is None:
                return False
            if material.processing_attempts >= self.config.max_infrastructure_attempts:
                return claims.exhaust(material)
            try:
                if self.processor_factory is not None:
                    processor = self.processor_factory(session, material.processing_backend)
                elif material.processing_backend == "offline":
                    processor = OfflineMaterialProcessor(
                        session,
                        LocalFileStorage(
                            self.config.rag_upload_dir, self.config.rag_max_file_bytes
                        ),
                        now=self.now,
                        configured_settings=self.config,
                    )
                else:
                    claim = claims.claim(material, backend="semantic", recover=True)
                    claims.fail(
                        claim,
                        RagError(
                            "material_processor_unavailable",
                            "The saved processing adapter is unavailable. Restore its configuration and request a fresh processing run.",
                            503,
                        ),
                    )
                    return True
                processor.process(material, recover=True)
            except LostMaterialClaim:
                session.rollback()
            except Exception:
                session.rollback()
                # Factory failures also need a bounded, visible outcome. When the
                # processor already recorded a failure or another claimant won,
                # claim() refuses this transition and preserves their state.
                try:
                    claim = claims.claim(
                        material, backend=material.processing_backend, recover=True
                    )
                    claims.fail(
                        claim,
                        RagError(
                            "material_processor_unavailable",
                            "The saved processing adapter could not run. Check its configuration before retrying.",
                            503,
                        ),
                    )
                except RagError:
                    session.rollback()
            return True
