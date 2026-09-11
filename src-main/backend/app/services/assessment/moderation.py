"""Policy-bound live moderation; every mutation shares the course decision lock."""

from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select, update

from app.domain.assessment import AssessmentResult, ResultState
from app.models.assessment import AssessmentAttempt, AssessmentDecision, TaskFormVersion
from app.models.assessment_moderation import ModerationPolicy, ModerationReview, ModerationSelection
from app.models.lms import Course
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class ModerationService:
    def __init__(self, session):
        self.session = session

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
        return {
            row.stage: row
            for row in self.session.scalars(
                select(ModerationReview)
                .where(ModerationReview.attempt_id == attempt_id)
                .order_by(ModerationReview.created_at, ModerationReview.id)
            )
        }

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
        if decision and decision.result_state != ResultState.PROVISIONAL:
            raise AssessmentReviewConflictError("Moderation must precede formal confirmation")
        reviews = self.reviews(attempt.id)
        if stage in reviews:
            saved = reviews[stage]
            entries = [asdict(entry) for entry in request.criteria]
            for entry in entries:
                entry["evidence_ids"] = list(entry["evidence_ids"])
            if (
                saved.actor_id == actor.id
                and saved.reason == request.reason.strip()
                and saved.criteria == entries
            ):
                return saved
            raise AssessmentReviewConflictError("This moderation decision is already recorded")
        state, _ = self.status(selection)
        expected = {
            "ORIGINAL_REQUIRED": "ORIGINAL",
            "SECOND_REQUIRED": "SECOND",
            "DISAGREEMENT": "RESOLUTION",
            "DRIFT_REQUIRED": "DRIFT",
            "DRIFT_DISAGREEMENT": "DRIFT_RESOLUTION",
        }.get(state)
        if stage != expected:
            raise AssessmentReviewConflictError(
                "Reload the current moderation stage before recording a decision"
            )
        if stage == "SECOND" and actor.id == reviews["ORIGINAL"].actor_id:
            raise AssessmentReviewValidationError(
                "A different authorised assessor must provide the independent second review"
            )
        if stage in {"RESOLUTION", "DRIFT_RESOLUTION"} and actor.id in {
            reviews["ORIGINAL"].actor_id,
            reviews["SECOND"].actor_id,
        }:
            raise AssessmentReviewValidationError(
                "A third authorised assessor must resolve the disagreement"
            )
        outcome, _references = human_service.evaluate_request(actor, attempt, request)
        drift_disagrees = stage == "DRIFT" and outcome.result.value != self.status(selection)[1]
        entries = [asdict(entry) for entry in request.criteria]
        row = ModerationReview(
            attempt_id=attempt.id,
            stage=stage,
            actor_id=actor.id,
            result=outcome.result.value,
            reason=request.reason.strip(),
            criteria=entries,
        )
        self.session.add(row)
        self.session.flush()
        if drift_disagrees:
            from app.services.assessment.evaluator_release import EvaluatorReleaseService

            EvaluatorReleaseService(self.session).invalidate_for_drift(attempt.course_id, row.id)
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
            next_stage = {
                "ORIGINAL_REQUIRED": "ORIGINAL",
                "SECOND_REQUIRED": "SECOND",
                "DISAGREEMENT": "RESOLUTION",
                "DRIFT_REQUIRED": "DRIFT",
                "DRIFT_DISAGREEMENT": "DRIFT_RESOLUTION",
            }.get(state)
            eligible = actor.id != attempt.student_id
            if next_stage == "SECOND":
                eligible &= actor.id != reviews["ORIGINAL"].actor_id
            if next_stage in {"RESOLUTION", "DRIFT_RESOLUTION"}:
                eligible &= actor.id not in {
                    reviews["ORIGINAL"].actor_id,
                    reviews["SECOND"].actor_id,
                }
            rows.append(
                {
                    "attempt_id": attempt.id,
                    "task_family": selection.task_family,
                    "sequence": selection.sequence,
                    "policy_id": selection.policy_id,
                    "drift_check": selection.drift_check,
                    "state": state,
                    "formal_state": decision.result_state.value if decision else None,
                    "result": result,
                    "next_stage": next_stage if eligible else None,
                    "history": [
                        {
                            "stage": r.stage,
                            "actor_id": r.actor_id,
                            "result": r.result,
                            "reason": r.reason,
                            "criteria": r.criteria,
                            "created_at": r.created_at,
                        }
                        for r in reviews.values()
                    ],
                }
            )
        return {"policy_status": "CONFIGURED" if active else "POLICY_REQUIRED", "records": rows}
