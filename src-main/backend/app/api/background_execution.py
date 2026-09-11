"""Keep session-owning background executors off the foreground API event loop."""

import asyncio

import anyio
from fastapi import Request


async def run_session_work(function, *args, limiter=None):
    """Do not let request cleanup race a still-running synchronous session user."""
    with anyio.CancelScope(shield=True):
        worker = asyncio.create_task(anyio.to_thread.run_sync(function, *args, limiter=limiter))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation:
            # Task.cancel() bypasses AnyIO's cancellation scopes. Drain the
            # worker before the caller can close or reuse its session, including
            # repeated cancellations during graceful request shutdown.
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
            try:
                worker.result()
            finally:
                raise cancellation


async def get_background_limiter(request: Request) -> anyio.CapacityLimiter:
    # Separate from the foreground dependency/route thread limit. SQLite still
    # serializes writers; queued jobs retain their existing durable leases.
    if not hasattr(request.app.state, "database_background_limiter"):
        request.app.state.database_background_limiter = anyio.CapacityLimiter(4)
    return request.app.state.database_background_limiter


class ThreadedBackgroundExecutor:
    """Run the complete existing executor/session lifetime on one worker thread."""

    def __init__(self, executor, limiter: anyio.CapacityLimiter):
        self._executor = executor
        self._limiter = limiter

    async def execute(self, *args) -> None:
        def run():
            asyncio.run(self._executor.execute(*args))

        # asyncio.run closes the job loop; the existing executor owns and closes
        # its sessions. AnyIO manages worker thread cleanup with the API loop.
        await run_session_work(run, limiter=self._limiter)
