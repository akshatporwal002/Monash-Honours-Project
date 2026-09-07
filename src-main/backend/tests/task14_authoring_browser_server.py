"""Isolated synthetic educator fixture for the episode authoring browser journey."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task14" / os.environ.get("TASK14_AUTHORING_RUN", "authoring")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'authoring.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5240",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from support.task_review import approve_fixture_task
    from test_assessment_definitions import _setup

    from app.db.session import engine
    from app.models.enums import TaskType
    from app.models.persistence import LearningTask

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        course_id, outcome_id, _, _ = _setup(session)
        task = session.scalar(select(LearningTask).where(LearningTask.course_id == course_id))
        task.task_type = TaskType.QUANTUM_CIRCUIT
        task.marking_criteria = {
            "required_gates": ["h"],
            "starter_circuit": {"qubits": 1, "operations": []},
        }
        session.commit()
        approve_fixture_task(session, task)
        (SCRATCH / "context.json").write_text(
            json.dumps({"course_id": course_id, "outcome_id": outcome_id, "task_id": task.id}),
            encoding="utf-8",
        )
    import uvicorn

    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8140)


if __name__ == "__main__":
    main()
