"""Isolated, synthetic teaching approvals for the complete-loop regression.

No responses, feedback, learner snapshots or assessment decisions are prebuilt.
"""

from dataclasses import replace
from uuid import uuid4

from sqlalchemy import select
from test_assessment_definitions import _draft

from app.core.security import hash_password
from app.domain.assessment import BloomProcess
from app.models.assessment import CriterionEvaluatorType, TaskFormVersion
from app.models.enums import MaterialIndexStatus, TaskType
from app.models.lms import Course, CourseState, LearningOutcome
from app.models.persistence import LearningMaterial, LearningTask, StudentProfile
from app.models.source_history import SourcePassage, SourceRevision
from app.models.user import User, UserRole
from app.schemas.curriculum import PathwayPublish
from app.schemas.episode import EpisodePlanV1
from app.services.assessment.definitions import AssessmentDefinitionService
from app.services.curriculum import CurriculumService
from app.services.lms import LmsService
from support.alignment import next_action_contract
from support.assessment_authoring import seed_authoring_context
from support.task_review import approve_sourced_fixture_task

LESSON = (
    "A Hadamard gate acting on the zero state creates equal probabilities for zero and one. "
    "Sampled counts can differ from exact probabilities."
)
SOURCE = (
    LESSON + " Applying two Hadamard gates consecutively restores their input state. "
    "A Pauli-X gate exchanges the zero and one states."
)


def seed_learning_loop(session):
    fixture = seed_authoring_context(session)
    teacher = session.scalar(select(User).where(User.email == fixture["educator_email"]))
    task = session.get(LearningTask, fixture["task_id"])
    outcome = session.get(LearningOutcome, fixture["outcome_id"])
    course = session.get(Course, fixture["course_id"])
    course.title = "Quantum learning loop"
    outcome.title = "Apply and explain Hadamard gates"
    outcome.statement = "Predict, construct and explain single-qubit Hadamard circuits."
    task.title = "Predict and explain a Hadamard circuit"
    task.task_type = TaskType.QUANTUM_CIRCUIT
    task.description = LESSON
    task.instructions = "Predict first, run H on a zero input, then explain the result."
    task.expected_answer = "H creates equal measurement probabilities from the zero input."
    task.marking_criteria = {
        "required_gates": ["h"],
        "starter_circuit": {"qubits": 1, "operations": []},
        "episode_plan": EpisodePlanV1(
            required_responses=("prediction", "reasoning", "explanation", "reflection"),
            supported_hints=("Connect the input state to the gate and the measurement basis.",),
            accessibility_support=("Use the circuit text description and keyboard controls.",),
            transfer={
                "prompt": "Fresh application: start at zero, apply X followed by two Hadamard gates, and predict the result.",
                "starter_circuit": {"qubits": 1, "operations": []},
                "solution": {
                    "answer": "PRIVATE: The final state is one with probability one. X prepares one and the two H gates restore that input."
                },
            },
        ).model_dump(mode="json"),
    }
    session.commit()
    tasks = [task]
    for position, title in enumerate(("Explain an X then H circuit", "Reflect on measurement"), 2):
        followup = LearningTask(
            slug=f"learning-loop-{uuid4().hex}",
            title=title,
            module=task.module,
            description=LESSON,
            instructions="Explain your reasoning using the approved source.",
            expected_answer="Hadamard measurement probabilities depend on the input state.",
            task_type=TaskType.EXPLANATION,
            difficulty="beginner",
            points=0,
            position=position,
            course_id=task.course_id,
            module_id=task.module_id,
            learning_outcome_id=task.learning_outcome_id,
        )
        session.add(followup)
        session.commit()
        tasks.append(followup)
    for item in tasks:
        approve_sourced_fixture_task(session, item, source_text=SOURCE)
        for passage_id in item.source_references:
            passage = session.get(SourcePassage, passage_id)
            revision = session.get(SourceRevision, passage.revision_id)
            session.get(
                LearningMaterial, revision.material_id
            ).indexing_status = MaterialIndexStatus.INDEXED
    session.commit()
    lms = LmsService(session)
    source = lms.create_assessment_outcome_version(teacher, course.id, outcome.id)
    draft = _draft(outcome_version_id=source.id, task_id=task.id, task_processes=["APPLY"])
    criteria = [
        replace(
            draft.criteria[0],
            stable_key=key,
            learner_description=description,
            evidence_description=description,
            evaluator_type=CriterionEvaluatorType.HUMAN,
            approved_anchors={},
            met_rule=description,
            not_met_rule="The saved response does not demonstrate this criterion.",
            not_evaluable_rule="The frozen response is unavailable or the task is faulty.",
            critical_error_rules={},
        )
        for key, description in (
            ("prediction", "Predict the single-H circuit before viewing simulation results."),
            (
                "explanation",
                "Explain the single-H result using the saved circuit and probabilities.",
            ),
            (
                "transfer",
                "Independently predict and explain the fresh circuit using saved evidence.",
            ),
        )
    ]
    service = AssessmentDefinitionService(session)
    definition = service.create_draft(
        course_id=course.id,
        learning_outcome_id=outcome.id,
        actor_user_id=teacher.id,
        draft=replace(
            draft,
            claim=outcome.statement,
            bloom_process=BloomProcess.APPLY,
            formal_result_eligible=True,
            criteria=criteria,
            next_action_contract=next_action_contract(*(c.stable_key for c in criteria)),
            pass_rule_expression={
                "operator": "ALL_OF",
                "clauses": [{"criterion": c.stable_key} for c in criteria],
            },
            permitted_tools={"allowed": ["QISKIT_SIMULATOR"]},
            instructional_support={"supported_stage": "unlimited approved conceptual hints"},
            transfer_rule={"required": True, "independence": "unaided fresh application"},
        ),
    )
    service.approve(
        course_id=course.id,
        assessment_definition_id=definition.assessment_definition_id,
        expected_version=1,
        actor_user_id=teacher.id,
        approval_reason="Synthetic course for local integration tests; no live content approval.",
    )
    form = session.scalar(
        select(TaskFormVersion).where(
            TaskFormVersion.assessment_definition_version_id == definition.id
        )
    )
    path = CurriculumService(session).publish(
        teacher,
        outcome.id,
        PathwayPublish(
            expected_version=0,
            request_key="learning-loop-pathway",
            title="Hadamard circuit practice",
            steps=[
                dict(
                    task_id=t.id,
                    concept="Hadamard",
                    prerequisites=[],
                    support_level="guided",
                    faded_support_level="independent",
                    evidence_rule="An accepted response records participation, not a formal result.",
                )
                for t in tasks
            ],
            diagnostic_prompt="Explain what H does to zero before considering the circuit activities.",
            diagnostic_task_id=tasks[1].id,
            independent_conditions="No instructional help; approved access support remains available.",
            reason="Synthetic pathway review for the integration test.",
        ),
    )
    student = User(
        email=f"loop-student-{uuid4().hex}@example.edu",
        full_name="Learning loop test learner",
        password_hash=hash_password("learning-loop-student-password"),
        role=UserRole.STUDENT,
    )
    session.add(student)
    session.flush()
    session.add(StudentProfile(user_id=student.id, display_name=student.full_name))
    session.commit()
    lms.set_course_state(teacher, course.id, CourseState.PUBLISHED)
    lms.enroll_student(teacher, course.id, student.id)
    return {
        **fixture,
        "student_email": student.email,
        "student_password": "learning-loop-student-password",
        "student_id": student.id,
        "teacher_id": teacher.id,
        "form_id": form.id,
        "next_task_id": tasks[1].id,
        "pathway_id": path.id,
    }
