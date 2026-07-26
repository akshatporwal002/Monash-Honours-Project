import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.routes.materials import (
    get_actor_id,
    get_course_access_policy,
    get_material_storage,
)
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models import LearningMaterial, MaterialIndexStatus
from app.services.rag.errors import InvalidDocumentError, MaterialTooLargeError
from app.services.rag.fakes import AllowAllCourseAccessPolicy
from app.services.rag.storage import LocalFileStorage


def _docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in (
            ("[Content_Types].xml", "<Types />"),
            ("word/document.xml", "<document />"),
        ):
            entry = zipfile.ZipInfo(name, date_time=(2024, 1, 1, 0, 0, 0))
            archive.writestr(entry, content)
    return buffer.getvalue()


def test_storage_rejects_path_traversal_and_invalid_signatures(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_file_bytes=1024)

    with pytest.raises(InvalidDocumentError):
        storage.stage_upload("../lecture.pdf", io.BytesIO(b"not a PDF"))
    with pytest.raises(InvalidDocumentError):
        storage.stage_upload("slides.docx", io.BytesIO(b"%PDF-1.7"))


def test_storage_enforces_size_and_keeps_committed_file_inside_root(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path, max_file_bytes=8)
    with pytest.raises(MaterialTooLargeError):
        storage.stage_upload("lecture.pdf", io.BytesIO(b"%PDF-12345"))

    storage = LocalFileStorage(tmp_path, max_file_bytes=1024)
    staged = storage.stage_upload("lecture.docx", io.BytesIO(_docx_bytes()))
    storage_key = storage.commit(staged, "material-1")

    assert storage_key == "material-1/source.docx"
    assert (tmp_path / storage_key).is_file()
    storage.delete(storage_key)
    assert not (tmp_path / storage_key).exists()


@pytest.fixture
def material_client(tmp_path: Path):
    database_path = tmp_path / "materials.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    storage = LocalFileStorage(tmp_path / "uploads", max_file_bytes=1024 * 1024)

    app.dependency_overrides[get_db_session] = lambda: session
    app.dependency_overrides[get_material_storage] = lambda: storage
    app.dependency_overrides[get_actor_id] = lambda: "test-educator"
    app.dependency_overrides[get_course_access_policy] = AllowAllCourseAccessPolicy
    try:
        with TestClient(app) as client:
            yield client, session, storage
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_upload_list_read_duplicate_and_delete_are_course_scoped(
    material_client: tuple[TestClient, Session, LocalFileStorage],
) -> None:
    client, session, storage = material_client
    response = client.post(
        "/api/v1/courses/course-1/materials/uploads?module_id=week-1",
        files={
            "file": (
                "lecture.docx",
                _docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 201
    material = response.json()
    assert material["course_id"] == "course-1"
    assert material["indexing_status"] == "pending"
    assert material["storage_key"].endswith("/source.docx")
    assert (storage.upload_dir / material["storage_key"]).is_file()

    assert client.get("/api/v1/courses/course-1/materials").json()[0]["id"] == material["id"]
    assert client.get(f"/api/v1/courses/course-2/materials/{material['id']}").status_code == 404

    duplicate = client.post(
        "/api/v1/courses/course-1/materials/uploads",
        files={"file": ("copy.docx", _docx_bytes(), "application/octet-stream")},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_material_id"] == material["id"]

    assert client.delete(f"/api/v1/courses/course-1/materials/{material['id']}").status_code == 204
    assert session.get(LearningMaterial, material["id"]) is None
    assert not (storage.upload_dir / material["storage_key"]).exists()


def test_processing_status_and_new_material_fields_are_persisted(
    material_client: tuple[TestClient, Session, LocalFileStorage],
) -> None:
    _, session, _ = material_client
    material = LearningMaterial(
        course_id="course-1",
        original_filename="source.pdf",
        storage_key="material/source.pdf",
        mime_type="application/pdf",
        content_hash="sha256:unique",
        indexing_status=MaterialIndexStatus.PROCESSING,
        file_size_bytes=10,
        processing_revision=0,
    )
    session.add(material)
    session.commit()

    assert (
        session.get(LearningMaterial, material.id).indexing_status is MaterialIndexStatus.PROCESSING
    )
    assert settings.rag_max_file_bytes > 0
