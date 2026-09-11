"""Change-sensitive evaluator validation records, separate from AI activation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import ValidationError
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.assessment import TaskFormVersion
from app.models.assessment_moderation import EvaluatorValidationEvent
from app.models.lms import PlatformAuditEvent
from app.models.persistence import LearningTask
from app.models.user import UserRole
from app.schemas.evaluator_governance import AssessmentGateEvidence
from app.services.assessment.moderation import ModerationService, utc
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)

DEPENDENCY_TABLES = {
    "task": (
        "learning_tasks",
        "task_revisions",
        "task_review_events",
        "task_form_versions",
        "task_approvals",
    ),
    "source": ("learning_materials", "source_revisions", "source_passages", "source_approvals"),
    "retrieval": ("material_chunks",),
    "bloom": ("bloom_target_versions",),
    "criteria": ("criterion_versions",),
    "pass_rule": ("pass_rule_versions", "assessment_definition_versions"),
    "curriculum": (
        "course_modules",
        "learning_outcomes",
        "outcome_versions",
        "curriculum_pathway_versions",
    ),
    "configuration": ("system_settings",),
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def semantic_record(row):
    ignored = {"storage_key", "processing_token", "processing_attempts", "extraction_error"}
    return {
        key: (value is not None if key in {"retired_at", "revoked_at"} else value)
        for key, value in row.items()
        if key not in ignored and (not key.endswith("_at") or key in {"retired_at", "revoked_at"})
    }


class EvaluatorReleaseService:
    def __init__(self, session, *, correlation_id=None):
        self.session = session
        if correlation_id:
            session.info["assessment_governance_correlation_id"] = correlation_id
        self.correlation_id = (
            correlation_id
            or session.info.get("assessment_governance_correlation_id")
            or str(uuid4())
        )

    def _audit(self, row):
        self.session.add(
            PlatformAuditEvent(
                actor_id=row.actor_id,
                action=f"assessment_evaluator.{row.state.lower()}",
                resource_type="evaluator_validation",
                resource_id=row.id,
                correlation_id=self.correlation_id,
                details={
                    "course_id": row.course_id,
                    "validation_revision": row.revision,
                    "result": row.state,
                    "fingerprint": row.fingerprint,
                    "model_version": settings.llm_model,
                    "provider": settings.llm_provider,
                    "dependency_versions": row.dependencies,
                    "reason": row.reason,
                },
            )
        )

    def dependencies(self, course_id):
        dependencies = {}
        connection = self.session.connection()
        for category, names in DEPENDENCY_TABLES.items():
            records = {}
            for name in names:
                table = Base.metadata.tables[name]
                statement = select(table).order_by(*table.primary_key.columns)
                if "course_id" in table.c:
                    statement = statement.where(table.c.course_id == course_id)
                # Shared retrieval/configuration and indirect source tables are
                # conservatively included globally; only digests are retained.
                records[name] = [
                    semantic_record(row) for row in connection.execute(statement).mappings()
                ]
            dependencies[category] = digest(records)
        configured = settings.model_dump(mode="json")
        dependencies["model"] = digest(
            {
                key: value
                for key, value in configured.items()
                if key.startswith(("llm_", "provider_", "worker_adapter")) and "key" not in key
            }
        )
        dependencies["retrieval_settings"] = digest(
            {
                key: value
                for key, value in configured.items()
                # Relocating identical stored uploads does not change retrieval policy.
                if key.startswith("rag_") and key != "rag_upload_dir"
            }
        )
        app = Path(__file__).resolve().parents[2]
        paths = set(app.rglob("*.py"))
        # Missing deployed code cannot accidentally match an approved snapshot.
        if not paths:
            raise AssessmentReviewConflictError("Evaluator dependency files are unavailable")
        dependencies["prompt_and_runtime"] = digest(
            {
                str(path.relative_to(app)).replace("\\", "/"): hashlib.sha256(
                    path.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest()
                for path in sorted(paths)
            }
        )
        return dependencies

    def latest(self, course_id):
        return self.session.scalar(
            select(EvaluatorValidationEvent)
            .where(EvaluatorValidationEvent.course_id == course_id)
            .order_by(EvaluatorValidationEvent.revision.desc())
            .limit(1)
        )

    def observe(self, course_id):
        latest = self.latest(course_id)
        if latest is None or latest.state != "VALIDATED":
            return latest
        current = self.dependencies(course_id)
        expired = latest.expires_at is None or utc(latest.expires_at) <= datetime.now(UTC)
        if latest.fingerprint != digest(current) or expired:
            changed = sorted(key for key in current if current[key] != latest.dependencies.get(key))
            row = EvaluatorValidationEvent(
                id=str(uuid4()),
                course_id=course_id,
                revision=latest.revision + 1,
                state="INVALIDATED",
                fingerprint=digest(current),
                dependencies=current,
                evidence={"prior_validation_id": latest.id, "changed_dependencies": changed},
                reason="Validation expired"
                if expired
                else "Material evaluator dependencies changed",
                actor_id=None,
            )
            self.session.add(row)
            self._audit(row)
            return row
        return latest

    def status(self, course_id):
        ModerationService(self.session).lock(course_id)
        latest = self.observe(course_id)
        self.session.flush()
        return {
            "state": latest.state if latest else "PENDING",
            "validation_id": latest.id if latest else None,
            "fingerprint": digest(self.dependencies(course_id)),
            "reason": latest.reason
            if latest
            else "Approved evaluator validation has not been recorded",
            "ai_activation": "RELEASED" if self.is_release(latest) else "PENDING",
        }

    def invalidate_for_drift(self, course_id, review_id):
        latest = self.latest(course_id)
        if latest is None or latest.state != "VALIDATED":
            return
        current = self.dependencies(course_id)
        row = EvaluatorValidationEvent(
            id=str(uuid4()),
            course_id=course_id,
            revision=latest.revision + 1,
            state="INVALIDATED",
            fingerprint=digest(current),
            dependencies=current,
            evidence={"prior_validation_id": latest.id, "moderation_review_id": review_id},
            reason="Live moderation drift disagreement requires evaluator revalidation",
            actor_id=None,
        )
        self.session.add(row)
        self._audit(row)

    def validate(
        self, actor, course_id, *, expected_fingerprint, evidence, expires_at, idempotency_key=None
    ):
        if actor.role is not UserRole.ADMINISTRATOR or not actor.is_active:
            raise AssessmentReviewValidationError(
                "Only an active administrator may record a signed evaluator release"
            )
        if {"record_kind", "request_digest", "approval", "validation_evidence"}.intersection(
            evidence
        ):
            raise AssessmentReviewValidationError(
                "Release and revocation metadata require their separate commands"
            )
        ModerationService(self.session).lock(course_id)
        identity = (
            str(uuid5(NAMESPACE_URL, f"evaluator:{course_id}:validation:{idempotency_key}"))
            if idempotency_key
            else str(uuid4())
        )
        request_digest = digest(
            {
                "expected_fingerprint": expected_fingerprint,
                "evidence": evidence,
                "expires_at": utc(expires_at).isoformat(),
            }
        )
        replay = self.session.get(EvaluatorValidationEvent, identity)
        if replay:
            if (
                replay.actor_id != actor.id
                or replay.evidence.get("request_digest") != request_digest
            ):
                raise AssessmentReviewConflictError(
                    "This validation key already has different content"
                )
            return replay
        current = self.dependencies(course_id)
        if digest(current) != expected_fingerprint:
            raise AssessmentReviewConflictError(
                "Evaluator dependencies changed after validation; repeat validation"
            )
        required = {
            "release_approval",
            "expert_review",
            "approved_cases",
            "human_agreement",
            "fairness_review",
            "revalidation_policy",
            "threshold_approval",
        }
        if any(
            not isinstance(evidence.get(key), str) or not evidence[key].strip() for key in required
        ):
            raise AssessmentReviewValidationError(
                "Supply the approved validation evidence and signed release references"
            )
        for name in ("false_pass", "false_incomplete"):
            measured, maximum = evidence.get(name), evidence.get(f"max_{name}")
            if (
                type(measured) not in (int, float)
                or type(maximum) not in (int, float)
                or not 0 <= measured <= maximum <= 1
            ):
                raise AssessmentReviewValidationError(
                    "Measured error rates must satisfy the explicitly approved limits"
                )
        if "assessment_gate" in evidence:
            self._assessment_gate(evidence)
        if utc(expires_at) <= datetime.now(UTC):
            raise AssessmentReviewValidationError("Validation expiry must be in the future")
        self.observe(course_id)
        self.session.flush()
        prior = self.latest(course_id)
        row = EvaluatorValidationEvent(
            id=identity,
            course_id=course_id,
            revision=prior.revision + 1 if prior else 1,
            state="VALIDATED",
            fingerprint=digest(current),
            dependencies=current,
            evidence={**evidence, "request_digest": request_digest},
            reason="Approved validation evidence recorded; operational AI activation remains separate",
            actor_id=actor.id,
            expires_at=expires_at,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(row)
        return row

    @staticmethod
    def _assessment_gate(evidence):
        try:
            return AssessmentGateEvidence.model_validate(evidence.get("assessment_gate"))
        except ValidationError as error:
            raise AssessmentReviewValidationError(
                "Complete the independent expert, sample, agreement, uncertainty, coverage and adjudication records: "
                + str(error)
            ) from error

    @staticmethod
    def is_release(row):
        if not row or row.state != "VALIDATED" or row.evidence.get("record_kind") != "RELEASE":
            return False
        key = row.evidence.get("approval", {}).get("idempotency_key")
        return row.id == str(uuid5(NAMESPACE_URL, f"evaluator:{row.course_id}:release:{key}"))

    @staticmethod
    def _administrator(actor):
        if actor.role is not UserRole.ADMINISTRATOR or not actor.is_active:
            raise AssessmentReviewValidationError(
                "An active administrator must record the signed decision"
            )

    def history(self, actor, course_id):
        self._administrator(actor)
        status = self.status(course_id)
        rows = self.session.scalars(
            select(EvaluatorValidationEvent)
            .where(EvaluatorValidationEvent.course_id == course_id)
            .order_by(EvaluatorValidationEvent.revision.desc())
        ).all()
        forms = self.session.execute(
            select(TaskFormVersion, LearningTask.title)
            .join(LearningTask, LearningTask.id == TaskFormVersion.learning_task_id)
            .where(TaskFormVersion.course_id == course_id)
        ).all()
        return {
            "status": status,
            "forms": [
                {
                    "id": form.id,
                    "title": title,
                    "version": form.version,
                    "approved": form.approval_state.value == "APPROVED",
                }
                for form, title in forms
            ],
            "history": [
                dict(
                    id=row.id,
                    revision=row.revision,
                    state=row.state,
                    reason=row.reason,
                    actor_id=row.actor_id,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                    fingerprint=row.fingerprint,
                    evidence=row.evidence,
                )
                for row in rows
            ],
        }

    def _command(self, actor, course_id, kind, command):
        self._administrator(actor)
        ModerationService(self.session).lock(course_id)
        identity = str(
            uuid5(NAMESPACE_URL, f"evaluator:{course_id}:{kind}:{command.idempotency_key}")
        )
        request_digest = digest(command.model_dump(mode="json"))
        prior = self.session.get(EvaluatorValidationEvent, identity)
        if prior and (
            prior.actor_id != actor.id or prior.evidence.get("request_digest") != request_digest
        ):
            raise AssessmentReviewConflictError(
                "This decision key was already used for different content"
            )
        return identity, request_digest, prior

    def release(self, actor, course_id, command):
        identity, request_digest, replay = self._command(actor, course_id, "release", command)
        if replay:
            return replay
        latest = self.observe(course_id)
        self.session.flush()
        if (
            latest is None
            or latest.id != command.validation_id
            or latest.state != "VALIDATED"
            or self.is_release(latest)
        ):
            raise AssessmentReviewConflictError(
                "Release requires the current unexpired validation record"
            )
        if latest.fingerprint != command.expected_fingerprint:
            raise AssessmentReviewConflictError("Release does not match the validated dependencies")
        self._assessment_gate(latest.evidence)
        now = datetime.now(UTC)
        if command.approved_at > now or command.approved_at < utc(latest.created_at):
            raise AssessmentReviewValidationError(
                "Release approval must follow validation and cannot be in the future"
            )
        if not now < command.expires_at <= utc(latest.expires_at):
            raise AssessmentReviewValidationError(
                "Release must expire within the validation period"
            )
        if (command.provider, command.model) != (settings.llm_provider, settings.llm_model):
            raise AssessmentReviewValidationError(
                "Release provider and model must match the validated configuration"
            )
        for identity_form in command.task_form_version_ids:
            form = self.session.get(TaskFormVersion, identity_form)
            if (
                form is None
                or form.course_id != course_id
                or form.approval_state.value != "APPROVED"
            ):
                raise AssessmentReviewValidationError(
                    "Release scope requires approved task forms in this course"
                )
        row = EvaluatorValidationEvent(
            id=identity,
            course_id=course_id,
            revision=latest.revision + 1,
            state="VALIDATED",
            fingerprint=latest.fingerprint,
            dependencies=latest.dependencies,
            evidence={
                "record_kind": "RELEASE",
                "validation_id": latest.id,
                "request_digest": request_digest,
                "approval": command.model_dump(mode="json"),
                "validation_evidence": latest.evidence,
            },
            reason="Signed release permits imported AI suggestions for scoped assessor review; human confirmation remains required",
            actor_id=actor.id,
            expires_at=command.expires_at,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(row)
        return row

    def revoke(self, actor, course_id, command):
        identity, request_digest, replay = self._command(actor, course_id, "revoke", command)
        if replay:
            return replay
        latest = self.latest(course_id)
        if latest is None or latest.id != command.expected_validation_id:
            raise AssessmentReviewConflictError(
                "Validation history changed; reload before revoking"
            )
        row = EvaluatorValidationEvent(
            id=identity,
            course_id=course_id,
            revision=latest.revision + 1,
            state="INVALIDATED",
            fingerprint=latest.fingerprint,
            dependencies=latest.dependencies,
            evidence={
                "record_kind": "REVOCATION",
                "prior_validation_id": latest.id,
                "request_digest": request_digest,
                "authority_reference": command.authority_reference,
            },
            reason=command.reason,
            actor_id=actor.id,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(row)
        return row

    def require_release(self, course_id, *, task_form_version_id):
        ModerationService(self.session).lock(course_id)
        latest = self.observe(course_id)
        self.session.flush()
        if (
            not self.is_release(latest)
            or task_form_version_id not in latest.evidence["approval"]["task_form_version_ids"]
        ):
            raise AssessmentReviewConflictError(
                "AI suggestions require a current signed release for this exact task form"
            )
        return latest


@event.listens_for(Session, "before_flush")
def _track_material_changes(session, _context, _instances):
    watched = {name for names in DEPENDENCY_TABLES.values() for name in names}
    if any(
        getattr(row, "__tablename__", None) in watched
        for row in session.new | session.dirty | session.deleted
    ):
        session.info["evaluator_dependencies_changed"] = True


@event.listens_for(Session, "after_flush_postexec")
def _invalidate_changed_validation(session, _context):
    if not session.info.pop("evaluator_dependencies_changed", False):
        return
    # Historical migration fixtures may intentionally stop before this ledger exists.
    if not inspect(session.connection()).has_table(EvaluatorValidationEvent.__tablename__):
        return
    service = EvaluatorReleaseService(session)
    for course_id in session.scalars(select(EvaluatorValidationEvent.course_id).distinct()):
        service.observe(course_id)
