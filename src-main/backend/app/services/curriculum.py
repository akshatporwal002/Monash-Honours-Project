"""Approved curriculum graph and human-confirmed, practice-only diagnostic paths."""

from dataclasses import asdict
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
)
from app.models.curriculum import (
    DiagnosticConfirmation,
    DiagnosticResponse,
    DiagnosticSession,
    PathwayVersion,
)
from app.models.lms import (
    Course,
    CourseModule,
    CourseState,
    Enrollment,
    EnrollmentStatus,
    LearningOutcome,
    utc_now,
)
from app.models.persistence import LearningTask
from app.models.user import User, UserRole
from app.schemas.curriculum import (
    DiagnosticConfirm,
    DiagnosticRead,
    DiagnosticStart,
    DiagnosticSubmit,
    PathwayPublish,
    PathwayRead,
)
from app.schemas.evidence import EvidenceArtifact, EvidenceRecord
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.submissions import AssessmentSubmissionService
from app.services.evidence.live import serialized
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.task_review import TaskReviewService
from app.services.validation_reads import reuse_validation_read


class CurriculumService:
    def __init__(self, session):
        self.session = session

    def _access(self, actor, course_id, *, owner=False):
        current = self.session.get(User, actor.id, populate_existing=True)
        course = self.session.get(Course, course_id, populate_existing=True)
        if not current or not current.is_active or not course:
            raise HTTPException(404, "Pathway is unavailable")
        if current.role == UserRole.EDUCATOR and course.educator_id == current.id:
            return course
        if not owner and current.role == UserRole.STUDENT and course.state == CourseState.PUBLISHED:
            if self.session.scalar(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == current.id,
                    Enrollment.status == EnrollmentStatus.ACTIVE,
                )
            ):
                return course
        if not owner and current.role != UserRole.STUDENT:
            try:
                RoleAssignmentService(self.session).require_assessor_access(current, course.id)
                return course
            except ScopedRoleAccessDeniedError:
                pass
        raise HTTPException(404, "Pathway is unavailable")

    def _latest(self, outcome_id):
        return self.session.scalar(
            select(PathwayVersion)
            .where(PathwayVersion.outcome_id == outcome_id)
            .order_by(PathwayVersion.version.desc())
            .limit(1)
        )

    def _bindings(self, course_id, outcome_id, payload):
        review = TaskReviewService(self.session)
        bindings = {}
        earlier = set()
        for step in payload.steps:
            task = self.session.get(LearningTask, step.task_id, populate_existing=True)
            if not task or (task.course_id, task.learning_outcome_id) != (course_id, outcome_id):
                raise HTTPException(422, "Every task must belong to this course and outcome")
            review.require_available(task)
            review.source_approvals(task, required=True)
            if not set(task.prerequisite_task_ids or []) <= earlier:
                raise HTTPException(
                    422, "Task prerequisites must precede the task within the pathway"
                )
            if not set(task.prerequisite_task_ids or []) <= set(step.prerequisites):
                raise HTTPException(422, "The pathway must preserve every task prerequisite")
            declaration = AssessmentSubmissionService(self.session).declaration_for_task(task)
            if declaration is not None and task.id == payload.diagnostic_task_id:
                raise HTTPException(422, "A diagnostic must use a non-assessed task")
            revision = review.latest_revision(task.id)
            event = review.latest_event(revision.id)
            bindings[task.id] = {
                "task_revision_id": revision.id,
                "review_event_id": event.id,
                "source_approvals": event.source_approvals,
                "title": task.title,
                "difficulty": task.difficulty,
                "task_form": task.task_type.value,
                "assessment": asdict(declaration.versions) if declaration else None,
            }
            earlier.add(task.id)
        return bindings

    def publish(self, actor, outcome_id, payload: PathwayPublish):
        outcome = self.session.get(LearningOutcome, outcome_id)
        module = self.session.get(CourseModule, outcome.module_id) if outcome else None
        if module is None:
            raise HTTPException(404, "Outcome is unavailable")
        self._access(actor, module.course_id, owner=True)
        self._lock(module.course_id)
        prior = self.session.scalar(
            select(PathwayVersion).where(
                PathwayVersion.outcome_id == outcome_id,
                PathwayVersion.request_key == payload.request_key,
            )
        )
        if prior:
            self._replay(prior.payload, payload)
            return self._path_read(prior)
        latest = self._latest(outcome_id)
        if (latest.version if latest else 0) != payload.expected_version:
            raise HTTPException(409, "Refresh the pathway version before publishing")
        bindings = self._bindings(module.course_id, outcome_id, payload)
        row = PathwayVersion(
            outcome_id=outcome_id,
            course_id=module.course_id,
            version=payload.expected_version + 1,
            request_key=payload.request_key,
            approved_by=actor.id,
            payload=payload.model_dump(),
            bindings=bindings,
        )
        self.session.add(row)
        self._commit()
        return self._path_read(row)

    @reuse_validation_read
    def _current(self, path):
        if self._latest(path.outcome_id).id != path.id:
            raise HTTPException(409, "A newer pathway is available. Start a new diagnostic")
        if (
            self._bindings(
                path.course_id, path.outcome_id, PathwayPublish.model_validate(path.payload)
            )
            != path.bindings
        ):
            raise HTTPException(
                409, "Task approval changed. The educator must publish a new pathway"
            )

    @staticmethod
    def _path_read(row):
        return PathwayRead(
            id=row.id,
            outcome_id=row.outcome_id,
            course_id=row.course_id,
            version=row.version,
            bindings=row.bindings,
            **{
                key: row.payload[key]
                for key in (
                    "title",
                    "steps",
                    "diagnostic_prompt",
                    "diagnostic_task_id",
                    "independent_conditions",
                )
            },
        )

    def list_paths(self, actor, course_id):
        self._access(actor, course_id)
        rows = self.session.scalars(
            select(PathwayVersion)
            .where(PathwayVersion.course_id == course_id)
            .order_by(PathwayVersion.version.desc())
        ).all()
        seen = set()
        result = []
        for row in rows:
            if row.outcome_id not in seen:
                seen.add(row.outcome_id)
                result.append(self._path_read(row))
        return result

    def start(self, actor, payload: DiagnosticStart):
        if actor.role != UserRole.STUDENT:
            raise HTTPException(403, "Only learners can request a diagnostic")
        path = self.session.get(PathwayVersion, payload.pathway_id)
        if not path:
            raise HTTPException(404, "Pathway is unavailable")
        self._access(actor, path.course_id)
        self._lock(path.course_id)
        prior = self.session.scalar(
            select(DiagnosticSession).where(
                DiagnosticSession.learner_id == actor.id,
                DiagnosticSession.request_key == payload.request_key,
            )
        )
        if prior:
            self._replay(prior.payload, payload)
            return self.read(actor, prior.id)
        self._current(path)
        self._bypass_tasks(path, payload.target_task_id)
        row = DiagnosticSession(
            pathway_id=path.id,
            learner_id=actor.id,
            request_key=payload.request_key,
            payload=payload.model_dump(),
        )
        self.session.add(row)
        self._commit()
        return self.read(actor, row.id)

    @staticmethod
    def _bypass_tasks(path, target):
        ids = [step["task_id"] for step in path.payload["steps"]]
        if target not in ids:
            raise HTTPException(422, "The diagnostic target must belong to this pathway")
        bypass = ids[: ids.index(target)]
        if any(path.bindings[task_id]["assessment"] for task_id in bypass + [target]):
            raise HTTPException(422, "Diagnostics cannot bypass or unlock formal assessment")
        return bypass

    def _session(self, actor, identity):
        row = self.session.get(DiagnosticSession, identity)
        path = self.session.get(PathwayVersion, row.pathway_id) if row else None
        if not path or (actor.role == UserRole.STUDENT and row.learner_id != actor.id):
            raise HTTPException(404, "Diagnostic is unavailable")
        self._access(actor, path.course_id)
        return row, path

    def read(self, actor, identity):
        row, path = self._session(actor, identity)
        response = self.session.scalar(
            select(DiagnosticResponse).where(DiagnosticResponse.session_id == row.id)
        )
        confirmation = self.session.scalar(
            select(DiagnosticConfirmation).where(DiagnosticConfirmation.session_id == row.id)
        )
        return DiagnosticRead(
            id=row.id,
            learner_id=row.learner_id,
            learner_name=self.session.get(User, row.learner_id).full_name,
            target_title=path.bindings[row.payload["target_task_id"]]["title"],
            pathway_id=path.id,
            purpose=row.payload["purpose"],
            target_task_id=row.payload["target_task_id"],
            state=confirmation.payload["decision"]
            if confirmation
            else "needs_review"
            if response
            else "started",
            prompt=path.payload["diagnostic_prompt"],
            independent_conditions=path.payload["independent_conditions"],
            evidence_id=response.evidence_id if response else None,
            response=response.payload if response else None,
            reason=confirmation.payload["reason"] if confirmation else None,
        )

    def list_diagnostics(self, actor, course_id, *, offset=0, limit=20):
        self._access(actor, course_id)
        query = (
            select(DiagnosticSession)
            .join(PathwayVersion)
            .where(PathwayVersion.course_id == course_id)
        )
        if actor.role == UserRole.STUDENT:
            query = query.where(DiagnosticSession.learner_id == actor.id)
        rows = self.session.scalars(
            query.order_by(DiagnosticSession.created_at.desc(), DiagnosticSession.id)
            .offset(offset)
            .limit(limit)
        )
        return [self.read(actor, row.id) for row in rows]

    def submit(self, actor, identity, payload: DiagnosticSubmit):
        row, path = self._session(actor, identity)
        if actor.role != UserRole.STUDENT or row.learner_id != actor.id:
            raise HTTPException(403, "Only the learner can submit this diagnostic")
        self._lock(path.course_id)
        existing = self.session.scalar(
            select(DiagnosticResponse).where(DiagnosticResponse.session_id == row.id)
        )
        if existing:
            self._replay(existing.payload, payload)
            return self.read(actor, row.id)
        self._current(path)
        evidence_id, artifact_id = str(uuid4()), str(uuid4())
        content = serialized(
            {
                "pathway_id": path.id,
                "target_task_id": row.payload["target_task_id"],
                "conditions": path.payload["independent_conditions"],
                "response": payload.model_dump(),
            }
        )
        digest = "sha256:" + sha256(content.encode()).hexdigest()
        when = utc_now()
        capture = EvidenceCapture(
            record=EvidenceRecord(
                evidence_id=evidence_id,
                course_id=path.course_id,
                learner_id=str(actor.id),
                outcome_id=path.outcome_id,
                activity_id=row.id,
                task_id=path.payload["diagnostic_task_id"],
                source_interaction_id=row.id,
                source_version=path.id,
                task_conditions_version=path.version,
                evidence_type=EvidenceType.DIAGNOSTIC,
                provenance=EvidenceProvenance.LEARNER,
                observation_type=ObservationType.SELF_REPORTED,
                instructional_support_level=InstructionalSupportLevel.CONCEPT_CUE,
                access_support_state=AccessSupportState.NOT_DECLARED,
                artifact_id=artifact_id,
                content_digest=digest,
                actor_reference=str(actor.id),
                agent_reference="curriculum.v1",
                correlation_id=row.id,
                schema_version="learnlens.diagnostic.v1",
                record_version=1,
                idempotency_key=row.id,
                occurred_at=when,
            ),
            artifact=EvidenceArtifact(
                artifact_id=artifact_id,
                course_id=path.course_id,
                learner_id=str(actor.id),
                content=content,
                content_digest=digest,
                content_format="application.json",
                record_version=1,
                occurred_at=when,
            ),
        )
        try:
            SqlAlchemyEvidenceRepository(self.session).capture(capture, commit=False)
            self.session.add(
                DiagnosticResponse(
                    session_id=row.id, evidence_id=evidence_id, payload=payload.model_dump()
                )
            )
            self._commit()
        except Exception:
            self.session.rollback()
            raise
        return self.read(actor, row.id)

    def confirm(self, actor, identity, payload: DiagnosticConfirm):
        row, path = self._session(actor, identity)
        self._lock(path.course_id)
        try:
            assignment = RoleAssignmentService(self.session).require_assessor_access(
                actor, path.course_id
            )
        except ScopedRoleAccessDeniedError:
            raise HTTPException(403, "A current course assessor grant is required") from None
        prior = self.session.scalar(
            select(DiagnosticConfirmation).where(DiagnosticConfirmation.session_id == row.id)
        )
        if prior:
            if prior.assessor_id != actor.id:
                raise HTTPException(409, "This diagnostic has already been reviewed")
            self._replay(prior.payload, payload)
            return self.read(actor, row.id)
        response = self.session.scalar(
            select(DiagnosticResponse).where(DiagnosticResponse.session_id == row.id)
        )
        if not response:
            raise HTTPException(409, "Diagnostic evidence is required before review")
        self._current(path)
        if payload.decision == "advance":
            self._bypass_tasks(path, row.payload["target_task_id"])
            if (
                not payload.independent_verified
                or not response.payload["independent_conditions_met"]
            ):
                raise HTTPException(
                    422,
                    "Both the learner declaration and assessor verification of independent conditions are required",
                )
        self.session.add(
            DiagnosticConfirmation(
                session_id=row.id,
                assessor_id=actor.id,
                assignment_id=assignment.id,
                payload=payload.model_dump(),
            )
        )
        self._commit()
        return self.read(actor, row.id)

    @staticmethod
    def _replay(stored, payload):
        if stored != payload.model_dump():
            raise HTTPException(409, "This request already has a different saved response")

    def _lock(self, course_id):
        try:
            self.session.execute(
                update(Course)
                .where(Course.id == course_id)
                .values(id=Course.id, updated_at=Course.updated_at)
            )
        except SQLAlchemyError:
            self.session.rollback()
            raise HTTPException(503, "The pathway is busy. Retry the original request") from None

    def _commit(self):
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(
                409, "Another request was saved first. Reload or retry the original request"
            ) from None
        except SQLAlchemyError:
            self.session.rollback()
            raise HTTPException(
                503, "The change could not be saved. Retry the original request"
            ) from None


