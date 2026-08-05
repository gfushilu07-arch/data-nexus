from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sql_matrix_normalize", MATRIX_ROOT / "normalize.py")
assert SPEC and SPEC.loader
NORMALIZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NORMALIZE)


class NormalizeSqlOutputTest(unittest.TestCase):
    def test_normalizes_line_endings_and_trailing_space(self) -> None:
        source = "101\tAda  \r\n102\tLin\r\n\r\n"
        self.assertEqual(NORMALIZE.normalize_text(source), "101\tAda\n102\tLin\n")

    def test_preserves_null_marker_and_row_order(self) -> None:
        source = "102\t<NULL>\n101\tada@example.test\n"
        self.assertEqual(NORMALIZE.normalize_text(source), source)

    def test_empty_output_stays_empty(self) -> None:
        self.assertEqual(NORMALIZE.normalize_text("\r\n\n"), "")

    def test_normalizes_mysql_error_identity(self) -> None:
        source = "ERROR 1054 (42S22) at line 6: Unknown column 'secret'\n"
        self.assertEqual(
            NORMALIZE.normalize_error_text(source, "mysql"),
            "mysql\t1054\t42S22\n",
        )

    def test_normalizes_postgres_sqlstate(self) -> None:
        source = "ERROR:  42703\n"
        self.assertEqual(
            NORMALIZE.normalize_error_text(source, "postgres"),
            "postgres\t42703\n",
        )

    def test_unclassified_error_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot classify"):
            NORMALIZE.normalize_error_text("connection closed", "postgres")

    def test_normalizes_mysql_affected_rows(self) -> None:
        source = "Query OK, 2 rows affected (0.01 sec)\nRows matched: 2\n"
        self.assertEqual(NORMALIZE.normalize_affected_rows(source, "mysql"), "2\n")

    def test_normalizes_postgres_affected_rows(self) -> None:
        self.assertEqual(NORMALIZE.normalize_affected_rows("UPDATE 3\n", "postgres"), "3\n")

    def test_affected_rows_requires_one_marker(self) -> None:
        with self.assertRaisesRegex(ValueError, "expected one"):
            NORMALIZE.normalize_affected_rows("UPDATE 1\nDELETE 1\n", "postgres")


if __name__ == "__main__":
    unittest.main()
