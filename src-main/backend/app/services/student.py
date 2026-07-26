from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Achievement,
    LearningTask,
    NotificationKind,
    StudentAchievement,
    StudentNotification,
    StudentProfile,
    StudentSubmission,
    SubmissionStatus,
    TaskType,
)
from app.schemas.student import ProgressRead, RecommendationRead, SimulationRequest
from app.services.quantum import CircuitOperation, simulate_circuit

DEMO_STUDENT_ID = "00000000-0000-4000-8000-000000000003"

TASKS = (
    (
        "qubit-basics",
        "Qubits & superposition",
        "Foundations",
        TaskType.QUIZ,
        "Beginner",
        100,
        "Explain what makes a qubit different from a classical bit.",
        "In two or three sentences, describe superposition and what happens during measurement.",
        None,
        "superposition",
    ),
    (
        "first-circuit",
        "Build your first circuit",
        "Quantum circuits",
        TaskType.CIRCUIT,
        "Beginner",
        150,
        "Create and run a circuit that puts one qubit into superposition.",
        "Add a Hadamard gate, run 1,024 shots, then submit the circuit.",
        None,
        None,
    ),
    (
        "bell-state",
        "Entangle a Bell pair",
        "Quantum circuits",
        TaskType.CODE,
        "Intermediate",
        250,
        "Use Qiskit-style code to create a Bell state.",
        "Complete the circuit with an H gate and CX gate, simulate it, then submit your code.",
        "from qiskit import QuantumCircuit\n\nqc = QuantumCircuit(2, 2)\n# Add gates here\nqc.measure([0, 1], [0, 1])",
        "qc.h",
    ),
    (
        "measurement",
        "Measurement challenge",
        "Measurement",
        TaskType.QUIZ,
        "Intermediate",
        200,
        "Predict measurement outcomes for common quantum states.",
        "Explain why repeated measurements produce a distribution rather than a fixed value.",
        None,
        "probability",
    ),
)

ACHIEVEMENTS = (
    ("first-step", "First Step", "Complete your first learning activity.", "✦"),
    ("circuit-maker", "Circuit Maker", "Complete a quantum circuit activity.", "⌁"),
    ("perfect-score", "Quantum Ace", "Earn a perfect task score.", "★"),
)


def seed_demo_data(db: Session) -> StudentProfile:
    student = db.get(StudentProfile, DEMO_STUDENT_ID)
    if student is None:
        student = StudentProfile(id=DEMO_STUDENT_ID, display_name="Alex Morgan", streak_days=3)
        db.add(student)
    existing_slugs = set(db.scalars(select(LearningTask.slug)).all())
    due = datetime.now(timezone.utc) + timedelta(days=4)
    for position, task in enumerate(TASKS, start=1):
        (
            slug,
            title,
            module,
            kind,
            difficulty,
            points,
            description,
            instructions,
            starter,
            expected,
        ) = task
        if slug not in existing_slugs:
            db.add(
                LearningTask(
                    slug=slug,
                    title=title,
                    module=module,
                    task_type=kind,
                    difficulty=difficulty,
                    points=points,
                    description=description,
                    instructions=instructions,
                    starter_code=starter,
                    expected_answer=expected,
                    position=position,
                    due_at=due,
                )
            )
    existing_codes = set(db.scalars(select(Achievement.code)).all())
    for code, name, description, icon in ACHIEVEMENTS:
        if code not in existing_codes:
            db.add(Achievement(code=code, name=name, description=description, icon=icon))
    db.flush()
    notification = db.scalar(
        select(StudentNotification).where(StudentNotification.student_id == student.id)
    )
    if notification is None:
        db.add(
            StudentNotification(
                student_id=student.id,
                kind=NotificationKind.REMINDER,
                title="Keep your streak alive",
                message="Complete one activity today to reach a 4-day streak.",
            )
        )
    db.commit()
    db.refresh(student)
    return student


