from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_unsupported_client", MATRIX_ROOT / "unsupported_client.py"
)
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class UnsupportedClientTest(unittest.TestCase):
    def sql_file(self, body: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False)
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        with handle:
            handle.write(
                "-- case: SQLT-UNSUPPORTED-999\n"
                "-- Purpose: Test parser.\n"
                "-- Expected: Test parser.\n"
                "-- Dialect: mysql, postgres\n\n"
                + body
            )
        return Path(handle.name)

    def test_single_statement_becomes_main_step(self) -> None:
        path = self.sql_file("SELECT 1;\n")
        self.assertEqual(CLIENT.sql_steps(path, "mysql"), [("main", "SELECT 1;")])

    def test_step_parser_selects_only_requested_dialect(self) -> None:
        path = self.sql_file(
            "-- @step first mysql\nSELECT 1;\n"
            "-- @step second postgres\nSELECT 2;\n"
            "-- @step third mysql\nSELECT 3;\n"
        )
        self.assertEqual(
            CLIENT.sql_steps(path, "mysql"),
            [("first", "SELECT 1;"), ("third", "SELECT 3;")],
        )

    def test_step_parser_rejects_unscoped_sql(self) -> None:
        path = self.sql_file("SELECT 0;\n-- @step first mysql\nSELECT 1;\n")
        with self.assertRaisesRegex(ValueError, "before the first"):
            CLIENT.sql_steps(path, "mysql")

    def test_step_parser_rejects_empty_dialect_selection(self) -> None:
        path = self.sql_file("-- @step first postgres\nSELECT 1;\n")
        with self.assertRaisesRegex(ValueError, "no SQL steps for dialect mysql"):
            CLIENT.sql_steps(path, "mysql")

    def test_capability_extracts_only_stable_code(self) -> None:
        self.assertEqual(
            CLIENT.capability("unsupported capability: mysql.load_data"),
            "mysql.load_data",
        )
        self.assertIsNone(CLIENT.capability("Access denied for /private/path"))


if __name__ == "__main__":
    unittest.main()
