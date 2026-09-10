#!/usr/bin/env python3
"""Capture a stopped Compose deployment or prepare a fresh rollback volume.

No cutover, data deletion, image build/pull, or automatic service restart occurs.
Use the same image tag and manifest together; keep the previous live volume intact.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, text=True, capture_output=capture)


def mount(path: Path, target: str, *, readonly: bool = False) -> list[str]:
    # Docker --mount is comma-delimited even when passed as one argv value.
    if "," in str(path):
        raise ValueError("Bind-mount paths must not contain commas")
    value = f"type=bind,src={path.resolve()},dst={target}"
    return ["--mount", value + (",readonly" if readonly else "")]


def compose(env_file: Path, hosted: bool) -> list[str]:
    if not env_file.is_file():
        raise ValueError("The deployment environment file must exist")
    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_file.resolve()),
        "-f",
        str(ROOT / "deploy" / "compose.yaml"),
    ]
    if hosted:
        command += ["-f", str(ROOT / "deploy" / "compose.hosted.yaml")]
    return command


def backup(env_file: Path, hosted: bool, output: Path) -> None:
    prefix = compose(env_file, hosted)
    active = run(prefix + ["ps", "--status", "running", "--services"], capture=True)
    if {"backend", "worker"} & set(active.stdout.splitlines()):
        raise ValueError("Stop backend and worker before capturing a release backup")
    if not output.is_dir():
        raise ValueError(
            "Create a restricted backup directory writable by container UID 10001"
        )
    run(
        prefix
        + [
            "run",
            "--rm",
            "--no-deps",
            "--pull",
            "never",
            "-T",
            "-e",
            "MIGRATE_ON_START=false",
            "-e",
            "BOOTSTRAP_DEMO=false",
            "--volume",
            f"{output.resolve()}:/backups",
            "backend",
            "python",
            "-c",
            # Read the same effective paths as the API, including a prior restored deployment.
            (
                "from pathlib import Path; from app.core.config import settings; "
                "from sqlalchemy.engine import make_url; "
                "from scripts.learning_backup import create_bundle; "
                "url = make_url(settings.database_url); "
                "assert url.get_backend_name() == 'sqlite' and url.database; "
                "print(create_bundle(Path(url.database), Path(settings.rag_upload_dir), Path('/backups')))"
            ),
        ]
    )


def restore(bundle: Path, image: str, volume: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]+", volume):
        raise ValueError("Use a new named Docker volume")
    if not image or image.startswith("-"):
        raise ValueError("Supply the retained backend image tag or digest")
    if not bundle.is_dir() or not (bundle / "manifest.json").is_file():
        raise ValueError("Supply a complete backup bundle directory")
    # Listing must succeed: a stopped daemon is not evidence that a volume is absent.
    existing = run(["docker", "volume", "ls", "--format", "{{.Name}}"], capture=True)
    if volume in existing.stdout.splitlines():
        raise ValueError("The restore volume already exists; choose a fresh candidate")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    expected = manifest["database"]["migration_head"]
    actual = run(
        [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--entrypoint",
            "python",
            image,
            "-c",
            "from app.core.readiness import MIGRATION_HEAD; print(MIGRATION_HEAD)",
        ],
        capture=True,
    ).stdout.strip()
    if actual != expected:
        raise ValueError("The retained image migration head does not match the backup")
    run(
        [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "python",
            "--mount",
            f"type=volume,src={volume},dst=/data",
            *mount(bundle, "/backup", readonly=True),
            image,
            "-m",
            "scripts.learning_backup",
            "restore",
            "--bundle",
            "/backup",
            "--destination",
            "/data/restored",
        ]
    )
    print("Verified candidate only; review and reconcile governance before cutover:")
    print(f"DATA_VOLUME_NAME={volume}")
    print("DATABASE_URL=sqlite:////data/restored/database.sqlite3")
    print("RAG_UPLOAD_DIR=/data/restored/uploads")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("backup")
    capture.add_argument("--env-file", type=Path, required=True)
    capture.add_argument("--hosted", action="store_true")
    capture.add_argument("--output", type=Path, required=True)
    candidate = commands.add_parser("prepare-rollback")
    candidate.add_argument("--bundle", type=Path, required=True)
    candidate.add_argument("--image", required=True)
    candidate.add_argument("--volume", required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup":
            backup(args.env_file, args.hosted, args.output)
        else:
            restore(args.bundle, args.image, args.volume)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        # Do not echo provider configuration or subprocess output.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        parser.exit(1, f"Release operation failed: {message}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
