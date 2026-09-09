"""A bounded tutor that sequences reviewed hints and preserves learner reasoning."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Callable
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.domain.assessment import QualityReviewDecision
from app.domain.platform_enums import InferenceStatus
from app.models.assessment import TaskApproval, TaskFormVersion
from app.models.assessment_work import AssessmentWorkStart
from app.models.episode import EpisodeStageStart
from app.models.persistence import LearningTask
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.models.tutor import TutorTurn
from app.models.user import User
from app.schemas.episode import EpisodeHelpUseWrite
from app.schemas.tutor import TutorConversationRead, TutorTurnRead, TutorTurnWrite
from app.services.assessment.publication import require_current_publication
from app.services.episode_contract import validate_reviewed_episode_plan
from app.services.episode_support import EpisodeSupportService
from app.services.episodes import EpisodeService
from app.services.evidence.live import LiveEvidenceCapture
from app.services.feedback.assessed import INSTRUCTION_PATTERN
from app.services.learner_model.repository import SqlAlchemyLearnerModelRepository
from app.services.learner_preferences.repository import SqlAlchemyLearnerPreferencesRepository
from app.services.learner_preferences.service import LearnerPreferencesService
from app.services.lms import LmsService, LmsServiceError
from app.services.task_review import TaskReviewService

RULE_VERSION = "reviewed-tutor-v1"
PROBE = "What do you expect to happen in this task, and what is your reason?"
REASONING = "Explain the reasoning behind your current approach before we consider another hint."
REFLECTION = (
    "Which observation supports your explanation? Describe one change you would make and why."
)
REDIRECT = "Let's work through your reasoning. What have you tried, and which step would you like to understand?"
FALLBACK = (
    "I cannot provide a checked hint for this step. Keep your work and ask your educator for help."
)
ANSWER_SEEKING = re.compile(
    r"(?:give|tell|show|write).{0,25}(?:answer|solution)|just.{0,12}(?:answer|solution)", re.I
)


@dataclass(frozen=True)
class TutorContext:
    task: LearningTask
    work: AssessmentWorkStart | None
    stage: EpisodeStageStart | None
    hints: tuple[str, ...]
    requires_reasoning: bool
    provenance: dict
    token: str


class TutorService:
    def __init__(self, session: Session, *, generate: Callable[[str, int], str] | None = None):
        self.session = session
        self.generate = generate or (lambda approved_reply, attempt: approved_reply)

    def _context(self, student: User, task_id: str) -> TutorContext:
        lms = LmsService(self.session)
        draft = lms.get_draft(student, task_id)
        task = self.session.get(LearningTask, task_id)
        work = (
            self.session.get(AssessmentWorkStart, draft.assessment_work_start_id)
            if draft and draft.assessment_work_start_id
            else None
        )
        stage = (
            self.session.scalar(
                select(EpisodeStageStart).where(
                    EpisodeStageStart.assessment_work_start_id == work.id
                )
            )
            if work
            else None
        )
        hints = ()
        requires_reasoning = False
        source_refs = list(task.source_references or [])
        if work:
            plan = EpisodeService(self.session).work_plan(work)
            form = self.session.get(TaskFormVersion, work.task_form_version_id)
            approval = self.session.get(TaskApproval, work.task_approval_id)
            require_current_publication(self.session, form, approval)
            revision_id = form.task_revision_id
            review_id = approval.task_review_event_id
            source_refs = work.source_references
            if plan:
                hints = plan.supported_hints
                requires_reasoning = bool(
                    {"reasoning", "explanation"}.intersection(plan.required_responses)
                )
        else:
            summary = TaskReviewService(self.session).summary(task)
            if not summary["available"]:
                raise LmsServiceError(
                    409, "This task needs educator review before tutor help is available"
                )
            revision_id = summary["revision_id"]
            review = self.session.scalar(
                select(TaskReviewEvent)
                .where(TaskReviewEvent.task_revision_id == revision_id)
                .order_by(TaskReviewEvent.version.desc())
                .limit(1)
            )
            review_id = review.id
            revision = self.session.get(TaskRevision, revision_id)
            plan = validate_reviewed_episode_plan(revision.snapshot.get("marking_criteria"))
            if plan:
                hints = plan.supported_hints
                requires_reasoning = bool(
                    {"reasoning", "explanation"}.intersection(plan.required_responses)
                )
        context = {
            "task_revision_id": revision_id,
            "task_review_event_id": review_id,
            "work_id": work.id if work else None,
            "stage_id": stage.id if stage else None,
            "source_references": source_refs,
            "rule_version": RULE_VERSION,
        }
        token = sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()
        return TutorContext(task, work, stage, tuple(hints), requires_reasoning, context, token)

    def read(self, student: User, task_id: str, *, offset: int = 0) -> TutorConversationRead:
        context = self._context(student, task_id)
        latest = self._latest(student.id, task_id)
        rows = (
            []
            if context.stage
            else list(
                self.session.scalars(
                    select(TutorTurn)
                    .where(
                        TutorTurn.student_id == student.id,
                        TutorTurn.task_id == task_id,
                        TutorTurn.context_token == context.token,
                    )
                    .order_by(TutorTurn.revision.desc())
                    .limit(21)
                    .offset(offset)
                )
            )
        )
        return TutorConversationRead(
            context_token=context.token,
            revision=latest.revision if latest else 0,
            instructional_help_available=context.stage is None,
            status="Fresh application is unaided. Accessibility support remains available."
            if context.stage
            else "Use this conversation to explain your reasoning and work through approved hints.",
            turns=[self._read_turn(row) for row in reversed(rows[:20])],
            next_offset=offset + 20 if len(rows) > 20 else None,
        )

    def send(self, student: User, task_id: str, payload: TutorTurnWrite) -> TutorTurnRead:
        try:
            self.session.execute(
                update(User).where(User.id == student.id).values(is_active=User.is_active)
            )
            current = self._context(student, task_id)
            task, work = current.task, current.work
            context, token = current.provenance, current.token
            hints = current.hints
            if current.stage:
                raise LmsServiceError(
                    422, "Instructional dialogue is unavailable during fresh application"
                )
            if payload.context_token != token:
                raise LmsServiceError(409, "The task changed. Reload before sending your message")
            prior = self.session.scalar(
                select(TutorTurn).where(
                    TutorTurn.student_id == student.id,
                    TutorTurn.task_id == task_id,
                    TutorTurn.request_key == payload.idempotency_key,
                )
            )
            if prior:
                if (prior.learner_text, prior.context_token) != (
                    payload.message,
                    payload.context_token,
                ):
                    raise LmsServiceError(
                        409, "This conversation key was used for a different turn"
                    )
                self.session.rollback()
                return self._read_turn(prior)
            latest = self._latest(student.id, task_id)
            revision = latest.revision if latest else 0
            if payload.context_token != token or payload.expected_revision != revision:
                raise LmsServiceError(
                    409, "The conversation or task changed. Reload before sending your message"
                )
            preferences = LearnerPreferencesService(
                SqlAlchemyLearnerPreferencesRepository(self.session)
            ).read(student.id)
            snapshot = (
                SqlAlchemyLearnerModelRepository(self.session).current(
                    course_id=task.course_id,
                    learner_id=str(student.id),
                    outcome_id=task.learning_outcome_id,
                )
                if preferences.personalisation_enabled
                else None
            )
            needs_review = bool(
                snapshot
                and any(
                    estimate.inference_status
                    in {InferenceStatus.NEEDS_REVIEW, InferenceStatus.CONTRADICTED}
                    for estimate in snapshot.estimates
                )
            )
            context.update(
                preference_revision=preferences.revision,
                model_snapshot_id=snapshot.snapshot_id if snapshot else None,
            )
            context["selection_reason"] = (
                "REVIEW_RECORDED_EVIDENCE" if needs_review else "APPROVED_HINT_SEQUENCE"
            )
            turns = list(
                self.session.scalars(
                    select(TutorTurn)
                    .where(
                        TutorTurn.student_id == student.id,
                        TutorTurn.task_id == task_id,
                        TutorTurn.context_token == token,
                    )
                    .order_by(TutorTurn.revision.desc())
                    .limit(2)
                )
            )
            hint_index = None
            if ANSWER_SEEKING.search(payload.message) or INSTRUCTION_PATTERN.search(
                payload.message
            ):
                candidate, kind = REDIRECT, "redirect"
            elif not turns:
                candidate, kind = (REFLECTION if needs_review else PROBE), "probe"
            elif current.requires_reasoning and turns[0].kind == "hint":
                candidate, kind = REASONING, "reasoning"
            elif hints:
                last_hint = self.session.scalar(
                    select(TutorTurn)
                    .where(
                        TutorTurn.student_id == student.id,
                        TutorTurn.task_id == task_id,
                        TutorTurn.context_token == token,
                        TutorTurn.kind == "hint",
                    )
                    .order_by(TutorTurn.revision.desc())
                    .limit(1)
                )
                hint_index = min((last_hint.hint_index + 1) if last_hint else 0, len(hints) - 1)
                candidate, kind = hints[hint_index], "hint"
            else:
                candidate, kind = REFLECTION, "reflection"
            quality = []
            reply = FALLBACK
            for attempt in range(2):
                try:
                    generated = self.generate(candidate, attempt)
                    approved = (
                        isinstance(generated, str)
                        and generated == candidate
                        and not INSTRUCTION_PATTERN.search(generated)
                    )
                    quality.append(
                        {
                            "attempt": attempt + 1,
                            "status": "COMPLETED",
                            "decision": (
                                QualityReviewDecision.APPROVED.value
                                if approved
                                else QualityReviewDecision.REJECTED.value
                            ),
                            "rule_version": RULE_VERSION,
                        }
                    )
                    if approved:
                        reply = generated
                        break
                except Exception:
                    quality.append(
                        {
                            "attempt": attempt + 1,
                            "status": "FAILED",
                            "decision": None,
                            "rule_version": RULE_VERSION,
                        }
                    )
            if reply == FALLBACK:
                kind, hint_index = "fallback", None
            row = TutorTurn(
                id=str(uuid4()),
                student_id=student.id,
                task_id=task_id,
                assessment_work_start_id=work.id if work else None,
                revision=revision + 1,
                request_key=payload.idempotency_key,
                context_token=token,
                learner_text=payload.message,
                reply=reply,
                kind=kind,
                hint_index=hint_index,
                context=context,
                quality=quality,
                created_at=datetime.now(UTC),
            )
            self.session.add(row)
            self.session.flush()
            if work and hint_index is not None:
                receipt = EpisodeSupportService(self.session).record(
                    work,
                    EpisodeHelpUseWrite(
                        assessment_work_start_id=work.id,
                        kind="conceptual_hint",
                        item_index=hint_index,
                        request_key="tutor:" + row.id,
                    ),
                )
                LiveEvidenceCapture(self.session).support(receipt)
            LiveEvidenceCapture(self.session).tutor(task, row)
            if row.kind == "fallback":
                from app.services.escalation_sources import record_signal

                record_signal(
                    self.session,
                    source_kind="TUTOR",
                    source_id=row.id,
                    trigger="REPEATED_REJECTION",
                    reason="Both tutor reply attempts failed their release checks.",
                )
            self.session.commit()
            return self._read_turn(row)
        except (IntegrityError, OperationalError) as error:
            self.session.rollback()
            raise LmsServiceError(
                409, "The conversation changed or is busy. Reload and retry"
            ) from error
        except Exception:
            self.session.rollback()
            raise

    def _latest(self, student_id: int, task_id: str):
        return self.session.scalar(
            select(TutorTurn)
            .where(TutorTurn.student_id == student_id, TutorTurn.task_id == task_id)
            .order_by(TutorTurn.revision.desc())
            .limit(1)
        )

    @staticmethod
    def _read_turn(row: TutorTurn) -> TutorTurnRead:
        return TutorTurnRead(
            id=row.id,
            revision=row.revision,
            message=row.learner_text,
            reply=row.reply,
            kind=row.kind,
            created_at=row.created_at,
            source_references=row.context["source_references"],
        )
