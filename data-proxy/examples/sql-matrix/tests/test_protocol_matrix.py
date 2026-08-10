from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_SPEC = importlib.util.spec_from_file_location("protocol_matrix", ROOT / "protocol_matrix.py")
assert MODULE_SPEC and MODULE_SPEC.loader
MATRIX = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MATRIX)


class ProtocolMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output = Path(self.temp_dir.name)
        self.spec = json.loads((ROOT / "protocol-matrix.json").read_text(encoding="utf-8"))
        self.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.summaries = self._write_summaries()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, suite: str, results: list[dict]) -> Path:
        path = self.output / suite / "summary.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps({"failed": 0, "passed": len(results), "results": results}) + "\n",
            encoding="utf-8",
        )
        return path

    def _write_summaries(self) -> dict[str, Path]:
        cases = {case["id"]: case for case in self.manifest["cases"]}
        prepared = [{"case_id": f"SQLT-PRP-{index:03d}", "status": "passed"} for index in range(1, 9)]
        extended = [
            {"case_id": f"SQLT-PGX-{index:03d}", "dialect": "postgres", "status": "passed"}
            for index in range(1, 9)
        ]
        cursor = [
            {"case_id": f"SQLT-CURSOR-{index:03d}", "dialect": "postgres", "status": "passed"}
            for index in range(1, 9)
        ]
        tcl_oracles = json.loads((ROOT / "tcl-oracles.json").read_text(encoding="utf-8"))["results"]
        tcl = [
            {"case_id": case_id, "dialect": dialect, "status": "passed"}
            for case_id, dialects in tcl_oracles.items()
            for dialect in dialects
        ]
        dml = [
            {"case_id": case_id, "dialect": dialect, "status": "passed"}
            for case_id, case in cases.items()
            if "SQLT-DML-003" <= case_id <= "SQLT-DML-043"
            for dialect in case["dialects"]
        ]
        ddl_oracles = json.loads((ROOT / "ddl-oracles.json").read_text(encoding="utf-8"))["results"]
        ddl = [
            {"case_id": case_id, "dialect": dialect, "path": path, "status": "passed"}
            for case_id, dialects in ddl_oracles.items()
            for dialect in dialects
            for path in ("direct", "gateway")
        ]
        return {
            name: self._write(name, results)
            for name, results in {
                "prepared": prepared,
                "extended": extended,
                "cursor": cursor,
                "tcl": tcl,
                "dml": dml,
                "ddl": ddl,
            }.items()
        }

    def aggregate(self, summaries: dict[str, Path] | None = None, complete: bool = True):
        return MATRIX.aggregate(
            self.spec,
            self.manifest,
            summaries or self.summaries,
            ROOT,
            "unit-test",
            complete,
        )

    def test_formal_matrix_closes_all_paths_and_lanes(self) -> None:
        results, summary = self.aggregate()
        self.assertEqual(len(results), 376)
        self.assertEqual(summary["suites"], {
            "prepared": 16, "extended": 16, "cursor": 18,
            "tcl": 40, "dml": 128, "ddl": 158,
        })
        self.assertEqual(summary["lanes"], {
            "mysql_binary_to_mysql": 16,
            "mysql_text_to_mysql": 148,
            "pg_extended_to_postgres": 16,
            "pg_simple_to_postgres": 196,
        })
        cursor_007 = [result for result in results if result["case_id"] == "SQLT-CURSOR-007"]
        self.assertEqual(len(cursor_007), 4)
        self.assertEqual({result["variant"] for result in cursor_007}, {"terminate", "eof"})

    def test_filtered_suite_cannot_claim_formal_acceptance(self) -> None:
        results, summary = self.aggregate({"prepared": self.summaries["prepared"]}, complete=False)
        self.assertEqual(len(results), 16)
        self.assertFalse(summary["acceptance_complete"])
        with self.assertRaisesRegex(MATRIX.MatrixError, "all six suite summaries"):
            self.aggregate({"prepared": self.summaries["prepared"]}, complete=True)

    def test_failed_child_result_is_rejected(self) -> None:
        value = json.loads(self.summaries["prepared"].read_text(encoding="utf-8"))
        value["results"][0]["status"] = "failed"
        self.summaries["prepared"].write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(MATRIX.MatrixError, "is not passed"):
            self.aggregate()

    def test_unknown_case_is_rejected(self) -> None:
        value = json.loads(self.summaries["prepared"].read_text(encoding="utf-8"))
        value["results"][0]["case_id"] = "SQLT-PRP-999"
        self.summaries["prepared"].write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(MATRIX.MatrixError, "unknown case"):
            self.aggregate()

    def test_duplicate_explicit_path_is_rejected(self) -> None:
        value = json.loads(self.summaries["ddl"].read_text(encoding="utf-8"))
        value["results"].append(copy.deepcopy(value["results"][0]))
        self.summaries["ddl"].write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(MATRIX.MatrixError, "duplicate path"):
            self.aggregate()

    def test_manifest_lane_drift_is_rejected(self) -> None:
        case = next(case for case in self.manifest["cases"] if case["id"] == "SQLT-PRP-001")
        case["frontends"] = ["mysql_text"]
        with self.assertRaisesRegex(MATRIX.MatrixError, "frontend is not declared"):
            self.aggregate()

    def test_unknown_summary_suite_is_rejected(self) -> None:
        with self.assertRaisesRegex(MATRIX.MatrixError, "unknown suites"):
            self.aggregate({"unknown": self.summaries["prepared"]}, complete=False)


if __name__ == "__main__":
    unittest.main()
