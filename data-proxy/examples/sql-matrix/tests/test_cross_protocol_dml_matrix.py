from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cross_protocol_dml_matrix", ROOT / "cross_protocol_dml_matrix.py"
)
assert SPEC and SPEC.loader
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)


class CrossProtocolDmlMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        step = {
            "name": "insert", "expected_error": False, "kind": "ok",
            "affected_rows": 1, "command_tag": None, "rows": [],
            "error_code": None, "sqlstate": None, "transaction_status": "I",
        }
        self.selection = {
            "case_id": "SQLT-XDML-001", "name": "autocommit_insert",
            "direction": "mysql_text_to_postgres", "frontend": "mysql_text",
            "backend": "postgres", "protocol": "mysql_text",
            "backend_control_protocol": "pg_simple",
            "gateway_steps": [step], "backend_control_steps": [step],
            "before_state": [["target", "4001", "alpha", "10.00", "new"]],
            "after_state": [["mutation", "9301", "cross insert", "10.50", "new"]],
        }
        self.transcript = {
            "protocol": "mysql_text", "connection": "same",
            "steps": [{**step, "expectation_met": True}],
        }
        self.backend_transcript = copy.deepcopy(self.transcript)
        self.backend_transcript["protocol"] = "pg_simple"
        self.state_before = self._state(self.selection["before_state"])
        self.state_after = self._state(self.selection["after_state"])
        self.paths = {
            "backend_before": "bb.json", "backend_transcript": "bt.json",
            "backend_after": "ba.json", "gateway_before": "gb.json",
            "gateway_transcript": "gt.json", "gateway_after": "ga.json",
        }

    @staticmethod
    def _state(rows):
        return {
            "protocol": "pg_simple",
            "columns": ["entity", "entity_id", "description", "amount", "status"],
            "types": ["text", "int8", "varchar", "text", "varchar"],
            "rows": rows,
            "rows_text": "ignored by exact row comparison\n",
            "row_count": len(rows),
        }

    def verify(self, **overrides):
        values = {
            "selection": self.selection,
            "backend_before": self.state_before,
            "backend_transcript": self.backend_transcript,
            "backend_after": self.state_after,
            "gateway_before": self.state_before,
            "gateway_transcript": self.transcript,
            "gateway_after": self.state_after,
            "evidence_paths": self.paths,
            "reproduction": "cmd",
        }
        values.update(overrides)
        return MATRIX.verify_path(**values)

    def test_verify_path_returns_full_step_and_state_evidence(self) -> None:
        value = self.verify()
        self.assertEqual(value["status"], "passed")
        self.assertEqual(value["affected_map"]["gateway"], {"insert": 1})
        self.assertEqual(
            value["error_transaction_map"]["gateway"]["insert"]["transaction_status"],
            "I",
        )
        self.assertEqual(value["final_state_evidence"]["gateway"], self.selection["after_state"])

    def test_step_or_state_drift_is_rejected(self) -> None:
        broken = copy.deepcopy(self.transcript)
        broken["steps"][0]["affected_rows"] = 0
        with self.assertRaisesRegex(MATRIX.MatrixError, "step insert mismatch"):
            self.verify(gateway_transcript=broken)
        broken_state = copy.deepcopy(self.state_after)
        broken_state["rows"] = []
        with self.assertRaisesRegex(MATRIX.MatrixError, "state rows mismatch"):
            self.verify(gateway_after=broken_state)

    def test_filtered_aggregate_cannot_claim_formal_acceptance(self) -> None:
        result = self.verify()
        summary = MATRIX.aggregate([self.selection], [result], "run", "/run", True)
        self.assertFalse(summary["acceptance_complete"])
        self.assertEqual(summary["paths"], 1)


if __name__ == "__main__":
    unittest.main()
