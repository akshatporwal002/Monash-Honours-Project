"""Durable monetary exposure, separate from observed tokens and billed actuals."""

from datetime import UTC, datetime

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderBudget(Base):
    __tablename__ = "provider_budgets"
    __table_args__ = (
        CheckConstraint("limit_micros >= 0 AND exposure_micros >= 0", name="budget_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    policy_version: Mapped[str] = mapped_column(String(120))
    limit_micros: Mapped[int] = mapped_column(BigInteger)
    exposure_micros: Mapped[int] = mapped_column(BigInteger, default=0)


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    __table_args__ = (
        CheckConstraint("reserved_micros >= 0", name="usage_reservation_nonnegative"),
        CheckConstraint("exposure_micros >= 0", name="usage_exposure_nonnegative"),
        CheckConstraint(
            "actual_micros IS NULL OR actual_micros >= 0", name="usage_actual_nonnegative"
        ),
        CheckConstraint(
            "state IN ('RESERVED','DISPATCHED','OBSERVED','UNKNOWN','RELEASED','NOT_SENT','RECONCILED')",
            name="usage_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    budget_id: Mapped[str] = mapped_column(ForeignKey("provider_budgets.id"), index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24))
    reserved_micros: Mapped[int] = mapped_column(BigInteger)
    exposure_micros: Mapped[int] = mapped_column(BigInteger)
    estimated_micros: Mapped[int | None] = mapped_column(BigInteger)
    actual_micros: Mapped[int | None] = mapped_column(BigInteger)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    provider_response_id: Mapped[str | None] = mapped_column(String(200))
    receipt_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    reconciliation_actor: Mapped[str | None] = mapped_column(String(120))
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
