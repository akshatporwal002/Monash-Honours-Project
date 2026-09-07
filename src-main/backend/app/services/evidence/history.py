"""Read-only task projection; caller enforces current learner and course access."""

from sqlalchemy import select

from app.models.learning_evidence import EvidenceLink, LearningEvidence
from app.schemas.live_evidence import LiveEvidencePage, LiveEvidenceRead
from app.services.evidence.live import utc


def task_history(session, *, learner_id, task_id, limit=50, offset=0):
    rows = list(
        session.scalars(
            select(LearningEvidence)
            .where(
                LearningEvidence.learner_id == learner_id,
                LearningEvidence.task_id == task_id,
            )
            .order_by(
                LearningEvidence.occurred_at, LearningEvidence.created_at, LearningEvidence.id
            )
            .limit(limit + 1)
            .offset(offset)
        )
    )
    ids = [row.id for row in rows[:limit]]
    links = {}
    for source, target in session.execute(
        select(EvidenceLink.evidence_id, EvidenceLink.linked_evidence_id)
        .where(EvidenceLink.evidence_id.in_(ids))
        .order_by(EvidenceLink.linked_evidence_id)
    ):
        links.setdefault(source, []).append(target)
    return LiveEvidencePage(
        items=[
            LiveEvidenceRead(
                evidence_id=row.id,
                task_id=row.task_id,
                outcome_id=row.outcome_id,
                response_version_id=row.response_version_id,
                source_interaction_id=row.source_interaction_id,
                evidence_type=row.evidence_type,
                observation_type=row.observation_type,
                access_support_state=row.access_support_state,
                instructional_support_level=row.instructional_support_level,
                occurred_at=utc(row.occurred_at),
                content_digest=row.content_digest,
                related_evidence_ids=links.get(row.id, []),
            )
            for row in rows[:limit]
        ],
        next_offset=offset + limit if len(rows) > limit else None,
    )
