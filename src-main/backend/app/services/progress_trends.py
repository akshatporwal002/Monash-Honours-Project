"""Grouped observation and result series, with paged contributing records."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import String, case, cast, func, literal, select, union_all

from app.domain.assessment import ResultState
from app.domain.platform_enums import EvidenceType
from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDecision,
    AssessmentDefinitionVersion,
    OutcomeVersion,
)
from app.models.learner_model import (
    LearnerModelEvidenceLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.misconceptions import MisconceptionHypothesis, MisconceptionReviewRecord
from app.models.user import User


def records_query(course_id, roster, outcome_id=None):
    def columns(identity, learner, outcome, when, kind, **extra):
        values = dict(
            id=identity,
            learner_id=learner,
            outcome_id=outcome,
            occurred_at=when,
            kind=kind,
            evidence_id=literal(None),
            task_id=literal(None),
            response_id=literal(None),
            workflow_id=literal(None),
            estimate_id=literal(None),
            uncertainty=literal(None),
            reason=literal(None),
        )
        values.update(extra)
        return [value.label(key) for key, value in values.items()]

    evidence_scope = [
        LearningEvidence.course_id == course_id,
        LearningEvidence.learner_id.in_(roster),
    ]
    evidence = select(
        *columns(
            LearningEvidence.id,
            LearningEvidence.learner_id,
            LearningEvidence.outcome_id,
            LearningEvidence.occurred_at,
            literal("observation:") + cast(LearningEvidence.evidence_type, String),
            evidence_id=LearningEvidence.id,
            task_id=LearningEvidence.task_id,
            response_id=LearningEvidence.response_version_id,
        )
    ).where(*evidence_scope)
    independence = select(
        *columns(
            LearningEvidence.id,
            LearningEvidence.learner_id,
            LearningEvidence.outcome_id,
            LearningEvidence.occurred_at,
            case(
                (LearningEvidence.instructional_support_level == 0, "response:independent"),
                else_="response:supported",
            ),
            evidence_id=LearningEvidence.id,
            task_id=LearningEvidence.task_id,
            response_id=LearningEvidence.response_version_id,
        )
    ).where(
        *evidence_scope,
        LearningEvidence.evidence_type.in_(
            [
                EvidenceType.RESPONSE,
                EvidenceType.REVISION,
                EvidenceType.TRANSFER,
            ]
        ),
    )
    estimates = (
        select(
            *columns(
                LearnerOutcomeEstimate.id,
                LearnerModelSnapshot.learner_id,
                LearnerModelSnapshot.outcome_id,
                LearnerModelSnapshot.occurred_at,
                literal("estimate:")
                + cast(LearnerOutcomeEstimate.dimension, String)
                + ":"
                + cast(LearnerOutcomeEstimate.inference_status, String),
                estimate_id=LearnerOutcomeEstimate.id,
                uncertainty=LearnerOutcomeEstimate.uncertainty,
                reason=LearnerOutcomeEstimate.reason_code,
            )
        )
        .join(LearnerModelSnapshot, LearnerModelSnapshot.id == LearnerOutcomeEstimate.snapshot_id)
        .where(
            LearnerModelSnapshot.course_id == course_id,
            LearnerModelSnapshot.learner_id.in_(roster),
        )
    )
    misconceptions = (
        select(
            *columns(
                MisconceptionReviewRecord.id,
                MisconceptionHypothesis.student_id,
                MisconceptionHypothesis.outcome_id,
                MisconceptionReviewRecord.created_at,
                literal("misconception:") + MisconceptionReviewRecord.state,
                evidence_id=MisconceptionReviewRecord.evidence_id,
                task_id=MisconceptionHypothesis.task_id,
            )
        )
        .join(
            MisconceptionHypothesis,
            MisconceptionHypothesis.id == MisconceptionReviewRecord.hypothesis_id,
        )
        .where(
            MisconceptionHypothesis.course_id == course_id,
            MisconceptionHypothesis.student_id.in_(roster),
        )
    )
    adaptation_scope = [
        ActivityProgress.course_id == course_id,
        ActivityProgress.learner_id.in_(roster),
    ]
    adaptations = (
        select(
            *columns(
                ActivityProgress.workflow_id,
                ActivityProgress.learner_id,
                ActivityProgress.outcome_id,
                ActivityProgress.created_at,
                literal("adaptation:") + ActivitySuggestion.decision["state"].as_string(),
                workflow_id=ActivityProgress.workflow_id,
                uncertainty=ActivitySuggestion.decision["uncertainty"].as_float(),
                reason=ActivitySuggestion.decision["reason"].as_string(),
            )
        )
        .join(ActivitySuggestion, ActivitySuggestion.workflow_id == ActivityProgress.workflow_id)
        .where(*adaptation_scope)
    )
    choices = (
        select(
            *columns(
                ActivityChoice.id,
                ActivityProgress.learner_id,
                ActivityProgress.outcome_id,
                ActivityChoice.created_at,
                literal("choice:") + ActivityChoice.payload["action"].as_string(),
                workflow_id=ActivityProgress.workflow_id,
                reason=ActivityChoice.payload["reason"].as_string(),
            )
        )
        .join(ActivityProgress, ActivityProgress.workflow_id == ActivityChoice.workflow_id)
        .where(*adaptation_scope)
    )
    released = AssessmentDecision.result_state.in_([ResultState.CONFIRMED, ResultState.OVERRIDDEN])
    results = (
        select(
            *columns(
                AssessmentAttempt.id,
                AssessmentAttempt.student_id,
                OutcomeVersion.learning_outcome_id,
                SubmissionAttempt.submitted_at,
                case(
                    (released, literal("result:") + cast(AssessmentDecision.result, String)),
                    else_="result:unreleased",
                ),
                response_id=SubmissionAttempt.id,
                task_id=SubmissionAttempt.task_id,
            )
        )
        .join(SubmissionAttempt, SubmissionAttempt.id == AssessmentAttempt.response_version_id)
        .join(
            AssessmentDefinitionVersion,
            AssessmentDefinitionVersion.id == AssessmentAttempt.assessment_definition_version_id,
        )
        .join(OutcomeVersion, OutcomeVersion.id == AssessmentDefinitionVersion.outcome_version_id)
        .outerjoin(
            AssessmentDecision,
            AssessmentDecision.assessment_attempt_id == AssessmentAttempt.id,
        )
        .where(
            AssessmentDefinitionVersion.course_id == course_id,
            AssessmentAttempt.student_id.in_(roster),
        )
    )
    source = union_all(
        evidence, independence, estimates, misconceptions, adaptations, choices, results
    ).subquery()
    query = select(source).where(source.c.outcome_id.is_not(None))
    if outcome_id is not None:
        query = query.where(source.c.outcome_id == outcome_id)
    return query.subquery()


def weekly_trends(session, source):
    weeks = defaultdict(dict)
    for kind, day, count in session.execute(
        select(
            source.c.kind,
            func.date(source.c.occurred_at),
            func.count(),
        ).group_by(source.c.kind, func.date(source.c.occurred_at))
    ):
        occurred = date.fromisoformat(day)
        week = (occurred - timedelta(days=occurred.weekday())).isoformat()
        weeks[week][kind] = weeks[week].get(kind, 0) + count
    return dict(sorted(weeks.items()))


def contributing_records(
    session, source, *, course_id, kind, week=None, response_id=None, limit=25, offset=0
):
    query = select(source).where(
        source.c.kind.startswith("result:") if kind == "result" else source.c.kind == kind
    )
    if response_id is not None:
        query = query.where(source.c.response_id == response_id)
    if week:
        query = query.where(
            func.date(source.c.occurred_at) >= week.isoformat(),
            func.date(source.c.occurred_at) < (week + timedelta(days=7)).isoformat(),
        )
    rows = (
        session.execute(
            query.order_by(source.c.occurred_at.desc(), source.c.id).limit(limit + 1).offset(offset)
        )
        .mappings()
        .all()
    )
    items = []
    for row in rows[:limit]:
        data = dict(row)
        data["learner_name"] = session.get(User, row["learner_id"]).full_name
        links = [row["evidence_id"]] if row["evidence_id"] else []
        if row["estimate_id"]:
            links = list(
                session.scalars(
                    select(LearnerModelEvidenceLink.evidence_id).where(
                        LearnerModelEvidenceLink.estimate_id == row["estimate_id"],
                    )
                )
            )
        if row["workflow_id"]:
            links = session.get(ActivityProgress, row["workflow_id"]).evidence_ids
        if row["response_id"] and not links:
            links = list(
                session.scalars(
                    select(LearningEvidence.id).where(
                        LearningEvidence.response_version_id == row["response_id"],
                    )
                )
            )
        # Related links must independently retain this record's learner and outcome scope.
        data["evidence_ids"] = list(
            session.scalars(
                select(LearningEvidence.id)
                .where(
                    LearningEvidence.id.in_(links),
                    LearningEvidence.course_id == course_id,
                    LearningEvidence.learner_id == row["learner_id"],
                    LearningEvidence.outcome_id == row["outcome_id"],
                )
                .order_by(LearningEvidence.id)
            )
        )
        items.append(data)
    return {"items": items, "next_offset": offset + limit if len(rows) > limit else None}
