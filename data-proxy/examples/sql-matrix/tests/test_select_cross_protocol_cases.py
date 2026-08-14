from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "select_cross_protocol_cases", ROOT / "select_cross_protocol_cases.py"
)
assert SPEC and SPEC.loader
SELECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTOR)


class SelectCrossProtocolCasesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = json.loads((ROOT / "cross-protocol-matrix.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.oracles = json.loads((ROOT / "cross-protocol-oracles.json").read_text(encoding="utf-8"))
        self.dql_oracles = json.loads((ROOT / "dql-oracles.json").read_text(encoding="utf-8"))

    def select(self, **kwargs):
        return SELECTOR.select_paths(
            self.spec, self.manifest, self.oracles, self.dql_oracles, ROOT, **kwargs
        )

    def test_formal_selection_is_exactly_twelve_cases_and_two_directions(self) -> None:
        selected = self.select()
        self.assertEqual(len(selected), 24)
        self.assertEqual(len({record["case_id"] for record in selected}), 12)
        self.assertEqual(
            {record["direction"] for record in selected},
            {"mysql_text_to_postgres", "pg_simple_to_mysql"},
        )

    def test_direction_and_case_filters_preserve_exact_records(self) -> None:
        selected = self.select(
            direction_filter="mysql_text_to_postgres",
            case_from="SQLT-XDQL-001",
            case_to="SQLT-XDQL-001",
        )
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["sql_file"], "cross/mysql-identifier-quote.sql")
        self.assertEqual(selected[0]["rewrite_tags"], ["identifier_quote"])

    def test_rows_use_target_backend_oracle(self) -> None:
        selected = self.select(case_from="SQLT-DQL-006", case_to="SQLT-DQL-006")
        rows = {record["direction"]: record["rows_text"] for record in selected}
        self.assertEqual(rows["mysql_text_to_postgres"], "NULL\tt\n")
        self.assertEqual(rows["pg_simple_to_mysql"], "NULL\t1\n")

    def test_source_case_must_be_bidialect_dql(self) -> None:
        broken = copy.deepcopy(self.spec)
        broken["cases"][0]["source_case_id"] = "SQLT-DQL-002"
        with self.assertRaisesRegex(SELECTOR.SelectionError, "both dialects"):
            SELECTOR.select_paths(
                broken, self.manifest, self.oracles, self.dql_oracles, ROOT
            )

    def test_spec_and_oracle_case_sets_must_match(self) -> None:
        broken = copy.deepcopy(self.oracles)
        broken["results"].pop("SQLT-XDQL-003")
        with self.assertRaisesRegex(SELECTOR.SelectionError, "do not match"):
            SELECTOR.select_paths(
                self.spec, self.manifest, broken, self.dql_oracles, ROOT
            )

    def test_frontend_type_count_must_match_columns(self) -> None:
        broken = copy.deepcopy(self.oracles)
        broken["results"]["SQLT-DQL-004"]["frontend_types"]["pg_simple_to_mysql"] = []
        with self.assertRaisesRegex(SELECTOR.SelectionError, "type count"):
            SELECTOR.select_paths(
                self.spec, self.manifest, broken, self.dql_oracles, ROOT
            )

    def test_unknown_direction_and_partial_range_are_rejected(self) -> None:
        with self.assertRaisesRegex(SELECTOR.SelectionError, "unknown"):
            self.select(direction_filter="unknown")
        with self.assertRaisesRegex(SELECTOR.SelectionError, "both case"):
            self.select(case_from="SQLT-DQL-001")


if __name__ == "__main__":
    unittest.main()
