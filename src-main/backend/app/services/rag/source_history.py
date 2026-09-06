"""Preserve source revisions and bind outputs without committing the caller's transaction."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LearningMaterial, MaterialChunk
from app.models.source_history import SourceApproval, SourcePassage, SourceRevision, SourceUse
from app.services.rag.contracts import ExtractedBlock
from app.services.rag.errors import MaterialNotFoundError


def snapshot_source(
    session: Session,
    material: LearningMaterial,
    chunks: list[MaterialChunk],
    *,
    blocks: Iterable[ExtractedBlock] | None = None,
    extraction_version: str = "legacy-snapshot-v1",
) -> SourceRevision:
    """Snapshot a complete extraction. Existing chunk IDs must never change meaning."""
    session.flush()
    version = (
        int(
            session.scalar(
                select(func.max(SourceRevision.version)).where(
                    SourceRevision.material_id == material.id
                )
            )
            or 0
        )
        + 1
    )
    revision = SourceRevision(
        material_id=material.id,
        course_id=material.course_id,
        module_id=material.module_id,
        version=version,
        source_label=material.original_filename or material.source_url or "Material",
        mime_type=material.mime_type,
        content_hash=material.content_hash,
        storage_key=material.storage_key,
        extraction_version=extraction_version,
        provenance="EXTRACTED" if blocks is not None else "LEGACY_SNAPSHOT",
        extracted_blocks=[asdict(block) for block in blocks] if blocks is not None else [],
    )
    session.add(revision)
    session.flush()
    session.add_all(
        [
            SourcePassage(
                id=chunk.id,
                revision_id=revision.id,
                course_id=material.course_id,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                heading=chunk.heading,
                location_label=chunk.location_label,
                chunk_hash=chunk.chunk_hash,
            )
            for chunk in chunks
        ]
    )
    session.flush()
    material.current_source_revision_id = revision.id
    return revision


def preserve_current_source(session: Session, material: LearningMaterial) -> SourceRevision | None:
    """Backfill still-existing legacy passages, without claiming historical approval."""
    if material.current_source_revision_id:
        return session.get(SourceRevision, material.current_source_revision_id)
    chunks = list(
        session.scalars(
            select(MaterialChunk)
            .where(MaterialChunk.material_id == material.id)
            .order_by(MaterialChunk.chunk_index)
        )
    )
    return snapshot_source(session, material, chunks) if chunks else None


def latest_approval(session: Session, revision_id: str) -> SourceApproval | None:
    return session.scalar(
        select(SourceApproval)
        .where(SourceApproval.revision_id == revision_id)
        .order_by(SourceApproval.sequence.desc())
        .limit(1)
    )


def record_approval(
    session: Session,
    *,
    course_id: str,
    material_id: str,
    revision_id: str,
    actor_id: str,
    state: str,
    reason: str,
) -> SourceApproval:
    revision = session.get(SourceRevision, revision_id)
    if revision is None or revision.course_id != course_id or revision.material_id != material_id:
        raise MaterialNotFoundError()
    if state not in {"APPROVED", "REVOKED"} or not reason.strip() or not actor_id.strip():
        raise ValueError("Approval requires a valid state, actor, and reason")
    previous = latest_approval(session, revision_id)
    approval = SourceApproval(
        revision_id=revision_id,
        sequence=previous.sequence + 1 if previous else 1,
        state=state,
        actor_id=actor_id,
        reason=reason.strip(),
    )
    session.add(approval)
    session.flush()
    return approval


def resolve_passages(
    session: Session,
    course_id: str,
    references: Iterable[str],
) -> list[tuple[str, SourcePassage, SourceRevision]]:
    """Resolve exact passage IDs; expand material aliases only at the binding boundary."""
    resolved: list[tuple[str, SourcePassage, SourceRevision]] = []
    for reference in dict.fromkeys(references):
        passage = session.get(SourcePassage, reference)
        if passage is None:
            chunk = session.get(MaterialChunk, reference)
            material = session.get(LearningMaterial, chunk.material_id if chunk else reference)
            if material is None or material.course_id != course_id:
                continue
            revision = preserve_current_source(session, material)
            if revision is None:
                continue
            if chunk:
                passage = session.get(SourcePassage, reference)
            else:
                resolved.extend(
                    (reference, item, revision)
                    for item in session.scalars(
                        select(SourcePassage)
                        .where(SourcePassage.revision_id == revision.id)
                        .order_by(SourcePassage.chunk_index)
                    )
                )
                continue
        if passage is not None and passage.course_id == course_id:
            revision = session.get(SourceRevision, passage.revision_id)
            if revision is not None and revision.course_id == course_id:
                resolved.append((reference, passage, revision))
    return resolved


def bind_sources(
    session: Session,
    *,
    course_id: str,
    output_type: str,
    output_id: str,
    output_version: str,
    references: Iterable[str],
    strict: bool = False,
) -> list[str]:
    """Append exact output citations, including approval evidence available when used."""
    references = list(dict.fromkeys(references))
    resolved = resolve_passages(session, course_id, references)
    if strict and set(references) != {reference for reference, _, _ in resolved}:
        raise ValueError("Source references must resolve to preserved passages in this course")
    if strict:
        for _, _, revision in resolved:
            material = session.get(LearningMaterial, revision.material_id)
            approval = latest_approval(session, revision.id)
            if (
                material is None
                or material.retired_at is not None
                or (approval and approval.state == "REVOKED")
            ):
                raise ValueError(
                    "Retired or revoked sources cannot be attached to new output versions"
                )
    for reference, passage, revision in resolved:
        existing = session.scalar(
            select(SourceUse.id).where(
                SourceUse.output_type == output_type,
                SourceUse.output_id == output_id,
                SourceUse.output_version == output_version,
                SourceUse.passage_id == passage.id,
            )
        )
        if existing is None:
            approval = latest_approval(session, revision.id)
            session.add(
                SourceUse(
                    course_id=course_id,
                    output_type=output_type,
                    output_id=output_id,
                    output_version=output_version,
                    source_id=reference,
                    passage_id=passage.id,
                    approval_id=approval.id if approval and approval.state == "APPROVED" else None,
                )
            )
            session.flush()
    return list(dict.fromkeys(passage.id for _, passage, _ in resolved))


def output_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def passage_label(passage: SourcePassage, revision: SourceRevision) -> str:
    return " - ".join(
        part for part in (revision.source_label, passage.location_label, passage.heading) if part
    )
