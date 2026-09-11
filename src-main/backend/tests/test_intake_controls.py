"""Synthetic adapter checks prove control flow, never malware detection efficacy."""

import io
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, settings
from app.models import (
    CourseModule,
    CourseState,
    Enrollment,
    LearningMaterial,
    MaterialChunk,
    User,
    UserRole,
)
from app.models.intake_history import MaterialScan
from app.models.source_history import SourcePassage, SourceRevision, SourceUse
from app.schemas.lms import CourseCreate, CourseUpdate
from app.services.lms import LmsService, LmsServiceError
from app.services.material_scanning import (
    ClamAvScanner,
    ScanVerdict,
    require_clean_material,
    revision_scan_is_clean,
)
from app.services.rag.contracts import ExtractedBlock, ExtractedDocument
from app.services.rag.errors import RagError
from app.services.rag.fakes import (
    DeterministicEmbeddingProvider,
    InMemoryVectorStore,
    StaticDocumentExtractor,
)
from app.services.rag.ingestion import MaterialProcessor
from app.services.rag.processing_claims import MaterialRetryRequired
from app.services.rag.source_history import bind_sources, record_approval
from app.services.rag.storage import LocalFileStorage


class SyntheticScanner:
    def __init__(self, status="CLEAN"):
        self.status = status
        self.seen = []

    def scan(self, content):
        self.seen.append(content)
        return ScanVerdict(
            self.status, "synthetic-test-only", "fixture-v1", "fixture_" + self.status.lower()
        )


@pytest.fixture
def actors(db_session):
    users = [
        User(
            email=f"actor{i}@example.test",
            password_hash="unused",
            full_name=f"Actor {i}",
            role=role,
        )
        for i, role in enumerate(
            [UserRole.EDUCATOR, UserRole.EDUCATOR, UserRole.STUDENT, UserRole.ADMINISTRATOR]
        )
    ]
    db_session.add_all(users)
    db_session.commit()
    return users


def test_course_restore_retains_every_revision_and_context(db_session, actors):
    owner, _, student, admin = actors
    service = LmsService(db_session)
    course = service.create_course(
        owner, CourseCreate(title="Original", description="Original description")
    )
    module = CourseModule(
        course_id=course.id, title="Module A", description="Module context", position=1
    )
    enrollment = Enrollment(course_id=course.id, student_id=student.id)
    db_session.add_all([module, enrollment])
    db_session.commit()
    service.update_course(
        owner,
        course.id,
        CourseUpdate(title="Second", description="Second description", enrollment_open=False),
    )
    service.set_course_state(owner, course.id, CourseState.ARCHIVED)
    history = service.course_revisions(owner, course.id)
    original = history[-1]
    archived = history[0]
    assert archived.context_snapshot["modules"][0]["title"] == "Module A"
    assert archived.context_snapshot["enrollments"][0]["status"] == "active"
    assert archived.metadata_snapshot["state"] == "archived"
    restored = service.restore_course(
        admin, course.id, original.id, archived.version, "Recover original details"
    )
    assert (restored.title, restored.description, restored.state, restored.enrollment_open) == (
        "Original",
        "Original description",
        CourseState.DRAFT,
        True,
    )
    db_session.expire_all()
    history = service.course_revisions(owner, course.id)
    assert [r.version for r in history] == [4, 3, 2, 1]
    assert history[0].restored_from_id == original.id
    assert history[0].actor_id == str(admin.id)
    assert history[0].reason == "Recover original details"
    assert db_session.get(Enrollment, enrollment.id).status == "active"
    assert db_session.get(CourseModule, module.id).title == "Module A"


