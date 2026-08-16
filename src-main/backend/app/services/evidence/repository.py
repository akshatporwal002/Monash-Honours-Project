"""Transactional, append-only SQLAlchemy repository for Person B evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.learning_evidence import (
    EvidenceArtifact as EvidenceArtifactModel,
)
from app.models.learning_evidence import EvidenceLink as EvidenceLinkModel
from app.models.learning_evidence import LearningEvidence as LearningEvidenceModel
from app.models.lms import Course, CourseModule, LearningOutcome
from app.models.persistence import LearningTask
from app.models.user import User
from app.schemas.evidence import (
    EvidenceArtifact as EvidenceArtifactPayload,
)
from app.schemas.evidence import EvidenceLink as EvidenceLinkPayload
from app.schemas.evidence import EvidenceRecord as EvidenceRecordPayload
from app.schemas.evidence import EvidenceRecordReference
from app.services.evidence.contracts import reference_from_record
from app.services.evidence.safety import (
    EvidenceConflictError,
    EvidenceNotFoundError,
    EvidencePersistenceError,
    EvidenceScopeError,
)


@dataclass(frozen=True, slots=True)
class EvidenceCapture:
    """One atomic append-only evidence write, including optional protected content."""

    record: EvidenceRecordPayload
    artifact: EvidenceArtifactPayload | None = None
    links: tuple[EvidenceLinkPayload, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceWriteResult:
    """The opaque result of a newly stored or exactly replayed capture."""

    reference: EvidenceRecordReference
    created: bool
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceTimelineItem:
    """A metadata-only timeline item ordered independently of insertion order."""

    reference: EvidenceRecordReference
    created_at: datetime


class SqlAlchemyEvidenceRepository:
    """Persist immutable records without exposing protected artefact content by default."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def capture(self, capture: EvidenceCapture) -> EvidenceWriteResult:
        """Atomically store an evidence record, its optional artefact, and its links."""

        self._validate_capture(capture)
        record = capture.record
        learner_id = _learner_id(record.learner_id)
        try:
            existing = self._by_idempotency(record.course_id, learner_id, record.idempotency_key)
            if existing is not None:
                return self._replay(existing, capture)

            self._validate_scope(record, learner_id)
            self._validate_links(capture, learner_id)
            artifact = self._artifact_model(capture.artifact, record, learner_id)
            if artifact is not None:
                self._session.add(artifact)
            evidence = self._evidence_model(record, learner_id)
            self._session.add(evidence)
            try:
                # Flush the evidence row before its links. This keeps the full
                # capture in one transaction while satisfying SQLite FK checks.
                self._session.flush()
                self._session.add_all(self._link_models(capture.links))
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                winner = self._by_idempotency(
                    record.course_id,
                    learner_id,
                    record.idempotency_key,
                )
                if winner is None:
                    raise EvidencePersistenceError("evidence persistence failed") from None
                return self._replay(winner, capture)
            self._session.refresh(evidence)
            return EvidenceWriteResult(
                reference=self._reference(evidence),
                created=True,
                created_at=_as_utc(evidence.created_at),
            )
        except (EvidenceConflictError, EvidencePersistenceError, EvidenceScopeError):
            raise
        except SQLAlchemyError:
            self._session.rollback()
            raise EvidencePersistenceError("evidence persistence failed") from None

    def timeline(self, *, course_id: str, learner_id: str) -> tuple[EvidenceTimelineItem, ...]:
        """Return opaque history in the stable timeline ordering required by FR19."""

        try:
            items = self._session.scalars(
                select(LearningEvidenceModel)
                .where(
                    LearningEvidenceModel.course_id == course_id,
                    LearningEvidenceModel.learner_id == _learner_id(learner_id),
                )
                .order_by(
                    LearningEvidenceModel.occurred_at,
                    LearningEvidenceModel.created_at,
                    LearningEvidenceModel.id,
                )
            ).all()
        except SQLAlchemyError:
            self._session.rollback()
            raise EvidencePersistenceError("evidence history could not be read") from None
        return tuple(
            EvidenceTimelineItem(
                reference=self._reference(item),
                created_at=_as_utc(item.created_at),
            )
            for item in items
        )

    def artifact(
        self,
        *,
        artifact_id: str,
        course_id: str,
        learner_id: str,
    ) -> EvidenceArtifactPayload:
        """Read protected content only after the service has authorized the request."""

        try:
            artifact = self._session.scalar(
                select(EvidenceArtifactModel).where(
                    EvidenceArtifactModel.id == artifact_id,
                    EvidenceArtifactModel.course_id == course_id,
                    EvidenceArtifactModel.learner_id == _learner_id(learner_id),
                )
            )
        except SQLAlchemyError:
            self._session.rollback()
            raise EvidencePersistenceError("evidence artifact could not be read") from None
        if artifact is None:
            raise EvidenceNotFoundError("evidence artifact is unavailable")
        return EvidenceArtifactPayload(
            artifact_id=artifact.id,
            course_id=artifact.course_id,
            learner_id=str(artifact.learner_id),
            content=artifact.content,
            content_digest=artifact.content_digest,
            content_format=artifact.content_format,
            record_version=artifact.record_version,
            occurred_at=_as_utc(artifact.occurred_at),
        )

    def _by_idempotency(
        self,
        course_id: str,
        learner_id: int,
        idempotency_key: str,
    ) -> LearningEvidenceModel | None:
        return self._session.scalar(
            select(LearningEvidenceModel).where(
                LearningEvidenceModel.course_id == course_id,
                LearningEvidenceModel.learner_id == learner_id,
                LearningEvidenceModel.idempotency_key == idempotency_key,
            )
        )

    def _validate_scope(self, record: EvidenceRecordPayload, learner_id: int) -> None:
        course_exists = self._session.get(Course, record.course_id) is not None
        learner_exists = self._session.get(User, learner_id) is not None
        task_exists = self._session.scalar(
            select(LearningTask.id).where(
                LearningTask.id == record.task_id,
                LearningTask.course_id == record.course_id,
                LearningTask.learning_outcome_id == record.outcome_id,
            )
        )
        outcome_exists = self._session.scalar(
            select(LearningOutcome.id)
            .join(CourseModule, LearningOutcome.module_id == CourseModule.id)
            .where(
                LearningOutcome.id == record.outcome_id,
                CourseModule.course_id == record.course_id,
            )
        )
        if not course_exists or not learner_exists or task_exists is None or outcome_exists is None:
            raise EvidenceScopeError(
                "evidence references must remain within one valid course scope"
            )

    def _validate_links(self, capture: EvidenceCapture, learner_id: int) -> None:
        record = capture.record
        for link in capture.links:
            if link.correlation_id != record.correlation_id:
                raise EvidenceScopeError("evidence links must use the capture correlation ID")
            if record.evidence_id not in (link.evidence_id, link.linked_evidence_id):
                raise EvidenceScopeError("evidence links must include the captured evidence record")
            for evidence_id in (link.evidence_id, link.linked_evidence_id):
                if evidence_id == record.evidence_id:
                    continue
                linked = self._session.get(LearningEvidenceModel, evidence_id)
                if (
                    linked is None
                    or linked.course_id != record.course_id
                    or linked.learner_id != learner_id
                ):
                    raise EvidenceScopeError(
                        "evidence links must target the same course and learner"
                    )

    def _validate_capture(self, capture: EvidenceCapture) -> None:
        record = capture.record
        _storage_identifier(record.evidence_id, "evidence ID")
        _storage_identifier(record.course_id, "course ID")
        _storage_identifier(record.outcome_id, "outcome ID")
        _storage_identifier(record.task_id, "task ID")
        _learner_id(record.learner_id)
        if capture.artifact is None:
            if record.artifact_id is not None:
                raise EvidenceScopeError("evidence artifact metadata is missing")
        else:
            artifact = capture.artifact
            _storage_identifier(artifact.artifact_id, "evidence artifact ID")
            if (
                record.artifact_id != artifact.artifact_id
                or record.course_id != artifact.course_id
                or record.learner_id != artifact.learner_id
                or record.content_digest != artifact.content_digest
            ):
                raise EvidenceScopeError("evidence artifact and metadata scope do not match")
        for link in capture.links:
            _storage_identifier(link.evidence_id, "linked evidence ID")
            _storage_identifier(link.linked_evidence_id, "linked evidence ID")
        if len(_link_signature(capture.links)) != len(capture.links):
            raise EvidenceScopeError("evidence links must be distinct")

    @staticmethod
    def _artifact_model(
        artifact: EvidenceArtifactPayload | None,
        record: EvidenceRecordPayload,
        learner_id: int,
    ) -> EvidenceArtifactModel | None:
        if artifact is None:
            return None
        return EvidenceArtifactModel(
            id=artifact.artifact_id,
            course_id=artifact.course_id,
            learner_id=learner_id,
            content=artifact.content,
            content_digest=artifact.content_digest,
            content_format=artifact.content_format,
            schema_version=artifact.contract_version,
            record_version=artifact.record_version,
            actor_reference=record.actor_reference,
            agent_reference=record.agent_reference,
            correlation_id=record.correlation_id,
            occurred_at=_as_utc(artifact.occurred_at),
        )

    @staticmethod
    def _evidence_model(record: EvidenceRecordPayload, learner_id: int) -> LearningEvidenceModel:
        return LearningEvidenceModel(
            id=record.evidence_id,
            artifact_id=record.artifact_id,
            course_id=record.course_id,
            learner_id=learner_id,
            outcome_id=record.outcome_id,
            activity_id=record.activity_id,
            task_id=record.task_id,
            response_version_id=record.response_version_id,
            source_interaction_id=record.source_interaction_id,
            source_version=record.source_version,
            task_conditions_version=record.task_conditions_version,
            evidence_type=record.evidence_type,
            provenance=record.provenance,
            observation_type=record.observation_type,
            instructional_support_level=int(record.instructional_support_level),
            access_support_state=record.access_support_state,
            content_digest=record.content_digest,
            actor_reference=record.actor_reference,
            agent_reference=record.agent_reference,
            correlation_id=record.correlation_id,
            schema_version=record.schema_version,
            record_version=record.record_version,
            idempotency_key=record.idempotency_key,
            occurred_at=_as_utc(record.occurred_at),
        )

    @staticmethod
    def _link_models(links: tuple[EvidenceLinkPayload, ...]) -> list[EvidenceLinkModel]:
        return [
            EvidenceLinkModel(
                id=_link_identifier(link),
                evidence_id=link.evidence_id,
                linked_evidence_id=link.linked_evidence_id,
                relation=link.relation,
                actor_reference=link.actor_reference,
                correlation_id=link.correlation_id,
                occurred_at=_as_utc(link.occurred_at),
            )
            for link in links
        ]

    def _replay(
        self,
        existing: LearningEvidenceModel,
        capture: EvidenceCapture,
    ) -> EvidenceWriteResult:
        if not self._same_capture(existing, capture):
            raise EvidenceConflictError(
                "evidence idempotency key was reused with different content"
            )
        return EvidenceWriteResult(
            reference=self._reference(existing),
            created=False,
            created_at=_as_utc(existing.created_at),
        )

    def _same_capture(self, existing: LearningEvidenceModel, capture: EvidenceCapture) -> bool:
        record = capture.record
        comparable = (
            existing.id == record.evidence_id
            and existing.artifact_id == record.artifact_id
            and existing.course_id == record.course_id
            and existing.learner_id == _learner_id(record.learner_id)
            and existing.outcome_id == record.outcome_id
            and existing.activity_id == record.activity_id
            and existing.task_id == record.task_id
            and existing.response_version_id == record.response_version_id
            and existing.source_interaction_id == record.source_interaction_id
            and existing.source_version == record.source_version
            and existing.task_conditions_version == record.task_conditions_version
            and existing.evidence_type == record.evidence_type
            and existing.provenance == record.provenance
            and existing.observation_type == record.observation_type
            and existing.instructional_support_level == int(record.instructional_support_level)
            and existing.access_support_state == record.access_support_state
            and existing.content_digest == record.content_digest
            and existing.actor_reference == record.actor_reference
            and existing.agent_reference == record.agent_reference
            and existing.correlation_id == record.correlation_id
            and existing.schema_version == record.schema_version
            and existing.record_version == record.record_version
            and _as_utc(existing.occurred_at) == _as_utc(record.occurred_at)
        )
        if not comparable or not self._same_artifact(existing, capture.artifact):
            return False
        return all(self._link_is_stored(link) for link in capture.links)

    def _link_is_stored(self, link: EvidenceLinkPayload) -> bool:
        stored = self._session.get(EvidenceLinkModel, _link_identifier(link))
        return stored is not None and _link_signature([stored]) == _link_signature((link,))

    def _same_artifact(
        self,
        existing: LearningEvidenceModel,
        artifact: EvidenceArtifactPayload | None,
    ) -> bool:
        if artifact is None:
            return existing.artifact_id is None
        stored = self._session.get(EvidenceArtifactModel, artifact.artifact_id)
        return stored is not None and (
            stored.id == artifact.artifact_id
            and stored.course_id == artifact.course_id
            and str(stored.learner_id) == artifact.learner_id
            and stored.content == artifact.content
            and stored.content_digest == artifact.content_digest
            and stored.content_format == artifact.content_format
            and stored.record_version == artifact.record_version
            and _as_utc(stored.occurred_at) == _as_utc(artifact.occurred_at)
        )

    @staticmethod
    def _reference(record: LearningEvidenceModel) -> EvidenceRecordReference:
        return reference_from_record(
            EvidenceRecordPayload(
                evidence_id=record.id,
                course_id=record.course_id,
                learner_id=str(record.learner_id),
                outcome_id=record.outcome_id,
                activity_id=record.activity_id,
                task_id=record.task_id,
                response_version_id=record.response_version_id,
                source_interaction_id=record.source_interaction_id,
                source_version=record.source_version,
                task_conditions_version=record.task_conditions_version,
                evidence_type=record.evidence_type,
                provenance=record.provenance,
                observation_type=record.observation_type,
                instructional_support_level=record.instructional_support_level,
                access_support_state=record.access_support_state,
                artifact_id=record.artifact_id,
                content_digest=record.content_digest,
                actor_reference=record.actor_reference,
                agent_reference=record.agent_reference,
                correlation_id=record.correlation_id,
                schema_version=record.schema_version,
                record_version=record.record_version,
                idempotency_key=record.idempotency_key,
                occurred_at=_as_utc(record.occurred_at),
            )
        )


