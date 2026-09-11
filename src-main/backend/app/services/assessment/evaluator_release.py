"""Change-sensitive evaluator validation records, separate from AI activation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models.assessment_moderation import EvaluatorValidationEvent
from app.models.lms import PlatformAuditEvent
from app.models.user import UserRole
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
            "ai_activation": "PENDING",
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

    def validate(self, actor, course_id, *, expected_fingerprint, evidence, expires_at):
        if actor.role is not UserRole.ADMINISTRATOR or not actor.is_active:
            raise AssessmentReviewValidationError(
                "Only an active administrator may record a signed evaluator release"
            )
        ModerationService(self.session).lock(course_id)
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
        if utc(expires_at) <= datetime.now(UTC):
            raise AssessmentReviewValidationError("Validation expiry must be in the future")
        self.observe(course_id)
        self.session.flush()
        prior = self.latest(course_id)
        row = EvaluatorValidationEvent(
            course_id=course_id,
            revision=prior.revision + 1 if prior else 1,
            state="VALIDATED",
            fingerprint=digest(current),
            dependencies=current,
            evidence=evidence,
            reason="Approved validation evidence recorded; operational AI activation remains separate",
            actor_id=actor.id,
            expires_at=expires_at,
        )
        self.session.add(row)
        self.session.flush()
        self._audit(row)
        return row


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
