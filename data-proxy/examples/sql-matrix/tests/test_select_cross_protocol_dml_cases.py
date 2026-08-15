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
    "select_cross_protocol_dml_cases", ROOT / "select_cross_protocol_dml_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectCrossProtocolDmlCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = json.loads(
            (ROOT / "cross-protocol-dml-matrix.json").read_text(encoding="utf-8")
        )
        self.oracles = json.loads(
            (ROOT / "cross-protocol-dml-oracles.json").read_text(encoding="utf-8")
        )

    def select(self, **kwargs):
        return SELECTOR.select_paths(self.spec, self.oracles, ROOT, **kwargs)

    def test_formal_selection_is_eight_cases_and_sixteen_paths(self) -> None:
        selected = self.select()
        self.assertEqual(len(selected), 16)
        self.assertEqual(len({record["case_id"] for record in selected}), 8)
        self.assertEqual(
            {record["direction"] for record in selected},
            {"mysql_text_to_postgres", "pg_simple_to_mysql"},
        )

    def test_error_identity_and_transaction_state_are_frontend_specific(self) -> None:
        selected = self.select(case_from="SQLT-XDML-008", case_to="SQLT-XDML-008")
        records = {record["direction"]: record for record in selected}
        mysql_error = records["mysql_text_to_postgres"]["gateway_steps"][2]
        postgres_error = records["pg_simple_to_mysql"]["gateway_steps"][2]
        self.assertEqual((mysql_error["error_code"], mysql_error["sqlstate"]), ("1105", "HY000"))
        self.assertEqual(mysql_error["transaction_status"], "T")
        self.assertEqual(postgres_error["sqlstate"], "XX000")
        self.assertEqual(postgres_error["transaction_status"], "E")

    def test_backend_control_uses_backend_dialect_script(self) -> None:
        selected = self.select(
            direction_filter="mysql_text_to_postgres",
            case_from="SQLT-XDML-001",
            case_to="SQLT-XDML-001",
        )
        self.assertEqual(selected[0]["sql_file"], "cross-dml/mysql-autocommit-insert.sql")
        self.assertEqual(
            selected[0]["backend_sql_file"],
            "cross-dml/postgres-autocommit-insert.sql",
        )

    def test_filters_cannot_change_expanded_oracle(self) -> None:
        selected = self.select(
            direction_filter="pg_simple_to_mysql",
            case_from="SQLT-XDML-006",
            case_to="SQLT-XDML-006",
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(
            [step["transaction_status"] for step in selected[0]["gateway_steps"]],
            ["T", "T", "I", "I"],
        )

    def test_missing_wire_profile_and_partial_range_are_rejected(self) -> None:
        broken = copy.deepcopy(self.oracles)
        broken["wire_profiles"]["gateway"]["mysql_text_to_postgres"].pop("ok_i")
        with self.assertRaisesRegex(SELECTOR.SelectionError, "wire fields"):
            SELECTOR.select_paths(self.spec, broken, ROOT)
        with self.assertRaisesRegex(SELECTOR.SelectionError, "both case"):
            self.select(case_from="SQLT-XDML-001")


if __name__ == "__main__":
    unittest.main()
