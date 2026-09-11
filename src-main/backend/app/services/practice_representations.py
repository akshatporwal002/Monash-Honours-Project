"""Deliver exact approved practice variants and retain observation-only evidence."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.domain.platform_enums import (
    AccessSupportState,
    EvidenceProvenance,
    EvidenceType,
    InstructionalSupportLevel,
    ObservationType,
)
from app.models.assessment_work import AssessmentWorkStart
from app.models.learning_evidence import EvidenceArtifact as StoredArtifact
from app.models.learning_evidence import LearningEvidence
from app.models.task_review import TaskRevision
from app.schemas.evidence import EvidenceArtifact, EvidenceRecord
from app.schemas.learner_preferences import PreferenceValues
from app.schemas.practice_representations import (
    PracticeRepresentationCatalog,
    PracticeRepresentationChoice,
    PracticeRepresentationReceipt,
    practice_representations,
)
from app.services.assessment.submissions import AssessmentSubmissionService
from app.services.assessment.transfer_boundary import active_course_transfer
from app.services.evidence.repository import EvidenceCapture, SqlAlchemyEvidenceRepository
from app.services.learner_preferences import LearnerPreferenceService
from app.services.lms import LmsService
from app.services.misconception_state import active_fresh_check
from app.services.task_review import TaskReviewError, TaskReviewService

VERSION = "learnlens.practice-representation.v1"


class PracticeRepresentationService:
    def __init__(self, session):
        self.session = session

    def _context(self, actor, task_id):
        preferences = LearnerPreferenceService(self.session).read(actor)
        lms = LmsService(self.session)
        task = lms._require_student_task(actor, task_id)
        lms._require_unlocked(actor, task)
        if AssessmentSubmissionService(self.session).declaration_for_task(
            task
        ) is not None or self.session.scalar(
            select(AssessmentWorkStart.id)
            .where(
                AssessmentWorkStart.task_id == task_id,
                AssessmentWorkStart.student_id == actor.id,
            )
            .limit(1)
        ):
            raise TaskReviewError(
                "Use the approved support for this assessment or fresh application", 409
            )
        review = TaskReviewService(self.session)
        review.require_available(task)
        review.source_approvals(task, require_scan=True)
        revision = review.latest_revision(task_id)
        approval = review.latest_event(revision.id)
        variants = practice_representations(
            revision.snapshot.get("marking_criteria") or {},
            revision.snapshot.get("source_references") or [],
        )
        transfer_active = (
            task.task_type.value == "transfer"
            or active_fresh_check(self.session, actor.id, task_id)
            or active_course_transfer(self.session, actor.id, task.course_id)
        )
        if transfer_active:
            variants = [item for item in variants if item.support_kind == "accessibility"]
        return task, revision, approval, variants, preferences, transfer_active

    def _latest(self, actor_id, task_id):
        return self.session.scalar(
            select(LearningEvidence)
            .where(
                LearningEvidence.learner_id == actor_id,
                LearningEvidence.task_id == task_id,
                LearningEvidence.schema_version == VERSION,
            )
            .order_by(LearningEvidence.occurred_at.desc(), LearningEvidence.id.desc())
            .limit(1)
        )

    def _saved(self, evidence):
        return json.loads(self.session.get(StoredArtifact, evidence.artifact_id).content)

    @staticmethod
    def _recommend(variants, preferences):
        values = (
            preferences.values if preferences.values.personalisation_enabled else PreferenceValues()
        )
        ranked = sorted(
            variants,
            key=lambda item: (
                item.mode != values.format,
                item.explanation_detail != values.explanation_detail,
            ),
        )
        selected = ranked[0] if ranked else None
        matched = (
            selected
            and selected.mode == values.format
            and selected.explanation_detail == values.explanation_detail
        )
        explanation = (
            "Your format and detail preferences match this reviewed version. You can choose another."
            if matched
            else "That format and detail combination is not available. Choose an available reviewed version."
        )
        if not variants:
            explanation = "No reviewed practice representations are available for this task."
        if not preferences.values.personalisation_enabled:
            explanation = "Personalisation is off. Baseline text and brief detail guide the selection where available; you can override it."
        return selected, values, explanation

    def catalog(self, actor, task_id):
        _, revision, approval, variants, preferences, transfer_active = self._context(
            actor, task_id
        )
        recommended, values, explanation = self._recommend(variants, preferences)
        selected_id = recommended.representation_id if recommended else None
        selection = "preference"
        last = self._latest(actor.id, task_id)
        if last:
            saved = self._saved(last)
            if (
                saved["request"]["revision_id"],
                saved["request"]["preference_version"],
                saved["request"]["selection"],
            ) == (revision.id, preferences.version, "override") and any(
                item.representation_id == saved["request"]["representation_id"] for item in variants
            ):
                selected_id, selection = saved["request"]["representation_id"], "override"
                explanation = "Your choice for this reviewed task version is retained. You can use your preferences again."
        if transfer_active:
            explanation = "Instructional representations are unavailable while a fresh application in this course is open. Reviewed access support remains available where offered."
        return PracticeRepresentationCatalog(
            revision_id=revision.id,
            review_event_id=approval.id,
            preference_version=preferences.version,
            on_request=values.support_amount == "on_request",
            recommended_id=recommended.representation_id if recommended else None,
            selected_id=selected_id,
            selection=selection,
            explanation=explanation,
            choices=[PracticeRepresentationChoice(**item.model_dump()) for item in variants],
        )

    def deliver(self, actor, task_id, command):
        try:
            task = LmsService(self.session)._require_student_task(actor, task_id)
            TaskReviewService(self.session)._lock_course(task.course_id)
            task, revision, approval, variants, preferences, transfer_active = self._context(
                actor, task_id
            )
            if command.revision_id != revision.id:
                raise TaskReviewError(
                    "The reviewed task changed. Reload the available representations", 409
                )
            variant = next(
                (item for item in variants if item.representation_id == command.representation_id),
                None,
            )
            if variant is None:
                if transfer_active:
                    raise TaskReviewError(
                        "Instructional representations are unavailable during an active fresh application in this course",
                        409,
                    )
                raise TaskReviewError("This representation is not in the reviewed task", 422)
            identity = str(
                uuid5(NAMESPACE_URL, f"{VERSION}:{actor.id}:{task_id}:{command.request_key}")
            )
            prior = self.session.get(LearningEvidence, identity)
            if prior:
                saved = self._saved(prior)
                if saved["request"] != command.model_dump():
                    raise TaskReviewError(
                        "Support request key already used for another selection", 409
                    )
                if saved["receipt"]["review_event_id"] != approval.id:
                    raise TaskReviewError(
                        "Task approval changed. Request the reviewed version again", 409
                    )
                self.session.rollback()
                return PracticeRepresentationReceipt.model_validate(saved["receipt"])
            if command.preference_version != preferences.version:
                raise TaskReviewError(
                    "Preferences changed. Reload the available representations", 409
                )
            recommended, _, _ = self._recommend(variants, preferences)
            if command.selection == "preference" and variant != recommended:
                raise TaskReviewError("Select this version as a learner override", 422)
            when = datetime.now(UTC)
            receipt = PracticeRepresentationReceipt(
                evidence_id=identity,
                revision_id=revision.id,
                review_event_id=approval.id,
                preference_version=preferences.version,
                selection=command.selection,
                delivered_at=when,
                representation=variant,
            )
            content = json.dumps(
                {
                    "request": command.model_dump(),
                    "receipt": receipt.model_dump(mode="json"),
                    "task_content_digest": revision.content_digest,
                    "source_approvals": approval.source_approvals,
                    "preferences": preferences.model_dump(),
                    "observation": "Reviewed content delivered; no strategy-success or learning inference.",
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            digest = "sha256:" + sha256(content.encode()).hexdigest()
            artifact_id = str(uuid5(NAMESPACE_URL, identity + ":artifact"))
            record = EvidenceRecord(
                evidence_id=identity,
                course_id=task.course_id,
                learner_id=str(actor.id),
                outcome_id=task.learning_outcome_id,
                activity_id=task.id,
                task_id=task.id,
                source_interaction_id=identity,
                source_version=revision.id,
                task_conditions_version=revision.version,
                evidence_type=EvidenceType.SCAFFOLD,
                provenance=EvidenceProvenance.SYSTEM,
                observation_type=ObservationType.SYSTEM_CAPTURED,
                instructional_support_level=InstructionalSupportLevel(
                    variant.instructional_support_level
                ),
                access_support_state=AccessSupportState.PROVIDED
                if variant.support_kind == "accessibility"
                else AccessSupportState.NOT_DECLARED,
                artifact_id=artifact_id,
                content_digest=digest,
                actor_reference=str(actor.id),
                agent_reference=VERSION,
                correlation_id=identity,
                schema_version=VERSION,
                record_version=1,
                idempotency_key=identity,
                occurred_at=when,
            )
            SqlAlchemyEvidenceRepository(self.session).capture(
                EvidenceCapture(
                    record=record,
                    artifact=EvidenceArtifact(
                        artifact_id=artifact_id,
                        course_id=task.course_id,
                        learner_id=str(actor.id),
                        content=content,
                        content_digest=digest,
                        content_format="application.json",
                        record_version=1,
                        occurred_at=when,
                    ),
                ),
                commit=False,
            )
            self.session.commit()
            return receipt
        except Exception:
            self.session.rollback()
            raise


def practice_support_observations(session, task_id, student_id, before):
    """Carry delivered support into practice evidence, never frozen assessed work."""
    if task_id is None or student_id is None:
        return []
    revision = session.scalar(
        select(TaskRevision)
        .where(
            TaskRevision.task_id == task_id,
            TaskRevision.created_at <= before,
        )
        .order_by(TaskRevision.version.desc())
        .limit(1)
    )
    if revision is None:
        return []
    return list(
        session.scalars(
            select(LearningEvidence).where(
                LearningEvidence.task_id == task_id,
                LearningEvidence.learner_id == student_id,
                LearningEvidence.course_id == revision.course_id,
                LearningEvidence.source_version == revision.id,
                LearningEvidence.schema_version == VERSION,
                LearningEvidence.occurred_at <= before,
            )
        )
    )
