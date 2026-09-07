"""Synthetic localhost Task 13 journey using normal authentication and policies.

Run from backend with PYTHONPATH including its tests directory. Seed/serve creates
an isolated database; republish records a real replacement definition approval.
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task13" / os.environ.get("TASK13_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5233",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from dataclasses import replace

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session
    from test_assessment_definitions import _draft
    from test_assessment_work_starts import republish, setup_work

    from app.db.session import engine
    from app.models.assessment import AssessmentDefinitionVersion, TaskFormVersion
    from app.models.persistence import LearningTask
    from app.models.user import User

    if len(sys.argv) > 1 and sys.argv[1] == "republish":
        data = json.loads((SCRATCH / "context.json").read_text())
        with Session(engine) as session:
            definition = session.get(AssessmentDefinitionVersion, data["definition_id"])
            form = session.get(TaskFormVersion, data["form_id"])
            draft = replace(
                _draft(outcome_version_id=definition.outcome_version_id, task_id=data["task_id"]),
                formal_result_eligible=True,
                instructional_support={"supported_stage": "unlimited approved conceptual hints"},
                transfer_rule={"required": True, "new_context": "fresh unaided circuit"},
            )
            new_form = republish(
                session,
                (
                    session.get(User, data["student_id"]),
                    session.get(LearningTask, data["task_id"]),
                    form,
                    definition,
                    draft,
                    definition.owner_user_id,
                ),
            )
            print(json.dumps({"replacement_form_id": new_form.id}))
        return
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        student, task, form, definition, _, _ = setup_work(session)
        data = {
            "student_id": student.id,
            "task_id": task.id,
            "form_id": form.id,
            "definition_id": definition.id,
            "student_email": student.email,
        }
        (SCRATCH / "context.json").write_text(json.dumps(data))
    import uvicorn

    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8133)


if __name__ == "__main__":
    main()
