"""POST body replay preserves size limits and real disconnect delivery."""

import asyncio

import pytest

from app.core.security import RequestSizeLimitMiddleware


def test_replayed_body_waits_for_real_disconnect():
    async def scenario():
        disconnected = asyncio.Event()
        replayed = asyncio.Event()
        original_calls = 0
        received = []

        async def receive():
            nonlocal original_calls
            original_calls += 1
            if original_calls == 1:
                return {"type": "http.request", "body": b"{}", "more_body": False}
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def app(scope, downstream_receive, send):
            received.append(await downstream_receive())
            replayed.set()
            received.append(await downstream_receive())

        async def send(message):
            pass

        task = asyncio.create_task(
            RequestSizeLimitMiddleware(app, maximum_bytes=100)(
                {"type": "http", "method": "POST", "headers": []}, receive, send
            )
        )
        await asyncio.wait_for(replayed.wait(), timeout=1)
        assert not task.done()
        disconnected.set()
        await asyncio.wait_for(task, timeout=1)
        assert original_calls == 2
        assert received == [
            {"type": "http.request", "body": b"{}", "more_body": False},
            {"type": "http.disconnect"},
        ]

    asyncio.run(scenario())


@pytest.mark.parametrize("declared", [False, True])
def test_oversized_declared_or_streamed_body_never_reaches_route(declared):
    messages = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )
    sent = []
    received = 0

    async def receive():
        nonlocal received
        received += 1
        return next(messages)

    async def app(scope, downstream_receive, send):
        pytest.fail("oversized request reached application")

    async def send(message):
        sent.append(message)

    asyncio.run(
        RequestSizeLimitMiddleware(app, maximum_bytes=8)(
            {
                "type": "http",
                "method": "POST",
                "headers": [(b"content-length", b"10")] if declared else [],
            },
            receive,
            send,
        )
    )
    assert sent[0]["status"] == 413
    assert b"request_too_large" in sent[1]["body"]
    assert received == (0 if declared else 2)


def test_disconnect_while_receiving_body_never_reaches_route():
    async def receive():
        return {"type": "http.disconnect"}

    async def app(scope, downstream_receive, send):
        pytest.fail("disconnected request reached application")

    async def send(message):
        pytest.fail("response sent after body disconnected")

    asyncio.run(
        RequestSizeLimitMiddleware(app, maximum_bytes=8)(
            {"type": "http", "method": "POST", "headers": []}, receive, send
        )
    )
