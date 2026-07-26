#!/usr/bin/env python3
"""Verify that the QuantumLearn SPA and same-origin API are reachable."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://localhost:8080"


class SmokeCheckError(RuntimeError):
    pass


def fetch(base_url: str, path: str, timeout: float) -> tuple[bytes, str]:
    url = urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    request = Request(
        url,
        headers={"User-Agent": "quantumlearn-smoke-check/1"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise SmokeCheckError(f"{path} returned HTTP {response.status}")
            return response.read(1_000_000), response.headers.get_content_type()
    except HTTPError as error:
        raise SmokeCheckError(f"{path} returned HTTP {error.code}") from None
    except URLError as error:
        reason = getattr(error, "reason", "connection failed")
        raise SmokeCheckError(f"{path} is unreachable: {reason}") from None


def check(base_url: str, timeout: float) -> None:
    page, page_type = fetch(base_url, "/", timeout)
    if page_type != "text/html" or b"<title>QuantumLearn</title>" not in page:
        raise SmokeCheckError("/ did not return the QuantumLearn HTML shell")

    health, health_type = fetch(base_url, "/api/v1/health", timeout)
    if health_type != "application/json":
        raise SmokeCheckError("/api/v1/health did not return JSON")
    try:
        payload = json.loads(health)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SmokeCheckError("/api/v1/health returned invalid JSON") from None
    if payload != {"status": "ok"}:
        raise SmokeCheckError("/api/v1/health returned an unexpected payload")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("QUANTUMLEARN_BASE_URL", DEFAULT_BASE_URL),
        help=(
            f"Public QuantumLearn origin. Defaults to QUANTUMLEARN_BASE_URL or {DEFAULT_BASE_URL}."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Timeout per request in seconds (default: 5).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("Smoke check failed: --timeout must be positive.", file=sys.stderr)
        return 2
    try:
        check(args.base_url, args.timeout)
    except SmokeCheckError as error:
        print(f"Smoke check failed: {error}", file=sys.stderr)
        return 1
    print(f"QuantumLearn smoke check passed: {args.base_url.rstrip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
