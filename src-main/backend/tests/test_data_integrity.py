from concurrent.futures import ThreadPoolExecutor
from json import loads
from pathlib import Path
from threading import Barrier

from sqlalchemy import Engine, select

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.models import LearningTask, SubmissionAttempt, User
from app.schemas.lms import SubmissionCreate
from app.services.lms import LmsService, bootstrap_demo
from scripts.verify_sqlite_backup import create_verified_backup, database_manifest


def _seed_database(database_path: Path) -> tuple[Engine, str]:
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        bootstrap_demo(session)
        task_id = session.scalar(select(LearningTask.id).order_by(LearningTask.position))
    assert task_id is not None
    return engine, task_id


def test_concurrent_submissions_receive_one_consistent_attempt_sequence(
    tmp_path: Path,
) -> None:
    engine, task_id = _seed_database(tmp_path / "concurrent-submissions.db")
    factory = create_session_factory(engine)
    worker_count = 8
    start = Barrier(worker_count)

    def submit(worker_number: int) -> tuple[int, str]:
        with factory() as session:
            student = session.scalar(select(User).where(User.email == "student@quantumlearn.demo"))
            assert student is not None
            start.wait(timeout=10)
            attempt = LmsService(session).submit(
                student,
                task_id,
                SubmissionCreate(answer="b", code=f"# worker {worker_number}"),
            )
            return attempt.attempt_number, attempt.id

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(submit, range(worker_count)))

    assert sorted(number for number, _ in results) == list(range(1, worker_count + 1))
    assert len({attempt_id for _, attempt_id in results}) == worker_count
    with factory() as session:
        stored = list(
            session.scalars(
                select(SubmissionAttempt)
                .where(SubmissionAttempt.task_id == task_id)
                .order_by(SubmissionAttempt.attempt_number)
            )
        )
        assert [attempt.attempt_number for attempt in stored] == list(range(1, worker_count + 1))
        assert len({attempt.feedback_reference for attempt in stored}) == worker_count
        assert {attempt.code for attempt in stored} == {
            f"# worker {worker_number}" for worker_number in range(worker_count)
        }
    engine.dispose()


def test_verified_backup_restore_reproduces_every_record(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "verification-source.db"
    engine, task_id = _seed_database(database_path)
    factory = create_session_factory(engine)
    with factory() as session:
        student = session.scalar(select(User).where(User.email == "student@quantumlearn.demo"))
        assert student is not None
        LmsService(session).submit(
            student,
            task_id,
            SubmissionCreate(answer="b"),
        )
    engine.dispose()

    result = create_verified_backup(database_path, tmp_path / "backups")
    source_manifest = database_manifest(database_path)
    backup_manifest = database_manifest(result.backup_path)

    assert backup_manifest == source_manifest
    assert result.record_count == sum(item.row_count for item in source_manifest.values())
    assert result.table_count == len(source_manifest)
    assert backup_manifest["submission_attempts"].row_count == 1
    assert backup_manifest["learning_events"].row_count >= 1
    assert backup_manifest["platform_audit_events"].row_count >= 1

    recorded = loads(result.manifest_path.read_text(encoding="utf-8"))
    assert recorded["dataset_digest"] == result.dataset_digest
    assert recorded["record_count"] == result.record_count
    assert recorded["tables"]["submission_attempts"]["row_count"] == 1
