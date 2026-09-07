"""Course-scoped material processing, source history, and review routes."""
# ruff: noqa: B008

from __future__ import annotations

import io
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.authentication import get_current_user
from app.core.config import settings
from app.db.session import get_db_session
from app.models import LearningMaterial, MaterialIndexStatus
from app.models.source_history import SourceApproval, SourcePassage, SourceRevision, SourceUse
from app.models.user import User
from app.schemas.content import (
    LearningMaterialLinkCreate,
    LearningMaterialRead,
    MaterialProcessingRead,
    SourceApprovalRead,
    SourceApprovalRequest,
    SourcePassageRead,
    SourceRevisionRead,
    SourceUseRead,
)
from app.services.access import SqlAlchemyCourseAccessPolicy
from app.services.material_indexing import OfflineMaterialProcessor
from app.services.rag.contracts import CourseAccessPolicy
from app.services.rag.errors import CourseAccessDeniedError, DuplicateMaterialError, RagError
from app.services.rag.repositories import MaterialRepository
from app.services.rag.source_history import preserve_current_source, record_approval
from app.services.rag.storage import FileStorage, LocalFileStorage
from app.services.rag.web import SafeHttpsFetcher

router = APIRouter(prefix="/courses/{course_id}/materials")


def get_course_access_policy(
    db: Session = Depends(get_db_session),
) -> CourseAccessPolicy:
    return SqlAlchemyCourseAccessPolicy(db)


def get_material_storage() -> Generator[FileStorage, None, None]:
    yield LocalFileStorage(settings.rag_upload_dir, settings.rag_max_file_bytes)


def get_material_processor(
    db: Session = Depends(get_db_session), storage: FileStorage = Depends(get_material_storage)
) -> OfflineMaterialProcessor:
    return OfflineMaterialProcessor(db, storage)


def get_actor_id(user: User = Depends(get_current_user)) -> str:
    return str(user.id)


def get_https_fetcher() -> SafeHttpsFetcher:
    return SafeHttpsFetcher()


def _http_error(error: RagError) -> HTTPException:
    detail: dict[str, str] = {"code": error.code, "message": error.safe_message}
    if isinstance(error, DuplicateMaterialError):
        detail["existing_material_id"] = error.material_id
    return HTTPException(status_code=error.http_status, detail=detail)


def _require_manage(policy: CourseAccessPolicy, actor_id: str, course_id: str) -> None:
    try:
        policy.require_manage(actor_id, course_id)
    except CourseAccessDeniedError as error:
        raise _http_error(error) from error


def _require_read(policy: CourseAccessPolicy, actor_id: str, course_id: str) -> None:
    try:
        policy.require_read(actor_id, course_id)
    except CourseAccessDeniedError as error:
        raise _http_error(error) from error


def _require_source_review_read(
    policy: CourseAccessPolicy, actor_id: str, course_id: str, db: Session
) -> None:
    try:
        policy.require_manage(actor_id, course_id)
        return
    except CourseAccessDeniedError:
        pass
    from app.services.task_review import TaskReviewError, TaskReviewService

    try:
        actor = db.get(User, int(actor_id), populate_existing=True)
    except ValueError:
        actor = None
    if actor is None:
        raise HTTPException(status_code=403, detail="Source review access denied")
    try:
        TaskReviewService(db).require_review_access(actor, course_id)
    except TaskReviewError as error:
        raise HTTPException(status_code=403, detail="Source review access denied") from error


@router.post("/uploads", response_model=LearningMaterialRead, status_code=status.HTTP_201_CREATED)
def upload_material(
    course_id: str,
    file: Annotated[UploadFile, File()],
    module_id: str | None = None,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    storage: FileStorage = Depends(get_material_storage),
    db: Session = Depends(get_db_session),
) -> LearningMaterial:
    _require_manage(policy, actor_id, course_id)
    try:
        staged = storage.stage_upload(file.filename, file.file)
        repository = MaterialRepository(db)
        duplicate = repository.find_by_course_hash(course_id, staged.content_hash)
        if duplicate is not None:
            staged.temporary_path.unlink(missing_ok=True)
            raise _http_error(DuplicateMaterialError(duplicate.id))
        material = LearningMaterial(
            course_id=course_id,
            module_id=module_id,
            original_filename=file.filename or f"source{staged.safe_extension}",
            mime_type=staged.mime_type,
            content_hash=staged.content_hash,
            indexing_status=MaterialIndexStatus.PENDING,
            file_size_bytes=staged.file_size_bytes,
        )
        db.add(material)
        db.flush()
        material.storage_key = storage.commit(staged, material.id)
        db.commit()
        db.refresh(material)
        return material
    except HTTPException:
        raise
    except RagError as error:
        db.rollback()
        raise _http_error(error) from error
    except IntegrityError as error:
        db.rollback()
        raise _http_error(DuplicateMaterialError("unknown")) from error


