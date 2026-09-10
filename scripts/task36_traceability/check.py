"""Read-only, standard-library validation of the separate Task 36 report."""

import ast
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "docs/01-implementation-requirements.md",
    "docs/02-pass-incomplete-bloom-assessment-spec.md",
    "docs/03-codex-implementation-work-order.md",
)
REPORT = "docs/learnlens/task-36-requirements-reconciliation.md"
ID = r"(?:NFR|FR|PD|BP|AC|AT)\d+"
STATUSES = {"IMPLEMENTED", "PARTIAL", "MISSING", "CONFLICTING", "UNVERIFIED"}


def discover(root):
    """Discover definitions, never assume fixed ranges or use cross-reference counts."""
    found = {}
    for source in SOURCES:
        lines = (root / source).read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            match = re.match(rf"^#{{1,6}}\s+({ID})\s+[-–—]\s+(.+)$", line)
            if match:
                identity, title = match.groups()
                if identity in found:
                    raise ValueError(
                        f"Duplicate definition: {identity} in {source}:{number}"
                    )
                found[identity] = (source, number, title)
    return found


def validate(root, report):
    inventory = discover(root)
    rows = []
    for line in report.splitlines():
        if re.match(rf"^\| {ID} \|", line):
            columns = [value.strip() for value in line.strip("|").split("|")]
            if len(columns) != 9:
                raise ValueError(f"Expected nine fields: {columns[0]}")
            rows.append(columns)
    counts = Counter(row[0] for row in rows)
    if set(counts) != set(inventory) or any(n != 1 for n in counts.values()):
        raise ValueError(
            f"Inventory mismatch: missing={set(inventory) - set(counts)}, "
            f"extra={set(counts) - set(inventory)}, duplicates="
            f"{[key for key, n in counts.items() if n != 1]}"
        )
    catalog = set(re.findall(r"^### (E-[A-Z0-9]+) —", report, re.MULTILINE))
    for (
        identity,
        source,
        summary,
        status,
        evidence,
        kind,
        gap,
        dependency,
        acceptance,
    ) in rows:
        expected_source, number, title = inventory[identity]
        if source != f"`{expected_source}:{number}`":
            raise ValueError(f"Wrong source: {identity}")
        body = []
        for line in (
            (root / expected_source).read_text(encoding="utf-8").splitlines()[number:]
        ):
            if line.startswith("#"):
                break
            body.append(line.strip().removeprefix("- "))
        expected_scope = (title + ". " + " ".join(filter(None, body))).replace("|", "/")
        if summary != expected_scope:
            raise ValueError(f"Source wording changed or omitted: {identity}")
        if status not in STATUSES or not all(
            (summary, evidence, kind, gap, dependency, acceptance)
        ):
            raise ValueError(f"Incomplete row: {identity}")
        refs = re.findall(r"E-[A-Z0-9]+", evidence)
        if not refs or not set(refs) <= catalog:
            raise ValueError(f"Unresolved evidence: {identity}")
        if kind not in {"R+F+A", "R+F+A; H absent", "R+F+A; X absent"}:
            raise ValueError(f"Unrecognised evidence qualification: {identity}")
        if status == "IMPLEMENTED" and not gap.startswith(
            "None in mapped implementation"
        ):
            raise ValueError(
                f"Implemented row with unresolved implementation gap: {identity}"
            )
        if status != "IMPLEMENTED" and gap.startswith("None"):
            raise ValueError(f"Open row without gap: {identity}")
    totals = Counter(row[3] for row in rows)
    for status in STATUSES:
        if f"| TOTAL {status} | {totals[status]} |" not in report:
            raise ValueError(f"Incorrect total: {status}")
    # All repo references use backticks. Branch-only references are qualified in prose,
    # never passed off as existing base-revision files.
    references = re.findall(
        r"`((?:src-main/|docs/|scripts/|\.github/)[^`\n]+)`", report
    )
    checked = set()
    for reference in references:
        path, _, case = reference.partition("::")
        path = re.sub(r":\d+$", "", path)
        target = (root / path).resolve()
        if not target.is_relative_to(root.resolve()) or not target.exists():
            raise ValueError(f"Missing or escaping path: {reference}")
        if case:
            names = {
                node.name
                for node in ast.walk(ast.parse(target.read_text(encoding="utf-8")))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            if case not in names:
                raise ValueError(f"Missing named case: {reference}")
        checked.add(reference)
    return len(rows), totals, len(checked)


if __name__ == "__main__":
    try:
        count, totals, references = validate(
            ROOT, (ROOT / REPORT).read_text(encoding="utf-8")
        )
        print(
            f"PASS: {count} requirements exactly once; {references} repository references valid"
        )
        print("; ".join(f"{key}={totals[key]}" for key in sorted(STATUSES)))
    except (ValueError, OSError, SyntaxError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
