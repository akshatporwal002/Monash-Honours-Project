import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import LearningMaterial, MaterialIndexStatus
from app.models.source_history import SourceApproval, SourcePassage, SourceRevision
from app.schemas.feedback import SubmissionContext, TaskContext
from app.services.rag.feedback_adapter import (
    FEEDBACK_RETRIEVAL_VERSION,
    RagFeedbackRetrievalProvider,
)
from app.services.rag.local_retrieval import LocalCourseRetrievalService
from app.services.rag.source_history import latest_approval


def source(
    session: Session,
    name: str,
    text: str,
    *,
    course: str = "course",
    approved=True,
    passage_hash="passage-hash",
):
    material = LearningMaterial(
        id=name,
        course_id=course,
        original_filename="notes.pdf",
        mime_type="application/pdf",
        content_hash=name + "-source-hash",
        indexing_status=MaterialIndexStatus.INDEXED,
    )
    session.add(material)
    session.flush()
    revision = SourceRevision(
        id=name + "-revision",
        material_id=name,
        course_id=course,
        version=1,
        source_label="Notes",
        mime_type="application/pdf",
        content_hash=name + "-source-hash",
        extracted_blocks=[],
        extraction_version="test-v1",
        provenance="EXTRACTED",
    )
    session.add(revision)
    session.flush()
    passage = SourcePassage(
        id=name + "-passage",
        revision_id=revision.id,
        course_id=course,
        chunk_index=0,
        chunk_text=text,
        chunk_hash=passage_hash,
    )
    session.add(passage)
    if approved:
        session.add(
            SourceApproval(
                revision_id=revision.id,
                sequence=1,
                state="APPROVED",
                actor_id="reviewer",
                reason="Checked the source",
            )
        )
    session.commit()
    return material, revision, passage


def retrieve(session: Session, references: list[str], *, assessed=True, answer="Hadamard"):
    task = TaskContext(
        task_id="task",
        course_id="course",
        task_type="quiz",
        prompt="Explain Hadamard superposition",
        difficulty="beginner",
        marking_criteria="Hadamard superposition",
        learning_outcome_id="outcome",
        source_references=references,
        assessed=assessed,
        source_approvals={
            reference: approval.id
            for reference in references
            if (passage := session.get(SourcePassage, reference))
            and (approval := latest_approval(session, passage.revision_id))
        },
    )
    submission = SubmissionContext(
        submission_id="response",
        task_id="task",
        course_id="course",
        student_id="learner",
        attempt_number=1,
        submitted_answer=answer,
        submitted_at=datetime.now(UTC),
    )
    return asyncio.run(
        RagFeedbackRetrievalProvider(LocalCourseRetrievalService(session)).get_retrieval_context(
            task, submission
        )
    )


def test_task16_retrieval_requires_approved_available_relevant_exact_sources(db_session):
    _, revision, good = source(db_session, "good", "Hadamard creates superposition")
    _, _, unrelated = source(db_session, "unrelated", "Photosynthesis converts sunlight")
    _, _, foreign = source(db_session, "foreign", "Hadamard creates superposition", course="other")
    _, _, unapproved = source(
        db_session, "unapproved", "Hadamard creates superposition", approved=False
    )
    retired, _, retired_passage = source(db_session, "retired", "Hadamard creates superposition")
    retired.retired_at = datetime.now(UTC)
    db_session.commit()
    hits = retrieve(
        db_session,
        [good.id, unrelated.id, foreign.id, unapproved.id, retired_passage.id],
        answer="Photosynthesis converts sunlight",
    )
    assert [hit.source_id for hit in hits] == [good.id]
    assert hits[0].source_revision_id == revision.id
    assert hits[0].source_digest == "good-source-hash"
    assert hits[0].passage_digest == "passage-hash"
    assert hits[0].approval_id
    assert hits[0].retrieval_version == FEEDBACK_RETRIEVAL_VERSION


def test_task16_empty_or_material_alias_never_expands_to_course_sources(db_session):
    material, _, _ = source(db_session, "good", "Hadamard creates superposition")
    assert retrieve(db_session, []) == []
    assert retrieve(db_session, [material.id]) == []
    assert retrieve(db_session, ["missing-passage"]) == []


def test_task16_revoked_source_is_not_reused_but_existing_passage_survives(db_session):
    _, revision, passage = source(db_session, "good", "Hadamard creates superposition")
    assert len(retrieve(db_session, [passage.id])) == 1
    db_session.add(
        SourceApproval(
            revision_id=revision.id,
            sequence=2,
            state="REVOKED",
            actor_id="reviewer",
            reason="Correction",
        )
    )
    db_session.commit()
    assert retrieve(db_session, [passage.id]) == []
    assert db_session.get(SourcePassage, passage.id).chunk_text == "Hadamard creates superposition"


def test_task16_legacy_practice_keeps_unapproved_preserved_evidence(db_session):
    _, _, passage = source(db_session, "legacy", "Hadamard creates superposition", approved=False)
    assert len(retrieve(db_session, [passage.id], assessed=False)) == 1
    assert retrieve(db_session, [passage.id]) == []


def test_task16_retrieval_rejects_foreign_submission_scope(db_session):
    task = TaskContext(
        task_id="task",
        course_id="course",
        task_type="quiz",
        prompt="Hadamard",
        difficulty="beginner",
        expected_answer="superposition",
        learning_outcome_id="outcome",
    )
    submission = SubmissionContext(
        submission_id="response",
        task_id="other",
        course_id="course",
        student_id="learner",
        attempt_number=1,
        submitted_answer="Hadamard",
        submitted_at=datetime.now(UTC),
    )
    with pytest.raises(ValueError, match="scope mismatch"):
        asyncio.run(
            RagFeedbackRetrievalProvider(
                LocalCourseRetrievalService(db_session)
            ).get_retrieval_context(task, submission)
        )


def test_task16_legacy_practice_missing_digest_is_explicitly_absent(db_session):
    _, _, passage = source(db_session, "old", "Hadamard creates superposition", passage_hash="")
    hits = retrieve(db_session, [passage.id], assessed=False)
    assert len(hits) == 1
    assert hits[0].passage_digest is None
