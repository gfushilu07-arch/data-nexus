from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "select_ddl_database_cases", MATRIX_ROOT / "select_ddl_database_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectDdlDatabaseCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads((MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads(
            (MATRIX_ROOT / "ddl-database-oracles.json").read_text(encoding="utf-8")
        )

    def test_selects_all_specialized_cases_in_manifest_order(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(
            [row[0] for row in rows],
            [f"SQLT-DDL-{case_id:03d}" for case_id in range(53, 58)],
        )
        self.assertTrue(all(row[1] == "mysql" for row in rows))

    def test_excludes_ordinary_ddl_even_if_oracle_is_injected(self) -> None:
        self.oracles["results"]["SQLT-DDL-001"] = {"mysql": {}}
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertNotIn("SQLT-DDL-001", [row[0] for row in rows])


if __name__ == "__main__":
    unittest.main()
