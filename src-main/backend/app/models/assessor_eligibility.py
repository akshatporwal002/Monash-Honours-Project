"""Course-lead approval history for assessor eligibility."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.persistence import new_uuid, utc_now


class AssessorEligibilityApproval(Base):
    __tablename__ = "assessor_eligibility_approvals"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "subject_user_id", "version", name="uq_assessor_eligibility_version"
        ),
        CheckConstraint("version > 0", name="assessor_eligibility_version"),
        CheckConstraint("state IN ('APPROVED', 'WITHDRAWN')", name="assessor_eligibility_state"),
        CheckConstraint("length(trim(reason)) > 0", name="assessor_eligibility_reason"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    subject_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    policy_version: Mapped[str] = mapped_column(String(64), default="assessor-access-v1-selection")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def _immutable(*_: Any) -> None:
    raise ValueError("Assessor eligibility history is append-only")


event.listen(AssessorEligibilityApproval, "before_update", _immutable)
event.listen(AssessorEligibilityApproval, "before_delete", _immutable)
for _action in ("UPDATE", "DELETE"):
    event.listen(
        AssessorEligibilityApproval.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER assessor_eligibility_no_{_action.lower()} BEFORE {_action} ON assessor_eligibility_approvals "
            "BEGIN SELECT RAISE(ABORT, 'Assessor eligibility history is append-only'); END"
        ).execute_if(dialect="sqlite"),
    )
event.listen(
    AssessorEligibilityApproval.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER assessor_eligibility_no_replace BEFORE INSERT ON assessor_eligibility_approvals "
        "WHEN EXISTS (SELECT 1 FROM assessor_eligibility_approvals WHERE id = NEW.id OR "
        "(course_id = NEW.course_id AND subject_user_id = NEW.subject_user_id AND version = NEW.version)) "
        "BEGIN SELECT RAISE(ABORT, 'Assessor eligibility history is append-only'); END"
    ).execute_if(dialect="sqlite"),
)
