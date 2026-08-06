from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("cursor_client", ROOT / "cursor_client.py")
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class CursorClientTest(unittest.TestCase):
    def test_read_steps_keeps_sql_and_declared_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.sql"
            path.write_text(
                "-- case: SQLT-CURSOR-999\n"
                "-- Purpose: Test parser.\n"
                "-- Expected: Preserve SQL blocks.\n"
                "-- Dialect: postgres\n\n"
                "-- @step first\nSELECT ';' AS value;\n"
                "-- @step terminate_backend\n-- @action backend_terminate\n"
                "SELECT pg_terminate_backend(:backend_pid);\n",
                encoding="utf-8",
            )
            steps = CLIENT.read_steps(path)
        self.assertEqual([step.name for step in steps], ["first", "terminate_backend"])
        self.assertEqual(steps[0].sql, "SELECT ';' AS value;")
        self.assertEqual(steps[1].action, "backend_terminate")

    def test_compare_step_requires_exact_error_identity(self) -> None:
        actual = {"name": "duplicate", "errors": [{"sqlstate": "42P03"}], "ready": ["E"]}
        CLIENT.compare_step(actual, {"sqlstates": ["42P03"], "ready": ["E"]})
        with self.assertRaisesRegex(AssertionError, "SQLSTATE"):
            CLIENT.compare_step(actual, {"sqlstates": ["34000"], "ready": ["E"]})

    def test_compare_step_requires_exact_cleanup_count(self) -> None:
        actual = {"name": "cleanup_probe", "rows": [["1"]], "commands": ["SELECT 1"]}
        with self.assertRaisesRegex(AssertionError, "rows"):
            CLIENT.compare_step(actual, {"rows": [["0"]], "commands": ["SELECT 1"]})

    def test_event_summary_normalizes_rows_commands_and_ready(self) -> None:
        events = [
            {"tag": "RowDescription", "columns": [{"name": "id"}]},
            {"tag": "DataRow", "row": ["101"]},
            {"tag": "CommandComplete", "command": "FETCH 1"},
            {"tag": "ReadyForQuery", "status": "T"},
        ]
        summary = CLIENT.event_summary(events)
        self.assertEqual(summary["rows"], [["101"]])
        self.assertEqual(summary["commands"], ["FETCH 1"])
        self.assertEqual(summary["ready"], ["T"])


if __name__ == "__main__":
    unittest.main()
