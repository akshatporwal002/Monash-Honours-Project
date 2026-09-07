"""Isolated synthetic Task 12 browser fixture, with ordinary application policies.

Run from the backend: python -m tests.task12_browser_server
The database stays in the ignored task scratch directory for evidence checks.
No live credentials, provider calls, role grants, or approvals are imported.
"""

import hashlib
import os
from pathlib import Path
from uuid import uuid4


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    scratch = root / ".tmp-task12" / f"browser-{uuid4()}"
    scratch.mkdir(parents=True)
    database_url = f"sqlite:///{(scratch / 'browser.db').as_posix()}"
    os.environ.update(
        DATABASE_URL=database_url,
        APP_ENV="development",
        FRONTEND_ORIGIN="http://localhost:5173",
        RAG_UPLOAD_DIR=str(scratch / "uploads"),
        LLM_API_KEY="",
        RESEARCH_ENABLED="false",
    )

    import uvicorn
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.main import create_app
    from app.models import LearningMaterial, LearningTask
    from app.models.source_history import SourcePassage, SourceRevision
    from app.services.lms import bootstrap_demo
    from app.services.task_review import TaskReviewService

    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    with SessionLocal() as session:
        _, course = bootstrap_demo(session)
        passage_text = "A Hadamard gate applied to zero gives equal measurement probabilities for zero and one."
        digest = hashlib.sha256(passage_text.encode()).hexdigest()
        material = LearningMaterial(
            course_id=course.id,
            original_filename="Synthetic Hadamard lesson.txt",
            content_hash=digest,
            mime_type="text/plain",
        )
        session.add(material)
        session.flush()
        revision = SourceRevision(
            material_id=material.id,
            course_id=course.id,
            version=1,
            source_label="Synthetic Hadamard lesson",
            mime_type="text/plain",
            content_hash=digest,
            extracted_blocks=[],
            extraction_version="synthetic-browser-fixture-v1",
            provenance="EXTRACTED",
        )
        session.add(revision)
        session.flush()
        passage = SourcePassage(
            id=str(uuid4()),
            revision_id=revision.id,
            course_id=course.id,
            chunk_index=0,
            chunk_text=passage_text,
            chunk_hash=digest,
        )
        session.add(passage)
        session.flush()
        for task in session.scalars(
            select(LearningTask).where(LearningTask.course_id == course.id)
        ):
            task.source_references = [passage.id]
            TaskReviewService(session).capture(task)
        session.commit()
    print(f"Synthetic browser evidence directory: {scratch}", flush=True)
    uvicorn.run(create_app(), host="127.0.0.1", port=8000, access_log=False)


if __name__ == "__main__":
    main()
