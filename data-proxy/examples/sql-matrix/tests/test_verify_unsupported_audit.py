from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


MATRIX_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sql_matrix_verify_unsupported_audit",
    MATRIX_ROOT / "verify_unsupported_audit.py",
)
assert SPEC and SPEC.loader
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def result(path: str, *capabilities: str) -> dict:
    return {
        "case_id": "SQLT-UNSUPPORTED-999",
        "dialect": "postgres",
        "path": path,
        "semantic": {
            "steps": [
                {"name": f"step_{index}", "error": {"capability": capability}}
                for index, capability in enumerate(capabilities)
            ]
        },
    }


def audit_line(capability: str, **overrides: str) -> str:
    fields = {
        "message": VERIFY.AUDIT_MESSAGE,
        "action": "query",
        "decision": "reject",
        "capability": capability,
    }
    fields.update(overrides)
    return json.dumps({"target": "data_nexus::audit", "fields": fields})


class VerifyUnsupportedAuditTest(unittest.TestCase):
    def test_expected_capabilities_only_use_gateway_steps(self) -> None:
        self.assertEqual(
            VERIFY.expected_capabilities(
                [result("direct", "postgres.copy_file"), result("gateway", "postgres.copy_file")]
            ),
            {"postgres.copy_file": 1},
        )

    def test_expected_capabilities_reject_missing_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "lacks capability"):
            VERIFY.expected_capabilities([result("gateway", "")])

    def test_audit_capabilities_preserve_multiplicity(self) -> None:
        self.assertEqual(
            VERIFY.audit_capabilities(
                [audit_line("postgres.maintenance"), audit_line("postgres.maintenance")]
            ),
            {"postgres.maintenance": 2},
        )

    def test_audit_capabilities_ignore_unrelated_json_events(self) -> None:
        self.assertEqual(
            VERIFY.audit_capabilities([json.dumps({"fields": {"message": "gateway start"}})]),
            {},
        )

    def test_audit_capabilities_require_stable_action_and_decision(self) -> None:
        with self.assertRaisesRegex(ValueError, "unstable identity"):
            VERIFY.audit_capabilities([audit_line("postgres.do", decision="allow")])

    def test_audit_capabilities_reject_non_json_logs(self) -> None:
        with self.assertRaisesRegex(ValueError, "not JSON"):
            VERIFY.audit_capabilities(["plain text"])

    def test_sensitive_sql_fragments_are_rejected_case_insensitively(self) -> None:
        with self.assertRaisesRegex(ValueError, "leaked sensitive SQL"):
            VERIFY.reject_sensitive_log_text("SELECT 42 INTO OUTFILE '/SQLT-UNREACHABLE-OUTFILE'")

    def test_low_cardinality_audit_text_passes(self) -> None:
        VERIFY.reject_sensitive_log_text(audit_line("mysql.outfile"))


if __name__ == "__main__":
    unittest.main()
