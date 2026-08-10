from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("select_cursor_cases", ROOT / "select_cursor_cases.py")
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectCursorCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads((ROOT / "cursor-oracles.json").read_text(encoding="utf-8"))

    def test_selects_all_named_cursor_cases(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0], ("SQLT-CURSOR-001", "postgres", "cursor/postgres-declare-fetch-close.sql"))
        self.assertEqual(rows[-1], ("SQLT-CURSOR-008", "postgres", "cursor/postgres-backend-disconnect.sql"))

    def test_excludes_other_frontend(self) -> None:
        case = next(value for value in self.manifest["cases"] if value["id"] == "SQLT-CURSOR-001")
        case["frontends"] = ["pg_extended"]
        self.assertNotIn("SQLT-CURSOR-001", [row[0] for row in SELECTOR.select_cases(self.manifest, self.oracles)])

    def test_case_range_is_inclusive(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles, "SQLT-CURSOR-007", "SQLT-CURSOR-007"))
        self.assertEqual([row[0] for row in rows], ["SQLT-CURSOR-007"])


if __name__ == "__main__":
    unittest.main()
