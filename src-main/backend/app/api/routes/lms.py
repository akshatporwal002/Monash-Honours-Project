from __future__ import annotations

from collections.abc import Generator, Iterator
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies.roles import (
    CurrentAdministrator,
    CurrentEducator,
    CurrentStudent,
    CurrentUser,
)
from app.api.feedback_dependencies import get_feedback_application, get_feedback_executor
from app.core.config import settings
from app.db.session import get_db
from app.models import CourseState
from app.schemas.lms import (
    AdminUserCreate,
    AdminUserRead,
    AdminUserUpdate,
    AttemptRead,
    BootstrapRead,
    BulkReminderCreate,
    CourseCreate,
    CourseRead,
    CourseUpdate,
    DraftRead,
    DraftWrite,
    EducatorDashboardRead,
    EducatorStudentRead,
    EnrollmentCreate,
    EnrollmentRead,
    MaterialLinkCreate,
    MaterialRead,
    ModuleCreate,
    ModuleRead,
    ModuleUpdate,
    OutcomeCreate,
    OutcomeRead,
    OutcomeUpdate,
    ReminderRead,
    SettingsRead,
    SettingsUpdate,
    StudentDashboardRead,
    SubmissionCreate,
    TaskCreate,
    TaskGenerateRequest,
    TaskRead,
    TaskUpdate,
)
from app.schemas.student import SimulationRead, SimulationRequest
from app.services.feedback.application import (
    FeedbackBackgroundExecutor,
    FeedbackWorkflowApplication,
)
from app.services.lms import LmsService, LmsServiceError, bootstrap_demo
from app.services.material_indexing import index_material_offline
from app.services.rag.errors import RagError
from app.services.rag.storage import FileStorage, LocalFileStorage
from app.services.student import simulate

router = APIRouter()


