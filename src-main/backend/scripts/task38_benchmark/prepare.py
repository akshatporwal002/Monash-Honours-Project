"""Later, opt-in preparation of a NEW local synthetic database. Never run on learner data."""

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, help="New, absent scratch directory")
    parser.add_argument("--learners", required=True, type=int)
    parser.add_argument("--ack-synthetic-only", action="store_true")
    args = parser.parse_args()
    if not args.ack_synthetic_only or not 1 <= args.learners <= 10000:
        parser.error("Explicit synthetic acknowledgement and 1–10000 learners required")
    directory = Path(args.directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    backend = Path(__file__).resolve().parents[2]
    database = directory / "task38-synthetic.sqlite"
    environment = {
        **os.environ,
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "LLM_API_KEY": "",
        "RESEARCH_ENABLED": "false",
        "APP_ENV": "development",
        "RAG_UPLOAD_DIR": str(directory / "uploads"),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend,
        env=environment,
        check=True,
    )
    os.environ.update(
        {
            key: environment[key]
            for key in (
                "DATABASE_URL",
                "LLM_API_KEY",
                "RESEARCH_ENABLED",
                "APP_ENV",
                "RAG_UPLOAD_DIR",
            )
        }
    )
    sys.path.insert(0, str(backend / "tests"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from support.learning_loop import seed_learning_loop

    from app.core.security import hash_password
    from app.models.lms import Enrollment
    from app.models.persistence import StudentProfile
    from app.models.user import User, UserRole

    from .fake import FIXTURE

    template = json.loads(FIXTURE.read_text(encoding="utf-8"))
    engine = create_engine(environment["DATABASE_URL"])
    with Session(engine) as session:
        fixture = seed_learning_loop(session)
        rows = [
            {
                **template,
                **{
                    k: fixture[k]
                    for k in (
                        "student_email",
                        "student_password",
                        "task_id",
                        "course_id",
                        "form_id",
                    )
                },
            }
        ]
        for _ in range(args.learners - 1):
            password = str(uuid4())
            user = User(
                email=f"task38-{uuid4().hex}@example.invalid",
                full_name="Synthetic Task 38 learner",
                password_hash=hash_password(password),
                role=UserRole.STUDENT,
            )
            session.add(user)
            session.flush()
            session.add(StudentProfile(user_id=user.id, display_name=user.full_name))
            session.add(Enrollment(course_id=fixture["course_id"], student_id=user.id))
            rows.append(
                {
                    **copy.deepcopy(rows[0]),
                    "student_email": user.email,
                    "student_password": password,
                }
            )
        session.commit()
    engine.dispose()
    (directory / "roster.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    # Private fixture receipt for the human assessor; keep out of benchmark reports.
    (directory / "fixture-private.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"Synthetic-only fixture prepared at {directory}; no server or campaign started.")


if __name__ == "__main__":
    main()
