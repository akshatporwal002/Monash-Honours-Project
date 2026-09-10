"""Negative checks for omissions, false evidence references and inconsistent claims."""

import unittest
from unittest.mock import patch

from check import REPORT, ROOT, SOURCES, discover, validate


class ReconciliationChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = (ROOT / REPORT).read_text(encoding="utf-8")

    def test_report_is_complete(self):
        self.assertEqual(validate(ROOT, self.report)[0], len(discover(ROOT)))

    def test_missing_and_duplicate_rows_are_rejected(self):
        row = next(
            line for line in self.report.splitlines() if line.startswith("| FR1 |")
        )
        for altered in (
            self.report.replace(row, ""),
            self.report + "\n" + row,
            self.report + "\n" + row.replace("| FR1 |", "| FR999 |", 1),
        ):
            with (
                self.subTest(altered=altered[-30:]),
                self.assertRaisesRegex(ValueError, "Inventory mismatch"),
            ):
                validate(ROOT, altered)

    def test_changed_source_wording_is_rejected(self):
        altered = self.report.replace(
            "User role management. Provide", "User role management. Omit", 1
        )
        self.assertNotEqual(altered, self.report)
        with self.assertRaisesRegex(ValueError, "Source wording changed or omitted"):
            validate(ROOT, altered)

    def test_source_discovery_accepts_additions_and_rejects_duplicate_definitions(self):
        # Source discovery needs text, not a writable OS temporary directory.
        # Real repository reads are covered separately by test_report_is_complete.
        texts = ["### FR80 - Added requirement\nSee FR1.\n", "", ""]
        self.assertEqual(len(texts), len(SOURCES))
        with patch("pathlib.Path.read_text", side_effect=texts):
            self.assertEqual(set(discover(ROOT)), {"FR80"})
        texts[1] = "### FR80 - Duplicate\n"
        with (
            patch("pathlib.Path.read_text", side_effect=texts),
            self.assertRaisesRegex(ValueError, "Duplicate definition"),
        ):
            discover(ROOT)

    def test_missing_path_and_named_case_are_rejected(self):
        for reference, error in (
            ("src-main/absent-task36-file.py", "Missing or escaping path"),
            (
                "src-main/backend/tests/test_tutor.py::test_absent_task36",
                "Missing named case",
            ),
        ):
            with (
                self.subTest(reference=reference),
                self.assertRaisesRegex(ValueError, error),
            ):
                validate(ROOT, self.report + f"\n`{reference}`\n")

    def test_status_gap_and_total_disagreement_are_rejected(self):
        for altered, error in (
            (
                self.report.replace("| IMPLEMENTED |", "| UNKNOWN |", 1),
                "Incomplete row",
            ),
            (
                self.report.replace(
                    "None in mapped implementation", "Missing behavior", 1
                ),
                "Implemented row",
            ),
            (
                self.report.replace("| TOTAL IMPLEMENTED |", "| WRONG TOTAL |"),
                "Incorrect total",
            ),
            (
                self.report.replace("[E-AUTH](#e-auth)", "[E-ABSENT](#e-absent)", 1),
                "Unresolved evidence",
            ),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                validate(ROOT, altered)


if __name__ == "__main__":
    unittest.main()
