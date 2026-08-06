from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("select_extended_cases", ROOT / "select_extended_cases.py")
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectExtendedCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads((ROOT / "extended-oracles.json").read_text(encoding="utf-8"))

    def test_selects_exact_extended_cases(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0], ("SQLT-PGX-001", "postgres", "extended/lifecycle.sql"))
        self.assertEqual(rows[-1], ("SQLT-PGX-008", "postgres", "extended/transaction-status.sql"))

    def test_excludes_wrong_frontend(self) -> None:
        case = next(value for value in self.manifest["cases"] if value["id"] == "SQLT-PGX-001")
        case["frontends"] = ["pg_simple"]
        self.assertNotIn("SQLT-PGX-001", [row[0] for row in SELECTOR.select_cases(self.manifest, self.oracles)])


if __name__ == "__main__":
    unittest.main()
