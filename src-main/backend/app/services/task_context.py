from app.models import LearningTask
from app.schemas.feedback import TaskContext


def to_feedback_task_context(task: LearningTask) -> TaskContext:
    """Convert a fully-grounded generated task into the feedback contract."""
    if not task.course_id or not task.learning_outcome_id:
        raise ValueError("task requires course_id and learning_outcome_id for feedback")
    if not task.source_references or any(not isinstance(reference, str) or not reference.strip() for reference in task.source_references):
        raise ValueError("task requires non-empty source references for feedback")
    if task.expected_answer is None and task.marking_criteria is None:
        raise ValueError("task requires expected_answer or marking_criteria for feedback")

    return TaskContext(
        task_id=task.id,
        course_id=task.course_id,
        task_type=task.task_type.value,
        prompt=task.instructions,
        difficulty=task.difficulty,
        expected_answer=task.expected_answer,
        marking_criteria=task.marking_criteria,
        learning_outcome_id=task.learning_outcome_id,
        source_references=task.source_references,
    )
