from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "select_governance_cases", ROOT / "select_governance_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectGovernanceCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = json.loads(
            (ROOT / "governance-matrix.json").read_text(encoding="utf-8")
        )
        self.oracles = json.loads(
            (ROOT / "governance-oracles.json").read_text(encoding="utf-8")
        )

    def select(self, oracles=None, **kwargs):
        return SELECTOR.select_paths(
            self.spec, oracles or self.oracles, ROOT,
            protocol_filter=kwargs.pop("protocol", ""),
            policy_filter=kwargs.pop("policy", ""),
            case_from=kwargs.pop("case_from", ""),
            case_to=kwargs.pop("case_to", ""),
        )

    def test_formal_selection_is_eight_policies_times_five_cases_times_two_protocols(self) -> None:
        selected = self.select()
        self.assertEqual(len(selected), 80)
        self.assertEqual(len({record["case_id"] for record in selected}), 5)
        self.assertEqual(
            {record["policy"] for record in selected},
            {"security_off", "deny_dml", "deny_select_targets", "row_filter_tenant10",
             "column_strip_amount", "mask_pii", "watermark_column", "max_rows_1"},
        )
        self.assertEqual(
            {record["protocol"] for record in selected},
            {"mysql_text_to_mysql", "pg_simple_to_postgres"},
        )

    def test_deny_dml_rejects_writes_before_backend_with_state_unchanged(self) -> None:
        selected = self.select(policy="deny_dml")
        for record in selected:
            steps = {step["name"]: step for step in record["gateway_steps"]}
            if record["case_id"] == "SQLT-GOV-003":
                self.assertTrue(steps["insert"]["expected_error"])
                self.assertEqual(record["after_state"], record["before_state"])
            if record["case_id"] == "SQLT-GOV-004":
                self.assertTrue(steps["insert"]["expected_error"])
                self.assertTrue(steps["delete"]["expected_error"])
                self.assertFalse(steps["verify_count"]["expected_error"])

    def test_row_filter_policy_narrows_customer_rows_only(self) -> None:
        selected = self.select(policy="row_filter_tenant10")
        by_case = {record["case_id"]: record for record in selected}
        self.assertEqual(
            by_case["SQLT-GOV-001"]["gateway_steps"][0]["rows"],
            [["101", "Ada"], ["102", "Lin"]],
        )
        # Non-customer statements stay allowed under the row-filter policy.
        self.assertFalse(by_case["SQLT-GOV-003"]["gateway_steps"][0]["expected_error"])
        self.assertEqual(by_case["SQLT-GOV-002"]["gateway_steps"][0]["rows"],
                         [["4001", "alpha", "10.00", "new"]])

    def test_deny_select_targets_never_leaks_target_rows(self) -> None:
        selected = self.select(policy="deny_select_targets")
        for record in selected:
            if record["case_id"] != "SQLT-GOV-002":
                continue
            step = record["gateway_steps"][0]
            self.assertEqual(step["kind"], "error")
            self.assertEqual(record["after_state"], record["before_state"])
            if record["protocol"] == "mysql_text_to_mysql":
                self.assertEqual((step["error_code"], step["sqlstate"]), ("1105", "HY000"))
            else:
                self.assertEqual(step["sqlstate"], "XX000")

    def test_security_off_baseline_is_full_access(self) -> None:
        selected = self.select(policy="security_off")
        for record in selected:
            for step in record["gateway_steps"]:
                self.assertFalse(step["expected_error"], (record["case_id"], step["name"]))
        insert = {
            record["case_id"]: record for record in selected
        }["SQLT-GOV-003"]
        self.assertEqual(insert["after_state"], [["customers", "4"], ["mutations", "1"]])

    def test_unknown_filters_are_rejected(self) -> None:
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(protocol="unknown_lane")
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(policy="unknown_policy")
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(case_from="SQLT-GOV-001")

    def test_mismatched_step_kind_is_rejected(self) -> None:
        oracles = copy.deepcopy(self.oracles)
        step = oracles["results"]["SQLT-GOV-002"]["pg_simple_to_postgres"]["deny_select_targets"]["steps"][0]
        step["kind"] = "rows"
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(oracles=oracles)

    def test_missing_policy_lane_is_rejected(self) -> None:
        oracles = copy.deepcopy(self.oracles)
        del oracles["results"]["SQLT-GOV-001"]["state"]["row_filter_tenant10"]
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(oracles=oracles)


if __name__ == "__main__":
    unittest.main()