def test_course_restore_denies_foreign_student_stale_and_foreign_revision(db_session, actors):
    owner, foreign, student, _ = actors
    service = LmsService(db_session)
    course = service.create_course(owner, CourseCreate(title="Owned"))
    original = service.course_revisions(owner, course.id)[0]
    for actor in [foreign, student]:
        with pytest.raises(LmsServiceError, match="access"):
            service.course_revisions(actor, course.id)
        with pytest.raises(LmsServiceError, match="access"):
            service.restore_course(actor, course.id, original.id, 1, "Denied")
    service.update_course(owner, course.id, CourseUpdate(title="New"))
    with pytest.raises(LmsServiceError, match="history changed"):
        service.restore_course(owner, course.id, original.id, 1, "Stale")
    db_session.rollback()
    other = service.create_course(foreign, CourseCreate(title="Other"))
    foreign_revision = service.course_revisions(foreign, other.id)[0]
    with pytest.raises(LmsServiceError, match="not found"):
        service.restore_course(owner, course.id, foreign_revision.id, 2, "Wrong course")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE course_revisions SET reason='changed'",
        "DELETE FROM course_revisions",
        "INSERT OR REPLACE INTO course_revisions SELECT * FROM course_revisions",
    ],
)
def test_course_history_is_immutable_even_through_sql(db_session, actors, statement):
    LmsService(db_session).create_course(actors[0], CourseCreate(title="Immutable"))
    with pytest.raises(IntegrityError, match="append-only"):
        db_session.execute(text(statement))


@pytest.fixture
def intake(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "material_scan_policy", "required")
    monkeypatch.setattr(settings, "material_scan_policy_version", "synthetic-policy-v1")
    config = Settings(
        material_scan_policy="required",
        material_scan_policy_version="synthetic-policy-v1",
        material_processing_retry_seconds=1,
    )
    storage = LocalFileStorage(tmp_path / "files", config.rag_max_file_bytes)
    staged = storage.stage_upload("source.pdf", io.BytesIO(b"%PDF-1.4 synthetic original bytes"))
    material = LearningMaterial(
        course_id="test-course",
        original_filename="source.pdf",
        mime_type="application/pdf",
        content_hash=staged.content_hash,
    )
    db_session.add(material)
    db_session.flush()
    material.storage_key = storage.commit(staged, material.id)
    db_session.commit()
    clock = [datetime.now(UTC)]
    extractor = StaticDocumentExtractor(
        ExtractedDocument(
            (
                ExtractedBlock(
                    0, "Approved exact source lesson text", "Heading", "Page 1", "paragraph"
                ),
            ),
            None,
            26,
        )
    )

    def processor(scanner):
        return MaterialProcessor(
            db_session,
            storage,
            {"application/pdf": extractor},
            DeterministicEmbeddingProvider(),
            InMemoryVectorStore(),
            configured_settings=config,
            now=lambda: clock[0],
            scanner=scanner,
        )

    return material, storage, config, clock, extractor, processor


@pytest.mark.parametrize(
    "scan_status,policy,expected,retry",
    [
        ("CLEAN", "disabled", "DISABLED", False),
        ("UNAVAILABLE", "required", "UNAVAILABLE", True),
        ("REJECTED", "required", "REJECTED", False),
    ],
)
def test_scanning_blocks_extraction_preserves_bytes_and_bounds_retry(
    db_session, intake, scan_status, policy, expected, retry
):
    material, storage, config, clock, extractor, processor = intake
    config.material_scan_policy = policy
    scanner = SyntheticScanner(scan_status)
    with pytest.raises(RagError):
        processor(scanner).process(material)
    db_session.refresh(material)
    assert extractor.calls == 0
    assert material.scan_status == expected
    assert (material.processing_retry_at is not None) == retry
    assert db_session.scalar(select(func.count()).select_from(MaterialChunk)) == 0
    assert db_session.scalar(select(func.count()).select_from(SourceRevision)) == 0
    with storage.open_read(material.storage_key) as source:
        assert source.read() == b"%PDF-1.4 synthetic original bytes"
    assert db_session.scalar(select(MaterialScan.status)) == expected
    with pytest.raises(RagError):
        require_clean_material(db_session, material, config)
    if retry:
        for _ in range(2):
            clock[0] += timedelta(seconds=2)
            with pytest.raises(RagError):
                processor(scanner).process(material, recover=True)
        assert material.processing_attempts == 3 and material.processing_retry_at is None
        with pytest.raises(MaterialRetryRequired):
            processor(scanner).process(material)
    config.material_scan_policy = "required"
    processor(SyntheticScanner()).process(material, force=True)
    assert material.scan_status == "CLEAN" and material.indexing_status == "indexed"


