from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "select_prepared_cases", MATRIX_ROOT / "select_prepared_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectPreparedCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads((MATRIX_ROOT / "prepared-oracles.json").read_text(encoding="utf-8"))

    def test_selects_exact_prepared_cases(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0], ("SQLT-PRP-001", "mysql", "prepared/zero-parameter-select.sql"))
        self.assertEqual(rows[-1], ("SQLT-PRP-008", "mysql", "prepared/schema-change-reprepare.sql"))

    def test_excludes_text_cursor_and_injected_oracle_entries(self) -> None:
        self.oracles["results"]["SQLT-CURSOR-001"] = {}
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertNotIn("SQLT-CURSOR-001", [row[0] for row in rows])

    def test_excludes_prepared_case_with_non_mysql_dialect_contract(self) -> None:
        prepared = next(case for case in self.manifest["cases"] if case["id"] == "SQLT-PRP-001")
        prepared["dialects"] = ["mysql", "postgres"]
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertNotIn("SQLT-PRP-001", [row[0] for row in rows])


if __name__ == "__main__":
    unittest.main()
