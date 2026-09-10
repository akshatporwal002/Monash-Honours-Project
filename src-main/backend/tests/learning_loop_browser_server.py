"""Disposable localhost app using real authentication, providers and worker."""

import asyncio
import os
import sys
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH_ROOT = ROOT / ".tmp-q25"
SCRATCH_ROOT.mkdir(exist_ok=True)
SCRATCH = Path(tempfile.mkdtemp(prefix="b-", dir=SCRATCH_ROOT))
API_PORT = int(os.environ.get("QUANTUMLEARN_E2E_API_PORT", "4180"))
WEB_PORT = int(os.environ.get("QUANTUMLEARN_E2E_WEB_PORT", "4173"))
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN=f"http://127.0.0.1:{WEB_PORT}",
    CORS_ALLOWED_ORIGINS=f"http://127.0.0.1:{WEB_PORT}",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
    WORKER_ADAPTER_FACTORY="app.worker:build_offline_worker_adapters",
    LEARNING_EVENT_PSEUDONYM_SECRET="learning-loop-test-only-pseudonym-secret-32-bytes",
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    import uvicorn
    from alembic import command
    from alembic.config import Config
    from fastapi import HTTPException
    from sqlalchemy import select
    from support.learning_loop import seed_learning_loop

    from app.db.session import SessionLocal
    from app.main import create_app
    from app.models.activity_continuation import ActivityProgress, ActivitySuggestion
    from app.models.learning_evidence import LearningEvidence
    from app.models.persistence import WorkflowRun
    from app.worker import create_configured_worker

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    app = create_app()
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            # The worker owns its event loop, as it does in the separate CLI process.
            loop = asyncio.new_event_loop()
            stop = asyncio.Event()
            worker = create_configured_worker()
            thread = threading.Thread(
                target=lambda: loop.run_until_complete(worker.run_forever(stop)), daemon=True
            )
            thread.start()
            try:
                yield
            finally:
                loop.call_soon_threadsafe(stop.set)
                thread.join(timeout=30)
                if not thread.is_alive():
                    loop.close()

    app.router.lifespan_context = lifespan

    @app.post("/e2e/misconception-fixture")
    def misconception_fixture():
        from support.misconceptions import seed_misconception_context

        with SessionLocal() as session:
            return seed_misconception_context(session)

    @app.post("/e2e/learning-loop-fixture")
    def fixture():
        with SessionLocal() as session:
            return seed_learning_loop(session)

    @app.get("/e2e/learning-loop/{response_id}/evidence")
    def evidence(response_id: str):
        with SessionLocal() as session:
            workflow = session.scalar(
                select(WorkflowRun).where(WorkflowRun.submission_id == response_id)
            )
            progress = session.get(ActivityProgress, workflow.id) if workflow else None
            if progress is None:
                raise HTTPException(404, "Continuation has not completed")
            rows = session.scalars(
                select(LearningEvidence).where(LearningEvidence.id.in_(progress.evidence_ids))
            ).all()
            suggestion = session.get(ActivitySuggestion, workflow.id)
            return {
                "snapshot_id": progress.snapshot_id,
                "evidence_types": sorted({item.evidence_type.value for item in rows}),
                "workflow_id": workflow.id,
                "next_task_id": suggestion.task_id if suggestion else None,
            }

    uvicorn.run(app, host="127.0.0.1", port=API_PORT)


if __name__ == "__main__":
    main()
