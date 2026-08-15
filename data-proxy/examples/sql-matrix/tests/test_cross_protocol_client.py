from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("cross_protocol_client", ROOT / "cross_protocol_client.py")
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class CrossProtocolClientTest(unittest.TestCase):
    def test_read_sql_skips_four_line_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.sql"
            path.write_text("-- case: X\n-- Purpose: P\n-- Expected: E\n-- Dialect: mysql\n\nSELECT 1;\n")
            self.assertEqual(CLIENT.read_sql(path), "SELECT 1;")

    def test_result_normalizes_null_decimal_boolean_and_order(self) -> None:
        value = CLIENT.result(
            "mysql_text", ["a", "b", "c"], ["LONG", "NEWDECIMAL", "TINY"],
            [[None, Decimal("12.50"), True], ["x", Decimal("0.00"), False]],
        )
        self.assertEqual(value["rows_text"], "NULL\t12.50\t1\nx\t0.00\t0\n")
        self.assertEqual(value["row_count"], 2)

    def test_mysql_client_uses_query_only_connection(self) -> None:
        source = (ROOT / "cross_protocol_client.py").read_text(encoding="utf-8")
        self.assertIn("class QueryOnlyConnection(MySQLConnection)", source)
        self.assertIn("def _post_connection(self) -> None:", source)
        self.assertIn("use_pure=True", source)


if __name__ == "__main__":
    unittest.main()
