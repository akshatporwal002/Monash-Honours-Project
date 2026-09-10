"""Migration-only snapshots of retired numeric learner fields and settings."""

from datetime import datetime

from sqlalchemy import DDL, JSON, DateTime, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LegacyNumericHistory(Base):
    __tablename__ = "legacy_numeric_history"

    source_table: Mapped[str] = mapped_column(String(100), primary_key=True)
    source_record_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    source_record: Mapped[dict] = mapped_column(JSON, nullable=False)
    migration_revision: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _migration_only(*_):
    raise ValueError("Legacy numeric history is migration-only and immutable")


for operation in ("insert", "update", "delete"):
    event.listen(LegacyNumericHistory, "before_" + operation, _migration_only)
    event.listen(
        LegacyNumericHistory.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER legacy_numeric_history_no_{operation} BEFORE {operation.upper()} "
            "ON legacy_numeric_history BEGIN SELECT RAISE(ABORT, "
            "'Legacy numeric history is migration-only and immutable'); END"
        ).execute_if(dialect="sqlite"),
    )
