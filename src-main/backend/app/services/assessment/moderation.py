"""Policy-bound live moderation; every mutation shares the course decision lock."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select, update

from app.domain.assessment import AssessmentResult, ResultState
from app.models.assessment import AssessmentAttempt, AssessmentDecision, TaskFormVersion
from app.models.assessment_moderation import ModerationPolicy, ModerationReview, ModerationSelection
from app.models.lms import Course, PlatformAuditEvent
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


NEXT_STAGE = {
    "ORIGINAL_REQUIRED": "ORIGINAL",
    "SECOND_REQUIRED": "SECOND",
    "DISAGREEMENT": "RESOLUTION",
    "DRIFT_REQUIRED": "DRIFT",
    "DRIFT_DISAGREEMENT": "DRIFT_RESOLUTION",
}


class ModerationService:
    def __init__(self, session, *, correlation_id=None):
        self.session = session
        self.correlation_id = correlation_id or str(uuid4())

    def lock(self, course_id):
        self.session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(id=Course.id, updated_at=Course.updated_at)
        )

    def policy(self, course_id):
        return self.session.scalar(
            select(ModerationPolicy)
            .where(ModerationPolicy.course_id == course_id)
            .order_by(ModerationPolicy.version.desc())
            .limit(1)
        )

    def configure(
        self,
        actor,
        course_id,
        *,
        initial_count,
        later_percent,
        drift_interval,
        approval_reference,
        training_reference,
        expires_at,
    ):
        RoleAssignmentService(self.session).require_assessor_access(actor, course_id)
        if (
            not approval_reference.strip()
            or not training_reference.strip()
            or utc(expires_at) <= datetime.now(UTC)
        ):
            raise AssessmentReviewValidationError(
                "Record approved sampling policy, assessor training reference and future expiry"
            )
        if not (0 <= initial_count and 0 <= later_percent <= 100 and drift_interval > 0):
            raise AssessmentReviewValidationError("Sampling settings are invalid")
        self.lock(course_id)
        RoleAssignmentService(self.session).require_assessor_access(actor, course_id)
        prior = self.policy(course_id)
        policy = ModerationPolicy(
            course_id=course_id,
            version=prior.version + 1 if prior else 1,
            initial_count=initial_count,
            later_percent=later_percent,
            drift_interval=drift_interval,
            approval_reference=approval_reference.strip(),
            training_reference=training_reference.strip(),
            expires_at=expires_at,
            actor_id=actor.id,
        )
        self.session.add(policy)
        self.session.flush()
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action="assessment_moderation.policy_recorded",
                resource_type="assessment_moderation_policy",
                resource_id=policy.id,
                correlation_id=self.correlation_id,
                details={
                    "course_id": course_id,
                    "policy_id": policy.id,
                    "policy_version": policy.version,
                    "result": "CONFIGURED",
                    "initial_count": initial_count,
                    "later_percent": later_percent,
                    "drift_interval": drift_interval,
                },
            )
        )
        return policy

    def select_attempt(self, attempt):
        self.lock(attempt.course_id)
        existing = self.session.get(ModerationSelection, attempt.id)
        if existing:
            return existing
        policy = self.policy(attempt.course_id)
        if policy is None or utc(policy.expires_at) <= datetime.now(UTC):
            raise AssessmentReviewConflictError(
                "Approved moderation sampling policy is missing or expired"
            )
        form = self.session.get(TaskFormVersion, attempt.task_form_version_id)
        # Order the full family, including earlier responses, rather than the order reviewers open it.
        ids = list(
            self.session.scalars(
                select(AssessmentAttempt.id)
                .join(TaskFormVersion)
                .where(
                    AssessmentAttempt.course_id == attempt.course_id,
                    TaskFormVersion.task_family == form.task_family,
                )
                .order_by(AssessmentAttempt.created_at, AssessmentAttempt.id)
            )
        )
        sequence = ids.index(attempt.id) + 1
        bucket = int(sha256(f"{policy.id}:{attempt.id}".encode()).hexdigest(), 16) % 100
        drift = sequence % policy.drift_interval == 0
        row = ModerationSelection(
            attempt_id=attempt.id,
            policy_id=policy.id,
            task_family=form.task_family,
            sequence=sequence,
            selected=sequence <= policy.initial_count or bucket < policy.later_percent or drift,
            drift_check=drift,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def reviews(self, attempt_id):
        cycle = (
            self.session.scalar(
                select(func.max(ModerationReview.cycle)).where(
                    ModerationReview.attempt_id == attempt_id
                )
            )
            or 1
        )
        return {
            row.stage: row
            for row in self.session.scalars(
                select(ModerationReview)
                .where(ModerationReview.attempt_id == attempt_id, ModerationReview.cycle == cycle)
                .order_by(ModerationReview.created_at, ModerationReview.id)
            )
        }

    @staticmethod
    def excluded_reviewers(stage, reviews):
        if stage == "SECOND":
            return {reviews["ORIGINAL"].actor_id}
        if stage == "RESOLUTION":
            return {reviews["ORIGINAL"].actor_id, reviews["SECOND"].actor_id}
        if stage == "DRIFT_RESOLUTION":
            prior = (
                {reviews["RESOLUTION"].actor_id}
                if "RESOLUTION" in reviews
                else {reviews["ORIGINAL"].actor_id, reviews["SECOND"].actor_id}
            )
            return prior | {reviews["DRIFT"].actor_id}
        return set()

    def withhold_judgements(self, actor, attempt_id):
        reviews = self.reviews(attempt_id)
        return bool(
            "ORIGINAL" in reviews
            and "SECOND" not in reviews
            and actor.id != reviews["ORIGINAL"].actor_id
        )

    def capture_if_configured(self, attempt):
        policy = self.policy(attempt.course_id)
        if policy and utc(policy.expires_at) > datetime.now(UTC):
            return self.select_attempt(attempt)
        return None

    def status(self, selection):
        reviews = self.reviews(selection.attempt_id)
        if not selection.selected:
            return "NOT_SAMPLED", None
        if "ORIGINAL" not in reviews:
            return "ORIGINAL_REQUIRED", None
        if "SECOND" not in reviews:
            return "SECOND_REQUIRED", None
        original, second = reviews["ORIGINAL"], reviews["SECOND"]
        if original.result != second.result and "RESOLUTION" not in reviews:
            return "DISAGREEMENT", None
        result = reviews.get("RESOLUTION", second).result
        if selection.drift_check and "DRIFT" not in reviews:
            return "DRIFT_REQUIRED", result
        if selection.drift_check and reviews["DRIFT"].result != result:
            if "DRIFT_RESOLUTION" not in reviews:
                return "DRIFT_DISAGREEMENT", None
            result = reviews["DRIFT_RESOLUTION"].result
        return "READY", result

    def require_ready(self, actor, attempt, result):
        RoleAssignmentService(self.session).require_assessor_access(actor, attempt.course_id)
        if actor.id == attempt.student_id:
            raise AssessmentReviewValidationError("Learners cannot review their own assessment")
        # No selected sampling policy exists in D-09. Preserve ordinary human
        # confirmation while the explicit moderation workspace reports POLICY_REQUIRED.
        if self.policy(attempt.course_id) is None:
            return
        if self.session.get(ModerationSelection, attempt.id) is None:
            prior = self.session.scalar(
                select(AssessmentDecision).where(
                    AssessmentDecision.assessment_attempt_id == attempt.id
                )
            )
            if prior and prior.result_state in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}:
                # Activating sampling is prospective; earlier human results keep
                # their existing review/correction rights and are never relabelled moderated.
                return
        selection = self.select_attempt(attempt)
        state, moderated_result = self.status(selection)
        if state not in {"READY", "NOT_SAMPLED"}:
            raise AssessmentReviewConflictError(
                f"Moderation blocks confirmation: {state}. Open assessment moderation."
            )
        if moderated_result is not None and result != AssessmentResult(moderated_result):
            raise AssessmentReviewConflictError(
                "The final result must match the resolved moderation decision"
            )

    def record(self, actor, attempt, stage, request, human_service):
        RoleAssignmentService(self.session).require_assessor_access(actor, attempt.course_id)
        self.lock(attempt.course_id)
        RoleAssignmentService(self.session).require_assessor_access(actor, attempt.course_id)
        selection = self.select_attempt(attempt)
        if not selection.selected or actor.id == attempt.student_id:
            raise AssessmentReviewValidationError(
                "This actor or attempt is not eligible for moderation"
            )
        decision = self.session.scalar(
            select(AssessmentDecision).where(AssessmentDecision.assessment_attempt_id == attempt.id)
        )
        if decision and decision.result_state == ResultState.VOID:
            raise AssessmentReviewConflictError("A void result cannot be moderated")
        reviews = self.reviews(attempt.id)
        request_digest = sha256(
            json.dumps(
                {"stage": stage, "request": asdict(request)}, sort_keys=True, default=str
            ).encode()
        ).hexdigest()
        saved = self.session.scalar(
            select(ModerationReview).where(
                ModerationReview.attempt_id == attempt.id,
                ModerationReview.request_key == request.idempotency_key,
            )
        )
        if saved:
            if saved.actor_id == actor.id and saved.request_digest == request_digest:
                return saved
            raise AssessmentReviewConflictError("This moderation action key was already used")
        state, _ = self.status(selection)
        expected = NEXT_STAGE.get(state)
        cycle = max((row.cycle for row in reviews.values()), default=1)
        if stage == "CORRECTION":
            if (
                state != "READY"
                or not decision
                or decision.result_state not in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}
            ):
                raise AssessmentReviewConflictError(
                    "Finish the current moderation and formal review before opening a correction"
                )
            cycle += 1
            stage = "ORIGINAL"
            expected = "ORIGINAL"
        if stage != expected:
            raise AssessmentReviewConflictError(
                "Reload the current moderation stage before recording a decision"
            )
        if actor.id in self.excluded_reviewers(stage, reviews):
            message = (
                "A different authorised assessor must provide the independent second review"
                if stage == "SECOND"
                else "A third authorised assessor outside the disagreement must resolve it"
            )
            raise AssessmentReviewValidationError(message)
        outcome, _references = human_service.evaluate_request(actor, attempt, request)
        drift_disagrees = stage == "DRIFT" and outcome.result.value != self.status(selection)[1]
        entries = [asdict(entry) for entry in request.criteria]
        row = ModerationReview(
            attempt_id=attempt.id,
            stage=stage,
            cycle=cycle,
            request_key=request.idempotency_key,
            request_digest=request_digest,
            actor_id=actor.id,
            result=outcome.result.value,
            reason=request.reason.strip(),
            criteria=entries,
        )
        self.session.add(row)
        self.session.flush()
        policy = self.session.get(ModerationPolicy, selection.policy_id)
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action="assessment_moderation.review_recorded",
                resource_type="assessment_moderation_review",
                resource_id=row.id,
                correlation_id=self.correlation_id,
                details={
                    "course_id": attempt.course_id,
                    "assessment_attempt_id": attempt.id,
                    "policy_id": selection.policy_id,
                    "policy_version": policy.version,
                    "stage": stage,
                    "cycle": cycle,
                    "result": row.result,
                    "assessment_definition_version_id": attempt.assessment_definition_version_id,
                    "task_form_version_id": attempt.task_form_version_id,
                    "bloom_target_version_id": attempt.bloom_target_version_id,
                    "pass_rule_version_id": attempt.pass_rule_version_id,
                },
            )
        )
        if drift_disagrees:
            from app.services.assessment.evaluator_release import EvaluatorReleaseService

            EvaluatorReleaseService(
                self.session, correlation_id=self.correlation_id
            ).invalidate_for_drift(attempt.course_id, row.id)
        return row

    def queue(self, actor, course_id):
        RoleAssignmentService(self.session).require_assessor_access(actor, course_id)
        policy = self.policy(course_id)
        active = bool(policy and utc(policy.expires_at) > datetime.now(UTC))
        rows = []
        attempts = self.session.scalars(
            select(AssessmentAttempt)
            .where(AssessmentAttempt.course_id == course_id)
            .order_by(AssessmentAttempt.created_at, AssessmentAttempt.id)
        ).all()
        for attempt in attempts:
            selection = self.session.get(ModerationSelection, attempt.id)
            decision = self.session.scalar(
                select(AssessmentDecision).where(
                    AssessmentDecision.assessment_attempt_id == attempt.id
                )
            )
            if selection is None and (
                not active or (decision and decision.result_state != ResultState.PROVISIONAL)
            ):
                continue
            selection = selection or self.select_attempt(attempt)
            state, result = self.status(selection)
            if not selection.selected:
                continue
            reviews = self.reviews(attempt.id)
            next_stage = NEXT_STAGE.get(state)
            if (
                state == "READY"
                and decision
                and decision.result_state in {ResultState.CONFIRMED, ResultState.OVERRIDDEN}
            ):
                next_stage = "CORRECTION"
            eligible = actor.id != attempt.student_id
            eligible &= actor.id not in self.excluded_reviewers(next_stage, reviews)
            withheld = self.withhold_judgements(actor, attempt.id)
            history = (
                []
                if withheld
                else list(
                    self.session.scalars(
                        select(ModerationReview)
                        .where(ModerationReview.attempt_id == attempt.id)
                        .order_by(
                            ModerationReview.cycle, ModerationReview.created_at, ModerationReview.id
                        )
                    )
                )
            )
            rows.append(
                {
                    "attempt_id": attempt.id,
                    "task_family": selection.task_family,
                    "sequence": selection.sequence,
                    "policy_id": selection.policy_id,
                    "drift_check": selection.drift_check,
                    "state": state,
                    "cycle": max((review.cycle for review in reviews.values()), default=1),
                    "formal_state": decision.result_state.value if decision else None,
                    "result": result,
                    "next_stage": next_stage if eligible else None,
                    "history_withheld": withheld,
                    "history": [
                        {
                            "stage": r.stage,
                            "cycle": r.cycle,
                            "actor_id": r.actor_id,
                            "result": r.result,
                            "reason": r.reason,
                            "criteria": r.criteria,
                            "created_at": r.created_at,
                        }
                        for r in history
                    ],
                }
            )
        return {"policy_status": "CONFIGURED" if active else "POLICY_REQUIRED", "records": rows}
