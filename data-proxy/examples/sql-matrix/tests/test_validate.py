from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sql_matrix_validate", MATRIX_ROOT / "validate.py")
assert SPEC and SPEC.loader
VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE)


class ValidateSqlMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "sql-matrix"
        shutil.copytree(MATRIX_ROOT, self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def manifest(self) -> dict:
        return json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def write_manifest(self, manifest: dict) -> None:
        (self.root / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    def errors(self) -> list[str]:
        return VALIDATE.validate_repository(self.root)

    def assert_has_error(self, text: str) -> None:
        errors = self.errors()
        self.assertTrue(
            any(text in error for error in errors),
            f"expected error containing {text!r}, got {errors!r}",
        )

    def test_repository_fixture_is_valid(self) -> None:
        self.assertEqual(self.errors(), [])

    def test_duplicate_case_id_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["cases"].append(copy.deepcopy(manifest["cases"][0]))
        self.write_manifest(manifest)
        self.assert_has_error("duplicate case ID")

    def test_missing_sql_file_is_rejected(self) -> None:
        manifest = self.manifest()
        sql_file = manifest["cases"][0]["sql_file"]
        (self.root / "cases" / sql_file).unlink()
        self.assert_has_error("SQL file does not exist")

    def test_comment_case_id_must_match_manifest(self) -> None:
        manifest = self.manifest()
        sql_path = self.root / "cases" / manifest["cases"][0]["sql_file"]
        text = sql_path.read_text(encoding="utf-8")
        sql_path.write_text(text.replace("SQLT-META-001", "SQLT-META-999", 1), encoding="utf-8")
        self.assert_has_error("SQL comment case ID")

    def test_required_comment_is_enforced(self) -> None:
        manifest = self.manifest()
        sql_path = self.root / "cases" / manifest["cases"][0]["sql_file"]
        lines = sql_path.read_text(encoding="utf-8").splitlines()
        lines[1] = "-- missing purpose"
        sql_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_has_error("SQL line 2 must start")

    def test_unknown_capability_value_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["cases"][0]["frontends"] = ["unknown_frontend"]
        self.write_manifest(manifest)
        self.assert_has_error("frontends has unknown values")

    def test_unknown_sql_capability_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["cases"][0]["capability"] = "metadata.not_registered"
        self.write_manifest(manifest)
        self.assert_has_error("capability is unknown")

    def test_execution_metadata_is_required(self) -> None:
        manifest = self.manifest()
        del manifest["cases"][0]["transaction_mode"]
        self.write_manifest(manifest)
        self.assert_has_error("transaction_mode is unknown")

    def test_top_level_outcome_is_rejected_as_ambiguous(self) -> None:
        manifest = self.manifest()
        manifest["cases"][0]["outcome"] = "allow"
        self.write_manifest(manifest)
        self.assert_has_error("outcome is ambiguous")

    def test_path_traversal_is_rejected(self) -> None:
        manifest = self.manifest()
        manifest["cases"][0]["sql_file"] = "../outside.sql"
        self.write_manifest(manifest)
        self.assert_has_error("must stay below the case root")

    def test_unreferenced_sql_file_is_rejected(self) -> None:
        extra = self.root / "cases" / "dql" / "not-registered.sql"
        extra.write_text("-- intentionally not registered\nSELECT 1;\n", encoding="utf-8")
        self.assert_has_error("unreferenced SQL file")

    def test_skip_requires_reason_issue_and_expiry(self) -> None:
        manifest = self.manifest()
        manifest["cases"][0]["skip"] = {"reason": "blocked"}
        self.write_manifest(manifest)
        self.assert_has_error("skip.issue")
        self.assert_has_error("skip.expires_when")

    def test_fixture_sql_comment_header_is_enforced(self) -> None:
        sql_path = self.root / "fixtures" / "mysql" / "schema.sql"
        lines = sql_path.read_text(encoding="utf-8").splitlines()
        lines[1] = "-- missing purpose"
        sql_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_has_error("fixtures/mysql/schema.sql: SQL line 2 must start")

    def test_fixture_sql_dialect_must_match_directory(self) -> None:
        sql_path = self.root / "fixtures" / "postgres" / "seed.sql"
        text = sql_path.read_text(encoding="utf-8")
        sql_path.write_text(text.replace("-- Dialect: postgres", "-- Dialect: mysql"), encoding="utf-8")
        self.assert_has_error("dialect comment must match parent directory")

    def test_metadata_family_meets_sqlt3a_budget(self) -> None:
        manifest = self.manifest()
        metadata_cases = [case for case in manifest["cases"] if case["family"] == "metadata"]
        self.assertGreaterEqual(len(metadata_cases), 20)
        self.assertEqual(
            {case["id"] for case in metadata_cases},
            {f"SQLT-META-{index:03d}" for index in range(1, 21)},
        )

    def test_dql_family_reaches_sqlt3b4_budget(self) -> None:
        manifest = self.manifest()
        dql_cases = [case for case in manifest["cases"] if case["family"] == "dql"]
        self.assertGreaterEqual(len(dql_cases), 80)
        self.assertEqual(
            {case["id"] for case in dql_cases},
            {f"SQLT-DQL-{index:03d}" for index in range(1, 85)},
        )

    def test_dql_oracle_must_cover_every_declared_dialect(self) -> None:
        oracle_path = self.root / "dql-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DQL-001"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-001 dialects must be")

    def test_dql_lock_oracle_must_cover_explicit_dql_cases(self) -> None:
        oracle_path = self.root / "dql-lock-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DQL-081"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-081 dialects must be")

    def test_dql_lock_oracle_requires_behavior_fields(self) -> None:
        oracle_path = self.root / "dql-lock-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DQL-084"]["mysql"]["after_rollback"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-084.mysql fields must be")

    def test_dml_tranches_have_contiguous_case_ids(self) -> None:
        manifest = self.manifest()
        dml_cases = [case for case in manifest["cases"] if case["family"] == "dml"]
        self.assertGreaterEqual(len(dml_cases), 43)
        self.assertTrue(
            {f"SQLT-DML-{index:03d}" for index in range(1, 44)}
            <= {case["id"] for case in dml_cases}
        )

    def test_dml_oracle_must_cover_every_declared_dialect(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DML-003"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DML-003 dialects must be")

    def test_dml_error_oracle_requires_stable_error_identity(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DML-011"]["mysql"]["error"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DML-011.mysql.error")

    def test_dml_state_query_must_exist_below_matrix_root(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["state_queries"]["update_delete"]["mysql"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("state_queries.update_delete.mysql escapes matrix root")

    def test_dml_update_oracle_requires_affected_rows(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DML-015"]["mysql"]["affected_rows"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DML-015.mysql must define affected_rows, returned_rows")

    def test_dml_returned_rows_must_be_normalized(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DML-036"]["postgres"]["returned_rows"] = ["row"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DML-036.postgres.returned_rows")

    def test_dml_recovered_error_requires_stable_error_identity(self) -> None:
        oracle_path = self.root / "dml-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DML-042"]["mysql"]["error"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DML-042.mysql.error")


if __name__ == "__main__":
    unittest.main()
