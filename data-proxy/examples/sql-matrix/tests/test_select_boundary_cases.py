from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_select_boundary_cases", MATRIX_ROOT / "select_boundary_cases.py"
)
assert SPEC and SPEC.loader
SELECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT)


class SelectBoundaryCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.oracles = json.loads((MATRIX_ROOT / "boundary-oracles.json").read_text(encoding="utf-8"))

    def test_selects_case_dialects_and_flows(self) -> None:
        rows = list(SELECT.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 12)
        self.assertEqual(
            rows[0],
            ("SQLT-INVALID-014", "mysql", "invalid/mysql-binary-bind-boundary.sql", "mysql_bind"),
        )
        self.assertEqual(
            rows[-1],
            ("SQLT-INVALID-021", "postgres", "invalid/postgres-frontend-message-limit.sql", "message_limit"),
        )

    def test_excludes_cases_not_owned_by_boundary_oracle(self) -> None:
        manifest = {"cases": [{"id": "SQLT-INVALID-001", "family": "invalid", "dialects": ["mysql"], "sql_file": "x.sql"}]}
        self.assertEqual(list(SELECT.select_cases(manifest, self.oracles)), [])


if __name__ == "__main__":
    unittest.main()
