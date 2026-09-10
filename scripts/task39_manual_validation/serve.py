"""Launch one existing disposable fixture server; no packages or shared config changed."""

import argparse
import os
import runpy
import secrets
import socket
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("standard", "loop"), required=True)
    parser.add_argument("--api-port", type=int, default=4490)
    parser.add_argument("--web-port", type=int, default=4491)
    args = parser.parse_args()
    if args.api_port == args.web_port or not all(
        1024 <= port <= 65535 for port in (args.api_port, args.web_port)
    ):
        parser.error("Use two distinct unprivileged ports.")
    root = Path(__file__).resolve().parents[2]
    backend = root / "src-main/backend"
    if (backend / ".env").exists():
        parser.error("Use a clean isolated worktree without a backend .env file.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.api_port))
    scratch_root = root / ".tmp-task39"
    scratch_root.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="manual-", dir=scratch_root))
    origin = f"http://127.0.0.1:{args.web_port}"
    os.environ.update(
        APP_ENV="development",
        DATABASE_URL=f"sqlite:///{(scratch / 'unused-default.db').as_posix()}",
        RAG_UPLOAD_DIR=str(scratch / "uploads"),
        FRONTEND_ORIGIN=origin,
        CORS_ALLOWED_ORIGINS=origin,
        LLM_API_KEY="",
        LLM_PROVIDER="openai",
        LLM_MODEL="",
        LLM_API_BASE_URL="https://api.openai.com/v1",
        RESEARCH_ENABLED="false",
        PRODUCTION_ADAPTERS_READY="false",
        WORKER_ADAPTER_FACTORY="app.worker:build_offline_worker_adapters",
        SESSION_SECRET_KEY=secrets.token_urlsafe(48),
        LEARNING_EVENT_PSEUDONYM_SECRET=secrets.token_urlsafe(48),
        SESSION_COOKIE_SECURE="false",
        CSRF_ENABLED="true",
        RATE_LIMIT_ENABLED="true",
        QUANTUMLEARN_E2E_API_PORT=str(args.api_port),
        QUANTUMLEARN_E2E_WEB_PORT=str(args.web_port),
    )
    # The standard server's TemporaryDirectory uses this private root. The loop
    # server already allocates a fresh database/uploads under backend/.tmp-q25.
    tempfile.tempdir = str(scratch)
    os.chdir(backend)
    sys.path[:0] = [str(backend / "tests"), str(backend)]
    entry = (
        "browser_e2e_server.py"
        if args.profile == "standard"
        else "learning_loop_browser_server.py"
    )
    print(
        f"Task 39 profile={args.profile}; API=127.0.0.1:{args.api_port}; web={origin}",
        flush=True,
    )
    print(f"Private scratch: {scratch}. Stop this terminal with Ctrl+C.", flush=True)
    runpy.run_path(str(backend / "tests" / entry), run_name="__main__")


if __name__ == "__main__":
    main()
