"""Bounded, explainable review cues, separate from results and learner inference."""

import json
import re
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.models.assessment import AssessmentAttempt, TaskApproval, TaskFormVersion
from app.models.assessment_work import AssessmentWorkStart
from app.models.enums import FeedbackStatus, TaskType
from app.models.escalation import EscalationCase
from app.models.learning_evidence import EvidenceArtifact
from app.models.lms import SubmissionAttempt
from app.models.source_history import SourcePassage
from app.models.task_review import TaskReviewEvent, TaskRevision
from app.models.tutor import TutorTurn
from app.services.escalation_sources import record_signal

RULE_VERSION = "learning-review-cues-v2"
HISTORY_LIMIT = 40
HISTORY_DAYS = 30
TEXT_LIMIT = 20_000
SOURCE_LIMIT = 12
MATCH_LIMIT = 20
COPY_WORDS = 30
COPY_CHARS = 160
RECONSTRUCTION_TYPES = {
    task_type.value
    for task_type in (
        TaskType.MATCHING,
        TaskType.SEQUENCING,
        TaskType.MULTIPLE_CHOICE,
        TaskType.MULTIPLE_ANSWER,
        TaskType.QUIZ,
    )
}
REDIRECT = "Explain one step in your own reasoning or make a prediction for a fresh example."
COPIED_SOLUTION = re.compile(
    r"\bI (?:copied|pasted) (?:this|the|a) (?:answer|solution|code)\b|"
    r"\bas an AI language model\b",
    re.I,
)


def recent_turns(session, *, student_id, task_id, at, context_token=None, work_id=None):
    """Same learner/task and exact context; never join another task or future turn."""
    at = at.replace(tzinfo=UTC) if at.tzinfo is None else at
    query = select(TutorTurn).where(
        TutorTurn.student_id == student_id,
        TutorTurn.task_id == task_id,
        TutorTurn.created_at <= at,
        TutorTurn.created_at >= at - timedelta(days=HISTORY_DAYS),
    )
    if context_token is not None:
        query = query.where(TutorTurn.context_token == context_token)
    else:
        query = query.where(TutorTurn.assessment_work_start_id == work_id)
    return list(session.scalars(query.order_by(TutorTurn.revision.desc()).limit(HISTORY_LIMIT)))


def _cue(matches, **context):
    if not matches:
        return None
    return {
        "rule_version": RULE_VERSION,
        "signals": list(dict.fromkeys(item["signal"] for item in matches)),
        "matches": matches,
        "interpretation": (
            "Uncertain review cue. Quotation, permitted assistance, a supplied template, "
            "or other context may explain this language or reuse. Review the task conditions "
            "and ask the learner before drawing any conclusion."
        ),
        "next_action": REDIRECT,
        "assessment_effect": "none",
        "limits": {
            "history_turns": HISTORY_LIMIT,
            "history_days": HISTORY_DAYS,
            "characters_per_field": TEXT_LIMIT,
            "source_passages": SOURCE_LIMIT,
            "matches": MATCH_LIMIT,
        },
        **context,
    }


def _language_matches(text, field):
    return [
        {
            "signal": "COPIED_SOLUTION_LANGUAGE",
            "field": field,
            "start": match.start(),
            "end": match.end(),
        }
        for match in list(COPIED_SOLUTION.finditer(text[:TEXT_LIMIT]))[:MATCH_LIMIT]
    ]


def dialogue_cue(message, previous_turns, answer_seeking):
    previous_turns = previous_turns[:HISTORY_LIMIT]
    repeated = [turn for turn in previous_turns if answer_seeking.search(turn.learner_text)]
    matches = _language_matches(message, "learner_text")
    current = answer_seeking.search(message)
    if current and repeated:
        matches.append(
            {
                "signal": "REPEATED_ANSWER_ONLY_REQUEST",
                "field": "learner_text",
                "start": current.start(),
                "end": current.end(),
                "related_turn_ids": [turn.id for turn in repeated],
            }
        )
    return _cue(
        matches,
        related_turn_ids=[turn.id for turn in repeated] if current else [],
        inspected_turn_ids=[turn.id for turn in previous_turns],
    )


def route_cue(session, *, cue, source_kind, source_id, key):
    """One case per signal, including when two signals occur in the same message."""
    # v1 stored a combined key when both dialogue signals occurred at once.
    legacy = (
        session.scalar(
            select(EscalationCase).where(
                EscalationCase.request_key
                == key + ":REPEATED_ANSWER_ONLY_REQUEST,COPIED_SOLUTION_LANGUAGE"
            )
        )
        if source_kind == "TUTOR"
        else None
    )
    return [
        legacy
        if legacy and signal in {"REPEATED_ANSWER_ONLY_REQUEST", "COPIED_SOLUTION_LANGUAGE"}
        else record_signal(
            session,
            source_kind=source_kind,
            source_id=source_id,
            trigger="LEARNING_INTEGRITY_REVIEW",
            request_key=f"{key}:{signal}",
            severity="NORMAL",
            reason=f"{signal}. {cue['interpretation']} {cue['next_action']} "
            "This is not a misconduct finding and has no assessment penalty.",
        )
        for signal in cue["signals"]
    ]


