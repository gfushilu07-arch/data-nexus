from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sql_matrix_select_invalid_cases", MATRIX_ROOT / "select_invalid_cases.py")
assert SPEC and SPEC.loader
SELECT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT)


class SelectInvalidCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.oracles = json.loads((MATRIX_ROOT / "invalid-oracles.json").read_text(encoding="utf-8"))

    def test_selects_declared_dialects_inclusive(self) -> None:
        rows = list(SELECT.select_cases(self.manifest, self.oracles, "SQLT-INVALID-010", "SQLT-INVALID-013"))
        self.assertEqual(rows, [
            ("SQLT-INVALID-010", "postgres", "invalid/postgres-division-by-zero.sql"),
            ("SQLT-INVALID-011", "postgres", "invalid/postgres-invalid-cast.sql"),
            ("SQLT-INVALID-012", "postgres", "invalid/postgres-function-signature.sql"),
            ("SQLT-INVALID-013", "mysql", "invalid/mysql-function-arity.sql"),
        ])

    def test_excludes_non_invalid_family(self) -> None:
        manifest = {"cases": [{"id": "SQLT-INVALID-010", "family": "dql", "dialects": ["postgres"], "sql_file": "x.sql"}]}
        self.assertEqual(list(SELECT.select_cases(manifest, self.oracles, "SQLT-INVALID-001", "SQLT-INVALID-999")), [])


if __name__ == "__main__":
    unittest.main()
