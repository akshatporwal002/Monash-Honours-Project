"""Run the security gate with complete-history and positive-control checks.

Uses only the Python standard library and the pinned Gitleaks executable.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path

VERSION = "8.28.0"
LOG_OPTIONS = ["--all", "--full-history", "--no-ext-diff", "--no-textconv"]


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    if result.stderr.strip():
        raise RuntimeError(
            "Git reported a diagnostic; history completeness is unverified"
        )
    return result.stdout.strip()


def expected_commits(repo):
    """Independently count commits with text patches, as Gitleaks 8.28 does.

    Binary-only, deletion-only, empty and ordinary merge commits do not supply
    text fragments. Pure renames (0/0 numstat) do not supply fragments either.
    This checks traversal without retaining source text or matched values.
    """
    history = git(
        repo,
        "log",
        "--format=COMMIT:%H",
        "--numstat",
        "--diff-filter=tuxdb",
        *LOG_OPTIONS,
    )
    commits = set()
    commit = None
    for line in history.splitlines():
        if line.startswith("COMMIT:"):
            commit = line.removeprefix("COMMIT:")
            continue
        counts = line.split("\t", 2)
        if (
            len(counts) == 3
            and counts[0].isdigit()
            and counts[1].isdigit()
            and int(counts[0]) + int(counts[1]) > 0
        ):
            commits.add(commit)
    if not commits or None in commits:
        raise RuntimeError("No verifiable text history to scan")
    return sorted(commits)


def scan(executable, repo, target, mode, report_dir, label, expected=None):
    report = report_dir / f"{label}.json"
    log_path = report_dir / f"{label}.log"
    # Never accept stale output from an earlier invocation.
    report.unlink(missing_ok=True)
    env = os.environ.copy()
    for name in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML"):
        env.pop(name, None)
    command = [
        executable,
        mode,
        str(target),
        "--redact=100",
        "--no-banner",
        "--no-color",
        "--log-level=info",
        "--report-format=json",
        f"--report-path={report}",
        f"--gitleaks-ignore-path={repo / '.gitleaksignore'}",
    ]
    # Apply the same repository configuration to both history and the fixture.
    if (repo / ".gitleaks.toml").exists():
        command.append(f"--config={repo / '.gitleaks.toml'}")
    if mode == "git":
        command.append("--log-opts=" + " ".join(LOG_OPTIONS))
    result = subprocess.run(
        command, cwd=repo, env=env, capture_output=True, text=True, check=False
    )
    log = result.stdout + result.stderr
    log_path.write_text(log, encoding="utf-8")
    print(log, end="", flush=True)
    if re.search(r"\b(?:ERR|FTL|PNC)\b", log):
        raise RuntimeError(f"{label}: scanner diagnostics invalidate the result")
    if re.search(r"\bWRN\b(?! leaks found: \d+\s*$)", log, re.MULTILINE):
        raise RuntimeError(f"{label}: unexpected scanner warning")
    if not re.search(r"\bINF scanned ~[1-9]\d* bytes .* in ", log):
        raise RuntimeError(f"{label}: missing scan-completion summary")
    if expected is not None:
        counts = re.findall(r"\bINF (\d+) commits scanned\.", log)
        if counts != [str(expected)]:
            raise RuntimeError(
                f"{label}: scanned commit count does not match Git traversal"
            )
    findings = json.loads(report.read_text(encoding="utf-8"))
    if not isinstance(findings, list):
        raise TypeError(f"{label}: malformed finding report")
    return result.returncode, findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", default="gitleaks")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.check_output([args.gitleaks, "version"], text=True).strip()
    if version != VERSION:
        raise RuntimeError(f"Expected Gitleaks {VERSION}, got {version}")
    if git(repo, "rev-parse", "--is-shallow-repository") != "false":
        raise RuntimeError("Full-history scanning requires an unshallow checkout")
    if not (repo / ".gitleaksignore").is_file():
        raise RuntimeError("Missing reviewed fingerprint file")
    commits = expected_commits(repo)
    (report_dir / "coverage.json").write_text(
        json.dumps(
            {
                "version": version,
                "head": git(repo, "rev-parse", "HEAD"),
                "reachable_commits": int(git(repo, "rev-list", "--count", "--all")),
                "expected_text_commits": commits,
                "log_options": LOG_OPTIONS,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    code, findings = scan(
        args.gitleaks, repo, repo, "git", report_dir, "history", len(commits)
    )
    if code != 0 or findings:
        raise RuntimeError(
            f"History gate failed: exit {code}, {len(findings)} findings"
        )
    if expected_commits(repo) != commits:
        raise RuntimeError(
            "Git refs changed during scanning; rerun for consistent evidence"
        )

    # Same path and line as a historical exclusion, but no matching commit.
    # The generated value has never been issued by a provider or used for access.
    with tempfile.TemporaryDirectory(
        prefix="positive-control-", dir=report_dir
    ) as temp:
        fixture = Path(temp)
        target = fixture / "src-main/backend/tests/support/assessment.py"
        target.parent.mkdir(parents=True)
        value = secrets.token_hex(24)
        target.write_text(
            "\n" * 309 + f'evaluation_idempotency_key="{value}"\n', encoding="utf-8"
        )
        code, findings = scan(
            args.gitleaks, repo, fixture, "dir", report_dir, "positive-control"
        )
        if (
            code != 1
            or len(findings) != 1
            or findings[0].get("RuleID") != "generic-api-key"
            or findings[0].get("StartLine") != 310
            or not findings[0]
            .get("File", "")
            .replace("\\", "/")
            .endswith("src-main/backend/tests/support/assessment.py")
            or findings[0].get("Secret") != "REDACTED"
        ):
            raise RuntimeError(
                "Positive control failed to detect the expected synthetic secret"
            )
        for suffix in ("json", "log"):
            if value in (report_dir / f"positive-control.{suffix}").read_text(
                encoding="utf-8"
            ):
                raise RuntimeError("Positive-control output was not fully redacted")
    print(
        f"PASS: Gitleaks {version}; {len(commits)} text commits; zero history findings; "
        "positive control detected and redacted"
    )


if __name__ == "__main__":
    main()
