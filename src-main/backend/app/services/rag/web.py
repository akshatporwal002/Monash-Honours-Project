"""Bounded HTTPS downloader for material links."""

from __future__ import annotations

import ipaddress
import socket
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


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise InvalidDocumentError()
    for item in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            raise InvalidDocumentError()


class SafeHttpsFetcher:
    def fetch(self, url: str) -> DownloadedMaterial:
        current = url
        for _ in range(4):
            _validate_url(current)
            with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=False, headers={"User-Agent": "QuantumLearn/1.0"}) as client:
                response = client.stream("GET", current)
                with response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise InvalidDocumentError()
                        current = str(response.url.join(location))
                        continue
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").split(";", 1)[0]
                    extension = {"application/pdf": ".pdf", "text/html": ".html", "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx", "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"}.get(content_type)
                    if extension is None:
                        raise InvalidDocumentError()
                    content = bytearray()
                    for part in response.iter_bytes():
                        content.extend(part)
                        if len(content) > settings.rag_max_file_bytes:
                            raise InvalidDocumentError()
                    return DownloadedMaterial(current, f"source{extension}", bytes(content))
        raise InvalidDocumentError()
