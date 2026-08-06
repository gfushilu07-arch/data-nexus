from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "select_tcl_cases", MATRIX_ROOT / "select_tcl_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectTclCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads((MATRIX_ROOT / "tcl-oracles.json").read_text(encoding="utf-8"))

    def test_selects_manifest_order_and_dialect_ownership(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0], ("SQLT-TCL-001", "mysql", "tcl/transaction-savepoint.sql"))
        self.assertEqual(rows[-1], ("SQLT-TCL-011", "postgres", "tcl/savepoint-error-recovery.sql"))
        self.assertEqual([row[1] for row in rows if row[0] == "SQLT-TCL-008"], ["mysql"])
        self.assertEqual([row[1] for row in rows if row[0] == "SQLT-TCL-009"], ["postgres"])

    def test_excludes_non_tcl_and_oracle_dialect_drift(self) -> None:
        self.oracles["results"]["SQLT-DML-003"] = {"mysql": {}}
        self.oracles["results"]["SQLT-TCL-008"]["postgres"] = {}
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertNotIn("SQLT-DML-003", [row[0] for row in rows])
        self.assertNotIn(("SQLT-TCL-008", "postgres", "tcl/serializable-transaction.sql"), rows)


if __name__ == "__main__":
    unittest.main()
