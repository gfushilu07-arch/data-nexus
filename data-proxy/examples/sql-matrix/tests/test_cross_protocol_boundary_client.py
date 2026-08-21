from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "cross_protocol_boundary_client", ROOT / "cross_protocol_boundary_client.py"
)
assert SPEC and SPEC.loader
CLIENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLIENT)

CASE_FILE = ROOT / "cases/cross-boundary/mysql-003-typed-parameter-roundtrip.sql"
PG_CASE_FILE = ROOT / "cases/cross-boundary/postgres-008-transactional-param-dml.sql"


class CrossProtocolBoundaryClientTest(unittest.TestCase):
    def test_read_steps_skips_header_and_keeps_step_names(self) -> None:
        steps = CLIENT.read_steps(CASE_FILE)
        self.assertEqual(list(steps), ["select"])
        self.assertIn("?", steps["select"])

    def test_read_steps_keeps_transaction_lifecycle(self) -> None:
        steps = CLIENT.read_steps(PG_CASE_FILE)
        self.assertEqual(
            list(steps),
            [
                "begin", "insert", "commit", "verify",
                "begin_rollback", "update", "rollback", "verify_rollback",
            ],
        )
        self.assertEqual(steps["insert"].count("$"), 4)

    def test_expand_parameter_converts_oracle_values(self) -> None:
        self.assertEqual(CLIENT.expand_parameter({"decimal": "12.30"}), Decimal("12.30"))
        self.assertEqual(
            CLIENT.expand_parameter({"datetime": "2026-08-15 10:20:30"}),
            dt.datetime(2026, 8, 15, 10, 20, 30),
        )
        self.assertEqual(CLIENT.expand_parameter(7), 7)
        self.assertIsNone(CLIENT.expand_parameter(None))

    def test_normalize_matches_oracle_row_text(self) -> None:
        self.assertEqual(CLIENT.normalize(Decimal("66.00")), "66.00")
        self.assertIsNone(CLIENT.normalize(None))
        self.assertEqual(
            CLIENT.normalize(dt.datetime(2026, 8, 15, 10, 20, 30)),
            "2026-08-15 10:20:30",
        )

    def test_classify_message_error_is_stable(self) -> None:
        self.assertEqual(
            CLIENT.classify_message_error(
                "translation policy 'p': DDL DROP is not supported for mysql -> postgresql"
            ),
            "translation_error",
        )
        self.assertEqual(
            CLIENT.classify_message_error(
                "postgresql prepared Execute expects 1 parameters, got 0"
            ),
            "gateway_error",
        )
        self.assertEqual(CLIENT.classify_message_error("some backend failure"), "backend_error")

    def test_oracle_parameters_and_steps_close_over_all_cases(self) -> None:
        oracle = json.loads(
            (ROOT / "cross-protocol-boundary-oracles.json").read_text(encoding="utf-8")
        )
        spec = json.loads(
            (ROOT / "cross-protocol-boundary-matrix.json").read_text(encoding="utf-8")
        )
        for case in spec["cases"]:
            for direction in spec["directions"]:
                lane = oracle["results"][case["id"]][direction]
                sql_path = ROOT / "cases" / case["sql"][direction]
                steps = CLIENT.read_steps(sql_path)
                step_names = {step["name"] for step in lane["steps"]}
                # Driver-issued parameter bindings must reference SQL steps that exist.
                for name in lane.get("parameters", {}):
                    self.assertIn(name, set(steps) | step_names)


if __name__ == "__main__":
    unittest.main()
