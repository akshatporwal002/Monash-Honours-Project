"""Validate completeness and structure of the LearnLens implementation gap matrix."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

REQUIRED_RANGES = {
    "FR": 39,
    "PD": 12,
    "BP": 15,
    "NFR": 31,
    "AC": 22,
    "AT": 24,
}
ALLOWED_STATUSES = {
    "IMPLEMENTED",
    "PARTIAL",
    "MISSING",
    "CONFLICTING",
    "UNVERIFIED",
}
REQUIREMENT_RE = re.compile(r"^(FR|PD|BP|NFR|AC|AT)([1-9][0-9]*)$")
PERSON_B_STEP_RE = re.compile(r"\bStep(?:s)?\s+([1-9]|[1-3][0-9]|4[0-3])\b")
PERSON_A_STEP_RE = re.compile(r"\bA[1-6]\b")


def required_ids() -> list[str]:
    """Return every required identifier in controlling-document order."""

    return [
        f"{prefix}{number}"
        for prefix, maximum in REQUIRED_RANGES.items()
        for number in range(1, maximum + 1)
    ]


def parse_rows(text: str) -> list[tuple[int, list[str]]]:
    """Return matrix rows as ``(line_number, cells)`` tuples."""

    rows: list[tuple[int, list[str]]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and REQUIREMENT_RE.fullmatch(cells[0]):
            rows.append((line_number, cells))
    return rows


def validate_gap_matrix(path: Path) -> list[str]:
    """Return validation errors for ``path`` without mutating the file."""

    if not path.is_file():
        return [f"matrix does not exist: {path}"]

    rows = parse_rows(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    identifiers = [cells[0] for _, cells in rows]
    counts = Counter(identifiers)
    expected = set(required_ids())
    actual = set(identifiers)

    missing = sorted(expected - actual, key=required_ids().index)
    unexpected = sorted(actual - expected)
    duplicates = sorted(identifier for identifier, count in counts.items() if count > 1)
    if missing:
        errors.append(f"missing requirement rows: {', '.join(missing)}")
    if unexpected:
        errors.append(f"unexpected requirement rows: {', '.join(unexpected)}")
    if duplicates:
        errors.append(f"duplicate requirement rows: {', '.join(duplicates)}")

    for line_number, cells in rows:
        identifier = cells[0]
        if len(cells) != 6:
            errors.append(
                f"line {line_number} ({identifier}): expected 6 cells, found {len(cells)}"
            )
            continue
        _, status, proof, gap, planned_change, tests = cells
        if status not in ALLOWED_STATUSES:
            errors.append(f"line {line_number} ({identifier}): invalid status {status!r}")
        for label, value in (
            ("existing proof", proof),
            ("gap", gap),
            ("planned change", planned_change),
            ("tests", tests),
        ):
            if not value or value in {"-", "—"}:
                errors.append(f"line {line_number} ({identifier}): empty {label} cell")
        if not (PERSON_B_STEP_RE.search(planned_change) or PERSON_A_STEP_RE.search(planned_change)):
            errors.append(
                f"line {line_number} ({identifier}): planned change has no Step 1-43 or A1-A6 reference"
            )

    if len(rows) != len(required_ids()):
        errors.append(f"expected {len(required_ids())} canonical rows, found {len(rows)}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", type=Path, help="Path to the Markdown gap matrix")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    errors = validate_gap_matrix(args.matrix)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    counts = ", ".join(f"{prefix}={maximum}" for prefix, maximum in REQUIRED_RANGES.items())
    print(f"Gap matrix valid: {len(required_ids())} rows ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
