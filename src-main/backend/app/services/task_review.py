"""Review exact task content before it can be published to learners."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Course,
    CourseModule,
    LearningMaterial,
    LearningOutcome,
    LearningTask,
    PlatformAuditEvent,
    User,
    UserRole,
)
from app.models.source_history import SourcePassage, SourceRevision
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.episode_contract import validate_reviewed_episode_plan
from app.services.quantum import (
    CircuitOperation,
    QuantumSimulationError,
    simulation_capabilities,
    validate_circuit,
)
from app.services.rag.source_history import latest_approval
from app.services.validation_reads import reuse_validation_read

TASK_CONTENT_FIELDS = (
    "id",
    "slug",
    "title",
    "module",
    "description",
    "instructions",
    "task_type",
    "difficulty",
    "points",
    "position",
    "starter_code",
    "expected_answer",
    "due_at",
    "course_id",
    "module_id",
    "learning_outcome_id",
    "marking_criteria",
    "source_references",
    "prerequisite_task_ids",
    "generation_provider",
    "generation_model",
    "generation_prompt_version",
)


class TaskReviewError(ValueError):
    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(detail)
        self.detail, self.status_code = detail, status_code


def _json_value(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        ).isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Unsupported task snapshot value")


def task_snapshot(session: Session, task: LearningTask) -> dict:
    values = {field: getattr(task, field) for field in TASK_CONTENT_FIELDS}
    outcome = (
        session.get(LearningOutcome, task.learning_outcome_id, populate_existing=True)
        if task.learning_outcome_id
        else None
    )
    values["outcome"] = (
        {
            "id": outcome.id,
            "module_id": outcome.module_id,
            "title": outcome.title,
            "statement": outcome.statement,
            "kind": outcome.kind,
        }
        if outcome
        else None
    )
    return json.loads(json.dumps(values, default=_json_value, allow_nan=False))


def snapshot_digest(snapshot: dict) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class TaskReviewService:
    def __init__(self, session: Session, *, correlation_id: str | None = None):
        self.session = session
        self.correlation_id = correlation_id or str(uuid4())

    @reuse_validation_read
    def latest_revision(self, task_id: str) -> TaskRevision | None:
        return self.session.scalar(
            select(TaskRevision)
            .where(TaskRevision.task_id == task_id)
            .order_by(TaskRevision.version.desc())
            .limit(1)
        )

    @reuse_validation_read
    def latest_event(self, revision_id: str) -> TaskReviewEvent | None:
        return self.session.scalar(
            select(TaskReviewEvent)
            .where(TaskReviewEvent.task_revision_id == revision_id)
            .order_by(TaskReviewEvent.version.desc())
            .limit(1)
        )

    def prepare_edit(
        self, actor: User, task: LearningTask, expected_revision_id: str | None
    ) -> None:
        self._lock_course(task.course_id)
        self.session.refresh(task)
        self._require_owner(actor, task.course_id)
        revision = self.latest_revision(task.id)
        if expected_revision_id is not None and (
            revision is None
            or revision.id != expected_revision_id
            or revision.content_digest != snapshot_digest(task_snapshot(self.session, task))
        ):
            raise TaskReviewError("Task content changed; reload before saving edits")

    def capture(
        self, task: LearningTask, actor_user_id: int | None = None, *, provenance: str | None = None
    ) -> TaskRevision:
        """Append to the caller's authoring transaction; never approve implicitly."""
        if not task.course_id or self.session.get(Course, task.course_id) is None:
            raise TaskReviewError("Task revisions require an existing course", 422)
        self._lock_course(task.course_id)
        self.session.flush()
        self.session.refresh(task)
        snapshot = task_snapshot(self.session, task)
        digest = snapshot_digest(snapshot)
        previous = self.latest_revision(task.id)
        if previous and previous.content_digest == digest:
            return previous
        generated = task.generation_provider is not None or task.slug.startswith("generated-")
        revision = TaskRevision(
            task_id=task.id,
            course_id=task.course_id,
            version=previous.version + 1 if previous else 1,
            snapshot=snapshot,
            content_digest=digest,
            provenance=provenance or ("GENERATED" if generated else "AUTHORED"),
            actor_user_id=actor_user_id,
        )
        self.session.add(revision)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise TaskReviewError("Task changed while its revision was saved") from error
        return revision

    def record(
        self,
        actor: User,
        task_id: str,
        *,
        expected_revision_id: str,
        expected_review_version: int,
        state: str,
        reason: str,
    ) -> TaskReviewEvent:
        try:
            task = self._get_task(task_id)
            self._lock_course(task.course_id)
            self.session.refresh(task)
            self._require_owner(actor, task.course_id)
            revision = self.latest_revision(task.id)
            if (
                revision is None
                or revision.id != expected_revision_id
                or revision.content_digest != snapshot_digest(task_snapshot(self.session, task))
            ):
                raise TaskReviewError("Task content changed; save a new revision before reviewing")
            previous = self.latest_event(revision.id)
            review_version = previous.version if previous else 0
            if review_version != expected_review_version:
                raise TaskReviewError("Task review changed; reload its history")
            prior_state = previous.state if previous else "DRAFT"
            allowed = {
                "SUBMITTED": {"DRAFT", "REJECTED", "WITHDRAWN"},
                "APPROVED": {"SUBMITTED"},
                "REJECTED": {"SUBMITTED"},
                "WITHDRAWN": {"SUBMITTED", "APPROVED"},
            }
            if state not in allowed or prior_state not in allowed[state]:
                raise TaskReviewError("This review action is not valid in the current state")
            if not reason.strip() or len(reason) > 2000:
                raise TaskReviewError("A review reason of up to 2000 characters is required", 422)
            sources = self.validate_ready(task) if state == "APPROVED" else {}
            event = TaskReviewEvent(
                task_revision_id=revision.id,
                course_id=task.course_id,
                version=review_version + 1,
                state=state,
                actor_user_id=actor.id,
                reason=reason.strip(),
                source_approvals=sources,
            )
            self.session.add(event)
            self.session.flush()
            self.session.add(
                PlatformAuditEvent(
                    actor_id=actor.id,
                    action="task_review." + state.lower(),
                    resource_type="task_revision",
                    resource_id=revision.id,
                    correlation_id=self.correlation_id,
                    details={
                        "task_id": task.id,
                        "course_id": task.course_id,
                        "content_digest": revision.content_digest,
                        "review_version": event.version,
                    },
                )
            )
            self.session.commit()
            return event
        except IntegrityError as error:
            self.session.rollback()
            raise TaskReviewError("Task review changed; reload its history") from error
        except TaskReviewError:
            self.session.rollback()
            raise

    def validate_ready(
        self, task: LearningTask, *, require_sources: bool = False, require_scan: bool = True
    ) -> dict[str, str]:
        module = (
            self.session.get(CourseModule, task.module_id, populate_existing=True)
            if task.module_id
            else None
        )
        outcome = (
            self.session.get(LearningOutcome, task.learning_outcome_id, populate_existing=True)
            if task.learning_outcome_id
            else None
        )
        if (
            module is None
            or module.course_id != task.course_id
            or outcome is None
            or outcome.module_id != module.id
            or not outcome.statement.strip()
        ):
            raise TaskReviewError("The task needs a valid course module and learning outcome", 422)
        if not all(
            str(value or "").strip() for value in (task.title, task.description, task.instructions)
        ):
            raise TaskReviewError("Task title, prompt, and instructions are required", 422)
        if not task.expected_answer and not task.marking_criteria:
            raise TaskReviewError("The task needs marking guidance before approval", 422)
        try:
            plan = validate_reviewed_episode_plan(
                task.marking_criteria if isinstance(task.marking_criteria, dict) else None
            )
        except ValueError as error:
            raise TaskReviewError(
                "The learning episode plan needs valid stage settings", 422
            ) from error
        if plan is not None:
            for representation in plan.support_representations:
                if not set(representation.source_references) <= set(task.source_references or []):
                    raise TaskReviewError(
                        "Support representations must cite declared task sources", 422
                    )
                if representation.circuit is not None:
                    self._validate_circuit_payload(representation.circuit)
            for circuit in (
                plan.transfer.starter_circuit,
                plan.transfer.solution.circuit if plan.transfer.solution else None,
            ):
                if circuit is not None:
                    self._validate_circuit_payload(circuit)
        from app.schemas.practice_representations import practice_representations

        try:
            for representation in practice_representations(
                task.marking_criteria or {}, task.source_references or []
            ):
                if representation.circuit is not None:
                    self._validate_circuit_payload(representation.circuit)
        except ValueError as error:
            raise TaskReviewError(str(error), 422) from error
        from app.schemas.choice_tasks import validate_choice_key
        from app.schemas.structured_tasks import definition_for, response_for
        from app.services.task_types import DEFAULT_TASK_TYPE_REGISTRY

        try:
            validate_choice_key(task.task_type.value, task.marking_criteria, task.expected_answer)
            if (
                task.generation_prompt_version == "task-generation-multipart-v1"
                or isinstance(task.marking_criteria, dict)
                and "multipart_candidate" in task.marking_criteria
            ):
                from app.services.multipart_generation import validate_multipart

                validate_multipart(
                    task.marking_criteria,
                    task.task_type.value,
                    {
                        ref: passage.chunk_text
                        for ref in task.source_references or []
                        if (passage := self.session.get(SourcePassage, ref)) is not None
                    },
                )
            if task.generation_prompt_version in {
                "task-generation-v2",
                "task-generation-multipart-v1",
            }:
                from app.schemas.generated_task_design import GeneratedTaskDesign

                GeneratedTaskDesign.model_validate(
                    (task.marking_criteria or {}).get("generation_design")
                )
            DEFAULT_TASK_TYPE_REGISTRY.resolve(task.task_type)
            structured = definition_for(
                task.task_type.value, task.marking_criteria or {}, task.source_references or []
            )
            if structured and task.expected_answer:
                response_for(structured, task.expected_answer, complete=True)
            if (
                structured
                and not task.expected_answer
                and task.marking_criteria.get("response_review") != "human"
            ):
                raise ValueError("Structured tasks require an answer key or explicit human review")
        except ValueError as error:
            raise TaskReviewError(str(error), 422) from error
        self._validate_circuit(task)
        return self.source_approvals(
            task,
            required=require_sources
            or task.generation_provider is not None
            or task.slug.startswith("generated-"),
            require_scan=require_scan,
        )

    @reuse_validation_read
    def source_approvals(
        self, task: LearningTask, *, required: bool = False, require_scan: bool = True
    ) -> dict[str, str]:
        if required and not task.source_references:
            raise TaskReviewError("Approved source passages are required for this task", 422)
        approved = {}
        for reference in task.source_references or []:
            passage = self.session.get(SourcePassage, reference)
            revision = self.session.get(SourceRevision, passage.revision_id) if passage else None
            material = (
                self.session.get(LearningMaterial, revision.material_id, populate_existing=True)
                if revision
                else None
            )
            approval = latest_approval(self.session, revision.id) if revision else None
            if (
                passage is None
                or passage.course_id != task.course_id
                or revision is None
                or revision.course_id != task.course_id
                or material is None
                or material.retired_at is not None
                or approval is None
                or approval.state != "APPROVED"
            ):
                raise TaskReviewError(
                    "Each source passage must have current approval in this course", 422
                )
            from app.services.material_scanning import revision_scan_is_clean

            if require_scan and not revision_scan_is_clean(self.session, revision):
                raise TaskReviewError("Source bytes need a successful malware scan", 422)
            approved[reference] = approval.id
        return approved

    @reuse_validation_read
    def summary(self, task: LearningTask) -> dict:
        revision = self.latest_revision(task.id)
        event = self.latest_event(revision.id) if revision else None
        issues = []
        if revision is None:
            issues.append("Save a task revision before review")
        elif revision.content_digest != snapshot_digest(task_snapshot(self.session, task)):
            issues.append("Task content changed after this revision")
        if event is None or event.state != "APPROVED":
            issues.append("Educator approval is required")
        elif not issues:
            try:
                sources = self.validate_ready(task, require_scan=False)
                if sources != event.source_approvals:
                    issues.append("Source approval changed after the task review")
            except TaskReviewError as error:
                issues.append(error.detail)
        return {
            "revision_id": revision.id if revision else None,
            "revision": revision.version if revision else 0,
            "content_digest": revision.content_digest if revision else None,
            "state": event.state if event else "DRAFT",
            "review_version": event.version if event else 0,
            "available": not issues,
            "issues": issues,
        }

    def require_available(self, task: LearningTask) -> None:
        summary = self.summary(task)
        if not summary["available"]:
            raise TaskReviewError("Task is unavailable: " + "; ".join(summary["issues"]), 409)

    def history(self, actor: User, task_id: str, *, limit: int = 20, offset: int = 0) -> list[dict]:
        if not 1 <= limit <= 100 or offset < 0:
            raise TaskReviewError("Invalid history page", 422)
        task = self._get_task(task_id)
        self.require_review_access(actor, task.course_id)
        revisions = self.session.scalars(
            select(TaskRevision)
            .where(TaskRevision.task_id == task.id)
            .order_by(TaskRevision.version.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [
            {
                "revision": revision,
                "events": list(
                    self.session.scalars(
                        select(TaskReviewEvent)
                        .where(TaskReviewEvent.task_revision_id == revision.id)
                        .order_by(TaskReviewEvent.version)
                    )
                ),
            }
            for revision in revisions
        ]

    def review_summary(self, actor: User, task_id: str) -> dict:
        task = self._get_task(task_id)
        self.require_review_access(actor, task.course_id)
        return self.summary(task)

    def require_review_access(self, actor: User, course_id: str) -> None:
        current = self.session.get(User, actor.id, populate_existing=True)
        course = self.session.get(Course, course_id, populate_existing=True)
        if current is None or not current.is_active or course is None:
            raise TaskReviewError("Task review access denied", 403)
        if current.role is UserRole.ADMINISTRATOR or (
            current.role is UserRole.EDUCATOR and course.educator_id == actor.id
        ):
            return
        try:
            RoleAssignmentService(self.session).require_assessor_access(current, course_id)
        except ScopedRoleAccessDeniedError:
            raise TaskReviewError("Task review access denied", 403) from None

    def _require_owner(self, actor: User, course_id: str) -> None:
        current = self.session.get(User, actor.id, populate_existing=True)
        course = self.session.get(Course, course_id, populate_existing=True)
        if (
            current is None
            or not current.is_active
            or current.role is not UserRole.EDUCATOR
            or course is None
            or course.educator_id != actor.id
        ):
            raise TaskReviewError("Only the course educator can review its learning tasks", 403)

    def _get_task(self, task_id: str) -> LearningTask:
        task = self.session.get(LearningTask, task_id)
        if task is None or not task.course_id:
            raise TaskReviewError("Task not found", 404)
        return task

    def _lock_course(self, course_id: str) -> None:
        self.session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(id=Course.id, updated_at=Course.updated_at)
        )

    @staticmethod
    def _validate_circuit(task: LearningTask) -> None:
        if task.task_type.value not in {"quantum_circuit", "circuit"}:
            return
        criteria = task.marking_criteria if isinstance(task.marking_criteria, dict) else {}
        supported = set(simulation_capabilities()["gates"])
        for name in ("required_gates", "allowed_gates"):
            gates = criteria.get(name, [])
            if not isinstance(gates, list) or any(
                not isinstance(gate, str) or gate.casefold() not in supported for gate in gates
            ):
                raise TaskReviewError(
                    "The task requires gates outside the supported simulator", 422
                )
        template = criteria.get("starter_circuit")
        if not isinstance(template, dict):
            raise TaskReviewError("Circuit tasks need a supported starter circuit", 422)
        for circuit in (template, criteria.get("expected_circuit")):
            if circuit is None:
                continue
            TaskReviewService._validate_circuit_payload(circuit)

    @staticmethod
    def _validate_circuit_payload(circuit: object) -> None:
        try:
            if (
                not isinstance(circuit, dict)
                or set(circuit) - {"qubits", "operations", "shots", "seed"}
                or not isinstance(circuit.get("operations"), list)
                or any(
                    not isinstance(operation, dict) or set(operation) != {"gate", "targets"}
                    for operation in circuit.get("operations", [])
                )
            ):
                raise QuantumSimulationError("Unsupported circuit shape")
            operations = [
                CircuitOperation(op["gate"], tuple(op["targets"])) for op in circuit["operations"]
            ]
            validate_circuit(
                qubits=circuit["qubits"],
                operations=operations,
                shots=circuit.get("shots", 1024),
                seed=circuit.get("seed", 42),
                allow_empty=True,
            )
        except (KeyError, TypeError, QuantumSimulationError) as error:
            raise TaskReviewError(
                "The task contains an unsupported circuit specification", 422
            ) from error
