#!/usr/bin/env python3
"""Smoke-check a noneditable backend install with the image's runtime sidecars."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Run outside the checkout, with editable import hooks removed. Otherwise the
# source tree can hide a module missing from the installed wheel.
PROBE = r"""
import importlib
import importlib.metadata
import importlib.util
import json
import runpy
import sys
from pathlib import Path

installed, runtime = (Path(value).resolve() for value in sys.argv[1:])
sys.dont_write_bytecode = True
sys.meta_path = [
    finder for finder in sys.meta_path
    if not getattr(finder, "__module__", "").startswith("__editable__")
]
sys.path = [str(installed), str(runtime)] + [
    value for value in sys.path
    if value and not value.startswith("__editable__")
    and not (Path(value) / "app" / "__init__.py").exists()
]
distributions = [
    item for item in importlib.metadata.distributions(path=[str(installed)])
    if item.metadata["Name"] == "quantumlearn-api"
]
assert len(distributions) == 1, "Expected one installed quantumlearn-api distribution"
entries = {
    entry.name: entry
    for entry in distributions[0].entry_points
    if entry.group == "console_scripts"
}
for name in ("quantumlearn-worker", "quantumlearn-provision-admin"):
    assert callable(entries[name].load()), f"Unusable entrypoint: {name}"
application = importlib.import_module("app.main")
assert callable(application.app), "ASGI application is missing"

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.readiness import MIGRATION_HEAD

config = Config(str(runtime / "alembic.ini"))
config.set_main_option("script_location", str(runtime / "migrations"))
scripts = ScriptDirectory.from_config(config)
assert scripts.get_heads() == [MIGRATION_HEAD], "Installed readiness and migration head differ"
revisions = list(scripts.walk_revisions())
assert revisions, "Migration history is missing"
for revision in revisions:
    assert Path(revision.path).resolve().is_relative_to(runtime / "migrations")

backup_spec = importlib.util.find_spec("scripts.learning_backup")
assert backup_spec is not None and backup_spec.origin is not None, "Backup CLI is missing"
assert Path(backup_spec.origin).resolve().is_relative_to(runtime / "scripts")
sys.argv = ["scripts.learning_backup", "--help"]
try:
    runpy.run_module("scripts.learning_backup", run_name="__main__")
except SystemExit as result:
    assert result.code in (0, None), "Packaged backup CLI failed"

loaded = []
for name, module in list(sys.modules.items()):
    if name == "app" or name.startswith("app."):
        location = getattr(module, "__file__", None)
        if location is not None:
            assert Path(location).resolve().is_relative_to(installed), (
                f"Source checkout masked the installed package: {name}"
            )
            loaded.append(name)
    elif name == "scripts" or name.startswith("scripts."):
        location = getattr(module, "__file__", None)
        if location is not None:
            assert Path(location).resolve().is_relative_to(runtime / "scripts"), (
                f"Source checkout masked the copied runtime scripts: {name}"
            )
assert loaded, "No installed application modules were checked"
print(json.dumps({
    "status": "passed",
    "distribution": distributions[0].metadata["Name"],
    "version": distributions[0].version,
    "installed_application_modules": len(loaded),
    "console_scripts": sorted(entries),
    "migration_head": MIGRATION_HEAD,
    "migration_revisions": len(revisions),
    "scope": "Noneditable Python package and copied runtime sidecars; no container or hosted claim",
}))
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    installed = args.installed.resolve(strict=True)
    runtime = args.runtime.resolve(strict=True)
    if (runtime / "app").exists() or (runtime / ".env").exists():
        parser.error("Use a clean runtime directory containing only copied image sidecars")
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": f"sqlite:///{(runtime / 'package-smoke.sqlite').as_posix()}",
        "RAG_UPLOAD_DIR": str(runtime / "uploads"),
        "LEARNING_EVENT_PSEUDONYM_SECRET": "package-smoke-only-pseudonym-secret-32-bytes",
        "SESSION_SECRET_KEY": "package-smoke-only-independent-session-secret-32-bytes",
        "RESEARCH_ENABLED": "false",
        "BOOTSTRAP_DEMO": "false",
        "LLM_API_KEY": "",
        "LLM_API_BASE_URL": "https://127.0.0.1:1",
        "WORKER_ADAPTER_FACTORY": "app.worker:build_offline_worker_adapters",
    }
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-I", "-c", PROBE, str(installed), str(runtime)],
        cwd=runtime,
        env=environment,
        timeout=60,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
