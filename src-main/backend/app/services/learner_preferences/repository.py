from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learner_preferences import LearnerPreferenceRevision


class SqlAlchemyLearnerPreferencesRepository:
    def __init__(self, session: Session):
        self.session = session

    def current(self, learner_id: int):
        return self.session.scalar(
            select(LearnerPreferenceRevision)
            .where(LearnerPreferenceRevision.learner_id == learner_id)
            .order_by(LearnerPreferenceRevision.revision.desc())
        )

    def by_key(self, learner_id: int, key: str):
        return self.session.scalar(
            select(LearnerPreferenceRevision).where(
                LearnerPreferenceRevision.learner_id == learner_id,
                LearnerPreferenceRevision.idempotency_key == key,
            )
        )

    def append(self, value: LearnerPreferenceRevision):
        self.session.add(value)
        self.session.commit()
        self.session.refresh(value)
        return value

    def history(self, learner_id: int, limit: int, offset: int):
        return list(
            self.session.scalars(
                select(LearnerPreferenceRevision)
                .where(LearnerPreferenceRevision.learner_id == learner_id)
                .order_by(LearnerPreferenceRevision.revision.desc())
                .limit(limit)
                .offset(offset)
            )
        )