def test_clean_scan_exact_source_bindings_survive_replacement_and_policy_change(
    db_session, intake, monkeypatch
):
    material, storage, config, _, _, processor = intake
    scanner = SyntheticScanner()
    processor(scanner).process(material)
    assert scanner.seen == [b"%PDF-1.4 synthetic original bytes"]
    revision = db_session.get(SourceRevision, material.current_source_revision_id)
    passage = db_session.scalar(select(SourcePassage))
    approval = record_approval(
        db_session,
        course_id=material.course_id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id="synthetic-owner",
        state="APPROVED",
        reason="Synthetic only",
    )
    bind_sources(
        db_session,
        course_id=material.course_id,
        output_type="assessment",
        output_id="attempt-1",
        output_version="v1",
        references=[passage.id],
        strict=True,
    )
    db_session.commit()
    old_key = material.storage_key
    staged = storage.stage_upload("replacement.pdf", io.BytesIO(b"%PDF-1.4 replacement"))
    material.storage_key = storage.commit(staged, material.id)
    material.content_hash = staged.content_hash
    material.scan_status = "QUARANTINED"
    material.current_scan_id = None
    db_session.commit()
    with pytest.raises(RagError):
        processor(SyntheticScanner("REJECTED")).process(material, force=True)
    assert revision_scan_is_clean(db_session, revision)
    citation = db_session.scalar(select(SourceUse))
    assert citation.passage_id == passage.id and citation.approval_id == approval.id
    assert (
        db_session.get(SourcePassage, passage.id).chunk_text == "Approved exact source lesson text"
    )
    with storage.open_read(old_key) as original:
        assert original.read() == scanner.seen[0]
    monkeypatch.setattr(settings, "material_scan_policy_version", "new-policy")
    assert not revision_scan_is_clean(db_session, revision)
    with pytest.raises(RagError, match="successful malware scan"):
        record_approval(
            db_session,
            course_id=material.course_id,
            material_id=material.id,
            revision_id=revision.id,
            actor_id="owner",
            state="APPROVED",
            reason="New approval",
        )
    assert (
        db_session.get(SourcePassage, passage.id).chunk_text == "Approved exact source lesson text"
    )


def test_hash_mismatch_never_reaches_scanner_or_extractor(db_session, intake):
    material, storage, _, _, _, processor = intake
    (storage.upload_dir / material.storage_key).write_bytes(b"%PDF-1.4 tampered")
    scanner = SyntheticScanner()
    with pytest.raises(RagError, match="quarantined"):
        processor(scanner).process(material)
    assert scanner.seen == []
    assert db_session.scalar(select(MaterialScan.code)) == "source_integrity_mismatch"
    assert db_session.scalar(select(func.count()).select_from(MaterialChunk)) == 0


@pytest.mark.parametrize(
    "exit_code,output,stderr,expected",
    [
        (0, "OK", b"", "CLEAN"),
        (1, "FOUND", b"", "REJECTED"),
        (2, "ERROR", b"error", "UNAVAILABLE"),
        (0, "SKIPPED", b"", "UNAVAILABLE"),
        (0, "OK", b"warning", "UNAVAILABLE"),
    ],
)
def test_local_clamav_contract_is_fail_closed(
    tmp_path, monkeypatch, exit_code, output, stderr, expected
):
    executable = tmp_path / "clamscan.exe"
    executable.write_bytes(b"synthetic subprocess placeholder")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if "--version" in args:
            return subprocess.CompletedProcess(args, 0, b"ClamAV 1.4.3/123/date\n", b"")
        assert "--alert-exceeds-max=yes" in args
        assert "--fail-if-cvd-older-than=7" in args
        assert kwargs["timeout"] == 60
        return subprocess.CompletedProcess(
            args, exit_code, f"{args[-1]}: {output}\n".encode(), stderr
        )

    monkeypatch.setattr(subprocess, "run", run)
    result = ClamAvScanner(Settings(material_clamscan_path=str(executable))).scan(b"synthetic")
    assert result.status == expected and len(calls) == 2


