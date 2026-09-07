"""Task 14 synthetic approved local browser fixture. No live assessment approval."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task14" / os.environ.get("TASK14_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5244",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT / "tests"))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "fail-next":
        (SCRATCH / "fail-next").write_text("Controlled synthetic timeout")
        return
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session
    from test_task14_lifecycle import setup_episode

    from app.db.session import engine

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        _, student, task, started = setup_episode(session)
        (SCRATCH / "context.json").write_text(
            json.dumps(
                {
                    "student_email": student.email,
                    "task_id": task.id,
                    "work_id": started.assessment_work_start_id,
                }
            )
        )
    import app.services.simulation_evidence as simulation_module
    from app.services.quantum import QuantumSimulationError

    actual = simulation_module.simulate_circuit

    def controlled(**kwargs):
        marker = SCRATCH / "fail-next"
        if marker.exists():
            marker.unlink()
            raise QuantumSimulationError("Controlled synthetic timeout", code="simulation_timeout")
        return actual(**kwargs)

    simulation_module.simulate_circuit = controlled
    import uvicorn

    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8144)


if __name__ == "__main__":
    main()
