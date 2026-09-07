"""Synthetic Task 15 assessor journey with ordinary authentication and real services."""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".tmp-task15" / os.environ.get("TASK15_BROWSER_RUN", "browser")
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(SCRATCH / 'browser.db').as_posix()}",
    APP_ENV="development",
    FRONTEND_ORIGIN="http://localhost:5255",
    RAG_UPLOAD_DIR=str(SCRATCH / "uploads"),
    LLM_API_KEY="",
    RESEARCH_ENABLED="false",
)
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session, sessionmaker
    from test_task15_migrated_review import setup_human

    from app.db.session import engine
    from app.services.assessment.jobs import (
        AssessmentEvaluationApplication,
        AssessmentEvaluationExecutor,
        SqlAlchemyAssessmentEvaluationJobRepository,
    )
    from app.services.assessment.runtime import build_assessment_evaluation_service

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    command.upgrade(config, "head")
    with Session(engine) as session:
        service, assessor, attempt, original_id = setup_human(
            session, revision=True, simulation_status="completed"
        )
        data = {
            "assessor_email": assessor.email,
            "attempt_id": attempt.id,
            "course_id": attempt.course_id,
            "original_response_id": original_id,
        }
        claim = AssessmentEvaluationApplication(
            SqlAlchemyAssessmentEvaluationJobRepository(session)
        ).start(attempt.response_version_id)
        asyncio.run(
            AssessmentEvaluationExecutor(
                sessionmaker(bind=engine), build_assessment_evaluation_service
            ).execute(claim)
        )
        detail = service.detail(assessor, assessment_attempt_id=attempt.id)
        assert detail["job_state"].value == "review_required"
        assert detail["can_finalise"]
        data["frozen_prompt"] = detail["frozen_context"].supported_prompt
        data["transfer_prompt"] = detail["frozen_context"].transfer_prompt
        data["historical_run_id"] = detail["historical_evidence"][0].simulations[0]["run_id"]
        (SCRATCH / "context.json").write_text(json.dumps(data), encoding="utf-8")
    import uvicorn

    from app.main import create_app

    uvicorn.run(create_app(), host="127.0.0.1", port=8155)


if __name__ == "__main__":
    main()