def test_missing_or_timed_out_clamav_is_unavailable(tmp_path, monkeypatch):
    assert ClamAvScanner(Settings()).scan(b"test").status == "UNAVAILABLE"
    executable = tmp_path / "scanner.exe"
    executable.write_bytes(b"synthetic")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("synthetic", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert (
        ClamAvScanner(Settings(material_clamscan_path=str(executable))).scan(b"test").status
        == "UNAVAILABLE"
    )


def test_legacy_approved_task_stays_readable_but_new_publication_and_restore_are_gated(
    db_session, intake, monkeypatch
):
    from support.task_review import approve_fixture_task

    from app.models import Course, LearningTask
    from app.services.lms import bootstrap_demo
    from app.services.task_review import TaskReviewError, TaskReviewService

    users, course = bootstrap_demo(db_session)
    owner = next(user for user in users if user.role is UserRole.EDUCATOR)
    material, _, _, _, _, processor = intake
    material.course_id = course.id
    db_session.commit()
    processor(SyntheticScanner()).process(material)
    revision = db_session.get(SourceRevision, material.current_source_revision_id)
    passage = db_session.scalar(select(SourcePassage))
    record_approval(
        db_session,
        course_id=course.id,
        material_id=material.id,
        revision_id=revision.id,
        actor_id=str(owner.id),
        state="APPROVED",
        reason="Synthetic source",
    )
    tasks = list(
        db_session.scalars(select(LearningTask).where(LearningTask.course_id == course.id))
    )
    tasks[0].source_references = [passage.id]
    db_session.commit()
    for task in tasks:
        approve_fixture_task(db_session, task)
    service = LmsService(db_session)
    service.set_course_state(owner, course.id, CourseState.PUBLISHED)
    published = service.course_revisions(owner, course.id)[0]
    service.set_course_state(owner, course.id, CourseState.ARCHIVED)
    latest = service.course_revisions(owner, course.id)[0]
    monkeypatch.setattr(settings, "material_scan_policy_version", "changed-policy")
    review = TaskReviewService(db_session)
    assert review.summary(tasks[0])["available"]
    assert review.history(owner, tasks[0].id)
    with pytest.raises(TaskReviewError, match="malware scan"):
        review.validate_ready(tasks[0])
    with pytest.raises(LmsServiceError, match="malware scan"):
        service.restore_course(owner, course.id, published.id, latest.version, "Restore published")
    db_session.rollback()
    assert db_session.get(Course, course.id).state == CourseState.ARCHIVED
    assert service.course_revisions(owner, course.id)[0].id == latest.id


def test_api_history_access_and_quarantined_binary_are_separate(db_session, actors, intake):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.api.routes.lms import get_lms_material_storage
    from app.db.session import get_db
    from app.main import create_app

    owner, foreign, student, _ = actors
    service = LmsService(db_session)
    course = service.create_course(owner, CourseCreate(title="API course"))
    material, storage, _, _, _, _ = intake
    material.course_id = course.id
    db_session.commit()
    app = create_app()
    actor = [owner]
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: actor[0]
    app.dependency_overrides[get_lms_material_storage] = lambda: storage
    with TestClient(app) as client:
        path = f"/api/v1/courses/{course.id}"
        history = client.get(path + "/revisions")
        assert history.status_code == 200
        revision_id = history.json()[0]["id"]
        assert client.get(path + f"/revisions/{revision_id}").status_code == 200
        assert client.get(path + f"/materials/{material.id}/content").status_code == 409
        for other in [foreign, student]:
            actor[0] = other
            assert client.get(path + "/revisions").status_code == 403
            assert (
                client.post(
                    path + f"/revisions/{revision_id}/restore",
                    json={"expected_version": 1, "reason": "Forbidden restore"},
                ).status_code
                == 403
            )


def test_scan_receipts_are_append_only(db_session, intake):
    material, _, _, _, _, processor = intake
    processor(SyntheticScanner()).process(material)
    with pytest.raises(IntegrityError, match="append-only"):
        db_session.execute(text("UPDATE material_scans SET status='REJECTED'"))


def test_https_link_is_saved_and_quarantined_before_html_extraction(
    db_session, actors, tmp_path, monkeypatch
):
    from support.material_scanning import enable_synthetic_scanning

    from app.schemas.lms import MaterialLinkCreate
    from app.services.material_indexing import OfflineMaterialProcessor
    from app.services.rag.web import DownloadedMaterial, SafeHttpsFetcher

    enable_synthetic_scanning(monkeypatch)
    monkeypatch.setattr(settings, "rag_upload_dir", str(tmp_path / "links"))
    content = b"<html><p>Hadamard prepares a useful superposition of quantum states.</p></html>"
    monkeypatch.setattr(
        SafeHttpsFetcher, "fetch", lambda self, url: DownloadedMaterial(url, "source.html", content)
    )
    service = LmsService(db_session)
    course = service.create_course(actors[0], CourseCreate(title="Linked sources"))
    material = service.register_material_link(
        actors[0], course.id, MaterialLinkCreate(source_url="https://example.test/lesson")
    )
    assert material.scan_status == "QUARANTINED"
    storage = LocalFileStorage(settings.rag_upload_dir, settings.rag_max_file_bytes)
    with storage.open_read(material.storage_key) as source:
        assert source.read() == content
    OfflineMaterialProcessor(db_session, storage).process(material)
    assert material.scan_status == "CLEAN"
    assert "Hadamard" in db_session.scalar(select(SourcePassage.chunk_text))


def test_frozen_form_remains_readable_when_policy_changes_but_new_form_review_is_blocked(
    db_session, monkeypatch
):
    from support.assessment_review import seed_review_context
    from support.material_scanning import enable_synthetic_scanning

    from app.models import LearningTask
    from app.models.assessment import TaskFormVersion
    from app.services.assessment.publication import (
        current_form_review,
        require_learner_task_available,
    )
    from app.services.task_review import TaskReviewError

    enable_synthetic_scanning(monkeypatch)
    context = seed_review_context(db_session)
    task = db_session.get(LearningTask, context["task_id"])
    form = db_session.scalar(
        select(TaskFormVersion).where(TaskFormVersion.learning_task_id == task.id)
    )
    monkeypatch.setattr(settings, "material_scan_policy", "disabled")
    require_learner_task_available(db_session, task)
    with pytest.raises(TaskReviewError, match="malware scan"):
        current_form_review(db_session, form)
    passage = db_session.get(SourcePassage, task.source_references[0])
    revision = db_session.get(SourceRevision, passage.revision_id)
    record_approval(
        db_session,
        course_id=task.course_id,
        material_id=revision.material_id,
        revision_id=revision.id,
        actor_id="fixture-owner",
        state="REVOKED",
        reason="Synthetic revocation",
    )
    db_session.commit()
    with pytest.raises(TaskReviewError):
        require_learner_task_available(db_session, task)


def test_synthetic_fixture_scope_restores_policy_and_keeps_per_test_overrides():
    from support.material_scanning import synthetic_scanning_scope

    from app.services import material_scanning

    original = (
        settings.material_scan_policy,
        settings.material_scan_policy_version,
        material_scanning.configured_scanner,
    )
    with synthetic_scanning_scope():
        assert settings.material_scan_policy == "required"
        with pytest.MonkeyPatch.context() as per_test:
            per_test.setattr(settings, "material_scan_policy", "disabled")
            assert settings.material_scan_policy == "disabled"
        assert settings.material_scan_policy == "required"
    assert (
        settings.material_scan_policy,
        settings.material_scan_policy_version,
        material_scanning.configured_scanner,
    ) == original


@pytest.mark.parametrize("operation", ["duplicate_update", "reused_code_restore"])
def test_course_code_conflict_returns_409_without_partial_history_or_metadata(
    db_session, actors, operation
):
    from fastapi.testclient import TestClient

    from app.api.dependencies.authentication import get_current_user
    from app.db.session import get_db
    from app.main import create_app

    owner = actors[0]
    service = LmsService(db_session)
    course = service.create_course(owner, CourseCreate(code="ORIGINAL", title="Original title"))
    original = service.course_revisions(owner, course.id)[0]
    if operation == "duplicate_update":
        service.create_course(owner, CourseCreate(code="TAKEN", title="Other course"))
    else:
        service.update_course(
            owner,
            course.id,
            CourseUpdate(code="CURRENT", title="Current title", enrollment_open=False),
        )
        service.create_course(owner, CourseCreate(code="ORIGINAL", title="Reused code"))
    current_version = service.course_revisions(owner, course.id)[0].version

    def stored_records():
        return {
            table: db_session.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in ("courses", "course_revisions", "platform_audit_events")
        }

    before = stored_records()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        path = f"/api/v1/courses/{course.id}"
        if operation == "duplicate_update":
            response = client.patch(
                path, json={"code": "TAKEN", "title": "Must not persist", "enrollment_open": False}
            )
        else:
            response = client.post(
                path + f"/revisions/{original.id}/restore",
                json={"expected_version": current_version, "reason": "Recover original wording"},
            )
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "The change conflicts with an existing record"
        # The same session is usable immediately; no caller rollback is needed.
        db_session.expire_all()
        assert stored_records() == before
        assert client.get(path).status_code == 200
