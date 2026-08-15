from __future__ import annotations

import importlib.util
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cross_protocol_dml_client", ROOT / "cross_protocol_dml_client.py"
)
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class CrossProtocolDmlClientTest(unittest.TestCase):
    def test_read_steps_preserves_order_and_expected_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.sql"
            path.write_text(
                "-- case: X\n-- Purpose: P\n-- Expected: E\n-- Dialect: mysql\n\n"
                "-- @step insert\nINSERT INTO t VALUES (1);\n"
                "-- @step duplicate\n-- @expect error\nINSERT INTO t VALUES (1);\n",
                encoding="utf-8",
            )
            steps = CLIENT.read_steps(path)
        self.assertEqual([step.name for step in steps], ["insert", "duplicate"])
        self.assertFalse(steps[0].expected_error)
        self.assertTrue(steps[1].expected_error)

    def test_pg_affected_accepts_native_and_gateway_tags(self) -> None:
        self.assertEqual(CLIENT.pg_affected("INSERT 0 1"), 1)
        self.assertEqual(CLIENT.pg_affected("UPDATE 3"), 3)
        self.assertEqual(CLIENT.pg_affected("DELETE 0"), 0)
        self.assertEqual(CLIENT.pg_affected("OK 2"), 2)
        self.assertEqual(CLIENT.pg_affected("BEGIN"), 0)

    def test_normalizes_decimal_boolean_and_null(self) -> None:
        self.assertEqual(
            CLIENT.normalized_rows([[Decimal("10.50"), True, None]]),
            [["10.50", "1", None]],
        )


if __name__ == "__main__":
    unittest.main()
