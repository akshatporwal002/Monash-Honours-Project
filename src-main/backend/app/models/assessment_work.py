"""The immutable assessment standard accepted when a learner starts work."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.assessment import new_uuid, utc_now
from app.models.assessment_work_integrity import install_work_guards


class AssessmentWorkStart(Base):
    __tablename__ = "assessment_work_starts"
    __table_args__ = (
        UniqueConstraint("student_id", "task_id", name="uq_assessment_work_student_task"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    assessment_definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT")
    )
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT")
    )
    bloom_target_version_id: Mapped[str] = mapped_column(
        ForeignKey("bloom_target_versions.id", ondelete="RESTRICT")
    )
    pass_rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("pass_rule_versions.id", ondelete="RESTRICT")
    )
    task_approval_id: Mapped[str] = mapped_column(
        ForeignKey("task_approvals.id", ondelete="RESTRICT")
    )
    declared_conditions: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_references: Mapped[list[str]] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


@event.listens_for(AssessmentWorkStart, "before_update")
@event.listens_for(AssessmentWorkStart, "before_delete")
def prevent_work_mutation(*_: object) -> None:
    raise RuntimeError("Assessment work starts are immutable")


install_work_guards(Base.metadata)
