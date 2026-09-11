"""Synthetic localhost fixture with ordinary authentication and curriculum services."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task21" / os.environ.get("TASK21_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5271",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


from support.material_scanning import synthetic_scanning_scope  # noqa: E402


@synthetic_scanning_scope()
def main():
    import uvicorn
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session
    from support.curriculum import setup_curriculum

    from app.db.session import engine
    from app.main import create_app

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        _, teacher, student, course, tasks, _, path = setup_curriculum(session)
        (SCRATCH / "context.json").write_text(
            json.dumps(
                {
                    "student_email": student.email,
                    "teacher_email": teacher.email,
                    "course_id": course.id,
                    "course_title": course.title,
                    "pathway_id": path.id,
                    "outcome_id": path.outcome_id,
                    "target_id": tasks[-1].id,
                }
            ),
            encoding="utf-8",
        )
    uvicorn.run(create_app(), host="127.0.0.1", port=8171)


if __name__ == "__main__":
    main()
