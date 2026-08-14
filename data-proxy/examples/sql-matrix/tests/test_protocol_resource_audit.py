from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "protocol_resource_audit", ROOT / "protocol_resource_audit.py"
)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class ProtocolResourceAuditTest(unittest.TestCase):
    def test_projects_match_all_child_runner_compose_names(self) -> None:
        self.assertEqual(
            AUDIT.ownership_rows("protocol-matrix-acceptance-02"),
            [
                (
                    "prepared",
                    "protocol-matrix-acceptance-02-prepared",
                    "sqlt3eprep-protocolmatrixacceptance02prepared",
                ),
                (
                    "extended",
                    "protocol-matrix-acceptance-02-extended",
                    "sqlt3epgx-protocolmatrixacceptance02extended",
                ),
                (
                    "cursor",
                    "protocol-matrix-acceptance-02-cursor",
                    "sqlt3ecursor-protocolmatrixacceptance02cursor",
                ),
                (
                    "tcl",
                    "protocol-matrix-acceptance-02-tcl",
                    "sqlt3etcl-protocolmatrixacceptance02tcl",
                ),
                (
                    "dml",
                    "protocol-matrix-acceptance-02-dml",
                    "sqlt3cdml-protocolmatrixacceptance02dml",
                ),
                (
                    "ddl",
                    "protocol-matrix-acceptance-02-ddl",
                    "sqlt3dddl-protocolmatrixacceptance02ddl",
                ),
            ],
        )

    def test_filtered_run_only_owns_selected_suite(self) -> None:
        self.assertEqual(
            AUDIT.ownership_rows("smoke-01", "prepared"),
            [("prepared", "smoke-01-prepared", "sqlt3eprep-smoke01prepared")],
        )

    def test_container_filter_accepts_compose_or_exact_child_run_label(self) -> None:
        lines = [
            "c1\tmysql\tsqlt3eprep-smoke01prepared\t",
            "c2\tclient\t\tsmoke-01-prepared",
            "c3\tunrelated\tother-project\tother-run",
            "c4\tsubstring\t\tteam-smoke-01-prepared-copy",
        ]
        self.assertEqual(
            AUDIT.owned_resource_lines("containers", lines, "smoke-01", "prepared"),
            lines[:2],
        )

    def test_network_and_volume_filters_ignore_concurrent_resources(self) -> None:
        project = "sqlt3dddl-formalddl"
        self.assertEqual(
            AUDIT.owned_resource_lines(
                "networks",
                [f"n1\t{project}_default\t{project}", "n2\topenhis_default\topenhis"],
                "formal",
                "ddl",
            ),
            [f"n1\t{project}_default\t{project}"],
        )
        self.assertEqual(
            AUDIT.owned_resource_lines(
                "volumes",
                [f"volume-a\t{project}", "anonymous-openhis\topenhis"],
                "formal",
                "ddl",
            ),
            [f"volume-a\t{project}"],
        )

    def test_invalid_run_id_and_snapshot_shape_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "ASCII alphanumeric"):
            AUDIT.ownership_rows("---")
        with self.assertRaisesRegex(ValueError, "expected 4"):
            AUDIT.owned_resource_lines("containers", ["id\tname"], "formal")


if __name__ == "__main__":
    unittest.main()
