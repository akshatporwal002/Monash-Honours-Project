"""Bounded, inspectable temporal associations; never causal learning claims."""

import json
import re
from datetime import UTC
from hashlib import sha256

from sqlalchemy import select

from app.domain.platform_enums import EvidenceLinkRelation, EvidenceType
from app.models.learning_evidence import EvidenceArtifact, EvidenceLink, LearningEvidence
from app.schemas.progress import ProgressIndicator

_CLARIFICATION = re.compile(
    r"\b(?:question|instruction|prompt|wording)\b.{0,70}\b(?:unclear|confus\w*|ambiguous|mean)\b"
    r"|\b(?:clarify|explain)\b.{0,50}\b(?:question|instruction|prompt|wording)\b",
    re.I,
)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def indicators(session, course_id, learner_id, outcome_id, *, limit=200):
    rows = session.scalars(
        select(LearningEvidence)
        .where(
            LearningEvidence.course_id == course_id,
            LearningEvidence.learner_id == learner_id,
            LearningEvidence.outcome_id == outcome_id,
        )
        .order_by(LearningEvidence.occurred_at.desc(), LearningEvidence.id)
        .limit(limit + 1)
    ).all()
    truncated = len(rows) > limit
    rows = rows[:limit]
    by_id = {row.id: row for row in rows}
    parents = {}
    for child, parent in session.execute(
        select(EvidenceLink.evidence_id, EvidenceLink.linked_evidence_id).where(
            EvidenceLink.evidence_id.in_(by_id),
            EvidenceLink.linked_evidence_id.in_(by_id),
            EvidenceLink.relation == EvidenceLinkRelation.DERIVES_FROM,
        )
    ):
        # A malformed or future edge must not imply a temporal relationship.
        if utc(by_id[parent].occurred_at) <= utc(by_id[child].occurred_at):
            parents.setdefault(child, set()).add(parent)

    def ancestors(key):
        seen, pending = set(), list(parents.get(key, ()))
        while pending:
            item = pending.pop()
            if item in seen:
                continue
            seen.add(item)
            pending.extend(parents.get(item, ()))
        return seen

    feedback = [row for row in rows if row.evidence_type == EvidenceType.FEEDBACK_INTERACTION]
    result = []
    for row in rows:
        if row.evidence_type in {EvidenceType.REVISION, EvidenceType.TRANSFER}:
            lineage = ancestors(row.id)
            for acknowledgment in feedback:
                if utc(acknowledgment.occurred_at) >= utc(row.occurred_at):
                    continue
                original = parents.get(acknowledgment.id, set()) & lineage
                original = {
                    key for key in original if by_id[key].evidence_type == EvidenceType.RESPONSE
                }
                if not original:
                    continue
                kind = (
                    "feedback_revision"
                    if row.evidence_type == EvidenceType.REVISION
                    else "feedback_transfer"
                )
                result.append(
                    ProgressIndicator(
                        id=f"{acknowledgment.id}:{row.id}",
                        kind=kind,
                        explanation="Feedback acknowledgement preceded linked "
                        + ("revision" if kind == "feedback_revision" else "transfer")
                        + ". Inspect the work to judge usefulness; this sequence does not establish that feedback caused improvement.",
                        evidence_ids=[acknowledgment.id, *sorted(original), row.id],
                        occurred_at=row.occurred_at,
                    )
                )
        if row.evidence_type != EvidenceType.SCAFFOLD or row.actor_reference != str(learner_id):
            continue
        artifact = session.get(EvidenceArtifact, row.artifact_id) if row.artifact_id else None
        if not artifact or (artifact.course_id, artifact.learner_id) != (course_id, learner_id):
            continue
        if (
            artifact.content_digest != row.content_digest
            or artifact.content_digest != "sha256:" + sha256(artifact.content.encode()).hexdigest()
        ):
            continue
        try:
            value = json.loads(artifact.content).get("value", {})
            message = value.get("message") if isinstance(value, dict) else None
        except (ValueError, AttributeError):
            continue
        if isinstance(message, str) and _CLARIFICATION.search(message[:4000]):
            result.append(
                ProgressIndicator(
                    id=row.id,
                    kind="question_clarification",
                    explanation="The learner used question-clarification language. Review the wording and context; this cue does not establish a question defect or a learner difficulty.",
                    evidence_ids=[row.id],
                    occurred_at=row.occurred_at,
                )
            )
    return sorted(result, key=lambda item: (item.occurred_at, item.id), reverse=True), truncated
