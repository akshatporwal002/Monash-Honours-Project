"""Pause a real worker after its committed model receipt so a test can kill it."""

import asyncio
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from app.core.config import Settings
from app.db.session import create_db_engine, create_session_factory
from app.services.continuation.activity import ApprovedActivityAdapter
from app.worker import build_database_worker, build_offline_worker_adapters


class PauseAfterProgress(ApprovedActivityAdapter):
    def bind(self, session_factory, now):
        return PauseAfterProgress(session_factory, now=now)

    async def record_terminal_feedback(self, request):
        await super().record_terminal_feedback(request)
        Path(sys.argv[3]).write_text("Model receipt committed", encoding="utf-8")
        await asyncio.Event().wait()


def main():
    database_url, clock = sys.argv[1:3]
    now = datetime.fromisoformat(clock)
    config = Settings(_env_file=None, database_url=database_url, research_enabled=False)
    engine = create_db_engine(database_url)
    adapters = replace(build_offline_worker_adapters(config), progress_adapter=PauseAfterProgress())
    worker = build_database_worker(
        adapters,
        configured_settings=config,
        engine=engine,
        session_factory=create_session_factory(engine),
        now=lambda: now,
    )
    try:
        asyncio.run(worker.run_forever())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
