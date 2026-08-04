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


if __name__ == "__main__":
    unittest.main()
