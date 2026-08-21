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
    "select_cross_protocol_boundary_cases", ROOT / "select_cross_protocol_boundary_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectCrossProtocolBoundaryCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = json.loads(
            (ROOT / "cross-protocol-boundary-matrix.json").read_text(encoding="utf-8")
        )
        self.oracles = json.loads(
            (ROOT / "cross-protocol-boundary-oracles.json").read_text(encoding="utf-8")
        )

    def select(self, oracles=None, **kwargs):
        return SELECTOR.select_paths(self.spec, oracles or self.oracles, ROOT, **kwargs)

    def test_formal_selection_is_thirteen_cases_and_twenty_six_paths(self) -> None:
        selected = self.select()
        self.assertEqual(len(selected), 26)
        self.assertEqual(len({record["case_id"] for record in selected}), 13)
        self.assertEqual(
            {record["direction"] for record in selected},
            {"mysql_binary_to_postgres", "pg_extended_to_mysql"},
        )
        outcomes = [record["outcome"] for record in selected]
        self.assertEqual(outcomes.count("success"), 16)
        self.assertEqual(outcomes.count("reject"), 10)

    def test_backend_control_uses_opposite_direction_params_and_sql(self) -> None:
        selected = self.select(
            direction_filter="mysql_binary_to_postgres",
            case_from="SQLT-XBND-001",
            case_to="SQLT-XBND-001",
        )
        record = selected[0]
        self.assertEqual(record["sql_file"], "cross-boundary/mysql-001-zero-parameter-lifecycle.sql")
        self.assertEqual(
            record["backend_sql_file"],
            "cross-boundary/postgres-001-zero-parameter-lifecycle.sql",
        )
        self.assertEqual(record["backend_direction"], "pg_extended_to_mysql")
        self.assertEqual(record["backend_control_protocol"], "pg_extended")

    def test_repeated_placeholder_params_differ_per_direction(self) -> None:
        selected = self.select(
            case_from="SQLT-XBND-004", case_to="SQLT-XBND-004"
        )
        records = {record["direction"]: record for record in selected}
        self.assertEqual(len(records["mysql_binary_to_postgres"]["parameters"]["select"]), 3)
        self.assertEqual(len(records["pg_extended_to_mysql"]["parameters"]["select"]), 2)
        for record in records.values():
            self.assertEqual(record["gateway_steps"][0]["rows"], [["7", "8", "7"]])

    def test_reject_paths_pin_stable_error_identity_and_backend_zero_touch(self) -> None:
        selected = self.select(outcome_filter="reject")
        self.assertEqual(len(selected), 10)
        by_id_direction = {(r["case_id"], r["direction"]): r for r in selected}
        mysql_ddl = by_id_direction[("SQLT-XBND-009", "mysql_binary_to_postgres")]
        self.assertEqual(
            (mysql_ddl["gateway_steps"][0]["error_code"], mysql_ddl["gateway_steps"][0]["sqlstate"]),
            ("1105", "HY000"),
        )
        self.assertEqual(mysql_ddl["gateway_steps"][0]["classification"], "translation_error")
        pg_ddl = by_id_direction[("SQLT-XBND-009", "pg_extended_to_mysql")]
        self.assertEqual(pg_ddl["gateway_steps"][0]["sqlstate"], "XX000")
        self.assertEqual(pg_ddl["gateway_steps"][0]["transaction_status"], "I")
        self.assertEqual(pg_ddl["gateway_steps"][0]["wire"], "1 2 E Z")
        for record in selected:
            self.assertEqual(record["before_state"], record["after_state"])
            self.assertTrue(any(step["kind"] == "error" for step in record["gateway_steps"]))

    def test_success_transaction_case_expects_mutation_state_change(self) -> None:
        selected = self.select(
            case_from="SQLT-XBND-008", case_to="SQLT-XBND-008"
        )
        for record in selected:
            self.assertEqual(record["before_state"], [["customers", "4"], ["mutations", "0"]])
            self.assertEqual(record["after_state"], [["customers", "4"], ["mutations", "1"]])

    def test_unknown_case_id_is_rejected(self) -> None:
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(case_from="SQLT-XBND-014", case_to="SQLT-XBND-014")

    def test_mismatched_expected_error_kind_is_rejected(self) -> None:
        oracles = copy.deepcopy(self.oracles)
        step = oracles["results"]["SQLT-XBND-009"]["pg_extended_to_mysql"]["steps"][0]
        step["expected_error"] = False
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(oracles=oracles)

    def test_missing_direction_lane_is_rejected(self) -> None:
        oracles = copy.deepcopy(self.oracles)
        del oracles["results"]["SQLT-XBND-001"]["pg_extended_to_mysql"]
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(oracles=oracles)

    def test_direction_and_outcome_filters_require_complete_pairs(self) -> None:
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(direction_filter="unknown_lane")
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(outcome_filter="unknown_outcome")
        with self.assertRaises(SELECTOR.SelectionError):
            self.select(case_from="SQLT-XBND-002")


if __name__ == "__main__":
    unittest.main()
