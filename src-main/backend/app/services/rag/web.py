"""Bounded HTTPS downloader for material links."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.rag.errors import InvalidDocumentError


@dataclass(frozen=True, slots=True)
class DownloadedMaterial:
    url: str
    filename: str
    content: bytes


def _validate_url(url: str, resolver: Callable[..., list[tuple]]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise InvalidDocumentError()
    for item in resolver(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise InvalidDocumentError()


class SafeHttpsFetcher:
    def __init__(
        self,
        client_factory: Callable[[], httpx.Client] | None = None,
        resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
    ) -> None:
        self._client_factory = client_factory
        self._resolver = resolver

    def fetch(self, url: str) -> DownloadedMaterial:
        current = url
        for _ in range(4):
            _validate_url(current, self._resolver)
            client = (
                self._client_factory()
                if self._client_factory
                else httpx.Client(
                    timeout=httpx.Timeout(30, connect=10),
                    follow_redirects=False,
                    headers={"User-Agent": "QuantumLearn/1.0"},
                )
            )
            with client, client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise InvalidDocumentError()
                    current = str(response.url.join(location))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0]
                extension = {
                    "application/pdf": ".pdf",
                    "text/html": ".html",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
                }.get(content_type)
                if extension is None:
                    raise InvalidDocumentError()
                content = bytearray()
                for part in response.iter_bytes():
                    content.extend(part)
                    if len(content) > settings.rag_max_file_bytes:
                        raise InvalidDocumentError()
                return DownloadedMaterial(current, f"source{extension}", bytes(content))
        raise InvalidDocumentError()
