"""Task 16 localhost fixture using ordinary source, task, and assessment approval."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task16" / os.environ.get("TASK16_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5266",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT / "tests"))


def prepare():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session
    from support.task16 import setup_task16_episode
    from test_task14_lifecycle import complete

    from app.db.session import engine

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        lms, student, task, started = setup_task16_episode(session)
        draft = complete(lms, student, task, started)
        lms.save_draft(student, task.id, draft)
        data = {
            "student_email": student.email,
            "task_id": task.id,
            "course_id": task.course_id,
            "work_id": started.assessment_work_start_id,
            "source_ids": task.source_references,
            "supported_answer": draft.answer,
            "reflection": draft.episode.supported.reflection,
        }
        assert data["source_ids"]
        (SCRATCH / "context.json").write_text(json.dumps(data), encoding="utf-8")
        return data


def main():
    prepare()
    if "--prepare-only" in sys.argv:
        return
    import uvicorn

    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8166)


if __name__ == "__main__":
    main()