@router.post("/links", response_model=LearningMaterialRead, status_code=status.HTTP_201_CREATED)
def register_linked_material(
    course_id: str,
    payload: LearningMaterialLinkCreate,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    storage: FileStorage = Depends(get_material_storage),
    fetcher: SafeHttpsFetcher = Depends(get_https_fetcher),
    db: Session = Depends(get_db_session),
) -> LearningMaterial:
    _require_manage(policy, actor_id, course_id)
    try:
        downloaded = fetcher.fetch(str(payload.source_url))
        staged = storage.stage_upload(downloaded.filename, io.BytesIO(downloaded.content))
        repository = MaterialRepository(db)
        duplicate = repository.find_by_course_hash(course_id, staged.content_hash)
        if duplicate is not None:
            staged.temporary_path.unlink(missing_ok=True)
            raise _http_error(DuplicateMaterialError(duplicate.id))
        material = LearningMaterial(
            course_id=course_id,
            module_id=payload.module_id,
            source_url=downloaded.url,
            mime_type=staged.mime_type,
            content_hash=staged.content_hash,
            indexing_status=MaterialIndexStatus.PENDING,
            file_size_bytes=staged.file_size_bytes,
        )
        db.add(material)
        db.flush()
        material.storage_key = storage.commit(staged, material.id)
        db.commit()
        db.refresh(material)
        return material
    except HTTPException:
        raise
    except RagError as error:
        db.rollback()
        raise _http_error(error) from error