def _learner_id(reference: str) -> int:
    try:
        learner_id = int(reference)
    except (TypeError, ValueError):
        raise EvidenceScopeError("learner reference is invalid") from None
    if learner_id <= 0 or str(learner_id) != reference:
        raise EvidenceScopeError("learner reference is invalid")
    return learner_id


def _storage_identifier(value: str | None, label: str) -> None:
    if value is None or len(value) > 36:
        raise EvidenceScopeError(f"{label} is invalid for evidence storage")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _link_signature(
    links: list[EvidenceLinkModel] | tuple[EvidenceLinkPayload, ...],
) -> set[tuple[str, str, str, str, str, datetime]]:
    return {
        (
            link.evidence_id,
            link.linked_evidence_id,
            link.relation.value,
            link.actor_reference,
            link.correlation_id,
            _as_utc(link.occurred_at),
        )
        for link in links
    }


def _link_identifier(link: EvidenceLinkPayload) -> str:
    value = "\x00".join((link.evidence_id, link.linked_evidence_id, link.relation.value))
    return f"link-{sha256(value.encode('utf-8')).hexdigest()[:31]}"


__all__ = [
    "EvidenceCapture",
    "EvidenceTimelineItem",
    "EvidenceWriteResult",
    "SqlAlchemyEvidenceRepository",
]
