from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "select_dml_cases", ROOT / "select_dml_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectDmlCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(
            (ROOT / "manifest.json").read_text(encoding="utf-8")
        )
        self.oracles = json.loads(
            (ROOT / "dml-oracles.json").read_text(encoding="utf-8")
        )

    def test_selects_all_owned_case_dialects(self) -> None:
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertEqual(len(rows), 64)
        self.assertEqual(rows[0][0:2], ("SQLT-DML-003", "mysql"))
        self.assertEqual(rows[-1][0:2], ("SQLT-DML-043", "postgres"))

    def test_case_range_is_inclusive(self) -> None:
        rows = list(
            SELECTOR.select_cases(
                self.manifest, self.oracles, "SQLT-DML-003", "SQLT-DML-003"
            )
        )
        self.assertEqual(
            [(case_id, dialect) for case_id, dialect, _ in rows],
            [("SQLT-DML-003", "mysql"), ("SQLT-DML-003", "postgres")],
        )

    def test_oracle_dialect_owns_selection(self) -> None:
        del self.oracles["results"]["SQLT-DML-003"]["postgres"]
        rows = list(SELECTOR.select_cases(self.manifest, self.oracles))
        self.assertNotIn(
            ("SQLT-DML-003", "postgres"),
            [(case_id, dialect) for case_id, dialect, _ in rows],
        )


if __name__ == "__main__":
    unittest.main()