@router.get("", response_model=list[LearningMaterialRead])
def list_materials(
    course_id: str,
    module_id: str | None = None,
    indexing_status: MaterialIndexStatus | None = None,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> list[LearningMaterial]:
    _require_read(policy, actor_id, course_id)
    return MaterialRepository(db).list(course_id, module_id, indexing_status)


@router.get("/{material_id}", response_model=LearningMaterialRead)
def read_material(
    course_id: str,
    material_id: str,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> LearningMaterial:
    _require_read(policy, actor_id, course_id)
    try:
        return MaterialRepository(db).get(course_id, material_id)
    except RagError as error:
        raise _http_error(error) from error


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    course_id: str,
    material_id: str,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> None:
    _require_manage(policy, actor_id, course_id)
    try:
        material = MaterialRepository(db).get(course_id, material_id, include_retired=True)
        preserve_current_source(db, material)
        if material.retired_at is None:
            material.retired_at = datetime.now(UTC)
            material.processing_token = None
            material.processing_lease_expires_at = None
            material.processing_retry_at = None
        db.commit()
    except RagError as error:
        db.rollback()
        raise _http_error(error) from error


@router.post("/{material_id}/process", response_model=MaterialProcessingRead)
def process_material(
    course_id: str,
    material_id: str,
    force: bool = False,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    processor: OfflineMaterialProcessor = Depends(get_material_processor),
    db: Session = Depends(get_db_session),
) -> MaterialProcessingRead:
    _require_manage(policy, actor_id, course_id)
    try:
        material = MaterialRepository(db).get(course_id, material_id)
        chunk_count, indexed_chunk_count = processor.process(material, force)
        db.refresh(material)
        return MaterialProcessingRead(
            material=LearningMaterialRead.model_validate(material),
            chunk_count=chunk_count,
            indexed_chunk_count=indexed_chunk_count,
            processing_revision=material.processing_revision,
        )
    except RagError as error:
        raise _http_error(error) from error
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail={
                "code": "material_processing_failed",
                "message": "The upload is saved. Check its processing status for retry details.",
            },
        ) from error


@router.get("/{material_id}/revisions", response_model=list[SourceRevisionRead])
def list_source_revisions(
    course_id: str,
    material_id: str,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> list[SourceRevisionRead]:
    _require_source_review_read(policy, actor_id, course_id, db)
    try:
        MaterialRepository(db).get(course_id, material_id, include_retired=True)
    except RagError as error:
        raise _http_error(error) from error
    return [
        _revision_read(db, revision)
        for revision in db.scalars(
            select(SourceRevision)
            .where(
                SourceRevision.material_id == material_id,
                SourceRevision.course_id == course_id,
            )
            .order_by(SourceRevision.version.desc())
        )
    ]


@router.get("/{material_id}/revisions/{revision_id}", response_model=SourceRevisionRead)
def read_source_revision(
    course_id: str,
    material_id: str,
    revision_id: str,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> SourceRevisionRead:
    _require_source_review_read(policy, actor_id, course_id, db)
    revision = db.get(SourceRevision, revision_id)
    if revision is None or revision.material_id != material_id or revision.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source revision not found")
    return _revision_read(db, revision)


@router.get("/passages/{passage_id}", response_model=SourcePassageRead)
def read_source_passage(
    course_id: str,
    passage_id: str,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> SourcePassage:
    _require_source_review_read(policy, actor_id, course_id, db)
    passage = db.get(SourcePassage, passage_id)
    if passage is None or passage.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source passage not found")
    return passage


@router.get("/citations/{output_type}/{output_id}", response_model=list[SourceUseRead])
def read_output_citations(
    course_id: str,
    output_type: Literal["task", "feedback", "assessment"],
    output_id: str,
    output_version: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> list[SourceUseRead]:
    _require_source_review_read(policy, actor_id, course_id, db)
    statement = (
        select(SourceUse, SourcePassage.revision_id, SourceRevision.material_id)
        .join(SourcePassage, SourceUse.passage_id == SourcePassage.id)
        .join(SourceRevision, SourcePassage.revision_id == SourceRevision.id)
        .where(
            SourceUse.course_id == course_id,
            SourceUse.output_type == output_type,
            SourceUse.output_id == output_id,
        )
    )
    if output_version is not None:
        statement = statement.where(SourceUse.output_version == output_version)
    return [
        SourceUseRead.model_validate(
            {
                **{
                    name: getattr(citation, name)
                    for name in SourceUseRead.model_fields
                    if name not in {"revision_id", "material_id"}
                },
                "revision_id": revision_id,
                "material_id": material_id,
            }
        )
        for citation, revision_id, material_id in db.execute(
            statement.order_by(SourceUse.created_at, SourceUse.id).offset(offset).limit(limit)
        )
    ]


@router.post(
    "/{material_id}/revisions/{revision_id}/approvals",
    response_model=SourceApprovalRead,
    status_code=201,
)
def approve_source_revision(
    course_id: str,
    material_id: str,
    revision_id: str,
    payload: SourceApprovalRequest,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    db: Session = Depends(get_db_session),
) -> SourceApproval:
    _require_manage(policy, actor_id, course_id)
    try:
        material = MaterialRepository(db).get(course_id, material_id, include_retired=True)
        if material.retired_at is not None and payload.state == "APPROVED":
            raise HTTPException(
                status_code=409, detail="Retired material cannot receive a new approval"
            )
        approval = record_approval(
            db,
            course_id=course_id,
            material_id=material_id,
            revision_id=revision_id,
            actor_id=actor_id,
            state=payload.state,
            reason=payload.reason,
            expected_sequence=payload.expected_sequence,
        )
        db.commit()
        db.refresh(approval)
        return approval
    except RagError as error:
        db.rollback()
        raise _http_error(error) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Source approval changed; reload and retry"
        ) from error


@router.post("/{material_id}/replacement", response_model=LearningMaterialRead)
def replace_material(
    course_id: str,
    material_id: str,
    file: Annotated[UploadFile, File()],
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    storage: FileStorage = Depends(get_material_storage),
    db: Session = Depends(get_db_session),
) -> LearningMaterial:
    _require_manage(policy, actor_id, course_id)
    try:
        material = MaterialRepository(db).get(course_id, material_id)
        if material.indexing_status == MaterialIndexStatus.PROCESSING:
            raise HTTPException(status_code=409, detail="Material is being processed")
        preserve_current_source(db, material)
        staged = storage.stage_upload(file.filename, file.file)
        duplicate = MaterialRepository(db).find_by_course_hash(course_id, staged.content_hash)
        if duplicate is not None and duplicate.id != material.id:
            staged.temporary_path.unlink(missing_ok=True)
            raise _http_error(DuplicateMaterialError(duplicate.id))
        material.storage_key = storage.commit(staged, material.id)
        material.content_hash = staged.content_hash
        material.original_filename = file.filename or f"source{staged.safe_extension}"
        material.source_url = None
        material.mime_type = staged.mime_type
        material.file_size_bytes = staged.file_size_bytes
        material.indexing_status = MaterialIndexStatus.PENDING
        material.processing_revision += 1
        material.processing_attempts = 0
        material.processing_token = None
        material.processing_lease_expires_at = None
        material.processing_retry_at = None
        material.processing_backend = "offline"
        material.extraction_error = material.error_code = material.failure_stage = None
        db.commit()
        db.refresh(material)
        return material
    except RagError as error:
        db.rollback()
        raise _http_error(error) from error
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Material changed; reload and retry") from error


def _revision_read(db: Session, revision: SourceRevision) -> SourceRevisionRead:
    approvals = list(
        db.scalars(
            select(SourceApproval)
            .where(SourceApproval.revision_id == revision.id)
            .order_by(SourceApproval.sequence)
        )
    )
    passages = list(
        db.scalars(
            select(SourcePassage)
            .where(SourcePassage.revision_id == revision.id)
            .order_by(SourcePassage.chunk_index)
        )
    )
    return SourceRevisionRead.model_validate(revision).model_copy(
        update={
            "approval_state": approvals[-1].state if approvals else "UNREVIEWED",
            "approvals": [SourceApprovalRead.model_validate(item) for item in approvals],
            "passages": [SourcePassageRead.model_validate(item) for item in passages],
        }
    )
