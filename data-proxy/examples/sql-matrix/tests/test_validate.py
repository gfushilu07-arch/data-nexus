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
            {f"SQLT-DQL-{index:03d}" for index in range(1, 87)},
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

    def test_dql_boundary_oracle_must_cover_boundary_cases(self) -> None:
        oracle_path = self.root / "dql-boundary-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DQL-085"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-085 dialects must be")

    def test_dql_boundary_oracle_rejects_invalid_hash(self) -> None:
        oracle_path = self.root / "dql-boundary-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DQL-086"]["mysql"]["sha256"] = "not-a-hash"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-086.mysql.sha256 must be a lowercase SHA-256")

    def test_dql_boundary_oracle_requires_fixed_chunk_size(self) -> None:
        oracle_path = self.root / "dql-boundary-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["chunk_bytes"] = 1_048_576
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("chunk_bytes must be 65536")

    def test_dql_boundary_oracle_rejects_unknown_summary_field(self) -> None:
        oracle_path = self.root / "dql-boundary-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DQL-085"]["mysql"]["unbounded_output"] = True
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DQL-085.mysql fields must be")

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

    def test_tcl_oracle_must_cover_every_case(self) -> None:
        oracle_path = self.root / "tcl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-TCL-011"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("tcl-oracles.json cases must be")

    def test_tcl_oracle_must_cover_every_declared_dialect(self) -> None:
        oracle_path = self.root / "tcl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-TCL-001"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-TCL-001 dialects must be")

    def test_tcl_state_query_must_exist_below_matrix_root(self) -> None:
        oracle_path = self.root / "tcl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["state_queries"]["tcl"]["mysql"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("state_queries.tcl.mysql escapes matrix root")

    def test_tcl_oracle_rejects_unknown_contract_field(self) -> None:
        oracle_path = self.root / "tcl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-TCL-001"]["mysql"]["force_continue"] = False
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-TCL-001.mysql fields must be")

    def test_prepared_oracle_must_cover_every_case(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-PRP-008"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("prepared-oracles.json cases must be")

    def test_prepared_oracle_rejects_unknown_field(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PRP-001"]["unexpected"] = True
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-001 fields must be")

    def test_prepared_case_must_use_binary_frontend(self) -> None:
        manifest = self.manifest()
        prepared = next(case for case in manifest["cases"] if case["id"] == "SQLT-PRP-001")
        prepared["frontends"] = ["mysql_text"]
        self.write_manifest(manifest)
        self.assert_has_error("SQLT-PRP-001 must use mysql_binary frontend")

    def test_prepared_case_must_be_mysql_only(self) -> None:
        manifest = self.manifest()
        prepared = next(case for case in manifest["cases"] if case["id"] == "SQLT-PRP-001")
        prepared["dialects"] = ["mysql", "postgres"]
        prepared["backends"] = ["mysql", "postgres"]
        self.write_manifest(manifest)
        self.assert_has_error("SQLT-PRP-001 must declare only mysql dialect")
        self.assert_has_error("SQLT-PRP-001 must declare only mysql backend")

    def test_prepared_oracle_sql_file_must_match_manifest(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PRP-001"]["sql_file"] = "prepared/single-parameter-select.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-001.sql_file must match manifest sql_file")

    def test_prepared_oracle_rejects_parameter_count_mismatch(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PRP-002"]["parameters"] = []
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-002.parameters must bind 1 placeholders")

    def test_prepared_oracle_rejects_rebind_parameter_count_mismatch(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PRP-007"]["parameters"][0] = [42]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-007.parameters[0] must bind 2 placeholders")

    def test_prepared_oracle_rejects_unknown_typed_binding(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PRP-002"]["parameters"] = [{"integer": 101}]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-002.parameters[0] has an unknown typed binding")

    def test_prepared_state_query_cannot_escape_matrix_root(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        outside = self.root.parent / "outside.sql"
        outside.write_text("SELECT 1;\n", encoding="utf-8")
        oracles["state_query"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("prepared-oracles.json state_query escapes matrix root")

    def test_prepared_control_sql_cannot_escape_matrix_root(self) -> None:
        oracle_path = self.root / "prepared-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        outside = self.root.parent / "outside.sql"
        outside.write_text("SELECT 1;\n", encoding="utf-8")
        oracles["results"]["SQLT-PRP-008"]["control_sql"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PRP-008.control_sql escapes matrix root")

    def test_extended_oracle_must_cover_every_case(self) -> None:
        oracle_path = self.root / "extended-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-PGX-008"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("extended-oracles.json cases must be")

    def test_extended_oracle_rejects_unknown_field(self) -> None:
        oracle_path = self.root / "extended-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PGX-001"]["unexpected"] = True
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PGX-001 fields must be")

    def test_extended_case_must_use_extended_frontend(self) -> None:
        manifest = self.manifest()
        case = next(value for value in manifest["cases"] if value["id"] == "SQLT-PGX-001")
        case["frontends"] = ["pg_simple"]
        self.write_manifest(manifest)
        self.assert_has_error("SQLT-PGX-001 must use only pg_extended frontend and protocol")

    def test_extended_ready_status_must_be_protocol_value(self) -> None:
        oracle_path = self.root / "extended-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-PGX-008"]["expected"]["ready"] = ["idle"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-PGX-008.expected.ready must contain only I, T, or E")

    def test_ddl_oracle_must_cover_every_declared_dialect(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-002"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-002 dialects must be")

    def test_ddl_error_oracle_requires_stable_error_identity(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-004"]["mysql"]["error"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-004.mysql.error")

    def test_ddl_error_oracle_requires_unchanged_catalog(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-004"]["postgres"]["unchanged"] = False
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-004.postgres error oracle must define unchanged=true")

    def test_ddl_setup_must_exist_below_matrix_root(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-003"]["mysql"]["setup"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-003.mysql.setup escapes matrix root")

    def test_ddl_data_probe_fields_must_be_declared_together(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-013"]["postgres"]["after_data"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("must define data_query, before_data, and after_data together")

    def test_ddl_data_query_must_exist_below_matrix_root(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-013"]["mysql"]["data_query"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-013.mysql.data_query escapes matrix root")

    def test_ddl_error_oracle_accepts_unchanged_data_probe(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        value = oracles["results"]["SQLT-DDL-004"]["mysql"]
        value["data_query"] = "fixtures/mysql/oracle-ddl-catalog.sql"
        value["before_data"] = ""
        value["after_data"] = ""
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(self.errors(), [])

    def test_ddl_error_probe_fields_must_be_declared_together(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-020"]["postgres"]["probe_error"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("must define error_probe and probe_error together")

    def test_ddl_error_probe_must_exist_below_matrix_root(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-020"]["mysql"]["error_probe"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-020.mysql.error_probe escapes matrix root")

    def test_ddl_probe_error_requires_stable_error_identity(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-020"]["postgres"]["probe_error"] = "23514"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-020.postgres.probe_error")

    def test_ddl_temp_oracle_must_cover_every_declared_dialect(self) -> None:
        oracle_path = self.root / "ddl-temp-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-014"]["postgres"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-014 dialects must be")

    def test_ddl_temp_oracle_requires_all_session_fields(self) -> None:
        oracle_path = self.root / "ddl-temp-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-014"]["mysql"]["after_disconnect_error"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-014.mysql fields must be")

    def test_ddl_database_cases_are_excluded_from_ordinary_oracles(self) -> None:
        oracle_path = self.root / "ddl-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-053"] = {
            "mysql": {"result": "success", "setup": None, "state": ""}
        }
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("ddl-oracles.json cases must be")

    def test_ddl_database_oracle_must_cover_all_boundary_cases(self) -> None:
        oracle_path = self.root / "ddl-database-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-053"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("ddl-database-oracles.json cases must be")

    def test_ddl_database_oracle_requires_exact_fields(self) -> None:
        oracle_path = self.root / "ddl-database-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        del oracles["results"]["SQLT-DDL-053"]["mysql"]["identity"]
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-053.mysql fields must be")

    def test_ddl_database_setup_must_stay_below_matrix_root(self) -> None:
        oracle_path = self.root / "ddl-database-oracles.json"
        oracles = json.loads(oracle_path.read_text(encoding="utf-8"))
        oracles["results"]["SQLT-DDL-053"]["mysql"]["setup"] = "../outside.sql"
        oracle_path.write_text(json.dumps(oracles, indent=2) + "\n", encoding="utf-8")
        self.assert_has_error("SQLT-DDL-053.mysql.setup escapes matrix root")

    def test_ddl_database_case_must_be_mysql_only(self) -> None:
        manifest = self.manifest()
        case = next(item for item in manifest["cases"] if item["id"] == "SQLT-DDL-053")
        case["dialects"] = ["mysql", "postgres"]
        sql_path = self.root / "cases" / case["sql_file"]
        sql = sql_path.read_text(encoding="utf-8").replace(
            "-- Dialect: mysql", "-- Dialect: mysql, postgres"
        )
        sql_path.write_text(sql, encoding="utf-8")
        self.write_manifest(manifest)
        self.assert_has_error("SQLT-DDL-053 must be MySQL-only")


if __name__ == "__main__":
    unittest.main()
