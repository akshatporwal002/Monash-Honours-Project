"""Teaching support reaches the real formal review boundary and practice observations."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from support.task_review import approve_sourced_fixture_task
from test_misconceptions import answer, context
from test_task15_human_review import request_for

from app.domain.assessment import BloomProcess
from app.domain.platform_enums import EvidenceType
from app.models.assessment import AssessmentAttempt, AssessmentDecision, CriterionVersion
from app.models.enums import FeedbackStatus
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.persistence import FeedbackRecord, LearningTask, StudentProfile, WorkflowRun
from app.schemas.feedback import SubmissionContext
from app.schemas.lms import SubmissionCreate
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.evaluation import CriterionEvaluationUnavailableError
from app.services.assessment.feedback_context import SqlAlchemyAssessmentFeedbackContextProvider
from app.services.assessment.frozen_review import FrozenReviewEvidenceReader
from app.services.assessment.human_review import HumanAssessmentService
from app.services.assessment.review import AssessmentReviewConflictError
from app.services.assessment.runtime import SqlAlchemyRuleCriterionEvaluationPort
from app.services.episode_responses import SqlAlchemyFrozenResponseReader
from app.services.lms import LmsService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


def test_direct_answer_is_visible_to_assessor_and_cannot_finalise_a_later_response(db_session):
    fixture, _, educator, _, student, service, _, saved = context(db_session, support_level=5)
    original = db_session.get(SubmissionAttempt, fixture["response_id"])
    old_decision = db_session.get(AssessmentDecision, fixture["decision_id"])
    old_result = (old_decision.result, old_decision.result_state)
    reader = SqlAlchemyFrozenResponseReader(db_session)
    frozen = FrozenReviewEvidenceReader(db_session, reader)
    original_attempt = db_session.get(AssessmentAttempt, fixture["attempt_id"])
    before = reader.read(assessment=frozen.reference(original_attempt)).model_dump_json()
    answer(service, student, saved)
    later = LmsService(db_session).submit(
        student,
        saved.task_id,
        SubmissionCreate(
            answer=original.answer,
            assessment_work_start_id=original.assessment_work_start_id,
            idempotency_key="revised-after-direct-answer",
        ),
    )
    attempt = db_session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == later.id)
    )
    human = HumanAssessmentService(
        db_session, assignments=RoleAssignmentService(db_session), reader=reader
    )
    detail = human.detail(educator, assessment_attempt_id=attempt.id)
    assert not detail["can_finalise"] and "fresh approved task" in " ".join(detail["issues"])
    assert detail["response"].recorded_teaching[0].instructional_support_level == 5
    assert detail["response"].recorded_teaching[0].explanation == saved.explanation
    criterion = db_session.get(CriterionVersion, detail["criteria"][0]["criterion_version_id"])
    with pytest.raises(AssessmentReviewConflictError, match="fresh approved task"):
        human.finalise(
            educator,
            assessment_attempt_id=attempt.id,
            request=request_for(human, educator, attempt, later, criterion),
        )
    with pytest.raises(CriterionEvaluationUnavailableError, match="instructional help"):
        SqlAlchemyRuleCriterionEvaluationPort(db_session).evaluate(
            assessment=frozen.reference(attempt),
            response_text=later.answer,
            bloom_process=BloomProcess.UNDERSTAND,
            criterion=criterion,
        )
    response = db_session.get(SubmissionAttempt, later.id)
    resolved = asyncio.run(
        SqlAlchemyAssessmentFeedbackContextProvider(db_session).resolve(
            SubmissionContext(
                submission_id=response.id,
                task_id=response.task_id,
                course_id=saved.course_id,
                student_id=str(student.id),
                attempt_number=response.attempt_number,
                submitted_answer=response.answer,
                submitted_at=response.submitted_at,
            )
        )
    )
    assert resolved.context.frozen_response.recorded_teaching[0].instructional_support_level == 5
    assert reader.read(assessment=frozen.reference(original_attempt)).model_dump_json() == before
    assert (old_decision.result, old_decision.result_state) == old_result
    assert (
        db_session.scalar(
            select(AssessmentDecision).where(AssessmentDecision.assessment_attempt_id == attempt.id)
        )
        is None
    )


def test_practice_revision_retains_help_and_excludes_other_learners_and_earlier_responses(
    db_session,
):
    _, _, educator, _, student, service, opened, saved = context(db_session)
    db_session.add(StudentProfile(user_id=student.id, display_name=student.full_name))
    original_task = db_session.get(LearningTask, saved.task_id)
    practice = LearningTask(
        id=str(uuid4()),
        title="Practice the evidence relationship",
        slug=f"practice-{uuid4().hex}",
        module=original_task.module,
        description=original_task.description,
        instructions=original_task.instructions,
        expected_answer=original_task.expected_answer,
        task_type=original_task.task_type,
        difficulty=original_task.difficulty,
        points=0,
        course_id=saved.course_id,
        module_id=original_task.module_id,
        learning_outcome_id=saved.outcome_id,
        position=original_task.position + 1,
        source_references=list(original_task.source_references),
    )
    db_session.add(practice)
    db_session.commit()
    approve_sourced_fixture_task(db_session, practice)
    lms = LmsService(db_session)
    first = lms.submit(
        student,
        practice.id,
        SubmissionCreate(answer="Initial practice explanation", idempotency_key="practice-one"),
    )
    assert first.assessment_work_start_id is None
    initial = db_session.scalar(
        select(LearningEvidence).where(
            LearningEvidence.response_version_id == first.id,
            LearningEvidence.evidence_type == EvidenceType.RESPONSE,
        )
    )
    workflow = db_session.scalar(select(WorkflowRun).where(WorkflowRun.submission_id == first.id))
    feedback = FeedbackRecord(
        id=str(uuid4()),
        submission_id=first.id,
        workflow_run_id=workflow.id,
        status=FeedbackStatus.ACCEPTED,
        generation_attempt=1,
        provider="synthetic",
        model="synthetic",
        prompt_version="misconception-test.v1",
        feedback_content={"explanation": "Review your observation."},
    )
    db_session.add(feedback)
    db_session.commit()
    check = service.open(
        educator,
        opened.model_copy(
            update={
                "request_key": "practice-check",
                "feedback_id": feedback.id,
                "evidence_ids": [initial.id],
                "fresh_question": "Consider another independent practice observation.",
                "explanation_support_level": 5,
            }
        ),
    )
    answer(service, student, check)
    later = lms.submit(
        student,
        practice.id,
        SubmissionCreate(answer="Revised practice explanation", idempotency_key="practice-two"),
    )
    evidence = db_session.scalar(
        select(LearningEvidence).where(
            LearningEvidence.response_version_id == later.id,
            LearningEvidence.evidence_type == EvidenceType.RESPONSE,
        )
    )
    assert evidence.instructional_support_level == 5
    assert initial.instructional_support_level == 0
    from app.services.evidence.live import LiveEvidenceCapture

    level, _, parents = LiveEvidenceCapture(db_session)._support_for(
        None, later.submitted_at, task_id=practice.id, student_id=educator.id
    )
    assert level == 0 and parents == ()
