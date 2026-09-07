from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lms import Course, PlatformAuditEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole


class RoleAssignmentError(Exception):
    """Base error for explicit scoped-role assignment operations."""


class RoleAssignmentValidationError(RoleAssignmentError):
    """An assignment command is invalid for the current database state."""


class RoleAssignmentNotFoundError(RoleAssignmentError):
    """The requested assignment does not exist."""


class RoleAssignmentConflictError(RoleAssignmentError):
    """Another change created the same assignment version."""


class RoleAssignmentPolicyRequiredError(RoleAssignmentError):
    """Assignment is blocked until an eligibility policy is supplied."""


class ScopedRoleAccessDeniedError(RoleAssignmentError):
    """The actor has no active scoped role for the requested course."""


class RoleAssignmentService:
    """Manage and enforce explicit course-scoped permissions.

    The service never derives a scoped permission from ``User.role``. Every
    access check reads the current assignment and account state from the
    database, so revocation and deactivation take effect on the next request.
    """

    def __init__(
        self,
        session: Session,
        *,
        correlation_id: str | None = None,
        now: Callable[[], datetime] | None = None,
        assignment_eligibility: Callable[[User, ScopedRole], bool] | None = None,
    ) -> None:
        self.session = session
        self.correlation_id = correlation_id or str(uuid4())
        self._now = now or (lambda: datetime.now(UTC))
        self._assignment_eligibility = assignment_eligibility

    def history(
        self, administrator: User, course_id: str, *, limit: int = 20, offset: int = 0
    ) -> list[RoleAssignment]:
        self._require_active_administrator(administrator)
        if self.session.get(Course, course_id) is None:
            raise RoleAssignmentNotFoundError("The course does not exist")
        return list(
            self.session.scalars(
                select(RoleAssignment)
                .where(RoleAssignment.course_id == course_id)
                .order_by(RoleAssignment.assigned_at.desc(), RoleAssignment.id)
                .limit(min(max(limit, 1), 100))
                .offset(max(offset, 0))
            )
        )

    def assign(
        self,
        administrator: User,
        *,
        subject_user_id: int,
        course_id: str,
        role: ScopedRole,
        reason: str,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> RoleAssignment:
        self._require_active_administrator(administrator)
        subject = self.session.get(User, subject_user_id)
        if subject is None or not subject.is_active:
            raise RoleAssignmentValidationError("subject_user_id must identify an active account")
        if self._assignment_eligibility is None:
            raise RoleAssignmentPolicyRequiredError(
                "scoped-role eligibility policy is not configured"
            )
        if not self._assignment_eligibility(subject, role):
            raise RoleAssignmentValidationError(
                "subject account is not eligible for the requested scoped role"
            )
        if self.session.get(Course, course_id) is None:
            raise RoleAssignmentValidationError("course_id must identify a course")

        clean_reason = self._clean_reason(reason)
        observed_at = self._utc(self._now())
        eligibility_approval = None
        if role is ScopedRole.ASSESSOR:
            from app.services.assessment.eligibility import AssessorEligibilityService

            self.session.execute(
                update(Course)
                .where(Course.id == course_id)
                .values(id=Course.id, updated_at=Course.updated_at)
            )
            try:
                self._require_active_administrator(administrator)
            except ScopedRoleAccessDeniedError:
                self.session.rollback()
                raise
            eligibility_approval = AssessorEligibilityService(self.session, now=self._now).current(
                course_id,
                subject_user_id,
                at=observed_at,
            )
            if eligibility_approval is None:
                self.session.rollback()
                raise RoleAssignmentValidationError(
                    "Current course-lead approval is required for an assessor grant"
                )
        starts_at = self._utc(valid_from) if valid_from is not None else observed_at
        ends_at = self._utc(valid_until) if valid_until is not None else None
        if eligibility_approval is not None and eligibility_approval.valid_until is not None:
            approval_end = self._utc(eligibility_approval.valid_until)
            if ends_at is None:
                ends_at = approval_end
            elif ends_at > approval_end:
                self.session.rollback()
                raise RoleAssignmentValidationError(
                    "The grant cannot extend beyond course-lead approval"
                )
        if ends_at is not None and ends_at <= starts_at:
            self.session.rollback()
            raise RoleAssignmentValidationError("valid_until must be later than valid_from")

        latest = self.session.scalar(
            select(RoleAssignment)
            .where(
                RoleAssignment.subject_user_id == subject_user_id,
                RoleAssignment.course_id == course_id,
                RoleAssignment.role == role,
            )
            .order_by(RoleAssignment.version.desc())
            .limit(1)
        )
        assignment_id = str(uuid4())
        version = 1 if latest is None else latest.version + 1
        action = "role_assignment.assigned" if latest is None else "role_assignment.changed"

        latest_is_active = (
            latest is not None
            and self._current_eligibility(latest, observed_at)
            and latest.revoked_at is None
            and self._utc(latest.valid_from) <= observed_at
            and (latest.valid_until is None or self._utc(latest.valid_until) > observed_at)
        )
        if latest_is_active and starts_at > observed_at:
            self.session.rollback()
            raise RoleAssignmentValidationError(
                "a future assignment cannot replace a currently active assignment"
            )

        if latest is not None and latest.revoked_at is None:
            self._revoke_if_current(
                latest,
                administrator,
                observed_at=observed_at,
                reason=f"Superseded by assignment {assignment_id}",
            )

        assignment = RoleAssignment(
            id=assignment_id,
            subject_user_id=subject_user_id,
            course_id=course_id,
            role=role,
            version=version,
            eligibility_approval_id=eligibility_approval.id if eligibility_approval else None,
            assigned_by_user_id=administrator.id,
            reason=clean_reason,
            assigned_at=observed_at,
            valid_from=starts_at,
            valid_until=ends_at,
            supersedes_assignment_id=latest.id if latest is not None else None,
        )
        self.session.add(assignment)
        self._audit(
            administrator,
            action,
            assignment,
            previous_assignment_id=latest.id if latest is not None else None,
        )
        self._commit()
        return assignment

    def revoke(
        self,
        administrator: User,
        assignment_id: str,
        *,
        reason: str,
    ) -> RoleAssignment:
        self._require_active_administrator(administrator)
        assignment = self.session.get(RoleAssignment, assignment_id)
        if assignment is None:
            raise RoleAssignmentNotFoundError("role assignment not found")
        if assignment.revoked_at is not None:
            raise RoleAssignmentValidationError("role assignment is already revoked")

        self._revoke_if_current(
            assignment,
            administrator,
            observed_at=self._utc(self._now()),
            reason=self._clean_reason(reason),
        )
        self._audit(administrator, "role_assignment.revoked", assignment)
        self._commit()
        return assignment

    def list_active_assignments(
        self,
        subject_user_id: int,
        *,
        at: datetime | None = None,
    ) -> list[RoleAssignment]:
        observed_at = self._utc(at) if at is not None else self._utc(self._now())
        rows = list(
            self.session.scalars(
                select(RoleAssignment)
                .join(User, User.id == RoleAssignment.subject_user_id)
                .where(
                    RoleAssignment.subject_user_id == subject_user_id,
                    User.is_active.is_(True),
                    RoleAssignment.revoked_at.is_(None),
                    RoleAssignment.valid_from <= observed_at,
                    or_(
                        RoleAssignment.valid_until.is_(None),
                        RoleAssignment.valid_until > observed_at,
                    ),
                )
                .order_by(
                    RoleAssignment.course_id,
                    RoleAssignment.role,
                    RoleAssignment.version,
                )
            ).all()
        )
        return [row for row in rows if self._current_eligibility(row, observed_at)]

    def require_assessor_access(
        self,
        actor: User,
        course_id: str,
    ) -> RoleAssignment:
        return self.require_access(actor, course_id, ScopedRole.ASSESSOR)

    def require_research_access(
        self,
        actor: User,
        course_id: str,
    ) -> RoleAssignment:
        return self.require_access(actor, course_id, ScopedRole.RESEARCH)

    def require_access(
        self,
        actor: User,
        course_id: str,
        role: ScopedRole,
    ) -> RoleAssignment:
        observed_at = self._utc(self._now())
        assignment = self.session.scalar(
            select(RoleAssignment)
            .join(User, User.id == RoleAssignment.subject_user_id)
            .where(
                RoleAssignment.subject_user_id == actor.id,
                RoleAssignment.course_id == course_id,
                RoleAssignment.role == role,
                User.is_active.is_(True),
                RoleAssignment.revoked_at.is_(None),
                RoleAssignment.valid_from <= observed_at,
                or_(
                    RoleAssignment.valid_until.is_(None),
                    RoleAssignment.valid_until > observed_at,
                ),
            )
            .order_by(RoleAssignment.version.desc())
            .limit(1)
        )
        if assignment is None or not self._current_eligibility(assignment, observed_at):
            raise ScopedRoleAccessDeniedError("active course-scoped permission required")
        return assignment

    def _current_eligibility(self, assignment: RoleAssignment, at: datetime) -> bool:
        if assignment.role is not ScopedRole.ASSESSOR:
            return True
        from app.services.assessment.eligibility import AssessorEligibilityService

        approval = AssessorEligibilityService(self.session, now=self._now).current(
            assignment.course_id,
            assignment.subject_user_id,
            at=at,
        )
        return approval is not None and approval.id == assignment.eligibility_approval_id

    def _require_active_administrator(self, actor: User) -> None:
        actor_id = self.session.scalar(
            select(User.id).where(
                User.id == actor.id,
                User.role == UserRole.ADMINISTRATOR,
                User.is_active.is_(True),
            )
        )
        if actor_id is None:
            raise ScopedRoleAccessDeniedError("active administrator permission required")

    def _audit(
        self,
        actor: User,
        action: str,
        assignment: RoleAssignment,
        *,
        previous_assignment_id: str | None = None,
    ) -> None:
        details: dict[str, str | int] = {
            "subject_user_id": assignment.subject_user_id,
            "course_id": assignment.course_id,
            "role": assignment.role.value,
            "version": assignment.version,
        }
        if previous_assignment_id is not None:
            details["previous_assignment_id"] = previous_assignment_id
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action=action,
                resource_type="role_assignment",
                resource_id=assignment.id,
                correlation_id=self.correlation_id,
                details=details,
            )
        )

    def _revoke_if_current(
        self,
        assignment: RoleAssignment,
        actor: User,
        *,
        observed_at: datetime,
        reason: str,
    ) -> None:
        result = self.session.execute(
            update(RoleAssignment)
            .where(
                RoleAssignment.id == assignment.id,
                RoleAssignment.revoked_at.is_(None),
            )
            .values(
                revoked_at=observed_at,
                revoked_by_user_id=actor.id,
                revocation_reason=reason,
            )
            .execution_options(synchronize_session="fetch")
        )
        if result.rowcount != 1:
            self.session.rollback()
            raise RoleAssignmentConflictError(
                "role assignment changed before this operation completed"
            )

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise RoleAssignmentConflictError(
                "role assignment change conflicts with current state"
            ) from error

    @staticmethod
    def _clean_reason(reason: str) -> str:
        clean = reason.strip()
        if not clean or len(clean) > 2_000:
            raise RoleAssignmentValidationError("reason must contain between 1 and 2000 characters")
        return clean

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
