"""Draft teaching content for D-11; composes existing contracts without activation.

Examples are original demonstration content, not approved teaching sources.
No learner code is executed and no source, task or assessment is approved here.
"""

from app.models import TaskType
from app.models.lms import OutcomeKind
from app.schemas.curriculum import PathwayPublish
from app.schemas.episode import EpisodePlanV1
from app.schemas.lms import CourseCreate, ModuleCreate, OutcomeCreate, TaskCreate
from app.services.assessment.definitions import CriterionDraft

VERSION = "conditional-programming.v1"
BUGGY_CODE = (
    'temperature = 20\nif temperature > 20:\n    label = "warm"\nelse:\n    label = "cool"\n'
)
TRANSFER_CODE = "items = 3\nif items >= 3:\n    fee = 0\nelse:\n    fee = 5\n"


def course_draft() -> CourseCreate:
    return CourseCreate(
        title="Conditional programming reuse demonstration",
        description="Draft D-11 exercise: trace, correct and transfer simple conditionals.",
        enrollment_open=False,
    )


def module_draft() -> ModuleCreate:
    return ModuleCreate(title="Trace and correct conditionals", position=1)


def outcome_draft() -> OutcomeCreate:
    return OutcomeCreate(
        title="Reason about conditional boundaries",
        statement="Trace a conditional, correct its boundary and explain a fresh application.",
        kind=OutcomeKind.TOPIC,
        position=1,
    )


def episode_plan() -> EpisodePlanV1:
    return EpisodePlanV1(
        required_responses=("prediction", "reasoning", "explanation", "reflection"),
        supported_hints=("Compare the equality case with the stated requirement.",),
        accessibility_support=("Read and edit the program as plain text with a keyboard.",),
        transfer={
            "part_id": "delivery-fee",
            "prompt": (
                "Fresh example: delivery is free for at least three items. Trace the supplied "
                "program for 2, 3 and 4 items. Explain whether its boundary is correct."
            ),
            "starter_code": TRANSFER_CODE,
            "solution": {"answer": "2 items: 5; 3 items: 0; 4 items: 0. >= includes equality."},
        },
    )


def task_drafts(*, module_id: str, outcome_id: str) -> tuple[TaskCreate, ...]:
    """Return API-ready drafts for IDs from the normal course-authoring workflow.

    Source references deliberately remain empty until an educator supplies approved
    course-scoped passages through the existing review workflow.
    """
    common = dict(
        module_id=module_id,
        learning_outcome_id=outcome_id,
        difficulty="beginner",
        points=0,
        starter_code=BUGGY_CODE,
    )
    return (
        TaskCreate(
            **common,
            title="Trace the equality case",
            prompt=(
                "A program sets temperature = 20. If temperature > 20 it assigns label = 'warm'; "
                "otherwise it assigns label = 'cool'. Which label does it assign?"
            ),
            instructions="Trace the supplied program without changing it. Choose one answer.",
            task_type=TaskType.MULTIPLE_CHOICE,
            position=1,
            expected_answer="cool",
            marking_criteria={
                "choices": [
                    {"id": "cool", "text": "cool"},
                    {"id": "warm", "text": "warm"},
                ]
            },
        ),
        TaskCreate(
            **common,
            title="Choose the boundary correction",
            prompt=(
                "The program assigns 'warm' when its condition is true and 'cool' otherwise. "
                "The requirement is warm at 20 or above. Which condition satisfies it?"
            ),
            instructions="Check 19, 20 and 21 before choosing a replacement condition.",
            task_type=TaskType.MULTIPLE_CHOICE,
            position=2,
            expected_answer="inclusive",
            marking_criteria={
                "choices": [
                    {"id": "strict", "text": "temperature > 20"},
                    {"id": "inclusive", "text": "temperature >= 20"},
                    {"id": "equal", "text": "temperature == 20"},
                ]
            },
        ),
        TaskCreate(
            **common,
            title="Explain, revise and transfer",
            prompt=(
                "The original program assigns 'warm' if temperature > 20 and 'cool' otherwise. "
                "Warm should mean 20 or above. Predict the original output at 20, supply the corrected "
                "program, and explain its outputs at 19, 20 and 21. Reflect on the boundary error."
            ),
            instructions=(
                "Write the corrected Python program in Your response. "
                "Record your prediction and reasoning, then explain the corrected code. "
                "Use the supported hint if needed. Complete the fresh example without hints. "
                "If revising an earlier submission, link it and explain the change. "
                "Code is retained as text for human review; it is not executed."
            ),
            task_type=TaskType.EXPLANATION,
            position=3,
            marking_criteria={
                "response_review": "human",
                "episode_plan": episode_plan().model_dump(mode="json"),
            },
        ),
    )


def criterion_drafts() -> list[CriterionDraft]:
    """Proposed human-review criteria, never an approval or an automatic code grade."""
    return [
        CriterionDraft(
            stable_key=key,
            learner_description=description,
            evidence_description=description,
            mandatory=True,
            evidence_source_types=["learner_response"],
            met_rule=met,
            not_met_rule=not_met,
            not_evaluable_rule="Required response or its work conditions cannot be verified.",
            approved_anchors={},
            critical_error_rules={},
        )
        for key, description, met, not_met in (
            (
                "trace",
                "Trace the original boundary case.",
                "Predicts cool at 20 and explains that > excludes equality.",
                "Predicts warm or treats > as including equality.",
            ),
            (
                "correction",
                "Correct and explain the conditional.",
                "Supplies a valid correction yielding cool, warm, warm at 19, 20, 21 and explains why.",
                "Correction fails one of the boundary cases or lacks an explanation.",
            ),
            (
                "transfer",
                "Apply the rule in the fresh delivery example without hints.",
                "Gives fees 5, 0, 0 for 2, 3, 4 items and explains the inclusive boundary unaided.",
                "Gives an incorrect fee or boundary explanation.",
            ),
        )
    ]


def pathway_draft(
    *, task_ids: tuple[str, str, str], expected_version: int, request_key: str, reason: str
) -> PathwayPublish:
    """Compose the shared curriculum command; only an educator may publish it.

    Call after all tasks and the assessment definition have actual approval, so
    the shared service freezes those versions. This factory grants no approval.
    """
    return PathwayPublish(
        expected_version=expected_version,
        request_key=request_key,
        title="Trace, correct and apply conditional boundaries",
        steps=[
            dict(
                task_id=task_id,
                concept="Conditional boundaries",
                prerequisites=list(task_ids[index - 1 : index]) if index else [],
                support_level="guided",
                faded_support_level="concept_cue",
                evidence_rule="An accepted response permits continuation; formal criteria require assessor review.",
            )
            for index, task_id in enumerate(task_ids)
        ],
        diagnostic_prompt="Trace the equality case and explain which branch runs.",
        diagnostic_task_id=task_ids[0],
        independent_conditions="Respond without instructional hints. Approved accessibility support remains available.",
        reason=reason,
    )