def _response_fields(response):
    fields = {"answer": response.answer or "", "code": response.code or ""}

    def visit(value, path):
        if not isinstance(value, dict):
            return
        for key, child in value.items():
            name = f"{path}.{key}"
            if isinstance(child, str) and key in {
                "answer",
                "code",
                "reasoning",
                "explanation",
                "reflection",
                "text",
            }:
                fields[name] = child
            elif isinstance(child, dict):
                visit(child, name)

    visit(response.episode, "episode")
    return fields


def _overlap(text, source, exclusions):
    """One exact, substantial token run; offsets always address original strings."""
    if len(source[:TEXT_LIMIT].split()) < COPY_WORDS:
        return None
    tokens = list(re.finditer(r"\S+", text[:TEXT_LIMIT]))
    for index in range(len(tokens) - COPY_WORDS + 1):
        start, end = tokens[index].start(), tokens[index + COPY_WORDS - 1].end()
        candidate = text[start:end]
        if len(candidate) < COPY_CHARS or any(candidate in item for item in exclusions):
            continue
        found = source.find(candidate, 0, TEXT_LIMIT)
        if found >= 0:
            return {
                "start": start,
                "end": end,
                "source_start": found,
                "source_end": found + len(candidate),
            }
    return None


def artifact_id(response_id):
    return str(uuid5(NAMESPACE_URL, f"learnlens.integrity-cue:{response_id}"))


def _transfer_exclusions(form, field):
    """Only the transfer form actually supplied for this frozen work is applicable."""
    if not form or not field.startswith("episode.transfer."):
        return []
    plan = (form.constraints or {}).get("episode_plan") or {}
    transfer = plan.get("transfer") or {}
    exclusions = [transfer.get(key) or "" for key in ("prompt", "instructions")]
    if field.endswith(".code"):
        exclusions.append(transfer.get("starter_code") or "")
    return exclusions


def retained_submission_cue(session, response):
    artifact = session.get(EvidenceArtifact, artifact_id(response.id))
    if artifact and artifact.learner_id == response.student_id:
        return json.loads(artifact.content)
    return None


def capture_submission_cue(session, task, response):
    """Freeze detection at acceptance; practice queue routing waits for terminal feedback."""
    retained = retained_submission_cue(session, response)
    if retained:
        return retained
    work = (
        session.get(AssessmentWorkStart, response.assessment_work_start_id)
        if response.assessment_work_start_id
        else None
    )
    form = session.get(TaskFormVersion, work.task_form_version_id) if work else None
    approval = session.get(TaskApproval, work.task_approval_id) if work else None
    review = (
        session.get(TaskReviewEvent, approval.task_review_event_id)
        if approval
        else session.scalar(
            select(TaskReviewEvent)
            .join(TaskRevision, TaskRevision.id == TaskReviewEvent.task_revision_id)
            .where(
                TaskRevision.task_id == task.id,
                TaskReviewEvent.state == "APPROVED",
                TaskReviewEvent.created_at <= response.submitted_at,
            )
            .order_by(TaskReviewEvent.created_at.desc(), TaskReviewEvent.id.desc())
            .limit(1)
        )
    )
    revision = (
        session.get(TaskRevision, form.task_revision_id if form else review.task_revision_id)
        if form or review
        else None
    )
    snapshot = revision.snapshot if revision else {}
    references = list(work.source_references if work else snapshot.get("source_references", []))
    turns = recent_turns(
        session,
        student_id=response.student_id,
        task_id=task.id,
        at=response.submitted_at,
        work_id=work.id if work else None,
    )
    # Practice has no work ID: use its exact reviewed revision, not old task versions.
    turns = [
        turn
        for turn in turns
        if turn.context.get("task_revision_id") == (revision.id if revision else None)
    ]
    fields = _response_fields(response)
    if snapshot.get("task_type") in RECONSTRUCTION_TYPES:
        fields.pop("answer", None)
    matches = [
        match for field, value in fields.items() for match in _language_matches(value, field)
    ][:MATCH_LIMIT]
    sources = []
    for reference in references[:SOURCE_LIMIT]:
        passage = session.get(SourcePassage, reference)
        if passage and passage.course_id == task.course_id:
            sources.append(
                (
                    {
                        "kind": "SOURCE_PASSAGE",
                        "id": passage.id,
                        "revision_id": passage.revision_id,
                        "approval_id": (review.source_approvals or {}).get(passage.id)
                        if review
                        else None,
                    },
                    passage.chunk_text,
                )
            )
    sources.extend(
        (
            {
                "kind": "TUTOR_REPLY",
                "id": turn.id,
                "source_references": turn.context.get("source_references", []),
            },
            turn.reply,
        )
        for turn in turns
        if turn.kind == "hint"
    )
    exclusions = [
        snapshot.get(key) or "" for key in ("instructions", "description", "starter_code")
    ]
    # Recognition/reconstruction naturally reuses supplied labels; it is not a copy cue.
    if snapshot.get("task_type") not in RECONSTRUCTION_TYPES:
        for field, value in fields.items():
            for source, text in sources:
                if len(matches) >= MATCH_LIMIT:
                    break
                match = _overlap(value, text, exclusions + _transfer_exclusions(form, field))
                if match:
                    matches.append(
                        {
                            "signal": "SUBSTANTIAL_EXACT_REUSE",
                            "field": field,
                            "source": source,
                            **match,
                        }
                    )
    cue = _cue(
        matches,
        response_id=response.id,
        task_id=task.id,
        assessment_work_start_id=work.id if work else None,
        task_revision_id=revision.id if revision else None,
        task_review_event_id=review.id if review else None,
        source_references=references,
        inspected_turn_ids=[turn.id for turn in turns],
        inspected_fields={name: min(len(value), TEXT_LIMIT) for name, value in fields.items()},
        minimum_exact_reuse={"tokens": COPY_WORDS, "characters": COPY_CHARS},
    )
    if cue:
        content = json.dumps(cue, sort_keys=True, separators=(",", ":"))
        session.add(
            EvidenceArtifact(
                id=artifact_id(response.id),
                course_id=task.course_id,
                learner_id=response.student_id,
                content=content,
                content_digest="sha256:" + sha256(content.encode()).hexdigest(),
                content_format="application.json",
                schema_version=RULE_VERSION,
                record_version=1,
                actor_reference="integrity-review-cues",
                agent_reference=RULE_VERSION,
                correlation_id=response.id,
                occurred_at=response.submitted_at,
            )
        )
        session.flush()
        assessment = session.scalar(
            select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response.id)
        )
        if assessment:
            route_cue(
                session,
                cue=cue,
                source_kind="ASSESSMENT",
                source_id=assessment.id,
                key=f"integrity:response:{response.id}",
            )
    return cue


