from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_select_unsupported", MATRIX_ROOT / "select_unsupported_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectUnsupportedCasesTest(unittest.TestCase):
    def test_selects_manifest_dialects_closed_by_oracle(self) -> None:
        manifest = {
            "cases": [
                {
                    "id": "SQLT-UNSUPPORTED-009",
                    "family": "unsupported",
                    "dialects": ["mysql", "postgres"],
                    "sql_file": "unsupported/privileged.sql",
                },
                {
                    "id": "SQLT-DQL-001",
                    "family": "dql",
                    "dialects": ["mysql"],
                    "sql_file": "dql/basic.sql",
                },
            ]
        }
        oracles = {
            "results": {
                "SQLT-UNSUPPORTED-009": {
                    "flow": "privileged",
                    "expected": {"mysql": {}, "postgres": {}},
                }
            }
        }
        self.assertEqual(
            list(SELECTOR.select_cases(manifest, oracles)),
            [
                (
                    "SQLT-UNSUPPORTED-009",
                    "mysql",
                    "unsupported/privileged.sql",
                    "privileged",
                ),
                (
                    "SQLT-UNSUPPORTED-009",
                    "postgres",
                    "unsupported/privileged.sql",
                    "privileged",
                ),
            ],
        )

    def test_skips_manifest_dialect_missing_from_oracle(self) -> None:
        manifest = {
            "cases": [{
                "id": "SQLT-UNSUPPORTED-004",
                "family": "unsupported",
                "dialects": ["mysql", "postgres"],
                "sql_file": "unsupported/call.sql",
            }]
        }
        oracles = {
            "results": {
                "SQLT-UNSUPPORTED-004": {
                    "flow": "procedure_call",
                    "expected": {"mysql": {}},
                }
            }
        }
        self.assertEqual(
            list(SELECTOR.select_cases(manifest, oracles)),
            [("SQLT-UNSUPPORTED-004", "mysql", "unsupported/call.sql", "procedure_call")],
        )


if __name__ == "__main__":
    unittest.main()
