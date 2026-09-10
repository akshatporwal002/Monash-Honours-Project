"""Fail-closed research policy; evidence and the release gate are independent."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.lms import Course, Enrollment, EnrollmentStatus
from app.models.research_governance import ResearchCaseGovernance, ResearchGovernanceEvent
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.schemas.research_governance import (
    PROCESSING_FIELDS,
    ApprovalDecision,
    ConsentDecision,
    EligibilityDecision,
    GovernanceCommand,
    ResearchGrant,
    RetentionHold,
    StudyScope,
)


def research_processing_approved() -> bool:
    """Intentionally closed for Task 33. Configuration is never institutional approval."""
    return False


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class GovernanceDenied(ValueError):
    """Controlled denial code containing no participant information."""


class GovernanceConflict(ValueError):
    """Concurrent revision or reused request key; the caller must reload."""


def lock_governance_write(session):
    """Serialize SQLite eligibility checks with withdrawals before a research write."""
    connection = session.connection()
    if (
        connection.dialect.name == "sqlite"
        and not connection.connection.driver_connection.in_transaction
    ):
        connection.exec_driver_sql("BEGIN IMMEDIATE")


class ResearchGovernanceService:
    def __init__(self, session, *, now=None):
        self.session = session
        self.now = now or (lambda: datetime.now(UTC))

    def events(self, study_id):
        return list(
            self.session.scalars(
                select(ResearchGovernanceEvent)
                .where(ResearchGovernanceEvent.study_id == study_id)
                .order_by(ResearchGovernanceEvent.revision)
                .execution_options(populate_existing=True)
            )
        )

    @staticmethod
    def decision(event):
        return GovernanceCommand.model_validate(event.command).decision

    def record(self, actor_id, study_id, command):
        try:
            lock_governance_write(self.session)
            return self._record(actor_id, study_id, command)
        except Exception:
            self.session.rollback()
            raise

    def _record(self, actor_id, study_id, command):
        actor = self.session.get(User, actor_id, populate_existing=True)
        if actor is None or not actor.is_active:
            raise GovernanceDenied("inactive_actor")
        decision = command.decision
        if isinstance(decision, ConsentDecision):
            if decision.subject_user_id != actor_id:
                raise GovernanceDenied("consent_owner_required")
        elif actor.role != UserRole.ADMINISTRATOR:
            raise GovernanceDenied("governance_custodian_required")
        existing = self.session.scalar(
            select(ResearchGovernanceEvent).where(
                ResearchGovernanceEvent.actor_user_id == actor_id,
                ResearchGovernanceEvent.request_key == command.request_key,
            )
        )
        payload = command.model_dump(mode="json")
        if existing:
            if existing.study_id == study_id and existing.command == payload:
                self.session.commit()
                return existing
            raise GovernanceConflict("request_key_reused")
        events = self.events(study_id)
        revision = events[-1].revision if events else 0
        if revision != command.expected_revision:
            raise GovernanceConflict("revision_changed")
        self._validate(decision, events)
        event = ResearchGovernanceEvent(
            study_id=study_id,
            revision=revision + 1,
            actor_user_id=actor_id,
            request_key=command.request_key,
            kind=decision.kind,
            command=payload,
            recorded_at=self.now(),
        )
        self.session.add(event)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(ResearchGovernanceEvent).where(
                    ResearchGovernanceEvent.actor_user_id == actor_id,
                    ResearchGovernanceEvent.request_key == command.request_key,
                )
            )
            if existing and existing.study_id == study_id and existing.command == payload:
                return existing
            raise GovernanceConflict("revision_changed") from None
        return event

    def _validate(self, decision, events):
        if isinstance(decision, StudyScope):
            if self.session.get(User, decision.processing_researcher_id) is None:
                raise GovernanceDenied("unknown_processing_researcher")
            if any(self.session.get(Course, c) is None for c in decision.course_ids):
                raise GovernanceDenied("unknown_course")
            return
        scope_event = next((e for e in reversed(events) if e.kind == "scope"), None)
        withdrawing = isinstance(decision, ConsentDecision) and decision.decision != "consented"
        if withdrawing:
            scope_event = next(
                (e for e in events if e.id == decision.scope_id and e.kind == "scope"), None
            )
        if scope_event is None or scope_event.id != decision.scope_id:
            raise GovernanceDenied("scope_version_mismatch")
        scope = self.decision(scope_event)
        if hasattr(decision, "course_id") and decision.course_id not in scope.course_ids:
            raise GovernanceDenied("course_out_of_scope")
        if hasattr(decision, "fields") and not set(decision.fields) <= set(scope.fields):
            raise GovernanceDenied("field_not_approved")
        if (
            hasattr(decision, "subject_user_id")
            and self.session.get(User, decision.subject_user_id) is None
        ):
            raise GovernanceDenied("unknown_subject")
        if isinstance(decision, ApprovalDecision | ResearchGrant):
            if not (
                scope.valid_from <= decision.valid_from < decision.valid_until <= scope.valid_until
            ):
                raise GovernanceDenied("invalid_access_window")
        if isinstance(decision, ConsentDecision) and not withdrawing:
            self.approved(scope_event.study_id)
            if decision.consent_version != scope.consent_version or not set(
                decision.purposes
            ) <= set(scope.purposes):
                raise GovernanceDenied("consent_scope_mismatch")
        if (
            isinstance(decision, EligibilityDecision)
            and decision.rule_version != scope.eligibility_rule_version
        ):
            raise GovernanceDenied("eligibility_version_mismatch")
        if isinstance(decision, RetentionHold) and decision.record_class not in {
            r.record_class for r in scope.retention
        }:
            raise GovernanceDenied("unknown_retention_class")

    def approved(self, study_id):
        events = self.events(study_id)
        scope_event = next((e for e in reversed(events) if e.kind == "scope"), None)
        if scope_event is None:
            raise GovernanceDenied("approval_missing")
        scope = self.decision(scope_event)
        approval_event = next((e for e in reversed(events) if e.kind == "approval"), None)
        if approval_event is None:
            raise GovernanceDenied("approval_missing")
        approval = self.decision(approval_event)
        now = utc(self.now())
        if approval.scope_id != scope_event.id or approval.state != "approved":
            raise GovernanceDenied("approval_inactive")
        if not (
            scope.valid_from <= now < scope.valid_until
            and approval.valid_from <= now < approval.valid_until
        ):
            raise GovernanceDenied("approval_expired")
        if any(item.review_at <= now for item in scope.retention):
            raise GovernanceDenied("retention_review_due")
        return scope_event, scope, events

    def participant(self, study_id, course_id, user_id, *, fields, purposes):
        scope_event, scope, events = self.approved(study_id)
        if course_id not in scope.course_ids or not set(fields) <= set(scope.fields):
            raise GovernanceDenied("scope_denied")
        user = self.session.get(User, user_id, populate_existing=True)
        enrolled = self.session.scalar(
            select(Enrollment.id).where(
                Enrollment.student_id == user_id,
                Enrollment.course_id == course_id,
                Enrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )
        if user is None or not user.is_active or enrolled is None:
            raise GovernanceDenied("participant_ineligible")
        consent_event = self._subject_event(events, "consent", course_id, user_id)
        eligibility_event = self._subject_event(events, "eligibility", course_id, user_id)
        if consent_event is None:
            raise GovernanceDenied("consent_missing")
        consent = self.decision(consent_event)
        if consent.decision != "consented":
            raise GovernanceDenied("consent_inactive")
        if (
            consent.scope_id != scope_event.id
            or consent.consent_version != scope.consent_version
            or not set(fields) <= set(consent.fields)
            or not set(purposes) <= set(consent.purposes) & set(scope.purposes)
        ):
            raise GovernanceDenied("consent_scope_mismatch")
        eligibility = self.decision(eligibility_event) if eligibility_event else None
        if (
            eligibility is None
            or eligibility.scope_id != scope_event.id
            or not eligibility.eligible
            or eligibility.rule_version != scope.eligibility_rule_version
            or eligibility.valid_until <= utc(self.now())
        ):
            raise GovernanceDenied("participant_ineligible")
        return scope_event, consent_event

    def grant(self, study_id, course_id, actor_id, fields):
        scope_event, scope, events = self.approved(study_id)
        now = utc(self.now())
        actor = self.session.get(User, actor_id, populate_existing=True)
        role = self.session.scalar(
            select(RoleAssignment.id).where(
                RoleAssignment.subject_user_id == actor_id,
                RoleAssignment.course_id == course_id,
                RoleAssignment.role == ScopedRole.RESEARCH,
                RoleAssignment.revoked_at.is_(None),
                RoleAssignment.valid_from <= now,
                (RoleAssignment.valid_until.is_(None) | (RoleAssignment.valid_until > now)),
            )
        )
        event = self._subject_event(events, "grant", course_id, actor_id)
        grant = self.decision(event) if event else None
        if (
            actor is None
            or not actor.is_active
            or role is None
            or grant is None
            or grant.revoked
            or grant.scope_id != scope_event.id
            or course_id not in scope.course_ids
            or not grant.valid_from <= now < grant.valid_until
        ):
            raise GovernanceDenied("grant_inactive")
        if not set(fields) <= set(grant.fields) & set(scope.fields):
            raise GovernanceDenied("field_denied")
        return event

    def _subject_event(self, events, kind, course_id, user_id):
        return next(
            (
                e
                for e in reversed(events)
                if e.kind == kind
                and self.decision(e).course_id == course_id
                and self.decision(e).subject_user_id == user_id
            ),
            None,
        )

    def processing_scope(self, course_id, user_id):
        if not research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        candidates = []
        studies = self.session.scalars(select(ResearchGovernanceEvent.study_id).distinct()).all()
        for study in studies:
            try:
                participant = self.participant(
                    study,
                    course_id,
                    user_id,
                    fields=PROCESSING_FIELDS,
                    purposes={"technical_pair", "provider_processing"},
                )
                scope = self.decision(participant[0])
                self.grant(study, course_id, scope.processing_researcher_id, PROCESSING_FIELDS)
                candidates.append(participant)
            except GovernanceDenied:
                continue
        if len(candidates) != 1:
            raise GovernanceDenied("unambiguous_study_required")
        return candidates[0]

    def require_case(
        self,
        case_id,
        *,
        fields=PROCESSING_FIELDS,
        purposes=("technical_pair", "provider_processing"),
    ):
        if not research_processing_approved():
            raise GovernanceDenied("research_governance_pending")
        binding = self.session.scalar(
            select(ResearchCaseGovernance)
            .where(ResearchCaseGovernance.case_id == case_id)
            .execution_options(populate_existing=True)
        )
        if binding is None:
            raise GovernanceDenied("legacy_case_unapproved")
        consent_event = self.session.get(ResearchGovernanceEvent, binding.consent_id)
        consent = self.decision(consent_event)
        scope, current_consent = self.participant(
            consent_event.study_id,
            binding.course_id,
            consent.subject_user_id,
            fields=fields,
            purposes=purposes,
        )
        if scope.id != binding.scope_id or current_consent.id != binding.consent_id:
            raise GovernanceDenied("case_consent_changed")
        if "provider_processing" in purposes:
            self.grant(
                scope.study_id,
                binding.course_id,
                self.decision(scope).processing_researcher_id,
                fields,
            )
        return binding

    def retention_disposition(self, study_id, record_class):
        events = self.events(study_id)
        scope_event = next((e for e in reversed(events) if e.kind == "scope"), None)
        if scope_event is None:
            return {"status": "schedule_missing", "disposal_permitted": False}
        schedule = next(
            (r for r in self.decision(scope_event).retention if r.record_class == record_class),
            None,
        )
        if schedule is None:
            return {"status": "schedule_missing", "disposal_permitted": False}
        holds = {}
        for event in events:
            decision = self.decision(event)
            if isinstance(decision, RetentionHold) and decision.record_class == record_class:
                holds[decision.hold_reference] = decision.active
        return {
            "status": "held" if any(holds.values()) else "review_required",
            "schedule": schedule.model_dump(mode="json") if schedule else None,
            "disposal_permitted": False,
        }
