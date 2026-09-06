"""Disposable fault injection at the real worker's claimed feedback boundary."""

import asyncio
import sys
from dataclasses import replace
from pathlib import Path

from app.core.config import settings
from app.worker import build_database_worker, load_worker_adapters


class PausedPipeline:
    def attach_progress_recorder(self, recorder):
        pass

    def attach_audit_events(self, events):
        pass

    async def run(self, *args, **kwargs):
        Path(sys.argv[1]).write_text("claimed", encoding="utf-8")
        await asyncio.Event().wait()


if __name__ == "__main__":
    adapters = load_worker_adapters(settings.worker_adapter_factory, settings)
    adapters = replace(adapters, feedback_pipeline_factory=lambda repository: PausedPipeline())
    asyncio.run(build_database_worker(adapters).run_forever())
