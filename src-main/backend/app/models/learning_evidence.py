"""Person B append-only evidence records kept separate from formal assessment results."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceLinkRelation,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
)


def new_uuid() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_type: type[Any], name: str) -> Enum[Any]:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class EvidenceArtifact(Base):
    """Authorised storage for protected learner content."""

    __tablename__ = "evidence_artifacts"
    __table_args__ = (
        CheckConstraint("record_version > 0", name="evidence_artifact_record_version"),
        CheckConstraint(
            "length(content_digest) = 71 AND content_digest GLOB 'sha256:*' "
            "AND content_digest NOT GLOB 'sha256:*[^0-9a-f]*'",
            name="evidence_artifact_content_digest",
        ),
        Index("ix_evidence_artifacts_learner_time", "learner_id", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    content_format: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearningEvidence(Base):
    """Append-only timeline metadata and references, never a learner result."""

    __tablename__ = "learning_evidence"
    __table_args__ = (
        CheckConstraint("record_version > 0", name="learning_evidence_record_version"),
        CheckConstraint(
            "instructional_support_level BETWEEN 0 AND 5",
            name="learning_evidence_instructional_support",
        ),
        CheckConstraint(
            "length(content_digest) = 71 AND content_digest GLOB 'sha256:*' "
            "AND content_digest NOT GLOB 'sha256:*[^0-9a-f]*'",
            name="learning_evidence_content_digest",
        ),
        UniqueConstraint(
            "course_id",
            "learner_id",
            "idempotency_key",
            name="uq_learning_evidence_idempotency",
        ),
        Index(
            "ix_learning_evidence_learner_outcome_timeline",
            "learner_id",
            "outcome_id",
            "occurred_at",
            "created_at",
            "id",
        ),
        Index(
            "ix_learning_evidence_course_outcome_timeline",
            "course_id",
            "outcome_id",
            "occurred_at",
        ),
        Index("ix_learning_evidence_response_version", "response_version_id"),
        Index("ix_learning_evidence_type_time", "evidence_type", "occurred_at"),
        Index("ix_learning_evidence_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("evidence_artifacts.id", ondelete="RESTRICT"), nullable=True
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    activity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    response_version_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_interaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    task_conditions_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_type: Mapped[EvidenceType] = mapped_column(
        enum_column(EvidenceType, "learning_evidence_type"), nullable=False
    )
    provenance: Mapped[EvidenceProvenance] = mapped_column(
        enum_column(EvidenceProvenance, "evidence_provenance"), nullable=False
    )
    observation_type: Mapped[ObservationType] = mapped_column(
        enum_column(ObservationType, "evidence_observation_type"), nullable=False
    )
    instructional_support_level: Mapped[InstructionalSupportLevel] = mapped_column(
        Integer, nullable=False
    )
    access_support_state: Mapped[AccessSupportState] = mapped_column(
        enum_column(AccessSupportState, "evidence_access_support_state"), nullable=False
    )
    content_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EvidenceLink(Base):
    """Immutable supporting, contradicting, or derived evidence relationship."""

    __tablename__ = "evidence_links"
    __table_args__ = (
        CheckConstraint("evidence_id <> linked_evidence_id", name="evidence_link_distinct_records"),
        UniqueConstraint(
            "evidence_id",
            "linked_evidence_id",
            "relation",
            name="uq_evidence_links_relation",
        ),
        Index("ix_evidence_links_linked_evidence", "linked_evidence_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT"), nullable=False
    )
    linked_evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT"), nullable=False
    )
    relation: Mapped[EvidenceLinkRelation] = mapped_column(
        enum_column(EvidenceLinkRelation, "evidence_link_relation"), nullable=False
    )
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


__all__ = ["EvidenceArtifact", "EvidenceLink", "LearningEvidence"]
