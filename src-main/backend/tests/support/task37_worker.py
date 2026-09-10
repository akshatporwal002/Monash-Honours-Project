"""Owned synthetic worker process; pause only after the durable feedback claim."""

import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.worker import build_database_worker, build_offline_worker_adapters


class PauseAfterClaim:
    def __init__(self, marker):
        self.marker = marker

    def attach_progress_recorder(self, recorder):
        pass

    def attach_audit_events(self, audit):
        pass

    async def run(self, submission_id, workflow_id, **kwargs):
        with self.marker.open("x", encoding="utf-8") as output:
            json.dump({"submission_id": submission_id, "workflow_id": workflow_id}, output)
        await asyncio.Event().wait()


def validate_synthetic_config(config, directory):
    from sqlalchemy.engine import make_url

    root = directory.resolve(strict=True)
    url = make_url(config.database_url)
    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or Path(url.database).resolve() != root / "study.sqlite"
        or not (root / "study.sqlite").is_file()
        or not (root / "uploads").is_dir()
        or Path(config.rag_upload_dir).resolve() != root / "uploads"
        or config.app_env != "test"
        or config.research_enabled
        or config.llm_provider != "local"
        or (config.llm_api_key and config.llm_api_key.get_secret_value())
        or config.llm_api_base_url != "https://127.0.0.1:1"
    ):
        raise ValueError("Task 37 worker requires its isolated synthetic configuration")
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--pause", action="store_true")
    args = parser.parse_args()
    config = Settings(_env_file=None)
    root = validate_synthetic_config(config, args.directory)
    adapters = build_offline_worker_adapters(config)
    if args.pause:
        adapters = replace(
            adapters, feedback_pipeline_factory=lambda repo: PauseAfterClaim(root / "claimed.json")
        )
    engine = create_db_engine(config.database_url)
    try:
        worker = build_database_worker(
            adapters,
            configured_settings=config,
            engine=engine,
            session_factory=create_session_factory(engine),
        )
        asyncio.run(worker.run_forever())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
