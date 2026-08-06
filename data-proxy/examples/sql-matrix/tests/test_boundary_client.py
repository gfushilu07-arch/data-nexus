from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sql_matrix_boundary_client", MATRIX_ROOT / "boundary_client.py")
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)


class BoundaryClientTest(unittest.TestCase):
    def test_generated_query_frame_has_exact_total_size(self) -> None:
        frame = CLIENT.generated_query_frame(4096)
        self.assertEqual(len(frame), 4096)
        self.assertEqual(frame[:1], b"Q")
        self.assertEqual(int.from_bytes(frame[1:5], "big"), 4095)
        self.assertEqual(frame[-1:], b"\0")

    def test_generated_query_frame_rejects_unbounded_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "fixed SQLT-3F2 bounds"):
            CLIENT.generated_query_frame(16 * 1024 * 1024 + 2)

    def test_nested_sql_has_fixed_dimensions(self) -> None:
        sql = CLIENT.generated_nested_sql(4, 8)
        self.assertEqual(sql.count("("), 5)
        self.assertEqual(sql.count(")"), 5)
        self.assertIn("0,1,2,3,4,5,6,7", sql)

    def test_mysql_execute_bodies_are_distinct(self) -> None:
        bodies = {kind: CLIENT.mysql_execute_body(7, kind) for kind in ("missing", "extra", "invalid_type")}
        self.assertEqual(len(bodies["missing"]), 9)
        self.assertNotEqual(bodies["extra"], bodies["invalid_type"])


if __name__ == "__main__":
    unittest.main()
