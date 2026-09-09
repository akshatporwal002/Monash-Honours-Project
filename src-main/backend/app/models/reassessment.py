"""Published outcome selection and explicit fresh reassessment authorisation."""

from datetime import datetime

from sqlalchemy import (
    DDL,
    JSON,
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
from app.models.append_only import protect_history
from app.models.assessment import new_uuid, utc_now


class OutcomeResultPolicy(Base):
    __tablename__ = "outcome_result_policies"
    __table_args__ = (
        UniqueConstraint("definition_version_id", name="uq_outcome_result_policy_definition"),
        CheckConstraint(
            "selection_rule IN ('LATEST_VALID', 'ANY_VALID_PASS', 'ALL_REQUIRED_FORMS')",
            name="outcome_policy_rule",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="outcome_policy_reason"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    definition_version_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_definition_versions.id", ondelete="RESTRICT")
    )
    selection_rule: Mapped[str] = mapped_column(String(24))
    required_form_ids: Mapped[list[str]] = mapped_column(JSON)
    approved_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReassessmentAuthorisation(Base):
    __tablename__ = "reassessment_authorisations"
    __table_args__ = (
        UniqueConstraint(
            "prior_attempt_id", "revision", name="uq_reassessment_authorisation_prior"
        ),
        UniqueConstraint("student_id", "task_id", name="uq_reassessment_authorisation_target"),
        CheckConstraint("decision_revision >= 0", name="reassessment_revision"),
        CheckConstraint("revision > 0", name="reassessment_authorisation_revision"),
        CheckConstraint(
            "length(trim(reason)) > 0 AND length(trim(learner_notice)) > 0",
            name="reassessment_reasons",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    prior_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_attempts.id", ondelete="RESTRICT")
    )
    prior_decision_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_decisions.id", ondelete="RESTRICT")
    )
    decision_revision: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str] = mapped_column(ForeignKey("learning_tasks.id", ondelete="RESTRICT"))
    task_form_version_id: Mapped[str] = mapped_column(
        ForeignKey("task_form_versions.id", ondelete="RESTRICT")
    )
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("outcome_result_policies.id", ondelete="RESTRICT")
    )
    approved_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    learner_notice: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


protect_history(OutcomeResultPolicy, unique_keys=(("definition_version_id",),))
protect_history(
    ReassessmentAuthorisation,
    unique_keys=(("prior_attempt_id", "revision"), ("student_id", "task_id")),
)

event.listen(
    ReassessmentAuthorisation.__table__,
    "after_create",
    DDL("""
CREATE TRIGGER IF NOT EXISTS reassessment_authorisations_scope BEFORE INSERT ON reassessment_authorisations
WHEN NOT EXISTS (
    SELECT 1 FROM assessment_attempts a
    JOIN assessment_decisions d ON d.assessment_attempt_id = a.id
    JOIN outcome_result_policies p ON p.definition_version_id = a.assessment_definition_version_id
    JOIN task_form_versions f ON f.assessment_definition_version_id = p.definition_version_id
    WHERE a.id = NEW.prior_attempt_id AND d.id = NEW.prior_decision_id
    AND p.id = NEW.policy_id AND a.student_id = NEW.student_id
    AND f.id = NEW.task_form_version_id AND f.learning_task_id = NEW.task_id
    AND a.task_id != NEW.task_id AND a.task_form_version_id != f.id
) BEGIN SELECT RAISE(ABORT, 'Reassessment authorisation scope mismatch'); END
""").execute_if(dialect="sqlite"),
)
