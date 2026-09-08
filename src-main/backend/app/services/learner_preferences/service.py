from datetime import UTC, datetime
from uuid import uuid4

from app.models.learner_preferences import LearnerPreferenceRevision
from app.services.learner_preferences.contracts import (
    LearnerPreferencesRead,
    LearnerPreferencesWrite,
)


class LearnerPreferencesConflictError(Exception):
    pass


class LearnerPreferencesService:
    def __init__(self, repository):
        self.repository = repository

    def read(self, learner_id: int) -> LearnerPreferencesRead:
        row = self.repository.current(learner_id)
        return self._read(row) if row else LearnerPreferencesRead.defaults()

    def save(self, learner_id: int, command: LearnerPreferencesWrite) -> LearnerPreferencesRead:
        current = self.repository.current(learner_id)
        replay = self.repository.by_key(learner_id, command.idempotency_key)
        if replay:
            if self._same(replay, command) and replay.revision - 1 == command.expected_revision:
                return self._read(replay)
            raise LearnerPreferencesConflictError(
                "idempotency key conflicts with existing preference revision"
            )
        revision = current.revision if current else 0
        if revision != command.expected_revision:
            raise LearnerPreferencesConflictError("a newer preference revision exists")
        row = LearnerPreferenceRevision(
            id=str(uuid4()),
            learner_id=learner_id,
            revision=revision + 1,
            prior_revision_id=current.id if current else None,
            actor_reference=str(learner_id),
            correlation_id=str(uuid4()),
            schema_version="learnlens.learner-preferences.v1",
            occurred_at=datetime.now(UTC),
            **command.model_dump(exclude={"expected_revision"}),
        )
        return self._read(self.repository.append(row))

    def history(self, learner_id: int, limit: int = 20, offset: int = 0):
        return [self._read(row) for row in self.repository.history(learner_id, limit, offset)]

    def _read(self, row):
        return LearnerPreferencesRead(
            pace=row.pace,
            format=row.format,
            explanation_detail=row.explanation_detail,
            optional_breaks_enabled=row.optional_breaks_enabled,
            repeat_practice_enabled=row.repeat_practice_enabled,
            personalisation_enabled=row.personalisation_enabled,
            revision=row.revision,
            saved=True,
            saved_at=row.created_at,
            schema_version=row.schema_version,
        )

    def _same(self, row, command):
        return all(
            getattr(row, key) == value
            for key, value in command.model_dump(
                exclude={"expected_revision", "idempotency_key"}
            ).items()
        )
