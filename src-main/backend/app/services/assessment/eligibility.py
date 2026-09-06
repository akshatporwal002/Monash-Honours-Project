"""A course lead approves eligibility; an administrator records the separate grant."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Course, PlatformAuditEvent, User, UserRole
from app.models.assessor_eligibility import AssessorEligibilityApproval
from app.services.assessment.access import (
    RoleAssignmentConflictError,
    RoleAssignmentValidationError,
    ScopedRoleAccessDeniedError,
)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AssessorEligibilityService:
    def __init__(self, session: Session, *, now=None, correlation_id: str | None = None):
        self.session = session
        self._now = now or (lambda: datetime.now(UTC))
        self.correlation_id = correlation_id or str(uuid4())

    def record(
        self,
        actor: User,
        *,
        course_id: str,
        subject_user_id: int,
        expected_version: int,
        state: str,
        reason: str,
        valid_until: datetime | None = None,
    ) -> AssessorEligibilityApproval:
        try:
            # Serialise approval changes and grant creation on the same course row.
            self.session.execute(
                update(Course)
                .where(Course.id == course_id)
                .values(id=Course.id, updated_at=Course.updated_at)
            )
            course = self.session.get(Course, course_id, populate_existing=True)
            current_actor = self.session.get(User, actor.id, populate_existing=True)
            if (
                course is None
                or current_actor is None
                or not current_actor.is_active
                or current_actor.role is not UserRole.EDUCATOR
                or course.educator_id != actor.id
            ):
                raise ScopedRoleAccessDeniedError(
                    "Only the course lead can approve assessor eligibility"
                )
            subject = self.session.get(User, subject_user_id, populate_existing=True)
            if subject is None:
                raise RoleAssignmentValidationError("The staff account does not exist")
            if state not in {"APPROVED", "WITHDRAWN"}:
                raise RoleAssignmentValidationError("Invalid eligibility state")
            if state == "APPROVED" and (
                not subject.is_active or subject.role is not UserRole.EDUCATOR
            ):
                raise RoleAssignmentValidationError(
                    "Assessor eligibility requires an active teaching account"
                )
            if not reason.strip() or len(reason) > 2000:
                raise RoleAssignmentValidationError("A reason of up to 2000 characters is required")
            latest = self.latest(course_id, subject_user_id)
            version = latest.version if latest else 0
            if expected_version != version:
                raise RoleAssignmentConflictError(
                    "Assessor eligibility changed; reload its history"
                )
            if state == "WITHDRAWN" and (latest is None or latest.state == "WITHDRAWN"):
                raise RoleAssignmentValidationError("There is no current approval to withdraw")
            observed_at = as_utc(self._now())
            ends_at = as_utc(valid_until) if valid_until else None
            if ends_at is not None and ends_at <= observed_at:
                raise RoleAssignmentValidationError("The approval end date must be in the future")
            row = AssessorEligibilityApproval(
                course_id=course_id,
                subject_user_id=subject_user_id,
                actor_user_id=actor.id,
                version=version + 1,
                state=state,
                reason=reason.strip(),
                created_at=observed_at,
                valid_until=ends_at if state == "APPROVED" else None,
            )
            self.session.add(row)
            self.session.flush()
            self.session.add(
                PlatformAuditEvent(
                    actor_id=actor.id,
                    action="assessor_eligibility." + state.lower(),
                    resource_type="assessor_eligibility",
                    resource_id=row.id,
                    correlation_id=self.correlation_id,
                    details={
                        "course_id": course_id,
                        "subject_user_id": subject_user_id,
                        "version": row.version,
                        "policy_version": row.policy_version,
                    },
                )
            )
            self.session.commit()
            return row
        except IntegrityError as error:
            self.session.rollback()
            raise RoleAssignmentConflictError(
                "Assessor eligibility changed; reload its history"
            ) from error
        except (
            RoleAssignmentConflictError,
            RoleAssignmentValidationError,
            ScopedRoleAccessDeniedError,
        ):
            self.session.rollback()
            raise

    def latest(self, course_id: str, subject_user_id: int) -> AssessorEligibilityApproval | None:
        return self.session.scalar(
            select(AssessorEligibilityApproval)
            .where(
                AssessorEligibilityApproval.course_id == course_id,
                AssessorEligibilityApproval.subject_user_id == subject_user_id,
            )
            .order_by(AssessorEligibilityApproval.version.desc())
            .limit(1)
        )

    def current(
        self, course_id: str, subject_user_id: int, *, at: datetime | None = None
    ) -> AssessorEligibilityApproval | None:
        approval = self.latest(course_id, subject_user_id)
        now = as_utc(at or self._now())
        subject = self.session.get(User, subject_user_id, populate_existing=True)
        if (
            approval is None
            or approval.state != "APPROVED"
            or as_utc(approval.created_at) > now
            or subject is None
            or not subject.is_active
            or subject.role is not UserRole.EDUCATOR
            or (approval.valid_until is not None and as_utc(approval.valid_until) <= now)
        ):
            return None
        return approval

    def history(
        self, actor: User, course_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[AssessorEligibilityApproval]:
        current_actor = self.session.get(User, actor.id, populate_existing=True)
        course = self.session.get(Course, course_id)
        if (
            course is None
            or current_actor is None
            or not current_actor.is_active
            or not (
                current_actor.role is UserRole.ADMINISTRATOR
                or (current_actor.role is UserRole.EDUCATOR and course.educator_id == actor.id)
            )
        ):
            raise ScopedRoleAccessDeniedError("Course lead or administrator access is required")
        return list(
            self.session.scalars(
                select(AssessorEligibilityApproval)
                .where(
                    AssessorEligibilityApproval.course_id == course_id,
                )
                .order_by(
                    AssessorEligibilityApproval.created_at.desc(), AssessorEligibilityApproval.id
                )
                .limit(min(max(limit, 1), 100))
                .offset(max(offset, 0))
            )
        )
