"""Research-only immutable forms, restricted bindings, and instrument observations."""

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now
from app.models.research_disposal import DISPOSAL_DELETE_AUTHORIZATION


class ResearchInstrumentForm(Base):
    __tablename__ = "research_instrument_forms"
    __table_args__ = (
        UniqueConstraint("study_id", "course_id", "instrument_key", "version"),
        UniqueConstraint("actor_user_id", "request_key"),
        CheckConstraint("version > 0", name="instrument_form_version"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    study_id: Mapped[str] = mapped_column(String(128))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    scope_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    instrument_key: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(71))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(71))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchInstrumentFreeze(Base):
    __tablename__ = "research_instrument_freezes"
    __table_args__ = (UniqueConstraint("form_id"), UniqueConstraint("actor_user_id", "request_key"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    form_id: Mapped[str] = mapped_column(ForeignKey("research_instrument_forms.id"))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(71))
    synthetic_review_reference: Mapped[str] = mapped_column(String(128))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ResearchInstrumentBinding(Base):
    __tablename__ = "research_instrument_bindings"
    __table_args__ = (UniqueConstraint("scope_id", "course_id", "subject_user_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scope_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    subject_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    participant_id: Mapped[str] = mapped_column(String(67))


class ResearchInstrumentRecord(Base):
    __tablename__ = "research_instrument_records"
    __table_args__ = (
        UniqueConstraint("actor_user_id", "request_key"),
        UniqueConstraint("series_id", "revision"),
        UniqueConstraint("supersedes_id"),
        CheckConstraint("revision > 0", name="instrument_record_revision"),
        CheckConstraint(
            "kind IN ('response','missingness','attrition','deviation')",
            name="instrument_record_kind",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    form_id: Mapped[str] = mapped_column(ForeignKey("research_instrument_forms.id"))
    binding_id: Mapped[str] = mapped_column(ForeignKey("research_instrument_bindings.id"))
    consent_id: Mapped[str] = mapped_column(ForeignKey("research_governance_events.id"))
    series_id: Mapped[str] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[str | None] = mapped_column(ForeignKey("research_instrument_records.id"))
    correction_reason_code: Mapped[str | None] = mapped_column(String(48))
    sequence_id: Mapped[str] = mapped_column(String(67))
    stage: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(24))
    links: Mapped[dict] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(71))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(128))
    request_digest: Mapped[str] = mapped_column(String(71))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RestrictedInstrumentEvidence(Base):
    __tablename__ = "restricted_instrument_evidence"
    __table_args__ = (UniqueConstraint("record_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    record_id: Mapped[str] = mapped_column(ForeignKey("research_instrument_records.id"))
    response_text: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(71))


for model, keys in (
    (
        ResearchInstrumentForm,
        (("study_id", "course_id", "instrument_key", "version"), ("actor_user_id", "request_key")),
    ),
    (ResearchInstrumentFreeze, (("form_id",), ("actor_user_id", "request_key"))),
    (ResearchInstrumentBinding, (("scope_id", "course_id", "subject_user_id"),)),
    (
        ResearchInstrumentRecord,
        (("series_id", "revision"), ("actor_user_id", "request_key"), ("supersedes_id",)),
    ),
    (RestrictedInstrumentEvidence, (("record_id",),)),
):
    protect_history(
        model,
        unique_keys=keys,
        delete_authorization=(
            DISPOSAL_DELETE_AUTHORIZATION if model is RestrictedInstrumentEvidence else None
        ),
    )
