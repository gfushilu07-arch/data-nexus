#!/usr/bin/env python3
"""Validate and aggregate the SQLT-4A same-protocol execution matrix."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shlex
from collections import Counter
from pathlib import Path
from typing import Any


LANES = {
    "mysql_text_to_mysql": ("mysql_text", "mysql", "mysql_text"),
    "mysql_binary_to_mysql": ("mysql_binary", "mysql", "mysql_binary"),
    "pg_simple_to_postgres": ("pg_simple", "postgres", "pg_simple"),
    "pg_extended_to_postgres": ("pg_extended", "postgres", "pg_extended"),
}
SUITES = {"prepared", "extended", "cursor", "tcl", "dml", "ddl"}
SUMMARY_SCHEMAS = {
    "case_double",
    "cursor_variants",
    "dialect_case_double",
    "explicit_paths",
}
SUITE_CONTRACTS = {
    "prepared": ("run-prepared-corpus.sh", "select_prepared_cases.py", "prepared-oracles.json", "SQLT-PRP-001", "SQLT-PRP-008", "case_double"),
    "extended": ("run-extended-corpus.sh", "select_extended_cases.py", "extended-oracles.json", "SQLT-PGX-001", "SQLT-PGX-008", "case_double"),
    "cursor": ("run-cursor-corpus.sh", "select_cursor_cases.py", "cursor-oracles.json", "SQLT-CURSOR-001", "SQLT-CURSOR-008", "cursor_variants"),
    "tcl": ("run-tcl-corpus.sh", "select_tcl_cases.py", "tcl-oracles.json", "SQLT-TCL-001", "SQLT-TCL-011", "dialect_case_double"),
    "dml": ("run-dml-corpus.sh", "select_dml_cases.py", "dml-oracles.json", "SQLT-DML-003", "SQLT-DML-043", "dialect_case_double"),
    "ddl": ("run-ddl-corpus.sh", "select_ddl_cases.py", "ddl-oracles.json", "SQLT-DDL-001", "SQLT-DDL-052", "explicit_paths"),
}


class MatrixError(ValueError):
    """Raised when a matrix contract or child result is invalid."""


def _object(value: Any, label: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    return value


def validate_spec(spec: Any, manifest: Any, root: Path | None = None) -> list[str]:
    """Return all static SQLT-4A specification errors."""
    errors: list[str] = []
    spec = _object(spec, "protocol-matrix.json", errors)
    manifest = _object(manifest, "manifest.json", errors)
    if spec.get("schema_version") != 1:
        errors.append("protocol-matrix.json schema_version must be 1")
    if spec.get("matrix_id") != "SQLT-4A":
        errors.append("protocol-matrix.json matrix_id must be SQLT-4A")
    if spec.get("policy") != "security_off":
        errors.append("protocol-matrix.json policy must be security_off")

    lanes = _object(spec.get("lanes"), "protocol-matrix.json lanes", errors)
    if set(lanes) != set(LANES):
        errors.append(f"protocol-matrix.json lanes must be {sorted(LANES)}")
    lane_totals: Counter[str] = Counter()
    for lane_name, contract in LANES.items():
        lane = _object(lanes.get(lane_name), f"lane {lane_name}", errors)
        actual = (lane.get("frontend"), lane.get("backend"), lane.get("protocol"))
        if actual != contract:
            errors.append(f"lane {lane_name} contract must be {contract}")
        expected_paths = lane.get("expected_paths")
        if not isinstance(expected_paths, int) or expected_paths <= 0:
            errors.append(f"lane {lane_name} expected_paths must be a positive integer")

    suites = spec.get("suites")
    if not isinstance(suites, list):
        errors.append("protocol-matrix.json suites must be an array")
        suites = []
    suite_names = [suite.get("name") for suite in suites if isinstance(suite, dict)]
    if set(suite_names) != SUITES or len(suite_names) != len(SUITES):
        errors.append(f"protocol-matrix.json suites must be exactly {sorted(SUITES)}")
    for index, value in enumerate(suites):
        suite = _object(value, f"suite[{index}]", errors)
        name = suite.get("name")
        if name not in SUITES:
            continue
        contract = SUITE_CONTRACTS[name]
        for offset, field in enumerate(
            ("runner", "selector", "oracles", "case_from", "case_to")
        ):
            if suite.get(field) != contract[offset]:
                errors.append(f"suite {name} {field} must be {contract[offset]}")
            elif root is not None and field in {"runner", "selector", "oracles"}:
                if not (root / contract[offset]).is_file():
                    errors.append(f"suite {name} {field} does not exist: {contract[offset]}")
        upper_name = name.upper()
        env_contracts = {
            "run_id_env": f"SQLT_{upper_name}_RUN_ID",
            "case_from_env": f"SQLT_{upper_name}_CASE_FROM",
            "case_to_env": f"SQLT_{upper_name}_CASE_TO",
        }
        for field, expected in env_contracts.items():
            if suite.get(field) != expected:
                errors.append(f"suite {name} {field} must be {expected}")
        if suite.get("summary_schema") != contract[5]:
            errors.append(f"suite {name} summary_schema must be {contract[5]}")
        expected_case_dialects = suite.get("expected_case_dialects")
        if not isinstance(expected_case_dialects, int) or expected_case_dialects <= 0:
            errors.append(f"suite {name} expected_case_dialects must be positive")
        coverage_tags = suite.get("coverage_tags")
        if (
            not isinstance(coverage_tags, list)
            or not coverage_tags
            or any(not isinstance(tag, str) or not tag for tag in coverage_tags)
            or len(coverage_tags) != len(set(coverage_tags))
        ):
            errors.append(f"suite {name} coverage_tags must be unique non-empty strings")
        suite_lanes = _object(suite.get("lane_paths"), f"suite {name} lane_paths", errors)
        for lane_name, count in suite_lanes.items():
            if lane_name not in LANES:
                errors.append(f"suite {name} references unknown lane {lane_name}")
            if not isinstance(count, int) or count <= 0:
                errors.append(f"suite {name} lane {lane_name} count must be positive")
            else:
                lane_totals[lane_name] += count
        variants = suite.get("variants", {})
        variants_valid = isinstance(variants, dict) and not any(
            not isinstance(case_id, str)
            or not isinstance(items, list)
            or not items
            or any(not isinstance(item, str) or not item for item in items)
            or len(items) != len(set(items))
            for case_id, items in variants.items()
        )
        if not variants_valid:
            errors.append(f"suite {name} variants must map case IDs to unique strings")
        if (
            root is not None
            and variants_valid
            and set(suite_lanes) <= set(lanes)
            and all(isinstance(lanes.get(lane_name), dict) for lane_name in suite_lanes)
            and all(
                suite.get(field) == contract[offset]
                for offset, field in enumerate(
                    ("runner", "selector", "oracles", "case_from", "case_to")
                )
            )
        ):
            try:
                selection = _selection_pairs(suite, manifest, root)
            except MatrixError as exc:
                errors.append(f"suite {name} selection failed: {exc}")
            else:
                if len(selection) != expected_case_dialects:
                    errors.append(
                        f"suite {name} expected_case_dialects must match "
                        f"selector count {len(selection)}"
                    )
                selected_ids = {case_id for case_id, _ in selection}
                if not set(variants) <= selected_ids:
                    errors.append(f"suite {name} variants reference unselected cases")
                selected_lane_paths: Counter[str] = Counter()
                manifest_cases = {
                    case.get("id"): case
                    for case in manifest.get("cases", [])
                    if isinstance(case, dict)
                }
                for case_id, dialect in selection:
                    try:
                        lane_name, lane = _lane_for(suite, dialect, lanes)
                    except MatrixError as exc:
                        errors.append(str(exc))
                        continue
                    case = manifest_cases.get(case_id, {})
                    for field, manifest_field in (
                        ("frontend", "frontends"),
                        ("backend", "backends"),
                        ("protocol", "protocols"),
                    ):
                        if lane.get(field) not in case.get(manifest_field, []):
                            errors.append(
                                f"{case_id}: lane {lane_name} {field} is not "
                                "declared by manifest"
                            )
                    variant_count = len(variants.get(case_id, ["default"]))
                    multiplier = 2 * (
                        variant_count if suite.get("summary_schema") == "cursor_variants" else 1
                    )
                    selected_lane_paths[lane_name] += multiplier
                if selected_lane_paths != Counter(suite_lanes):
                    errors.append(
                        f"suite {name} lane_paths do not match selector paths: "
                        f"{dict(selected_lane_paths)}"
                    )

    expected_paths = spec.get("expected_paths")
    if expected_paths != sum(lane_totals.values()):
        errors.append("protocol-matrix.json expected_paths does not match suite lane totals")
    if spec.get("expected_suites") != len(SUITES):
        errors.append(f"protocol-matrix.json expected_suites must be {len(SUITES)}")
    for lane_name, lane in lanes.items():
        if isinstance(lane, dict) and lane.get("expected_paths") != lane_totals[lane_name]:
            errors.append(f"lane {lane_name} expected_paths does not match suite totals")
    if not isinstance(manifest.get("cases"), list) or not manifest["cases"]:
        errors.append("manifest.json cases must be a non-empty array")
    return errors


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MatrixError(f"cannot read {path}: {exc}") from exc


def _selection_pairs(
    suite: dict[str, Any], manifest: dict[str, Any], root: Path
) -> list[tuple[str, str]]:
    selector_path = root / suite["selector"]
    module_spec = importlib.util.spec_from_file_location(
        f"protocol_matrix_{suite['name']}_selector", selector_path
    )
    if not module_spec or not module_spec.loader:
        raise MatrixError(f"cannot load selector {selector_path}")
    selector = importlib.util.module_from_spec(module_spec)
    try:
        module_spec.loader.exec_module(selector)
    except (ImportError, OSError, SyntaxError) as exc:
        raise MatrixError(f"cannot load selector {selector_path}: {exc}") from exc
    if not callable(getattr(selector, "select_cases", None)):
        raise MatrixError(f"selector {selector_path.name} has no select_cases function")
    oracles = _load(root / suite["oracles"])
    try:
        rows = list(
            selector.select_cases(
                manifest, oracles, suite["case_from"], suite["case_to"]
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixError(f"selector {selector_path.name} failed: {exc}") from exc
    pairs: list[tuple[str, str]] = []
    for row in rows:
        if (
            not isinstance(row, tuple)
            or len(row) < 2
            or not isinstance(row[0], str)
            or not isinstance(row[1], str)
        ):
            raise MatrixError(f"selector {selector_path.name} returned an invalid row")
        pairs.append((row[0], row[1]))
    if len(pairs) != len(set(pairs)):
        raise MatrixError(f"selector {selector_path.name} returned duplicate case/dialects")
    return pairs


def _dialect(result: dict[str, Any], case: dict[str, Any]) -> str:
    dialect = result.get("dialect")
    if dialect is None and len(case.get("dialects", [])) == 1:
        dialect = case["dialects"][0]
    if not isinstance(dialect, str) or dialect not in case.get("dialects", []):
        raise MatrixError(f"{case.get('id')}: result dialect is not declared by manifest")
    return dialect


def _lane_for(suite: dict[str, Any], dialect: str, lanes: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    matches = [
        name
        for name in suite["lane_paths"]
        if isinstance(lanes.get(name), dict) and lanes[name].get("backend") == dialect
    ]
    if len(matches) != 1:
        raise MatrixError(f"suite {suite['name']} dialect {dialect} must resolve to exactly one lane")
    return matches[0], lanes[matches[0]]


def _reproduce(root: Path, suite: dict[str, Any], case_id: str) -> str:
    values = {
        "DATA_NEXUS_SQL_MATRIX_CACHE": "/Volumes/fushilu/.caches/data-nexus/sql-matrix",
        suite["run_id_env"]: f"reproduce-{suite['name']}-{case_id.lower()}",
        suite["case_from_env"]: case_id,
        suite["case_to_env"]: case_id,
    }
    env = " ".join(f"{name}={shlex.quote(value)}" for name, value in values.items())
    return f"{env} {shlex.quote(str(root / suite['runner']))}"


def aggregate(
    spec: dict[str, Any],
    manifest: dict[str, Any],
    summaries: dict[str, Path],
    root: Path,
    run_id: str,
    acceptance_complete: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Normalize child summaries and enforce filtered or formal acceptance gates."""
    errors = validate_spec(spec, manifest, root)
    if errors:
        raise MatrixError("; ".join(errors))
    suite_specs = {suite["name"]: suite for suite in spec["suites"]}
    unknown = set(summaries) - set(suite_specs)
    if unknown:
        raise MatrixError(f"unknown suites: {sorted(unknown)}")
    if not summaries:
        raise MatrixError("at least one suite summary is required")
    if acceptance_complete and set(summaries) != set(suite_specs):
        raise MatrixError("formal acceptance requires all six suite summaries")

    cases = {
        case.get("id"): case
        for case in manifest["cases"]
        if isinstance(case, dict) and isinstance(case.get("id"), str)
    }
    results: list[dict[str, Any]] = []
    suite_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    path_keys: set[tuple[str, str, str, str, str]] = set()
    for suite_name, summary_path in summaries.items():
        suite = suite_specs[suite_name]
        selected_pairs = Counter(_selection_pairs(suite, manifest, root))
        child_pairs: Counter[tuple[str, str]] = Counter()
        summary = _load(summary_path)
        if not isinstance(summary, dict) or not isinstance(summary.get("results"), list):
            raise MatrixError(f"suite {suite_name} summary must contain results")
        child_results = summary["results"]
        if summary.get("failed") != 0:
            raise MatrixError(f"suite {suite_name} summary reports failed executions")
        if summary.get("passed") != len(child_results):
            raise MatrixError(f"suite {suite_name} passed count does not match results")
        for child in child_results:
            if not isinstance(child, dict):
                raise MatrixError(f"suite {suite_name} has a non-object result")
            case_id = child.get("case_id")
            if not isinstance(case_id, str) or case_id not in cases:
                raise MatrixError(f"suite {suite_name} references unknown case {case_id!r}")
            if child.get("status") != "passed":
                raise MatrixError(f"suite {suite_name} case {case_id} is not passed")
            case = cases[case_id]
            dialect = _dialect(child, case)
            if (case_id, dialect) not in selected_pairs:
                raise MatrixError(
                    f"suite {suite_name} case/dialect is outside selector ownership: "
                    f"{case_id}/{dialect}"
                )
            child_pairs[(case_id, dialect)] += 1
            lane_name, lane = _lane_for(suite, dialect, spec["lanes"])
            for field, manifest_field in (("frontend", "frontends"), ("backend", "backends"), ("protocol", "protocols")):
                if lane[field] not in case.get(manifest_field, []):
                    raise MatrixError(f"{case_id}: lane {lane_name} {field} is not declared by manifest")

            schema = suite["summary_schema"]
            variants = suite.get("variants", {}).get(case_id, ["default"])
            if schema == "explicit_paths":
                paths = [(child.get("path"), "default")]
            elif schema == "cursor_variants":
                paths = [(path, variant) for path in ("direct", "gateway") for variant in variants]
            else:
                paths = [(path, "default") for path in ("direct", "gateway")]
            for path_name, variant in paths:
                if path_name not in {"direct", "gateway"}:
                    raise MatrixError(f"suite {suite_name} case {case_id} has invalid path {path_name!r}")
                key = (suite_name, case_id, dialect, path_name, variant)
                if key in path_keys:
                    raise MatrixError(f"duplicate path: {key}")
                path_keys.add(key)
                results.append({
                    "suite": suite_name,
                    "case_id": case_id,
                    "dialect": dialect,
                    "frontend": lane["frontend"],
                    "backend": lane["backend"],
                    "protocol": lane["protocol"],
                    "lane": lane_name,
                    "path": path_name,
                    "variant": variant,
                    "status": "passed",
                    "evidence": str(summary_path.parent),
                    "reproduce_command": _reproduce(root, suite, case_id),
                    "run_id": run_id,
                })
                suite_counts[suite_name] += 1
                lane_counts[lane_name] += 1
        if acceptance_complete:
            expected_child_pairs = selected_pairs.copy()
            if suite["summary_schema"] == "explicit_paths":
                expected_child_pairs = Counter(
                    {pair: count * 2 for pair, count in selected_pairs.items()}
                )
            if child_pairs != expected_child_pairs:
                raise MatrixError(
                    f"suite {suite_name} case/dialect selection mismatch: "
                    f"{dict(child_pairs)}"
                )

    expected_suite_paths = {name: sum(suite["lane_paths"].values()) for name, suite in suite_specs.items()}
    expected_lane_paths = {name: lane["expected_paths"] for name, lane in spec["lanes"].items()}
    if acceptance_complete:
        if suite_counts != Counter(expected_suite_paths):
            raise MatrixError(f"suite path counts mismatch: {dict(suite_counts)}")
        if lane_counts != Counter(expected_lane_paths):
            raise MatrixError(f"lane path counts mismatch: {dict(lane_counts)}")
        if len(results) != spec["expected_paths"]:
            raise MatrixError(f"path count mismatch: {len(results)}")
    summary = {
        "matrix_id": spec["matrix_id"],
        "schema_version": spec["schema_version"],
        "run_id": run_id,
        "policy": spec["policy"],
        "acceptance_complete": acceptance_complete,
        "expected_paths": spec["expected_paths"],
        "path_executions": len(results),
        "passed": len(results),
        "failed": 0,
        "suites": dict(sorted(suite_counts.items())),
        "lanes": dict(sorted(lane_counts.items())),
        "results": results,
    }
    return results, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--summary", action="append", metavar="SUITE=PATH")
    parser.add_argument("--filtered", action="store_true")
    args = parser.parse_args()
    summaries: dict[str, Path] = {}
    for item in args.summary or []:
        if "=" not in item:
            parser.error("--summary must be SUITE=PATH")
        suite, path = item.split("=", 1)
        if suite in summaries:
            parser.error(f"duplicate summary suite: {suite}")
        summaries[suite] = Path(path)
    try:
        _, summary = aggregate(
            _load(args.spec), _load(args.manifest), summaries, args.root.resolve(),
            args.run_id, not args.filtered,
        )
    except MatrixError as exc:
        print(f"protocol matrix failed: {exc}", flush=True)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    results_path = args.output.parent / "results.jsonl"
    results_path.write_text(
        "".join(json.dumps(result, sort_keys=True) + "\n" for result in summary["results"]),
        encoding="utf-8",
    )
    print(json.dumps({key: summary[key] for key in ("path_executions", "passed", "failed", "acceptance_complete", "suites", "lanes")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
