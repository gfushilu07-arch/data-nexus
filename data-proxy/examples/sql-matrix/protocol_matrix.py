#!/usr/bin/env python3
"""Validate and aggregate the SQLT-4A same-protocol execution matrix."""

from __future__ import annotations

import argparse
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
    "prepared": ("run-prepared-corpus.sh", "SQLT_PREPARED_RUN_ID", "SQLT_PREPARED_CASE_FROM", "SQLT_PREPARED_CASE_TO", "case_double"),
    "extended": ("run-extended-corpus.sh", "SQLT_EXTENDED_RUN_ID", "SQLT_EXTENDED_CASE_FROM", "SQLT_EXTENDED_CASE_TO", "case_double"),
    "cursor": ("run-cursor-corpus.sh", "SQLT_CURSOR_RUN_ID", "SQLT_CURSOR_CASE_FROM", "SQLT_CURSOR_CASE_TO", "cursor_variants"),
    "tcl": ("run-tcl-corpus.sh", "SQLT_TCL_RUN_ID", "SQLT_TCL_CASE_FROM", "SQLT_TCL_CASE_TO", "dialect_case_double"),
    "dml": ("run-dml-corpus.sh", "SQLT_DML_RUN_ID", "SQLT_DML_CASE_FROM", "SQLT_DML_CASE_TO", "dialect_case_double"),
    "ddl": ("run-ddl-corpus.sh", "SQLT_DDL_RUN_ID", "SQLT_DDL_CASE_FROM", "SQLT_DDL_CASE_TO", "explicit_paths"),
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
        runner = suite.get("runner")
        if runner != contract[0]:
            errors.append(f"suite {name} runner must be {contract[0]}")
        elif root is not None and not (root / runner).is_file():
            errors.append(f"suite {name} runner does not exist: {runner}")
        for offset, field in enumerate(("run_id_env", "case_from_env", "case_to_env"), start=1):
            value = suite.get(field)
            if value != contract[offset]:
                errors.append(f"suite {name} {field} must be {contract[offset]}")
        if suite.get("summary_schema") != contract[4]:
            errors.append(f"suite {name} summary_schema must be {contract[4]}")
        suite_lanes = _object(suite.get("lane_paths"), f"suite {name} lane_paths", errors)
        for lane_name, count in suite_lanes.items():
            if lane_name not in LANES:
                errors.append(f"suite {name} references unknown lane {lane_name}")
            if not isinstance(count, int) or count <= 0:
                errors.append(f"suite {name} lane {lane_name} count must be positive")
            else:
                lane_totals[lane_name] += count
        variants = suite.get("variants", {})
        if not isinstance(variants, dict) or any(
            not isinstance(case_id, str)
            or not isinstance(items, list)
            or not items
            or len(items) != len(set(items))
            or any(not isinstance(item, str) or not item for item in items)
            for case_id, items in (variants.items() if isinstance(variants, dict) else [])
        ):
            errors.append(f"suite {name} variants must map case IDs to unique strings")

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


def _dialect(result: dict[str, Any], case: dict[str, Any]) -> str:
    dialect = result.get("dialect")
    if dialect is None and len(case.get("dialects", [])) == 1:
        dialect = case["dialects"][0]
    if not isinstance(dialect, str) or dialect not in case.get("dialects", []):
        raise MatrixError(f"{case.get('id')}: result dialect is not declared by manifest")
    return dialect


def _lane_for(suite: dict[str, Any], dialect: str, lanes: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    matches = [name for name in suite["lane_paths"] if lanes[name]["backend"] == dialect]
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
        summary = _load(summary_path)
        if not isinstance(summary, dict) or not isinstance(summary.get("results"), list):
            raise MatrixError(f"suite {suite_name} summary must contain results")
        if summary.get("failed") != 0:
            raise MatrixError(f"suite {suite_name} summary reports failed executions")
        for child in summary["results"]:
            if not isinstance(child, dict):
                raise MatrixError(f"suite {suite_name} has a non-object result")
            case_id = child.get("case_id")
            if case_id not in cases:
                raise MatrixError(f"suite {suite_name} references unknown case {case_id!r}")
            if child.get("status") != "passed":
                raise MatrixError(f"suite {suite_name} case {case_id} is not passed")
            case = cases[case_id]
            dialect = _dialect(child, case)
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
