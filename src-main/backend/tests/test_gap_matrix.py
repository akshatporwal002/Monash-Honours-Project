from __future__ import annotations

import importlib.util
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SRC_ROOT.parent
VALIDATOR_PATH = SRC_ROOT / "scripts" / "validate_gap_matrix.py"
MATRIX_PATH = REPOSITORY_ROOT / "docs" / "learnlens" / "implementation-gap-matrix.md"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_gap_matrix", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _complete_matrix() -> str:
    header = "| Requirement | Status | Existing proof | Gap | Planned change | Tests |\n"
    divider = "| --- | --- | --- | --- | --- | --- |\n"
    rows = "".join(
        f"| {identifier} | MISSING | No current proof. | Required behaviour is absent. | Step 1 records it. | NOT RUN; planned test. |\n"
        for identifier in validator.required_ids()
    )
    return header + divider + rows


def test_repository_gap_matrix_is_complete_and_valid() -> None:
    assert validator.validate_gap_matrix(MATRIX_PATH) == []


def test_validator_accepts_exact_required_ranges(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.md"
    matrix.write_text(_complete_matrix(), encoding="utf-8")

    assert validator.validate_gap_matrix(matrix) == []


def test_validator_reports_duplicates_missing_cells_status_and_step_reference(
    tmp_path: Path,
) -> None:
    matrix = tmp_path / "matrix.md"
    text = _complete_matrix()
    text = text.replace(
        "| FR1 | MISSING | No current proof. | Required behaviour is absent. | Step 1 records it. | NOT RUN; planned test. |",
        "| FR1 | UNKNOWN | | Required behaviour is absent. | No owner yet. | NOT RUN; planned test. |\n"
        "| FR1 | MISSING | Duplicate. | Duplicate. | Step 1 records it. | Duplicate. |",
    )
    text = text.replace(
        "| AT24 | MISSING | No current proof. | Required behaviour is absent. | Step 1 records it. | NOT RUN; planned test. |\n",
        "",
    )
    matrix.write_text(text, encoding="utf-8")

    errors = validator.validate_gap_matrix(matrix)

    assert any("missing requirement rows: AT24" in error for error in errors)
    assert any("duplicate requirement rows: FR1" in error for error in errors)
    assert any("invalid status 'UNKNOWN'" in error for error in errors)
    assert any("empty existing proof cell" in error for error in errors)
    assert any("has no Step 1-43 or A1-A6 reference" in error for error in errors)
