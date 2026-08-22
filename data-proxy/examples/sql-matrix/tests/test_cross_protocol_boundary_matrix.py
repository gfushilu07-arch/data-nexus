from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "cross_protocol_boundary_matrix", ROOT / "cross_protocol_boundary_matrix.py"
)
assert SPEC and SPEC.loader
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)

SELECTION = importlib.util.spec_from_file_location(
    "select_cross_protocol_boundary_cases", ROOT / "select_cross_protocol_boundary_cases.py"
)
assert SELECTION and SELECTION.loader
SELECTOR = importlib.util.module_from_spec(SELECTION)
SELECTION.loader.exec_module(SELECTOR)

BASELINE = [["customers", "4"], ["mutations", "0"]]
MUTATED = [["customers", "4"], ["mutations", "1"]]


def state(protocol: str, rows: list) -> dict:
    return {
        "protocol": protocol,
        "columns": ["entity", "cnt"],
        "types": ["text", "text"],
        "rows": rows,
        "rows_text": [", ".join(str(cell) for cell in row) for row in rows],
        "row_count": len(rows),
    }


def transcript(selection: dict, protocol: str, direction: str | None = None) -> dict:
    source = selection["gateway_steps"]
    if direction is not None and direction == selection.get("backend_direction"):
        source = selection["backend_steps"]
    steps = []
    for expected in source:
        step = dict(expected)
        step.setdefault("rows", [])
        step.setdefault("columns", None)
        step.setdefault("affected_rows", None)
        step.setdefault("command_tag", None)
        step.setdefault("transaction_status", None)
        step.setdefault("error_code", None)
        step.setdefault("sqlstate", None)
        step.setdefault("classification", None)
        step.setdefault("wire", None)
        step["expectation_met"] = (step["kind"] == "error") == step["expected_error"]
        steps.append(step)
    return {
        "protocol": protocol,
        "case_id": selection["case_id"],
        "direction": direction or selection["direction"],
        "steps": steps,
    }


class CrossProtocolBoundaryMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        spec = json.loads((ROOT / "cross-protocol-boundary-matrix.json").read_text(encoding="utf-8"))
        oracles = json.loads(
            (ROOT / "cross-protocol-boundary-oracles.json").read_text(encoding="utf-8")
        )
        self.selections = {
            (record["case_id"], record["direction"]): record
            for record in SELECTOR.select_paths(spec, oracles, ROOT)
        }

    def test_success_path_closes_against_backend_control_and_states(self) -> None:
        selection = self.selections[("SQLT-XBND-001", "mysql_binary_to_postgres")]
        backend = transcript(selection, "pg_extended", selection["backend_direction"])
        gateway = transcript(selection, "mysql_binary")
        result = MATRIX.verify_success_path(
            selection,
            state("pg_simple", BASELINE),
            backend,
            state("pg_simple", BASELINE),
            state("pg_simple", BASELINE),
            gateway,
            state("pg_simple", BASELINE),
            {name: f"/evidence/{name}" for name in (
                "backend_before", "backend_transcript", "backend_after",
                "gateway_before", "gateway_transcript", "gateway_after",
            )},
            "repro-command",
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["outcome"], "success")
        self.assertEqual(
            result["step_transcript"]["gateway"][0]["rows"],
            [["1001", "12.50", "paid"], ["1002", "99.99", "paid"]],
        )

    def test_transaction_success_path_requires_state_change(self) -> None:
        selection = self.selections[("SQLT-XBND-008", "pg_extended_to_mysql")]
        gateway = transcript(selection, "pg_extended")
        backend = transcript(selection, "mysql_binary", selection["backend_direction"])
        result = MATRIX.verify_success_path(
            selection,
            state("mysql_text", BASELINE),
            backend,
            state("mysql_text", MUTATED),
            state("mysql_text", BASELINE),
            gateway,
            state("mysql_text", MUTATED),
            {name: f"/evidence/{name}" for name in (
                "backend_before", "backend_transcript", "backend_after",
                "gateway_before", "gateway_transcript", "gateway_after",
            )},
            "repro-command",
        )
        self.assertEqual(result["gateway_evidence"]["after_state"], MUTATED)

    def test_reject_path_requires_error_and_unchanged_backend(self) -> None:
        selection = self.selections[("SQLT-XBND-009", "pg_extended_to_mysql")]
        gateway = transcript(selection, "pg_extended")
        result = MATRIX.verify_reject_path(
            selection,
            state("mysql_text", BASELINE),
            gateway,
            state("mysql_text", BASELINE),
            {
                "backend_before": "/evidence/backend_before",
                "gateway_transcript": "/evidence/gateway_transcript",
                "backend_after": "/evidence/backend_after",
            },
            "repro-command",
        )
        self.assertEqual(result["reject_evidence"]["backend_execute_count"], 0)
        self.assertTrue(result["reject_evidence"]["backend_state_unchanged"])
        self.assertEqual(
            result["reject_evidence"]["frontend_errors"][0]["sqlstate"], "XX000"
        )

    def test_reject_path_fails_when_backend_state_mutated(self) -> None:
        selection = self.selections[("SQLT-XBND-011", "mysql_binary_to_postgres")]
        gateway = transcript(selection, "mysql_binary")
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.verify_reject_path(
                selection,
                state("pg_simple", BASELINE),
                gateway,
                state("pg_simple", MUTATED),
                {
                    "backend_before": "/evidence/backend_before",
                    "gateway_transcript": "/evidence/gateway_transcript",
                    "backend_after": "/evidence/backend_after",
                },
                "repro-command",
            )

    def test_wire_or_classification_mismatch_fails(self) -> None:
        selection = self.selections[("SQLT-XBND-013", "pg_extended_to_mysql")]
        gateway = transcript(selection, "pg_extended")
        gateway["steps"][1]["wire"] = "3 Z E"
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.verify_reject_path(
                selection,
                state("mysql_text", BASELINE),
                gateway,
                state("mysql_text", BASELINE),
                {
                    "backend_before": "/evidence/backend_before",
                    "gateway_transcript": "/evidence/gateway_transcript",
                    "backend_after": "/evidence/backend_after",
                },
                "repro-command",
            )

    def test_formal_aggregate_requires_exact_shape(self) -> None:
        results = []
        selections = []
        for (case_id, direction), selection in sorted(self.selections.items()):
            selections.append(selection)
            protocol = "mysql_binary" if direction == "mysql_binary_to_postgres" else "pg_extended"
            if selection["outcome"] == "success":
                backend_protocol = (
                    "pg_extended" if direction == "mysql_binary_to_postgres" else "mysql_binary"
                )
                state_protocol = (
                    "pg_simple" if direction == "mysql_binary_to_postgres" else "mysql_text"
                )
                before = state(state_protocol, selection["before_state"])
                after = state(state_protocol, selection["after_state"])
                results.append(MATRIX.verify_success_path(
                    selection,
                    before,
                    transcript(selection, backend_protocol, selection["backend_direction"]),
                    after,
                    before,
                    transcript(selection, protocol),
                    after,
                    {name: f"/evidence/{name}" for name in (
                        "backend_before", "backend_transcript", "backend_after",
                        "gateway_before", "gateway_transcript", "gateway_after",
                    )},
                    "repro-command",
                ))
            else:
                state_protocol = (
                    "pg_simple" if direction == "mysql_binary_to_postgres" else "mysql_text"
                )
                before = state(state_protocol, selection["before_state"])
                results.append(MATRIX.verify_reject_path(
                    selection,
                    before,
                    transcript(selection, protocol),
                    before,
                    {
                        "backend_before": "/evidence/backend_before",
                        "gateway_transcript": "/evidence/gateway_transcript",
                        "backend_after": "/evidence/backend_after",
                    },
                    "repro-command",
                ))
        summary = MATRIX.aggregate(selections, results, "run-id", "/run/dir", filtered=False)
        self.assertTrue(summary["acceptance_complete"])
        self.assertEqual(summary["paths"], 26)
        self.assertEqual(summary["success_paths"], 16)
        self.assertEqual(summary["reject_paths"], 10)
        self.assertEqual(summary["lanes"], {"mysql_binary_to_postgres": 13, "pg_extended_to_mysql": 13})

    def test_incomplete_aggregate_fails(self) -> None:
        selection = self.selections[("SQLT-XBND-001", "mysql_binary_to_postgres")]
        state_protocol = "pg_simple"
        before = state(state_protocol, BASELINE)
        gateway = transcript(selection, "mysql_binary")
        backend = transcript(selection, "pg_extended", selection["backend_direction"])
        result = MATRIX.verify_success_path(
            selection, before, backend, before, before, gateway, before,
            {name: f"/evidence/{name}" for name in (
                "backend_before", "backend_transcript", "backend_after",
                "gateway_before", "gateway_transcript", "gateway_after",
            )},
            "repro-command",
        )
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.aggregate([selection], [result], "run-id", "/run/dir", filtered=False)
        summary = MATRIX.aggregate([selection], [result], "run-id", "/run/dir", filtered=True)
        self.assertFalse(summary["acceptance_complete"])


if __name__ == "__main__":
    unittest.main()