def route_terminal_submission_cue(session, feedback):
    if feedback.status not in {FeedbackStatus.ACCEPTED, FeedbackStatus.SAFE_FALLBACK}:
        return
    response = session.get(SubmissionAttempt, feedback.submission_id)
    if response is None or response.assessment_work_start_id:
        return
    cue = retained_submission_cue(session, response)
    if cue:
        route_cue(
            session,
            cue=cue,
            source_kind="FEEDBACK",
            source_id=feedback.id,
            key=f"integrity:response:{response.id}",
        )


def review_evidence(session, case, source):
    """Called only after the queue service has checked course-scoped staff access."""
    if case.trigger != "LEARNING_INTEGRITY_REVIEW":
        return None
    if case.source_kind == "TUTOR":
        cue = source.record.context.get("integrity_review_cue")
        response = None
        # Keep the original trigger and its context; include bounded later dialogue
        # so a deduplicated case can also show explanations and repeated occurrences.
        later = list(
            session.scalars(
                select(TutorTurn)
                .where(
                    TutorTurn.student_id == case.student_id,
                    TutorTurn.task_id == case.task_id,
                    TutorTurn.context_token == source.record.context_token,
                    TutorTurn.revision > source.record.revision,
                )
                .order_by(TutorTurn.revision.desc())
                .limit(HISTORY_LIMIT)
            )
        )
        turn_ids = [
            source.record.id,
            *(cue or {}).get("inspected_turn_ids", (cue or {}).get("related_turn_ids", [])),
            *(turn.id for turn in later),
        ]
    else:
        response_id = (
            source.record.response_version_id
            if case.source_kind == "ASSESSMENT"
            else source.record.submission_id
        )
        response = session.get(SubmissionAttempt, response_id)
        cue = retained_submission_cue(session, response) if response else None
        turn_ids = (cue or {}).get("inspected_turn_ids", [])
    if not cue:
        return None
    turns = list(
        session.scalars(
            select(TutorTurn)
            .where(
                TutorTurn.id.in_(turn_ids),
                TutorTurn.student_id == case.student_id,
                TutorTurn.task_id == case.task_id,
            )
            .order_by(TutorTurn.revision)
        )
    )
    source_ids = cue.get(
        "source_references",
        source.record.context.get("source_references", []) if case.source_kind == "TUTOR" else [],
    )
    passages = list(
        session.scalars(
            select(SourcePassage).where(
                SourcePassage.id.in_(source_ids[:SOURCE_LIMIT]),
                SourcePassage.course_id == case.course_id,
            )
        )
    )
    return {
        "integrity_review_cue": cue,
        "response": {
            "id": response.id,
            "fields": _response_fields(response),
            "declared_conditions": response.declared_conditions,
        }
        if response
        else None,
        "turns": [
            {
                "id": turn.id,
                "message": turn.learner_text,
                "reply": turn.reply,
                "context_token": turn.context_token,
                "context": turn.context,
            }
            for turn in turns
        ],
        "sources": [
            {"id": passage.id, "revision_id": passage.revision_id, "text": passage.chunk_text}
            for passage in passages
        ],
    }
