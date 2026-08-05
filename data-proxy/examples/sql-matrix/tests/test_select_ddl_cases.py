from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_select_ddl_cases", MATRIX_ROOT / "select_ddl_cases.py"
)
assert SPEC and SPEC.loader
SELECT_DDL_CASES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECT_DDL_CASES)


class SelectDdlCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (MATRIX_ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        cls.oracles = json.loads(
            (MATRIX_ROOT / "ddl-oracles.json").read_text(encoding="utf-8")
        )

    def test_excludes_cases_owned_by_specialized_runner(self) -> None:
        rows = list(
            SELECT_DDL_CASES.select_cases(
                self.manifest, self.oracles, "SQLT-DDL-013", "SQLT-DDL-015"
            )
        )
        self.assertEqual(
            rows,
            [
                ("SQLT-DDL-013", "mysql", "ddl/truncate-table.sql"),
                ("SQLT-DDL-013", "postgres", "ddl/truncate-table.sql"),
                ("SQLT-DDL-015", "mysql", "ddl/alter-add-primary-key.sql"),
                ("SQLT-DDL-015", "postgres", "ddl/alter-add-primary-key.sql"),
            ],
        )

    def test_range_is_inclusive(self) -> None:
        rows = list(
            SELECT_DDL_CASES.select_cases(
                self.manifest, self.oracles, "SQLT-DDL-016", "SQLT-DDL-016"
            )
        )
        self.assertEqual(
            rows,
            [("SQLT-DDL-016", "mysql", "ddl/mysql-drop-primary-key.sql")],
        )


if __name__ == "__main__":
    unittest.main()
