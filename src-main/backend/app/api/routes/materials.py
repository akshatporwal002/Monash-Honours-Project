"""Educator material lifecycle routes; processing is added in a later stage."""
# ruff: noqa: B008

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session
from app.models import LearningMaterial, MaterialIndexStatus
from app.schemas.content import LearningMaterialRead, MaterialProcessingRead
from app.services.rag.contracts import CourseAccessPolicy
from app.services.rag.embeddings import SentenceTransformerEmbeddingProvider
from app.services.rag.errors import CourseAccessDeniedError, DuplicateMaterialError, RagError
from app.services.rag.extraction.docx import DocxDocumentExtractor
from app.services.rag.extraction.pdf import PdfDocumentExtractor
from app.services.rag.extraction.pptx import PptxDocumentExtractor
from app.services.rag.fakes import AllowAllCourseAccessPolicy, DenyAllCourseAccessPolicy
from app.services.rag.ingestion import MaterialProcessor
from app.services.rag.repositories import MaterialRepository
from app.services.rag.storage import FileStorage, LocalFileStorage
from app.services.rag.vector_store import ChromaVectorStore

router = APIRouter(prefix="/courses/{course_id}/materials")


def get_course_access_policy() -> CourseAccessPolicy:
    if settings.app_env in {"development", "test"}:
        return AllowAllCourseAccessPolicy()
    return DenyAllCourseAccessPolicy()


def get_material_storage() -> Generator[FileStorage, None, None]:
    yield LocalFileStorage(settings.rag_upload_dir, settings.rag_max_file_bytes)


def get_material_processor(
    db: Session = Depends(get_db_session), storage: FileStorage = Depends(get_material_storage)
) -> MaterialProcessor:
    embedding = SentenceTransformerEmbeddingProvider()
    return MaterialProcessor(
        db,
        storage,
        {
            "application/pdf": PdfDocumentExtractor(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxDocumentExtractor(),
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": PptxDocumentExtractor(),
        },
        embedding,
        ChromaVectorStore(embedding.model_id, embedding.dimension),
    )


def get_actor_id(x_actor_id: Annotated[str | None, Header()] = None) -> str:
    return x_actor_id or "development-actor"


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
    storage: FileStorage = Depends(get_material_storage),
    db: Session = Depends(get_db_session),
) -> None:
    _require_manage(policy, actor_id, course_id)
    try:
        material = MaterialRepository(db).get(course_id, material_id)
        storage.delete(material.storage_key)
        db.delete(material)
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
    processor: MaterialProcessor = Depends(get_material_processor),
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
