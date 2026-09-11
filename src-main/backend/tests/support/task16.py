"""Ordinary approved Task 16 fixtures with relevant synthetic teaching sources."""

from dataclasses import replace

from sqlalchemy import select
from test_assessment_definitions import _draft, _service, _setup

from app.domain.assessment import BloomProcess
from app.models.assessment import TaskFormVersion
from app.models.enums import MaterialIndexStatus, TaskType
from app.models.lms import Course, CourseState, Enrollment
from app.models.persistence import LearningMaterial, LearningTask
from app.models.source_history import SourcePassage, SourceRevision
from app.models.user import UserRole
from app.schemas.episode import EpisodePlanV1
from app.services.lms import LmsService
from support.alignment import next_action_contract
from support.task_review import (
    approve_fixture_task,
    approve_sourced_fixture_task,
    bootstrap_reviewed_demo,
)


def setup_task16_episode(session, task_type=TaskType.QUANTUM_CIRCUIT):
    course_id, outcome_id, owner_id, outcome_version_id = _setup(session)
    task = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
    task.description = "A Hadamard circuit has equal outcome probabilities from a zero input."
    task.instructions = "Explain the Hadamard circuit outcome and apply it in a fresh context."
    approve_sourced_fixture_task(session, task)
    # The synthetic archive contains its complete extracted passage. Declare its
    # index available before ordinary task and formal publication review.
    for passage_id in task.source_references:
        passage = session.get(SourcePassage, passage_id)
        revision = session.get(SourceRevision, passage.revision_id)
        material = session.get(LearningMaterial, revision.material_id)
        material.indexing_status = MaterialIndexStatus.INDEXED
    session.commit()
    plan = EpisodePlanV1(
        transfer={
            "prompt": "SYNTHETIC PRIVATE fresh Hadamard application",
            "starter_circuit": {"qubits": 1, "operations": []},
            "solution": {"answer": "NEVER REVEAL solution"},
        },
        supported_hints=("Consider how H changes the input state.",),
        accessibility_support=("Text circuit and keyboard controls",),
    )
    task.task_type = task_type
    task.marking_criteria = {
        "required_gates": ["h"],
        "starter_circuit": {"qubits": 1, "operations": []},
        "episode_plan": plan.model_dump(mode="json"),
    }
    session.commit()
    approve_fixture_task(session, task)
    draft = replace(
        _draft(outcome_version_id=outcome_version_id, task_id=task.id, task_processes=["APPLY"]),
        formal_result_eligible=True,
        bloom_process=BloomProcess.APPLY,
        claim="Apply a Hadamard circuit through prediction, explanation, and fresh application.",
    )
    criteria = [
        replace(
            draft.criteria[0],
            stable_key=key,
            learner_description=description,
            evidence_description=description,
        )
        for key, description in (
            ("prediction", "Predict the circuit outcome."),
            ("explanation", "Explain the circuit outcome."),
            ("application", "Apply the circuit in a fresh context."),
        )
    ]
    draft = replace(
        draft,
        criteria=criteria,
        next_action_contract=next_action_contract(*(c.stable_key for c in criteria)),
        pass_rule_expression={
            "operator": "ALL_OF",
            "clauses": [{"criterion": criterion.stable_key} for criterion in criteria],
        },
        instructional_support={"supported_stage": "unlimited approved conceptual hints"},
        transfer_rule={"required": True, "independence": "unaided fresh application"},
    )
    service = _service(session)
    definition = service.create_draft(
        course_id=course_id, learning_outcome_id=outcome_id, actor_user_id=owner_id, draft=draft
    )
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    assert form.constraints["episode_plan"] == plan.model_dump(mode="json")
    service.approve(
        course_id=course_id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=owner_id,
        approval_reason="Synthetic episode approved for this test",
    )
    users, _ = bootstrap_reviewed_demo(session)
    student = next(u for u in users if u.role is UserRole.STUDENT)
    session.get(Course, course_id).state = CourseState.PUBLISHED
    session.add(Enrollment(course_id=course_id, student_id=student.id))
    session.commit()
    lms = LmsService(session)
    started = lms.start_assessment_work(student, task.id, form.id)
    return lms, student, task, started
