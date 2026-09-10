"""Read-only progress from frozen evidence scope and the released-result policy."""

import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import func, select, union

from app.domain.platform_enums import EvidenceType
from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.assessment import AssessmentAttempt, AssessmentDefinitionVersion, OutcomeVersion
from app.models.learner_model import (
    LearnerModelEvidenceLink,
    LearnerModelSnapshot,
    LearnerOutcomeEstimate,
)
from app.models.learning_evidence import EvidenceArtifact, LearningEvidence
from app.models.lms import (
    CourseModule,
    Enrollment,
    EnrollmentStatus,
    LearningOutcome,
    SubmissionAttempt,
)
from app.models.misconceptions import MisconceptionHypothesis
from app.models.user import User, UserRole
from app.schemas.progress import (
    LearningProgressPage,
    ProgressAdaptation,
    ProgressEstimate,
    ProgressObservation,
    ProgressResult,
    ProgressScopeRead,
)
from app.services.assessment.learner_results import LearnerResultService
from app.services.assessment.outcome_results import OutcomeResultService
from app.services.curriculum import CurriculumService


class LearningProgressService:
    def __init__(self, session):
        self.session = session

    def scope(self, actor, course_id, *, learner_id=None):
        if not actor.is_active or actor.role not in {UserRole.STUDENT, UserRole.EDUCATOR}:
            raise HTTPException(404, "Learning progress is unavailable")
        course = CurriculumService(self.session)._access(
            actor, course_id, owner=actor.role == UserRole.EDUCATOR
        )
        if actor.role == UserRole.STUDENT:
            if learner_id is not None and learner_id != actor.id:
                raise HTTPException(404, "Learning progress is unavailable")
            learner_id = actor.id
        roster = (
            select(User.id)
            .join(Enrollment, Enrollment.student_id == User.id)
            .where(
                Enrollment.course_id == course_id,
                Enrollment.status == EnrollmentStatus.ACTIVE,
                User.is_active.is_(True),
                User.role == UserRole.STUDENT,
            )
        )
        if learner_id is not None:
            roster = roster.where(User.id == learner_id)
            if self.session.scalar(roster) is None:
                raise HTTPException(404, "Learning progress is unavailable")
        return course, roster

    def read(self, actor, course_id, *, learner_id=None, outcome_id=None, limit=10, offset=0):
        course, roster = self.scope(actor, course_id, learner_id=learner_id)
        scope = [LearningEvidence.course_id == course_id, LearningEvidence.learner_id.in_(roster)]
        if outcome_id is not None:
            scope.append(LearningEvidence.outcome_id == outcome_id)
        cohort, weekly = self._counts(scope)
        from app.services.progress_trends import records_query, weekly_trends

        trends = weekly_trends(self.session, records_query(course_id, roster, outcome_id))
        # Preserve historical outcome scope even if current curriculum metadata moves.
        scopes = union(
            select(LearningEvidence.learner_id, LearningEvidence.outcome_id).where(*scope),
            select(Enrollment.student_id, LearningOutcome.id)
            .join(CourseModule, CourseModule.course_id == Enrollment.course_id)
            .join(LearningOutcome, LearningOutcome.module_id == CourseModule.id)
            .where(Enrollment.course_id == course_id, Enrollment.student_id.in_(roster)),
            select(LearnerModelSnapshot.learner_id, LearnerModelSnapshot.outcome_id).where(
                LearnerModelSnapshot.course_id == course_id,
                LearnerModelSnapshot.learner_id.in_(roster),
            ),
            select(AssessmentAttempt.student_id, OutcomeVersion.learning_outcome_id)
            .join(
                AssessmentDefinitionVersion,
                AssessmentDefinitionVersion.id
                == AssessmentAttempt.assessment_definition_version_id,
            )
            .join(
                OutcomeVersion, OutcomeVersion.id == AssessmentDefinitionVersion.outcome_version_id
            )
            .where(
                AssessmentDefinitionVersion.course_id == course_id,
                AssessmentAttempt.student_id.in_(roster),
            ),
        ).subquery()
        query = select(scopes).order_by(scopes.c.learner_id, scopes.c.outcome_id)
        if outcome_id is not None:
            query = query.where(scopes.c.outcome_id == outcome_id)
        pairs = self.session.execute(query.limit(limit + 1).offset(offset)).all()
        return LearningProgressPage(
            course_id=course.id,
            course_title=course.title,
            generated_at=datetime.now(UTC),
            cohort_observations=cohort,
            cohort_weekly_observations=weekly,
            cohort_weekly_trends=trends,
            items=[self._scope(course_id, learner, outcome) for learner, outcome in pairs[:limit]],
            next_offset=offset + limit if len(pairs) > limit else None,
        )

    def _counts(self, scope):
        counts = {
            kind.value: count
            for kind, count in self.session.execute(
                select(LearningEvidence.evidence_type, func.count())
                .where(*scope)
                .group_by(LearningEvidence.evidence_type)
            )
        }
        weekly = defaultdict(dict)
        rows = self.session.execute(
            select(
                LearningEvidence.evidence_type,
                func.date(LearningEvidence.occurred_at),
                func.count(),
            )
            .where(*scope)
            .group_by(LearningEvidence.evidence_type, func.date(LearningEvidence.occurred_at))
        )
        for kind, day, count in rows:
            date = datetime.strptime(day, "%Y-%m-%d").date()
            week = (date - timedelta(days=date.weekday())).isoformat()
            weekly[week][kind.value] = weekly[week].get(kind.value, 0) + count
        return counts, dict(sorted(weekly.items()))

    def _confidence(self, evidence):
        if evidence.actor_reference != str(evidence.learner_id):
            return None
        artifact = (
            self.session.get(EvidenceArtifact, evidence.artifact_id)
            if evidence.artifact_id
            else None
        )
        if not artifact or (artifact.course_id, artifact.learner_id) != (
            evidence.course_id,
            evidence.learner_id,
        ):
            return None
        if (
            artifact.content_digest != evidence.content_digest
            or artifact.content_digest != "sha256:" + sha256(artifact.content.encode()).hexdigest()
        ):
            return None
        try:
            payload = json.loads(artifact.content)
            value = (
                payload.get("response")
                if evidence.schema_version == "learnlens.diagnostic.v1"
                else payload.get("value")
            )
        except (ValueError, AttributeError):
            return None
        value = (
            value.get("confidence")
            if isinstance(value, dict)
            else value
            if evidence.evidence_type == EvidenceType.CONFIDENCE
            else None
        )
        if type(value) in {float, int} and 0 <= value <= 1:
            return float(value)
        if isinstance(value, str) and value in {"unsure", "somewhat_sure", "sure"}:
            return value
        return None

    def _scope(self, course_id, learner_id, outcome_id):
        scope = [
            LearningEvidence.course_id == course_id,
            LearningEvidence.learner_id == learner_id,
            LearningEvidence.outcome_id == outcome_id,
        ]
        counts, weekly = self._counts(scope)
        levels = dict(
            self.session.execute(
                select(LearningEvidence.instructional_support_level, func.count())
                .where(
                    *scope,
                    LearningEvidence.evidence_type.in_(
                        [EvidenceType.RESPONSE, EvidenceType.REVISION, EvidenceType.TRANSFER]
                    ),
                )
                .group_by(LearningEvidence.instructional_support_level)
            ).all()
        )
        evidence = self.session.scalars(
            select(LearningEvidence)
            .where(*scope)
            .order_by(LearningEvidence.occurred_at.desc(), LearningEvidence.id)
            .limit(20)
        ).all()
        outcome = self.session.scalar(
            select(LearningOutcome)
            .join(CourseModule, CourseModule.id == LearningOutcome.module_id)
            .where(LearningOutcome.id == outcome_id, CourseModule.course_id == course_id)
        )
        snapshots = self.session.scalars(
            select(LearnerModelSnapshot)
            .where(
                LearnerModelSnapshot.course_id == course_id,
                LearnerModelSnapshot.learner_id == learner_id,
                LearnerModelSnapshot.outcome_id == outcome_id,
            )
            .order_by(LearnerModelSnapshot.record_version.desc())
            .limit(20)
        ).all()
        estimates = []
        for snapshot in reversed(snapshots):
            for estimate in self.session.scalars(
                select(LearnerOutcomeEstimate).where(
                    LearnerOutcomeEstimate.snapshot_id == snapshot.id
                )
            ):
                links = self.session.execute(
                    select(LearnerModelEvidenceLink.evidence_id, LearnerModelEvidenceLink.relation)
                    .join(
                        LearningEvidence,
                        LearningEvidence.id == LearnerModelEvidenceLink.evidence_id,
                    )
                    .where(LearnerModelEvidenceLink.estimate_id == estimate.id, *scope)
                ).all()
                estimates.append(
                    ProgressEstimate(
                        snapshot_id=snapshot.id,
                        prior_snapshot_id=snapshot.prior_snapshot_id,
                        estimate_id=estimate.id,
                        dimension=estimate.dimension.value,
                        status=estimate.inference_status.value,
                        uncertainty=estimate.uncertainty,
                        reason=estimate.reason_code,
                        occurred_at=snapshot.occurred_at,
                        evidence=[
                            {"evidence_id": key, "relation": relation.value}
                            for key, relation in links
                        ],
                    )
                )
        results = []
        responses = self.session.scalars(
            select(SubmissionAttempt)
            .join(AssessmentAttempt, AssessmentAttempt.response_version_id == SubmissionAttempt.id)
            .join(
                AssessmentDefinitionVersion,
                AssessmentDefinitionVersion.id
                == AssessmentAttempt.assessment_definition_version_id,
            )
            .join(
                OutcomeVersion, OutcomeVersion.id == AssessmentDefinitionVersion.outcome_version_id
            )
            .where(
                AssessmentAttempt.student_id == learner_id,
                AssessmentDefinitionVersion.course_id == course_id,
                OutcomeVersion.learning_outcome_id == outcome_id,
            )
            .order_by(SubmissionAttempt.submitted_at.desc(), SubmissionAttempt.id)
            .limit(20)
        ).all()
        learner = self.session.get(User, learner_id)
        outcomes = {}
        for response in responses:
            attempt = self.session.scalar(
                select(AssessmentAttempt).where(
                    AssessmentAttempt.response_version_id == response.id
                )
            )
            # The real actor's frozen course/learner scope is already authorized.
            released = LearnerResultService(self.session).project_authorized(attempt)
            result, status = released.result, released.status
            outcome_result = OutcomeResultService(self.session).project_authorized(attempt)
            outcomes[outcome_result.definition_version_id] = outcome_result.model_dump(
                exclude={"authorisations"}
            )
            results.append(
                ProgressResult(
                    response_id=response.id,
                    task_id=response.task_id,
                    result=result,
                    status=status,
                    occurred_at=response.submitted_at,
                )
            )
        adaptations = []
        for receipt, suggestion in self.session.execute(
            select(ActivityProgress, ActivitySuggestion)
            .join(
                ActivitySuggestion, ActivitySuggestion.workflow_id == ActivityProgress.workflow_id
            )
            .where(
                ActivityProgress.course_id == course_id,
                ActivityProgress.learner_id == learner_id,
                ActivityProgress.outcome_id == outcome_id,
            )
            .order_by(ActivityProgress.created_at.desc())
            .limit(20)
        ):
            decision = suggestion.decision
            choices = self.session.scalars(
                select(ActivityChoice)
                .where(ActivityChoice.workflow_id == receipt.workflow_id)
                .order_by(ActivityChoice.version)
            ).all()
            adaptations.append(
                ProgressAdaptation(
                    workflow_id=receipt.workflow_id,
                    state=decision.get("state", receipt.state),
                    reason=decision.get("reason", "No adaptation reason was recorded."),
                    uncertainty=decision.get("uncertainty", 1),
                    snapshot_id=receipt.snapshot_id,
                    evidence_ids=receipt.evidence_ids,
                    occurred_at=receipt.created_at,
                    choices=[
                        {
                            "version": row.version,
                            "created_at": row.created_at,
                            "action": row.payload["action"],
                            "task_id": row.payload.get("selected_task_id"),
                            "reason": row.payload["reason"],
                            "educator": row.payload["action"] == "educator_override",
                        }
                        for row in choices
                    ],
                )
            )
        return ProgressScopeRead(
            learner_id=learner_id,
            learner_name=learner.full_name,
            outcome_id=outcome_id,
            outcome_title=outcome.title if outcome else "Saved outcome history",
            observations=counts,
            weekly_observations=weekly,
            independent_responses=levels.get(0, 0),
            supported_responses=sum(count for level, count in levels.items() if level > 0),
            recent_evidence=[
                ProgressObservation(
                    evidence_id=row.id,
                    task_id=row.task_id,
                    response_id=row.response_version_id,
                    kind=row.evidence_type.value,
                    support_level=row.instructional_support_level,
                    occurred_at=row.occurred_at,
                    confidence=self._confidence(row),
                )
                for row in evidence
            ],
            estimates=estimates,
            results=results,
            outcome_results=list(outcomes.values()),
            adaptations=adaptations,
            misconception_ids=list(
                self.session.scalars(
                    select(MisconceptionHypothesis.id)
                    .where(
                        MisconceptionHypothesis.course_id == course_id,
                        MisconceptionHypothesis.student_id == learner_id,
                        MisconceptionHypothesis.outcome_id == outcome_id,
                    )
                    .order_by(MisconceptionHypothesis.created_at.desc())
                    .limit(20)
                )
            ),
        )