def pathway_progress(session, learner_id, task):
    """Only current practice graphs can grant prerequisite bypass or optional fading."""
    return PathwayProgressReader(session, learner_id).read(task)


class PathwayProgressReader:
    """Validate each pathway once within one learner dashboard read.

    Create a new reader for every operation; never retain it across requests or
    mutations. No approval or learner evidence is cached on the session/service.
    """

    def __init__(self, session, learner_id):
        self.session = session
        self.learner_id = learner_id
        self.service = CurriculumService(session)
        self.paths = {}
        self.bypasses = {}

    def read(self, task):
        fallback = (set(), set(task.prerequisite_task_ids or []), None)
        if not task.learning_outcome_id:
            return fallback
        if task.learning_outcome_id not in self.paths:
            self.paths[task.learning_outcome_id] = self.service._latest(task.learning_outcome_id)
        path = self.paths[task.learning_outcome_id]
        if not path:
            return fallback
        step = next((item for item in path.payload["steps"] if item["task_id"] == task.id), None)
        if not step or path.bindings[task.id]["assessment"]:
            return fallback
        if path.id not in self.bypasses:
            # The original approval checks still run before any bypass is used.
            self.service._current(path)
            rows = self.session.execute(
                select(DiagnosticSession, DiagnosticConfirmation)
                .join(
                    DiagnosticConfirmation,
                    DiagnosticConfirmation.session_id == DiagnosticSession.id,
                )
                .where(
                    DiagnosticSession.pathway_id == path.id,
                    DiagnosticSession.learner_id == self.learner_id,
                )
            ).all()
            bypassed = set()
            for diagnostic, confirmation in rows:
                if confirmation.payload["decision"] == "advance":
                    bypassed.update(
                        self.service._bypass_tasks(path, diagnostic.payload["target_task_id"])
                    )
            self.bypasses[path.id] = bypassed
        bypassed = self.bypasses[path.id]
        faded = bool(bypassed & set(step["prerequisites"]))
        support = step["faded_support_level"] if faded else step["support_level"]
        return set(bypassed), set(step["prerequisites"]), support


def pathway_completions(session, learner_id, task):
    """Apply an approved practice exit rule without reading legacy numeric grades."""
    from app.models.lms import SubmissionAttempt

    service = CurriculumService(session)
    path = service._latest(task.learning_outcome_id) if task.learning_outcome_id else None
    if not path or task.id not in path.bindings or path.bindings[task.id]["assessment"]:
        return set()
    service._current(path)
    practice = [
        step["task_id"]
        for step in path.payload["steps"]
        if step["exit_rule"] == "accepted_response"
        and not path.bindings[step["task_id"]]["assessment"]
    ]
    return set(
        session.scalars(
            select(SubmissionAttempt.task_id).where(
                SubmissionAttempt.student_id == learner_id,
                SubmissionAttempt.task_id.in_(practice),
            )
        )
    )
