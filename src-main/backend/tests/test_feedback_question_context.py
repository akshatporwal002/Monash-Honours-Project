"""Retrieval keeps the authored question without using private or learner text."""

import asyncio

import pytest
from support.task16 import setup_task16_episode
from test_task14_lifecycle import complete
from test_task16_retrieval import source

from app.models import LearningTask, TaskType
from app.schemas.feedback import AssessmentContextStatus
from app.schemas.lms import SubmissionCreate
from app.services.assessment.feedback_context import SqlAlchemyAssessmentFeedbackContextProvider
from app.services.feedback.runtime import LmsSubmissionProvider
from app.services.rag.contracts import RetrievalResult
from app.services.rag.feedback_adapter import RagFeedbackRetrievalProvider
from app.services.task_context import to_feedback_task_context

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


class RecordingRetrieval:
    def __init__(self, session):
        self.session = session
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return RetrievalResult("query", False, (), None, 0, "test-query-recorder")


def test_assessed_query_keeps_supported_question_and_excludes_private_transfer(db_session):
    lms, student, task, started = setup_task16_episode(db_session)
    payload = complete(lms, student, task, started)
    response = lms.submit(
        student,
        task.id,
        SubmissionCreate(**payload.model_dump(), idempotency_key="question-context-privacy"),
    )
    submission = asyncio.run(LmsSubmissionProvider(db_session).get_submission(response.id))
    resolved = asyncio.run(
        SqlAlchemyAssessmentFeedbackContextProvider(db_session).resolve(submission)
    )
    assert resolved.status is AssessmentContextStatus.RESOLVED
    frozen_task = resolved.context.task
    assert frozen_task.prompt == task.description + "\n\n" + task.instructions

    retrieval = RecordingRetrieval(db_session)
    asyncio.run(
        RagFeedbackRetrievalProvider(retrieval).get_retrieval_context(
            frozen_task,
            submission.model_copy(update={"submitted_answer": "LEARNER_PRIVATE_QUERY"}),
        )
    )
    query = retrieval.queries[0]
    assert task.description in query.text and task.instructions in query.text
    assert query.allowed_chunk_ids == tuple(task.source_references)
    assert query.min_relevance == 0.45
    assert "SYNTHETIC PRIVATE" not in query.text
    assert "NEVER REVEAL" not in query.text
    assert "LEARNER_PRIVATE_QUERY" not in query.text


def test_practice_query_keeps_question_without_solution_or_private_episode(db_session):
    _, _, passage = source(db_session, "practice", "Hadamard creates superposition")
    task = LearningTask(
        id="practice-task",
        course_id="course",
        learning_outcome_id="outcome",
        task_type=TaskType.SHORT_ANSWER,
        difficulty="beginner",
        description="What does Hadamard do to a zero input?",
        instructions="Explain your reasoning.",
        source_references=[passage.id],
        expected_answer="PRIVATE_MODEL_ANSWER",
        marking_criteria={
            "required_terms": ["superposition"],
            "episode_plan": {"transfer": {"prompt": "PRIVATE_TRANSFER_PROMPT"}},
        },
    )
    retrieval = RecordingRetrieval(db_session)
    RagFeedbackRetrievalProvider(retrieval)._retrieve(to_feedback_task_context(task))
    query = retrieval.queries[0]
    assert task.description in query.text and task.instructions in query.text
    assert "PRIVATE_MODEL_ANSWER" not in query.text
    assert "PRIVATE_TRANSFER_PROMPT" not in query.text
    assert query.allowed_chunk_ids == (passage.id,)
