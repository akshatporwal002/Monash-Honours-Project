"""Preserved learner notices and assessor reasons for resolved review requests."""

from datetime import datetime

from sqlalchemy import DDL, DateTime, ForeignKey, Integer, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.assessment import new_uuid, utc_now


class AppealResolution(Base):
    __tablename__ = "appeal_resolutions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    appeal_id: Mapped[str] = mapped_column(
        ForeignKey("appeals_or_corrections.id", ondelete="RESTRICT"), unique=True
    )
    assessor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision_revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    learner_notice: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def resolution_guards() -> tuple[str, ...]:
    return tuple(
        f"CREATE TRIGGER IF NOT EXISTS appeal_resolutions_no_{operation.lower()} "
        f"BEFORE {operation} ON appeal_resolutions "
        "BEGIN SELECT RAISE(ABORT, 'Appeal resolutions are immutable'); END"
        for operation in ("UPDATE", "DELETE")
    ) + (
        "CREATE TRIGGER IF NOT EXISTS appeal_resolutions_no_replace BEFORE INSERT "
        "ON appeal_resolutions WHEN EXISTS (SELECT 1 FROM appeal_resolutions "
        "WHERE id=NEW.id OR appeal_id=NEW.appeal_id) "
        "BEGIN SELECT RAISE(ABORT, 'Appeal resolutions are immutable'); END",
    )


def _immutable(*_: object) -> None:
    raise ValueError("Appeal resolutions are immutable")


event.listen(AppealResolution, "before_update", _immutable)
event.listen(AppealResolution, "before_delete", _immutable)
for _statement in resolution_guards():
    event.listen(
        AppealResolution.__table__, "after_create", DDL(_statement).execute_if(dialect="sqlite")
    )
