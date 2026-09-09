"""Course-scoped human triage without authority to change assessment results."""

from datetime import UTC
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.enums import FeedbackStatus
from app.models.escalation import EscalationCase, EscalationEvent, EscalationQueueRevision
from app.models.lms import Course, PlatformAuditEvent, SubmissionAttempt
from app.models.persistence import FeedbackRecord, LearningTask
from app.models.user import User, UserRole
from app.schemas.escalation import (
    EscalationNotice,
    EscalationQueueRead,
    EscalationRead,
    EscalationStaffRead,
    QueueMember,
    QueueRead,
)
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.escalation_sources import record_signal, source_for
from app.services.lms import LmsService, LmsServiceError

STATES = ("OPEN", "ACKNOWLEDGED", "ACTIONED", "RESOLVED", "CLOSED")


class EscalationService:
    def __init__(self, session: Session):
        self.session = session
        self.assignments = RoleAssignmentService(session)

    def require_access(self, actor, course_id, kind):
        if not actor or not actor.is_active or self.session.get(Course, course_id) is None:
            raise LmsServiceError(403, "Queue access is required")
        if kind == "ASSESSOR":
            self.assignments.require_assessor_access(actor, course_id)
        elif actor.role is not UserRole.ADMINISTRATOR:
            raise LmsServiceError(403, "Technical queue access requires an active administrator")

    def configuration(self, course_id, kind):
        return self.session.scalar(
            select(EscalationQueueRevision)
            .where(
                EscalationQueueRevision.course_id == course_id,
                EscalationQueueRevision.kind == kind,
            )
            .order_by(EscalationQueueRevision.revision.desc())
            .limit(1)
        )

    def queues(self, actor):
        choices = []
        for course in self.session.scalars(select(Course).order_by(Course.title, Course.id)):
            for kind in ("ASSESSOR", "TECHNICAL"):
                try:
                    self.require_access(actor, course.id, kind)
                except (LmsServiceError, ScopedRoleAccessDeniedError):
                    continue
                configuration = self.configuration(course.id, kind)
                choices.append(
                    EscalationQueueRead(
                        course_id=course.id,
                        course_title=course.title,
                        kind=kind,
                        configuration=QueueRead.model_validate(configuration)
                        if configuration
                        else None,
                        eligible_members=[],
                    )
                )
        return choices

    def setup(self, actor, course_id, kind):
        self.require_access(actor, course_id, kind)
        members = []
        for user in self.session.scalars(
            select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
        ):
            try:
                self.require_access(user, course_id, kind)
            except (LmsServiceError, ScopedRoleAccessDeniedError):
                continue
            members.append(QueueMember(id=user.id, name=user.full_name))
        current = self.configuration(course_id, kind)
        return EscalationQueueRead(
            course_id=course_id,
            course_title=self.session.get(Course, course_id).title,
            kind=kind,
            configuration=QueueRead.model_validate(current) if current else None,
            eligible_members=members,
        )

    def configure(self, actor, course_id, kind, command):
        self._lock(actor.id)
        self.require_access(actor, course_id, kind)
        prior = self.configuration(course_id, kind)
        values = command.model_dump(exclude={"expected_revision"})
        if (
            prior
            and prior.revision == command.expected_revision + 1
            and prior.approved_by_user_id == actor.id
            and all(getattr(prior, key) == value for key, value in values.items())
        ):
            self.session.rollback()
            return QueueRead.model_validate(prior)
        if (prior.revision if prior else 0) != command.expected_revision:
            raise LmsServiceError(409, "Queue ownership changed; reload before saving")
        if command.primary_user_id == command.backup_user_id:
            raise LmsServiceError(422, "Choose separate primary and backup owners")
        for owner in (command.primary_user_id, command.backup_user_id):
            self.require_access(self.session.get(User, owner), course_id, kind)
        row = EscalationQueueRevision(
            course_id=course_id,
            kind=kind,
            revision=command.expected_revision + 1,
            approved_by_user_id=actor.id,
            **values,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(actor.id, row.id, "escalation.queue_configured")
        self.session.commit()
        return QueueRead.model_validate(row)

    def report(self, learner, command):
        self._lock(learner.id)
        source = source_for(self.session, command.source_kind, command.source_id)
        if (
            not learner.is_active
            or learner.role is not UserRole.STUDENT
            or source is None
            or source.student_id != learner.id
        ):
            raise LmsServiceError(404, "This output is unavailable")
        LmsService(self.session).get_draft(learner, source.task.id)
        if command.source_kind == "FEEDBACK" and source.record.status not in {
            FeedbackStatus.ACCEPTED,
            FeedbackStatus.SAFE_FALLBACK,
        }:
            raise LmsServiceError(404, "This output is unavailable")
        key = f"learner:{learner.id}:{command.idempotency_key}"
        prior = self.session.scalar(select(EscalationCase).where(EscalationCase.request_key == key))
        if prior and (
            prior.source_kind,
            prior.source_id,
            prior.queue_kind,
            prior.severity,
            prior.reason,
        ) != (
            command.source_kind,
            command.source_id,
            command.queue_kind,
            command.severity,
            command.reason,
        ):
            raise LmsServiceError(409, "This report key already has different details")
        case = record_signal(
            self.session,
            source_kind=command.source_kind,
            source_id=command.source_id,
            queue_kind=command.queue_kind,
            trigger="LEARNER_REPORT",
            severity=command.severity,
            reason=command.reason,
            request_key=key,
        )
        if not prior:
            self._audit(learner.id, case.id, "escalation.reported")
        self.session.commit()
        return self.read_case(case)

    def learner_cases(self, learner, task_id):
        LmsService(self.session).get_draft(learner, task_id)
        return [
            self.read_case(case)
            for case in self.session.scalars(
                select(EscalationCase)
                .where(
                    EscalationCase.student_id == learner.id,
                    EscalationCase.task_id == task_id,
                )
                .order_by(EscalationCase.created_at, EscalationCase.id)
            )
        ]

    def queue(self, actor, course_id, kind, offset=0):
        self.require_access(actor, course_id, kind)
        return [
            self.read_case(case, staff=True)
            for case in self.session.scalars(
                select(EscalationCase)
                .where(
                    EscalationCase.course_id == course_id,
                    EscalationCase.queue_kind == kind,
                )
                .order_by(EscalationCase.created_at.desc(), EscalationCase.id)
                .limit(50)
                .offset(offset)
            )
        ]

    def act(self, actor, case_id, command):
        self._lock(actor.id)
        case = self.session.get(EscalationCase, case_id)
        if case is None:
            raise LmsServiceError(404, "Report not found")
        self.require_access(actor, case.course_id, case.queue_kind)
        configuration = self.configuration(case.course_id, case.queue_kind)
        if configuration is None:
            raise LmsServiceError(409, "Configure the queue owners and response targets first")
        if actor.id not in {configuration.primary_user_id, configuration.backup_user_id}:
            raise LmsServiceError(
                403, "Only the current primary or backup owner can act on this queue"
            )
        if command.owner_user_id not in {
            configuration.primary_user_id,
            configuration.backup_user_id,
        }:
            raise LmsServiceError(422, "Assign the case to its current primary or backup owner")
        self.require_access(
            self.session.get(User, command.owner_user_id), case.course_id, case.queue_kind
        )
        events = self._events(case.id)
        prior = next(
            (event for event in events if event.request_key == command.idempotency_key), None
        )
        values = command.model_dump(exclude={"expected_revision", "idempotency_key"})
        if prior:
            exact = (
                prior.actor_user_id == actor.id and prior.revision == command.expected_revision + 1
            )
            for key, value in values.items():
                stored = getattr(prior, key)
                if key.endswith("_due_at"):
                    stored = stored.replace(tzinfo=UTC) if stored.tzinfo is None else stored
                exact = exact and stored == value
            if not exact:
                raise LmsServiceError(409, "This action key already has different details")
            self.session.rollback()
            return self.read_case(case, staff=True)
        latest = events[-1] if events else None
        if (latest.revision if latest else 0) != command.expected_revision:
            raise LmsServiceError(409, "The report changed; reload its history before acting")
        current = latest.status if latest else "OPEN"
        if current == "CLOSED" or STATES.index(command.status) not in {
            STATES.index(current),
            STATES.index(current) + 1,
        }:
            raise LmsServiceError(
                422,
                "A report must move through acknowledgement, action, resolution and closure in order",
            )
        event = EscalationEvent(
            case_id=case.id,
            queue_revision_id=configuration.id,
            revision=command.expected_revision + 1,
            request_key=command.idempotency_key,
            actor_user_id=actor.id,
            **values,
        )
        self.session.add(event)
        self.session.flush()
        self._audit(actor.id, case.id, f"escalation.{command.status.lower()}")
        self.session.commit()
        return self.read_case(case, staff=True)

    def samples(self, actor, course_id, offset=0):
        self.require_access(actor, course_id, "ASSESSOR")
        return list(
            self.session.scalars(
                select(FeedbackRecord.id)
                .join(SubmissionAttempt, SubmissionAttempt.id == FeedbackRecord.submission_id)
                .join(LearningTask, LearningTask.id == SubmissionAttempt.task_id)
                .where(
                    LearningTask.course_id == course_id,
                    FeedbackRecord.status == FeedbackStatus.ACCEPTED,
                )
                .order_by(FeedbackRecord.created_at.desc(), FeedbackRecord.id)
                .limit(50)
                .offset(offset)
            )
        )

    def sample(self, actor, course_id, command):
        self._lock(actor.id)
        self.require_access(actor, course_id, "ASSESSOR")
        source = source_for(self.session, "FEEDBACK", command.feedback_id)
        if (
            source is None
            or source.task.course_id != course_id
            or source.record.status is not FeedbackStatus.ACCEPTED
        ):
            raise LmsServiceError(404, "Accepted feedback not found in this course")
        case = record_signal(
            self.session,
            source_kind="FEEDBACK",
            source_id=command.feedback_id,
            trigger="HUMAN_SAMPLE",
            reason=command.reason,
            severity="NORMAL",
        )
        self.session.commit()
        return self.read_case(case, staff=True)

    def evidence(self, actor, case_id):
        case = self.session.get(EscalationCase, case_id)
        if case is None:
            raise LmsServiceError(404, "Report not found")
        self.require_access(actor, case.course_id, case.queue_kind)
        source = source_for(self.session, case.source_kind, case.source_id)
        if source is None:
            raise LmsServiceError(404, "Retained evidence is unavailable")
        if case.source_kind == "FEEDBACK":
            return {
                "feedback": source.record.feedback_content,
                "quality_status": source.record.status.value,
            }
        if case.source_kind == "TUTOR":
            return {"reply": source.record.reply, "quality": source.record.quality}
        return {
            "response_id": source.record.response_version_id,
            "state": source.record.state.value,
            "fault_reason": source.record.fault_reason,
        }

    def _events(self, case_id):
        return list(
            self.session.scalars(
                select(EscalationEvent)
                .where(EscalationEvent.case_id == case_id)
                .order_by(EscalationEvent.revision)
            )
        )

    def read_case(self, case, *, staff=False):
        events = self._events(case.id)
        latest = events[-1] if events else None
        values = dict(
            id=case.id,
            task_id=case.task_id,
            source_kind=case.source_kind,
            source_id=case.source_id,
            queue_kind=case.queue_kind,
            status=latest.status if latest else "OPEN",
            revision=latest.revision if latest else 0,
            severity=latest.severity if latest else case.severity,
            created_at=case.created_at,
            acknowledgement_due_at=latest.acknowledgement_due_at if latest else None,
            resolution_due_at=latest.resolution_due_at if latest else None,
            notices=[EscalationNotice.model_validate(event) for event in events],
        )
        if not staff:
            return EscalationRead(**values)
        configuration = self.configuration(case.course_id, case.queue_kind)
        owner = (
            latest.owner_user_id
            if latest and configuration and latest.queue_revision_id == configuration.id
            else configuration.primary_user_id
            if configuration
            else None
        )
        return EscalationStaffRead(
            **values,
            trigger=case.trigger,
            reason=case.reason,
            owner_user_id=owner,
            backup_user_id=configuration.backup_user_id if configuration else None,
            history=[
                dict(
                    revision=event.revision,
                    status=event.status,
                    reason=event.reason,
                    actor_user_id=event.actor_user_id,
                    owner_user_id=event.owner_user_id,
                    queue_revision_id=event.queue_revision_id,
                    at=event.created_at.isoformat(),
                )
                for event in events
            ],
        )

    def _lock(self, actor_id):
        self.session.execute(
            update(User).where(User.id == actor_id).values(id=User.id, updated_at=User.updated_at)
        )

    def _audit(self, actor_id, record_id, action):
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor_id,
                action=action,
                resource_type="escalation",
                resource_id=record_id,
                correlation_id=str(uuid4()),
                details={},
            )
        )
