import socket

import httpx
import pytest

from app.services.rag.errors import InvalidDocumentError
from app.services.rag.web import SafeHttpsFetcher


def _resolver(addresses: dict[str, str]):
    def resolve(host: str, port: int, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addresses[host], port))]

    return resolve


def _client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_fetcher_rejects_loopback_and_private_addresses_before_request() -> None:
    for address in ("127.0.0.1", "10.0.0.1"):
        fetcher = SafeHttpsFetcher(
            _client(lambda request: httpx.Response(200)), _resolver({"blocked.test": address})
        )
        with pytest.raises(InvalidDocumentError):
            fetcher.fetch("https://blocked.test/notes.pdf")


def test_fetcher_revalidates_redirect_targets_and_rejects_unsupported_or_oversized_responses() -> (
    None
):
    redirect = SafeHttpsFetcher(
        _client(
            lambda request: httpx.Response(
                302, headers={"location": "https://private.test/file.pdf"}
            )
        ),
        _resolver({"public.test": "8.8.8.8", "private.test": "192.168.1.2"}),
    )
    with pytest.raises(InvalidDocumentError):
        redirect.fetch("https://public.test/file.pdf")

    unsupported = SafeHttpsFetcher(
        _client(lambda request: httpx.Response(200, headers={"content-type": "text/plain"})),
        _resolver({"public.test": "8.8.8.8"}),
    )
    with pytest.raises(InvalidDocumentError):
        unsupported.fetch("https://public.test/file.txt")

    oversized = SafeHttpsFetcher(
        _client(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"x" * (20 * 1024 * 1024 + 1),
            )
        ),
        _resolver({"public.test": "8.8.8.8"}),
    )
    with pytest.raises(InvalidDocumentError):
        oversized.fetch("https://public.test/file.pdf")
