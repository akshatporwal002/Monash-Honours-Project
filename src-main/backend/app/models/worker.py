from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

WORKER_HEARTBEAT_SLOT = "primary"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WorkerHeartbeat(Base):
    """Singleton heartbeat shared by the API and the SQLite worker."""

    __tablename__ = "worker_heartbeats"
    __table_args__ = (
        CheckConstraint(
            f"slot = '{WORKER_HEARTBEAT_SLOT}'",
            name="worker_heartbeat_singleton",
        ),
    )

    slot: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=WORKER_HEARTBEAT_SLOT,
    )
    worker_id: Mapped[str] = mapped_column(String(36), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
