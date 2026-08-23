from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "governance_matrix", ROOT / "governance_matrix.py"
)
assert SPEC and SPEC.loader
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)

SELECTION = importlib.util.spec_from_file_location(
    "select_governance_cases", ROOT / "select_governance_cases.py"
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


def transcript(selection: dict, protocol: str) -> dict:
    steps = []
    for expected in selection["gateway_steps"]:
        step = dict(expected)
        step.setdefault("affected_rows", None)
        step.setdefault("command_tag", None)
        step.setdefault("error_code", None)
        step.setdefault("sqlstate", None)
        step.setdefault("transaction_status", None)
        if "rows" not in step:
            step["rows"] = []
        step["expectation_met"] = (step["kind"] == "error") == step["expected_error"]
        steps.append(step)
    connection = (
        "orchestrated" if selection.get("requires_ticket_orchestration") else "same"
    )
    return {
        "protocol": protocol,
        "connection": connection,
        "steps": steps,
    }


class GovernanceMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        spec = json.loads((ROOT / "governance-matrix.json").read_text(encoding="utf-8"))
        oracles = json.loads((ROOT / "governance-oracles.json").read_text(encoding="utf-8"))
        self.selections = {
            (record["case_id"], record["policy"], record["protocol"]): record
            for record in SELECTOR.select_paths(spec, oracles, ROOT)
        }

    def evidence(self) -> dict[str, str]:
        return {
            "gateway_before": "/evidence/before",
            "gateway_transcript": "/evidence/transcript",
            "gateway_after": "/evidence/after",
        }

    def test_baseline_insert_persists_state_change(self) -> None:
        selection = self.selections[("SQLT-GOV-003", "security_off", "mysql_text_to_mysql")]
        result = MATRIX.verify_path(
            selection,
            state("mysql_text", selection["before_state"]),
            transcript(selection, "mysql_text"),
            state("mysql_text", selection["after_state"]),
            self.evidence(),
            "repro-command",
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["state_evidence"]["after_state"], selection["after_state"])
        self.assertEqual(result["denied_steps"], [])

    def test_denied_write_requires_unchanged_backend_state(self) -> None:
        selection = self.selections[("SQLT-GOV-003", "deny_dml", "pg_simple_to_postgres")]
        gateway = transcript(selection, "pg_simple")
        result = MATRIX.verify_path(
            selection,
            state("pg_simple", selection["before_state"]),
            gateway,
            state("pg_simple", selection["before_state"]),
            self.evidence(),
            "repro-command",
        )
        self.assertEqual(len(result["denied_steps"]), 1)
        self.assertTrue(result["policy_enabled"])
        # A deny that nonetheless changed backend state must trip the invariant.
        mutated = [row if row[0] != "mutations" else ["mutations", "1"]
                   for row in selection["before_state"]]
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.verify_path(
                selection,
                state("pg_simple", selection["before_state"]),
                gateway,
                state("pg_simple", mutated),
                self.evidence(),
                "repro-command",
            )

    def test_row_filter_policy_narrows_rows_without_backend_change(self) -> None:
        selection = self.selections[("SQLT-GOV-001", "row_filter_tenant10", "pg_simple_to_postgres")]
        result = MATRIX.verify_path(
            selection,
            state("pg_simple", selection["before_state"]),
            transcript(selection, "pg_simple"),
            state("pg_simple", selection["after_state"]),
            self.evidence(),
            "repro-command",
        )
        self.assertEqual(
            result["step_transcript"]["gateway"][0]["rows"],
            [["101", "Ada"], ["102", "Lin"]],
        )

    def test_step_value_mismatch_fails(self) -> None:
        selection = self.selections[("SQLT-GOV-002", "deny_select_targets", "mysql_text_to_mysql")]
        gateway = transcript(selection, "mysql_text")
        gateway["steps"][0]["sqlstate"] = "XX000"
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.verify_path(
                selection,
                state("mysql_text", selection["before_state"]),
                gateway,
                state("mysql_text", selection["after_state"]),
                self.evidence(),
                "repro-command",
            )

    def test_formal_aggregate_requires_exact_shape(self) -> None:
        results = []
        selections = []
        for (_, _, _), selection in sorted(self.selections.items()):
            selections.append(selection)
            state_protocol = MATRIX.state_protocol_for(selection["backend"])
            before = state(state_protocol, selection["before_state"])
            after = state(state_protocol, selection["after_state"])
            results.append(MATRIX.verify_path(
                selection, before, transcript(selection, selection["client_protocol"]),
                after, self.evidence(), "repro-command",
            ))
        summary = MATRIX.aggregate(selections, results, "run-id", "/run/dir", filtered=False)
        self.assertTrue(summary["acceptance_complete"])
        self.assertEqual(summary["paths"], 144)
        self.assertEqual(summary["cases"], 6)
        self.assertEqual(summary["policies"]["security_off"], 12)
        self.assertEqual(summary["protocols"]["mysql_text_to_mysql"], 72)

    def test_filtered_aggregate_marks_incomplete(self) -> None:
        selection = self.selections[("SQLT-GOV-004", "deny_dml", "pg_simple_to_postgres")]
        before = state("pg_simple", selection["before_state"])
        result = MATRIX.verify_path(
            selection, before, transcript(selection, "pg_simple"), before,
            self.evidence(), "repro-command",
        )
        summary = MATRIX.aggregate([selection], [result], "run-id", "/run/dir", filtered=True)
        self.assertFalse(summary["acceptance_complete"])
        with self.assertRaises(MATRIX.MatrixError):
            MATRIX.aggregate([selection], [result], "run-id", "/run/dir", filtered=False)


if __name__ == "__main__":
    unittest.main()
