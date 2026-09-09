"""Synthetic localhost fixture with ordinary authentication and preference services."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task20" / os.environ.get("TASK20_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5270",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    import uvicorn
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from support.task16 import setup_task16_episode

    from app.db.session import engine
    from app.main import create_app
    from app.models.persistence import LearningTask

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        _, student, task, _ = setup_task16_episode(session)
        practice = session.scalar(
            select(LearningTask).where(LearningTask.task_type == "multiple_choice")
        )
        (SCRATCH / "context.json").write_text(
            json.dumps(
                {
                    "student_email": student.email,
                    "task_id": task.id,
                    "practice_id": practice.id if practice else None,
                }
            ),
            encoding="utf-8",
        )
    uvicorn.run(create_app(), host="127.0.0.1", port=8170)


if __name__ == "__main__":
    main()
