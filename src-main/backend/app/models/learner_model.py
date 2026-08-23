"""Append-only Person B learner-model snapshots, estimates, and evidence links."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.platform_enums import (
    CorrectionAction,
    CorrectionTargetKind,
    EvidenceLinkRelation,
    InferenceStatus,
    LearnerModelDimension,
    ModelSource,
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


class LearnerModelSnapshot(Base):
    """Immutable outcome-specific state assembled from linked evidence only."""

    __tablename__ = "learner_model_snapshots"
    __table_args__ = (
        CheckConstraint("record_version > 0", name="learner_model_snapshot_record_version"),
        UniqueConstraint(
            "course_id",
            "learner_id",
            "outcome_id",
            "idempotency_key",
            name="uq_learner_model_snapshot_idempotency",
        ),
        Index(
            "ix_learner_model_snapshots_timeline",
            "course_id",
            "learner_id",
            "outcome_id",
            "occurred_at",
            "created_at",
            "id",
        ),
        Index("ix_learner_model_snapshots_prior", "prior_snapshot_id"),
        Index("ix_learner_model_snapshots_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    # Scope-preserving repository validation checks this immutable predecessor.
    # A self-FK is deliberately avoided because SQLite cannot safely tear down a
    # history containing predecessor records; populated migration downgrades are
    # separately refused before any append-only data could be discarded.
    prior_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    model_source: Mapped[ModelSource] = mapped_column(
        enum_column(ModelSource, "learner_model_source"), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearnerOutcomeEstimate(Base):
    """One controlled inference dimension in a snapshot, with uncertainty."""

    __tablename__ = "learner_outcome_estimates"
    __table_args__ = (
        CheckConstraint(
            "uncertainty >= 0 AND uncertainty <= 1",
            name="learner_outcome_estimate_uncertainty",
        ),
        UniqueConstraint(
            "snapshot_id",
            "dimension",
            name="uq_learner_outcome_estimate_dimension",
        ),
        Index("ix_learner_outcome_estimates_dimension", "dimension", "evidence_observed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("learner_model_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    dimension: Mapped[LearnerModelDimension] = mapped_column(
        enum_column(LearnerModelDimension, "learner_model_dimension"), nullable=False
    )
    inference_status: Mapped[InferenceStatus] = mapped_column(
        enum_column(InferenceStatus, "learner_model_inference_status"), nullable=False
    )
    uncertainty: Mapped[float] = mapped_column(nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearnerModelEvidenceLink(Base):
    """Immutable support or contradiction link required by each inference."""

    __tablename__ = "learner_model_evidence_links"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('SUPPORTS', 'CONTRADICTS')",
            name="learner_model_evidence_relation",
        ),
        UniqueConstraint(
            "estimate_id",
            "evidence_id",
            name="uq_learner_model_evidence_link",
        ),
        Index("ix_learner_model_evidence_links_evidence", "evidence_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    estimate_id: Mapped[str] = mapped_column(
        ForeignKey("learner_outcome_estimates.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT"), nullable=False
    )
    relation: Mapped[EvidenceLinkRelation] = mapped_column(
        enum_column(EvidenceLinkRelation, "learner_model_evidence_relation_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearnerModelAnnotation(Base):
    """Protected learner context attached to one evidence record or inference."""

    __tablename__ = "learner_model_annotations"
    __table_args__ = (
        CheckConstraint("record_version > 0", name="learner_model_annotation_record_version"),
        CheckConstraint("action = 'ANNOTATED'", name="learner_model_annotation_action"),
        CheckConstraint(
            "(target_kind = 'EVIDENCE' AND evidence_id IS NOT NULL AND estimate_id IS NULL) OR "
            "(target_kind = 'ESTIMATE' AND estimate_id IS NOT NULL AND evidence_id IS NULL)",
            name="learner_model_annotation_target",
        ),
        CheckConstraint(
            "length(trim(note)) BETWEEN 1 AND 2000",
            name="learner_model_annotation_note",
        ),
        UniqueConstraint(
            "id",
            "course_id",
            "learner_id",
            "outcome_id",
            name="uq_learner_model_annotation_scope",
        ),
        Index(
            "ix_learner_model_annotations_timeline",
            "course_id",
            "learner_id",
            "outcome_id",
            "occurred_at",
            "created_at",
            "id",
        ),
        Index(
            "ix_learner_model_annotations_target",
            "target_kind",
            "evidence_id",
            "estimate_id",
        ),
        Index("ix_learner_model_annotations_correlation", "correlation_id"),
        Index(
            "ix_learner_model_annotations_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    target_kind: Mapped[CorrectionTargetKind] = mapped_column(
        enum_column(CorrectionTargetKind, "learner_model_correction_target_kind"), nullable=False
    )
    evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_evidence.id", ondelete="RESTRICT"), nullable=True
    )
    estimate_id: Mapped[str | None] = mapped_column(
        ForeignKey("learner_outcome_estimates.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[CorrectionAction] = mapped_column(
        enum_column(CorrectionAction, "learner_model_annotation_action_type"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearnerModelCorrectionReview(Base):
    """Ordered educator decision over an immutable learner annotation."""

    __tablename__ = "learner_model_correction_reviews"
    __table_args__ = (
        CheckConstraint("review_version > 0", name="learner_model_correction_review_version"),
        CheckConstraint(
            "expected_latest_review_version >= 0",
            name="learner_model_correction_expected_version",
        ),
        CheckConstraint(
            "(review_version = 1 AND expected_latest_review_version = 0 "
            "AND prior_review_id IS NULL) OR "
            "(review_version > 1 AND expected_latest_review_version = review_version - 1 "
            "AND prior_review_id IS NOT NULL)",
            name="learner_model_correction_review_ancestry",
        ),
        CheckConstraint(
            "action IN ('ACCEPTED', 'REJECTED', 'NEEDS_REVIEW')",
            name="learner_model_correction_review_action",
        ),
        CheckConstraint(
            "length(trim(reason)) BETWEEN 1 AND 2000",
            name="learner_model_correction_review_reason",
        ),
        ForeignKeyConstraint(
            ["annotation_id", "course_id", "learner_id", "outcome_id"],
            [
                "learner_model_annotations.id",
                "learner_model_annotations.course_id",
                "learner_model_annotations.learner_id",
                "learner_model_annotations.outcome_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id",
            "annotation_id",
            "review_version",
            name="uq_learner_model_correction_review_ancestry",
        ),
        UniqueConstraint(
            "id",
            "course_id",
            "learner_id",
            "outcome_id",
            name="uq_learner_model_correction_review_scope",
        ),
        UniqueConstraint(
            "annotation_id",
            "review_version",
            name="uq_learner_model_correction_review_version",
        ),
        Index(
            "ix_learner_model_correction_reviews_history",
            "annotation_id",
            "review_version",
            "occurred_at",
            "id",
        ),
        Index("ix_learner_model_correction_reviews_correlation", "correlation_id"),
        Index(
            "ix_learner_model_correction_reviews_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    annotation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    learner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    outcome_id: Mapped[str] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="RESTRICT"), nullable=False
    )
    prior_review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_latest_review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[CorrectionAction] = mapped_column(
        enum_column(CorrectionAction, "learner_model_correction_review_action_type"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class LearnerModelCorrectionSnapshotLink(Base):
    """Immutable proof that an accepted correction informed a later snapshot."""

    __tablename__ = "learner_model_correction_snapshot_links"
    __table_args__ = (
        CheckConstraint(
            "record_version > 0", name="learner_model_correction_snapshot_link_version"
        ),
        ForeignKeyConstraint(
            ["review_id", "course_id", "learner_id", "outcome_id"],
            [
                "learner_model_correction_reviews.id",
                "learner_model_correction_reviews.course_id",
                "learner_model_correction_reviews.learner_id",
                "learner_model_correction_reviews.outcome_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("review_id", name="uq_learner_model_correction_snapshot_review"),
        Index(
            "ix_learner_model_correction_snapshot_links_snapshot",
            "snapshot_id",
            "occurred_at",
        ),
        Index("ix_learner_model_correction_snapshot_links_correlation", "correlation_id"),
        Index(
            "ix_learner_model_correction_snapshot_links_idempotency",
            "course_id",
            "learner_id",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    review_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("learner_model_snapshots.id", ondelete="RESTRICT"), nullable=False
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
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    record_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


__all__ = [
    "LearnerModelAnnotation",
    "LearnerModelCorrectionReview",
    "LearnerModelCorrectionSnapshotLink",
    "LearnerModelEvidenceLink",
    "LearnerModelSnapshot",
    "LearnerOutcomeEstimate",
]