def get_lms_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> Generator[LmsService, None, None]:
    try:
        yield LmsService(
            session,
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    except LmsServiceError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error


def get_lms_material_storage() -> FileStorage:
    return LocalFileStorage(settings.rag_upload_dir, settings.rag_max_file_bytes)


Lms = Annotated[LmsService, Depends(get_lms_service)]


@router.get("/courses", response_model=list[CourseRead])
def list_courses(actor: CurrentUser, service: Lms) -> list[CourseRead]:
    return service.list_courses(actor)


@router.post(
    "/courses",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    payload: CourseCreate,
    educator: CurrentEducator,
    service: Lms,
) -> CourseRead:
    return service.create_course(educator, payload)


@router.get("/courses/{course_id}", response_model=CourseRead)
def get_course(
    course_id: str,
    actor: CurrentUser,
    service: Lms,
) -> CourseRead:
    return service.get_course_for_actor(actor, course_id)


@router.patch("/courses/{course_id}", response_model=CourseRead)
def update_course(
    course_id: str,
    payload: CourseUpdate,
    educator: CurrentEducator,
    service: Lms,
) -> CourseRead:
    return service.update_course(educator, course_id, payload)


@router.post("/courses/{course_id}/publish", response_model=CourseRead)
def publish_course(
    course_id: str,
    educator: CurrentEducator,
    service: Lms,
) -> CourseRead:
    return service.set_course_state(educator, course_id, CourseState.PUBLISHED)


@router.post("/courses/{course_id}/archive", response_model=CourseRead)
def archive_owned_course(
    course_id: str,
    educator: CurrentEducator,
    service: Lms,
) -> CourseRead:
    return service.set_course_state(educator, course_id, CourseState.ARCHIVED)


@router.get("/courses/{course_id}/modules", response_model=list[ModuleRead])
def list_modules(
    course_id: str,
    actor: CurrentUser,
    service: Lms,
):
    return service.list_modules(actor, course_id)


@router.post(
    "/courses/{course_id}/modules",
    response_model=ModuleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_module(
    course_id: str,
    payload: ModuleCreate,
    educator: CurrentEducator,
    service: Lms,
):
    return service.create_module(educator, course_id, payload)


@router.patch("/modules/{module_id}", response_model=ModuleRead)
def update_module(
    module_id: str,
    payload: ModuleUpdate,
    educator: CurrentEducator,
    service: Lms,
):
    return service.update_module(educator, module_id, payload)


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    module_id: str,
    educator: CurrentEducator,
    service: Lms,
) -> None:
    service.delete_module(educator, module_id)


@router.get("/modules/{module_id}/outcomes", response_model=list[OutcomeRead])
def list_outcomes(
    module_id: str,
    actor: CurrentUser,
    service: Lms,
):
    return service.list_outcomes(actor, module_id)


@router.post(
    "/modules/{module_id}/outcomes",
    response_model=OutcomeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_outcome(
    module_id: str,
    payload: OutcomeCreate,
    educator: CurrentEducator,
    service: Lms,
):
    return service.create_outcome(educator, module_id, payload)


@router.patch("/outcomes/{outcome_id}", response_model=OutcomeRead)
def update_outcome(
    outcome_id: str,
    payload: OutcomeUpdate,
    educator: CurrentEducator,
    service: Lms,
):
    return service.update_outcome(educator, outcome_id, payload)


@router.delete("/outcomes/{outcome_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outcome(
    outcome_id: str,
    educator: CurrentEducator,
    service: Lms,
) -> None:
    service.delete_outcome(educator, outcome_id)


@router.get(
    "/courses/{course_id}/enrollments",
    response_model=list[EnrollmentRead],
)
def list_enrollments(
    course_id: str,
    educator: CurrentEducator,
    service: Lms,
) -> list[EnrollmentRead]:
    return service.list_enrollments(educator, course_id)


@router.post(
    "/courses/{course_id}/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
def enroll_student(
    course_id: str,
    payload: EnrollmentCreate,
    educator: CurrentEducator,
    service: Lms,
) -> EnrollmentRead:
    return service.enroll_student(educator, course_id, payload.student_id)


@router.get("/courses/{course_id}/tasks", response_model=list[TaskRead])
def list_tasks(
    course_id: str,
    actor: CurrentUser,
    service: Lms,
) -> list[TaskRead]:
    return service.list_tasks(actor, course_id)


@router.post(
    "/courses/{course_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    course_id: str,
    payload: TaskCreate,
    educator: CurrentEducator,
    service: Lms,
) -> TaskRead:
    return service.create_task(educator, course_id, payload)


@router.post(
    "/courses/{course_id}/generate-tasks",
    response_model=list[TaskRead],
    status_code=status.HTTP_201_CREATED,
)
async def generate_tasks(
    course_id: str,
    payload: TaskGenerateRequest,
    educator: CurrentEducator,
    service: Lms,
) -> list[TaskRead]:
    return await service.generate_scaffolded_tasks(educator, course_id, payload)


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: str,
    actor: CurrentUser,
    service: Lms,
) -> TaskRead:
    return service.get_task_for_actor(actor, task_id)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    educator: CurrentEducator,
    service: Lms,
) -> TaskRead:
    return service.update_task(educator, task_id, payload)


# The legacy RAG router retains GET /materials during migration. This
# authenticated canonical path avoids changing its established test contract.
@router.get(
    "/courses/{course_id}/materials/list",
    response_model=list[MaterialRead],
)
def list_course_materials(
    course_id: str,
    actor: CurrentUser,
    service: Lms,
):
    return service.list_materials(actor, course_id)


@router.post(
    "/courses/{course_id}/materials/link",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
def link_course_material(
    course_id: str,
    payload: MaterialLinkCreate,
    educator: CurrentEducator,
    service: Lms,
):
    return service.register_material_link(educator, course_id, payload)


@router.post(
    "/courses/{course_id}/materials/upload",
    response_model=MaterialRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_course_material(
    course_id: str,
    file: Annotated[UploadFile, File()],
    educator: CurrentEducator,
    service: Lms,
    module_id: Annotated[str | None, Query()] = None,
    storage: Annotated[FileStorage, Depends(get_lms_material_storage)] = None,
):
    try:
        material = service.upload_material(
            educator,
            course_id,
            module_id,
            file.filename,
            file.file,
            storage,
        )
        try:
            return index_material_offline(service.session, storage, material)
        except Exception:
            service.session.expire_all()
            return service.get_material_for_actor(
                educator,
                course_id,
                material.id,
            )
    except RagError as error:
        raise HTTPException(
            status_code=error.http_status,
            detail=error.safe_message,
        ) from error


@router.get(
    "/courses/{course_id}/materials/{material_id}/content",
    response_model=None,
)
def access_course_material(
    course_id: str,
    material_id: str,
    actor: CurrentUser,
    service: Lms,
    storage: Annotated[FileStorage, Depends(get_lms_material_storage)],
):
    material = service.get_material_for_actor(actor, course_id, material_id)
    if material.source_url:
        return RedirectResponse(
            material.source_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )
    if not material.storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning material content is unavailable",
        )
    filename = material.original_filename or "learning-material"
    encoded_filename = quote(filename, safe="")
    try:
        with storage.open_read(material.storage_key):
            pass
    except (FileNotFoundError, OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Learning material content is unavailable",
        ) from None
    return StreamingResponse(
        _stored_blocks(storage, material.storage_key),
        media_type=material.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _stored_blocks(storage: FileStorage, storage_key: str) -> Iterator[bytes]:
    with storage.open_read(storage_key) as source:
        while block := source.read(64 * 1024):
            yield block


@router.get("/students/me/dashboard", response_model=StudentDashboardRead)
def student_dashboard(
    student: CurrentStudent,
    service: Lms,
) -> StudentDashboardRead:
    return service.student_dashboard(student)


@router.get("/students/me/tasks/{task_id}", response_model=TaskRead)
def student_task(
    task_id: str,
    student: CurrentStudent,
    service: Lms,
) -> TaskRead:
    return service.get_student_task(student, task_id)


@router.get(
    "/students/me/tasks/{task_id}/draft",
    response_model=DraftRead | None,
)
def get_student_draft(
    task_id: str,
    student: CurrentStudent,
    service: Lms,
) -> DraftRead | None:
    return service.get_draft(student, task_id)


@router.put("/students/me/tasks/{task_id}/draft", response_model=DraftRead)
def save_student_draft(
    task_id: str,
    payload: DraftWrite,
    student: CurrentStudent,
    service: Lms,
) -> DraftRead:
    return service.save_draft(student, task_id, payload)


@router.post(
    "/students/me/tasks/{task_id}/submissions",
    response_model=AttemptRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_student_task(
    task_id: str,
    payload: SubmissionCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    student: CurrentStudent,
    service: Lms,
    feedback_application: Annotated[
        FeedbackWorkflowApplication,
        Depends(get_feedback_application),
    ],
    feedback_executor: Annotated[
        FeedbackBackgroundExecutor,
        Depends(get_feedback_executor),
    ],
) -> AttemptRead:
    attempt = service.submit(student, task_id, payload)
    request_correlation_id = getattr(request.state, "correlation_id", None)
    correlation_id = request_correlation_id if isinstance(request_correlation_id, str) else None
    try:
        claim = feedback_application.start(
            attempt.id,
            correlation_id=correlation_id,
        )
    except Exception:
        service.mark_assessment_fault(
            attempt.id,
            "The feedback workflow could not start. The response is saved for review.",
        )
        raise
    if claim.should_start:
        background_tasks.add_task(
            feedback_executor.execute,
            claim.workflow_run_id,
            attempt.id,
            claim.execution_token,
            correlation_id,
        )
    return attempt


@router.get(
    "/students/me/tasks/{task_id}/submissions",
    response_model=list[AttemptRead],
)
def list_student_attempts(
    task_id: str,
    student: CurrentStudent,
    service: Lms,
) -> list[AttemptRead]:
    return service.list_attempts(student, task_id)


@router.post("/students/me/simulate", response_model=SimulationRead)
def simulate_student_circuit(
    payload: SimulationRequest,
    _: CurrentStudent,
) -> dict:
    return simulate(payload)


@router.patch(
    "/students/me/reminders/{reminder_id}/read",
    response_model=ReminderRead,
)
def mark_student_reminder_read(
    reminder_id: str,
    student: CurrentStudent,
    service: Lms,
) -> ReminderRead:
    return service.mark_reminder_read(student, reminder_id)


@router.get("/educator/dashboard", response_model=EducatorDashboardRead)
def educator_dashboard(
    educator: CurrentEducator,
    service: Lms,
) -> EducatorDashboardRead:
    return service.educator_dashboard(educator)


@router.get("/educator/students", response_model=list[EducatorStudentRead])
def educator_students(
    educator: CurrentEducator,
    service: Lms,
    course_id: Annotated[str | None, Query()] = None,
) -> list[EducatorStudentRead]:
    return service.educator_students(educator, course_id)


@router.post(
    "/educator/students/notifications",
    response_model=list[ReminderRead],
    status_code=status.HTTP_201_CREATED,
)
def notify_students(
    payload: BulkReminderCreate,
    educator: CurrentEducator,
    service: Lms,
) -> list[ReminderRead]:
    return service.send_bulk_reminders(educator, payload)


@router.get("/admin/users", response_model=list[AdminUserRead])
def list_users(
    _: CurrentAdministrator,
    service: Lms,
) -> list[AdminUserRead]:
    return service.list_users()


@router.post(
    "/admin/users",
    response_model=AdminUserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: AdminUserCreate,
    administrator: CurrentAdministrator,
    service: Lms,
) -> AdminUserRead:
    return service.create_user(administrator, payload)


@router.patch("/admin/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    administrator: CurrentAdministrator,
    service: Lms,
) -> AdminUserRead:
    return service.update_user(administrator, user_id, payload)


@router.post("/admin/users/{user_id}/deactivate", response_model=AdminUserRead)
def deactivate_user(
    user_id: int,
    administrator: CurrentAdministrator,
    service: Lms,
) -> AdminUserRead:
    return service.set_user_active(administrator, user_id, False)


@router.post("/admin/users/{user_id}/reactivate", response_model=AdminUserRead)
def reactivate_user(
    user_id: int,
    administrator: CurrentAdministrator,
    service: Lms,
) -> AdminUserRead:
    return service.set_user_active(administrator, user_id, True)


@router.get("/admin/settings", response_model=SettingsRead)
def read_settings(
    _: CurrentAdministrator,
    service: Lms,
) -> SettingsRead:
    return service.read_settings()


@router.put("/admin/settings", response_model=SettingsRead)
def update_settings(
    payload: SettingsUpdate,
    administrator: CurrentAdministrator,
    service: Lms,
) -> SettingsRead:
    return service.update_settings(administrator, payload)


@router.get("/admin/courses", response_model=list[CourseRead])
def admin_courses(
    administrator: CurrentAdministrator,
    service: Lms,
) -> list[CourseRead]:
    return service.list_courses(administrator)


@router.post("/admin/courses/{course_id}/archive", response_model=CourseRead)
def admin_archive_course(
    course_id: str,
    administrator: CurrentAdministrator,
    service: Lms,
) -> CourseRead:
    return service.admin_archive_course(administrator, course_id)


@router.post(
    "/admin/bootstrap-demo",
    response_model=BootstrapRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=not settings.production,
)
def bootstrap_demo_environment(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> BootstrapRead:
    client_host = request.client.host if request.client is not None else ""
    if settings.production or client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    users, course = bootstrap_demo(session)
    service = LmsService(session)
    return BootstrapRead(
        users=[service._admin_user_read(user) for user in users],
        course=service._course_read(course),
    )
