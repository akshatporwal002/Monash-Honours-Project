from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import (
    LearningTask,
    StudentNotification,
    StudentProfile,
    StudentSubmission,
    SubmissionStatus,
)
from app.schemas.student import (
    DashboardRead,
    EducatorStudentRead,
    NotificationRead,
    ProgressRead,
    SimulationRead,
    SimulationRequest,
    SubmissionRead,
    SubmissionWrite,
    TaskRead,
)
from app.services.quantum import QuantumSimulationError
from app.services.student import (
    award_achievements,
    calculate_progress,
    grade_submission,
    recommendations,
    seed_demo_data,
    simulate,
)

router = APIRouter(prefix="/students")


def get_student(student_id: str, db: Session) -> StudentProfile:
    seed_demo_data(db)
    student = db.get(StudentProfile, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def task_read(task: LearningTask, submission: StudentSubmission | None = None) -> TaskRead:
    data = TaskRead.model_validate(task)
    return data.model_copy(
        update={
            "status": submission.status if submission else None,
            "score": submission.score if submission else None,
        }
    )


@router.get("/demo", response_model=DashboardRead)
def demo_dashboard(db: Session = Depends(get_db_session)) -> DashboardRead:
    student = seed_demo_data(db)
    return dashboard(student.id, db)


@router.get("/{student_id}/dashboard", response_model=DashboardRead)
def dashboard(student_id: str, db: Session = Depends(get_db_session)) -> DashboardRead:
    student = get_student(student_id, db)
    submissions = {
        item.task_id: item
        for item in db.scalars(
            select(StudentSubmission).where(StudentSubmission.student_id == student.id)
        ).all()
    }
    tasks = db.scalars(select(LearningTask).order_by(LearningTask.position)).all()
    notifications = db.scalars(
        select(StudentNotification)
        .where(StudentNotification.student_id == student.id)
        .order_by(StudentNotification.created_at.desc())
        .limit(5)
    ).all()
    return DashboardRead(
        progress=calculate_progress(db, student),
        tasks=[task_read(task, submissions.get(task.id)) for task in tasks],
        recommendations=recommendations(db, student),
        notifications=[NotificationRead.model_validate(item) for item in notifications],
    )


@router.get("/{student_id}/tasks/{task_id}", response_model=TaskRead)
def get_task(student_id: str, task_id: str, db: Session = Depends(get_db_session)) -> TaskRead:
    student = get_student(student_id, db)
    task = db.get(LearningTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    submission = db.scalar(
        select(StudentSubmission).where(
            StudentSubmission.student_id == student.id, StudentSubmission.task_id == task.id
        )
    )
    return task_read(task, submission)


@router.put("/{student_id}/tasks/{task_id}/submission", response_model=SubmissionRead)
def save_submission(
    student_id: str, task_id: str, payload: SubmissionWrite, db: Session = Depends(get_db_session)
) -> StudentSubmission:
    student = get_student(student_id, db)
    task = db.get(LearningTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    submission = db.scalar(
        select(StudentSubmission).where(
            StudentSubmission.student_id == student.id, StudentSubmission.task_id == task.id
        )
    )
    if submission is None:
        submission = StudentSubmission(
            student_id=student.id, task_id=task.id, status=SubmissionStatus.DRAFT
        )
        db.add(submission)
    was_complete = submission.status == SubmissionStatus.COMPLETED
    submission.answer = payload.answer
    submission.code = payload.code
    submission.circuit = payload.circuit
    if payload.submit:
        score, feedback = grade_submission(task, payload.answer, payload.code, payload.circuit)
        submission.status = SubmissionStatus.COMPLETED
        submission.score = score
        submission.feedback = feedback
        submission.attempts = (submission.attempts or 0) + 1
        submission.submitted_at = datetime.now(timezone.utc)
        if not was_complete:
            student.points += task.points
        award_achievements(db, student, task, score)
    else:
        submission.status = SubmissionStatus.DRAFT
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{student_id}/submissions", response_model=list[SubmissionRead])
def list_submissions(
    student_id: str, db: Session = Depends(get_db_session)
) -> list[StudentSubmission]:
    student = get_student(student_id, db)
    return list(
        db.scalars(
            select(StudentSubmission)
            .where(StudentSubmission.student_id == student.id)
            .order_by(StudentSubmission.updated_at.desc())
        ).all()
    )


@router.post("/{student_id}/simulate", response_model=SimulationRead)
def run_simulation(
    student_id: str, payload: SimulationRequest, db: Session = Depends(get_db_session)
) -> dict:
    get_student(student_id, db)
    try:
        return simulate(payload)
    except QuantumSimulationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{student_id}/progress", response_model=ProgressRead)
def progress(student_id: str, db: Session = Depends(get_db_session)) -> ProgressRead:
    return calculate_progress(db, get_student(student_id, db))


@router.patch("/{student_id}/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    student_id: str, notification_id: str, db: Session = Depends(get_db_session)
) -> StudentNotification:
    student = get_student(student_id, db)
    notification = db.get(StudentNotification, notification_id)
    if notification is None or notification.student_id != student.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.get("/educator-progress", response_model=list[EducatorStudentRead])
def educator_progress(db: Session = Depends(get_db_session)) -> list[EducatorStudentRead]:
    seed_demo_data(db)
    students = db.scalars(select(StudentProfile)).all()
    total_tasks = db.scalar(select(func.count(LearningTask.id))) or 0
    result = []
    for student in students:
        completed = list(
            db.scalars(
                select(StudentSubmission).where(
                    StudentSubmission.student_id == student.id,
                    StudentSubmission.status == SubmissionStatus.COMPLETED,
                )
            ).all()
        )
        result.append(
            EducatorStudentRead(
                student_id=student.id,
                display_name=student.display_name,
                completed_tasks=len(completed),
                total_tasks=total_tasks,
                completion_percent=round(len(completed) / total_tasks * 100) if total_tasks else 0,
                average_score=round(sum(s.score for s in completed) / len(completed))
                if completed
                else 0,
                last_active=max((s.updated_at for s in completed), default=None),
            )
        )
    return result
