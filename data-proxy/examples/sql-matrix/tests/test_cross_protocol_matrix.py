from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cross_protocol_matrix", ROOT / "cross_protocol_matrix.py")
assert SPEC and SPEC.loader
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)


class CrossProtocolMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = {
            "case_id": "SQLT-DQL-004", "source_case_id": "SQLT-DQL-004",
            "direction": "mysql_text_to_postgres", "frontend": "mysql_text",
            "backend": "postgres", "protocol": "mysql_text",
            "backend_control_protocol": "pg_simple", "columns": ["one_value"],
            "frontend_types": ["VAR_STRING"], "rows_text": "1\n",
            "backend_rows_text": "1\n", "rewrite_tags": [],
        }
        self.backend = {
            "protocol": "pg_simple", "columns": ["one_value"], "types": ["int4"],
            "rows": [["1"]], "rows_text": "1\n", "row_count": 1,
        }
        self.gateway = {
            "protocol": "mysql_text", "columns": ["one_value"], "types": ["VAR_STRING"],
            "rows": [["1"]], "rows_text": "1\n", "row_count": 1,
        }

    def test_verify_path_returns_structured_passed_record(self) -> None:
        value = MATRIX.verify_path(self.selection, self.backend, self.gateway, "b.json", "g.json", "cmd")
        self.assertEqual(value["status"], "passed")
        self.assertEqual(
            value["type_map"],
            {"backend_control": ["int4"], "gateway": ["VAR_STRING"]},
        )

    def test_gateway_type_or_rows_drift_is_rejected(self) -> None:
        broken = copy.deepcopy(self.gateway)
        broken["types"] = ["LONG"]
        with self.assertRaisesRegex(MATRIX.MatrixError, "frontend types"):
            MATRIX.verify_path(self.selection, self.backend, broken, "b", "g", "cmd")
        broken = copy.deepcopy(self.gateway)
        broken["rows_text"] = "2\n"
        with self.assertRaisesRegex(MATRIX.MatrixError, "gateway rows"):
            MATRIX.verify_path(self.selection, self.backend, broken, "b", "g", "cmd")

    def test_filtered_aggregate_cannot_claim_formal_acceptance(self) -> None:
        result = MATRIX.verify_path(self.selection, self.backend, self.gateway, "b", "g", "cmd")
        summary = MATRIX.aggregate([self.selection], [result], "run", "/run", True)
        self.assertFalse(summary["acceptance_complete"])
        self.assertEqual(summary["paths"], 1)


if __name__ == "__main__":
    unittest.main()