def calculate_progress(db: Session, student: StudentProfile) -> ProgressRead:
    tasks = db.scalars(select(LearningTask)).all()
    submissions = db.scalars(
        select(StudentSubmission)
        .where(
            StudentSubmission.student_id == student.id,
            StudentSubmission.status == SubmissionStatus.COMPLETED,
        )
        .options(selectinload(StudentSubmission.task))
    ).all()
    completed = len(submissions)
    scores = [item.score for item in submissions]
    module_totals: dict[str, int] = defaultdict(int)
    module_done: dict[str, int] = defaultdict(int)
    for task in tasks:
        module_totals[task.module] += 1
    for item in submissions:
        module_done[item.task.module] += 1
    awards = db.scalars(
        select(StudentAchievement)
        .where(StudentAchievement.student_id == student.id)
        .options(selectinload(StudentAchievement.achievement))
    ).all()
    points_in_level = student.points % 500
    return ProgressRead(
        student_id=student.id,
        display_name=student.display_name,
        completed_tasks=completed,
        total_tasks=len(tasks),
        completion_percent=round(completed / len(tasks) * 100) if tasks else 0,
        average_score=round(sum(scores) / len(scores)) if scores else 0,
        points=student.points,
        streak_days=student.streak_days,
        level=student.points // 500 + 1,
        level_progress=round(points_in_level / 500 * 100),
        achievements=[
            {
                "code": a.achievement.code,
                "name": a.achievement.name,
                "description": a.achievement.description,
                "icon": a.achievement.icon,
                "earned_at": a.earned_at,
            }
            for a in awards
        ],
        module_progress={
            name: round(module_done[name] / total * 100) for name, total in module_totals.items()
        },
    )


def recommendations(db: Session, student: StudentProfile) -> list[RecommendationRead]:
    tasks = db.scalars(select(LearningTask).order_by(LearningTask.position)).all()
    submissions = {
        s.task_id: s
        for s in db.scalars(
            select(StudentSubmission).where(StudentSubmission.student_id == student.id)
        ).all()
    }
    result: list[RecommendationRead] = []
    for task in tasks:
        submission = submissions.get(task.id)
        if submission is None:
            reason = "Recommended next step based on your course sequence."
            priority = "high" if not result else "medium"
        elif submission.score < 70:
            reason = f"Revisit this topic to improve your {submission.score}% result."
            priority = "high"
        else:
            continue
        result.append(
            RecommendationRead(task_id=task.id, title=task.title, reason=reason, priority=priority)
        )
    return result[:3]


def grade_submission(
    task: LearningTask, answer: str, code: str | None, circuit: dict | None
) -> tuple[int, str]:
    content = (code or answer).lower()
    if task.task_type == TaskType.CIRCUIT:
        operations = (circuit or {}).get("operations", [])
        correct = any(op.get("gate") == "h" for op in operations)
    else:
        correct = bool(task.expected_answer and task.expected_answer.lower() in content)
    if correct:
        return 100, "Excellent work — your response demonstrates the key concept."
    if len(content.strip()) >= 20:
        return 70, "Good attempt. Review the key terminology, then refine your explanation."
    return 40, "Add more detail and connect your answer to the learning objective."


def award_achievements(
    db: Session, student: StudentProfile, task: LearningTask, score: int
) -> list[str]:
    earned_codes = set(
        db.scalars(
            select(Achievement.code)
            .join(StudentAchievement)
            .where(StudentAchievement.student_id == student.id)
        ).all()
    )
    wanted = {"first-step"}
    if task.task_type == TaskType.CIRCUIT:
        wanted.add("circuit-maker")
    if score == 100:
        wanted.add("perfect-score")
    newly_earned: list[str] = []
    for achievement in db.scalars(
        select(Achievement).where(Achievement.code.in_(wanted - earned_codes))
    ).all():
        db.add(StudentAchievement(student_id=student.id, achievement_id=achievement.id))
        db.add(
            StudentNotification(
                student_id=student.id,
                kind=NotificationKind.ACHIEVEMENT,
                title=f"Achievement unlocked: {achievement.name}",
                message=achievement.description,
            )
        )
        newly_earned.append(achievement.name)
    return newly_earned


def simulate(request: SimulationRequest) -> dict:
    result = simulate_circuit(
        qubits=request.qubits,
        operations=[
            CircuitOperation(gate=operation.gate, targets=tuple(operation.targets))
            for operation in request.operations
        ],
        shots=request.shots,
    )
    return {
        "counts": result.counts,
        "probabilities": result.probabilities,
        "circuit_text": result.circuit_text,
        "engine": result.engine,
    }
