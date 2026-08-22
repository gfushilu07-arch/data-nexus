#!/usr/bin/env python3
"""Validate and select SQLT-4B3 cross-protocol prepared boundary paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_DIRECTIONS = {
    "mysql_binary_to_postgres": {
        "frontend": "mysql_binary",
        "frontend_dialect": "mysql",
        "backend": "postgres",
        "backend_dialect": "postgres",
        "protocol": "mysql_binary",
        "backend_control_protocol": "pg_extended",
        "backend_control_port": 25432,
    },
    "pg_extended_to_mysql": {
        "frontend": "pg_extended",
        "frontend_dialect": "postgres",
        "backend": "mysql",
        "backend_dialect": "mysql",
        "protocol": "pg_extended",
        "backend_control_protocol": "mysql_binary",
        "backend_control_port": 23306,
    },
}

STEP_KINDS = {"ok", "rows", "error", "closed", "describe"}
STEP_FIELDS = {
    "name", "expected_error", "kind", "rows", "columns", "affected_rows",
    "command_tag", "transaction_status", "error_code", "sqlstate",
    "classification", "wire",
}
REQUIRED_STEP_FIELDS = {"name", "expected_error", "kind"}


class SelectionError(ValueError):
    pass


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_file(root: Path, relative: str, prefix: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".sql":
        raise SelectionError(f"unsafe SQL path: {relative!r}")
    path = root / prefix / pure
    if not path.is_file():
        raise SelectionError(f"missing SQL file: {relative}")
    return path


def _validate_header(path: Path, case_id: str, dialect: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 6 or lines[0] != f"-- case: {case_id}":
        raise SelectionError(f"{path.name}: case header must be {case_id}")
    for index, label in ((1, "-- Purpose: "), (2, "-- Expected: ")):
        if not lines[index].startswith(label) or not lines[index][len(label):].strip():
            raise SelectionError(f"{path.name}: missing {label.strip('- ')} header")
    declared = [item.strip() for item in lines[3].removeprefix("-- Dialect: ").split(",")]
    if dialect not in declared:
        raise SelectionError(f"{path.name}: dialect {dialect!r} is not declared")


def _validate_lane(case_id: str, direction: str, lane: Any) -> None:
    if not isinstance(lane, dict) or not set(lane) <= {"parameters", "steps"}:
        raise SelectionError(f"{case_id}/{direction}: lane fields are invalid")
    steps = lane.get("steps")
    if not isinstance(steps, list) or not steps:
        raise SelectionError(f"{case_id}/{direction}: steps must be a non-empty list")
    names: set[str] = set()
    error_count = 0
    for step in steps:
        if not isinstance(step, dict) or not REQUIRED_STEP_FIELDS <= set(step) or set(step) - STEP_FIELDS:
            raise SelectionError(f"{case_id}/{direction}: step fields are invalid")
        if step["name"] in names:
            raise SelectionError(f"{case_id}/{direction}: duplicate step name {step['name']!r}")
        names.add(step["name"])
        if step["kind"] not in STEP_KINDS:
            raise SelectionError(f"{case_id}/{direction}: step kind {step['kind']!r} is invalid")
        if not isinstance(step["expected_error"], bool):
            raise SelectionError(f"{case_id}/{direction}: expected_error must be boolean")
        if (step["kind"] == "error") != step["expected_error"]:
            raise SelectionError(
                f"{case_id}/{direction}: step {step['name']!r} kind/expected_error disagree"
            )
        if step["kind"] == "error":
            error_count += 1
        if "rows" in step and not isinstance(step["rows"], list):
            raise SelectionError(f"{case_id}/{direction}: step rows must be a list")
    parameters = lane.get("parameters", {})
    if not isinstance(parameters, dict) or not all(
        isinstance(values, list) for values in parameters.values()
    ):
        raise SelectionError(f"{case_id}/{direction}: parameters must map step names to lists")


def select_paths(
    spec: dict[str, Any],
    oracles: dict[str, Any],
    root: Path,
    direction_filter: str = "",
    case_from: str = "",
    case_to: str = "",
    outcome_filter: str = "",
) -> list[dict[str, Any]]:
    if spec.get("schema_version") != 1 or spec.get("matrix_id") != "SQLT-4B3":
        raise SelectionError("cross-protocol boundary spec identity is invalid")
    if oracles.get("schema_version") != 1 or oracles.get("matrix_id") != "SQLT-4B3":
        raise SelectionError("cross-protocol boundary oracle identity is invalid")
    directions = spec.get("directions")
    if not isinstance(directions, dict) or set(directions) != set(EXPECTED_DIRECTIONS):
        raise SelectionError("cross-protocol boundary directions must be the two SQLT-4B3 lanes")
    for name, expected in EXPECTED_DIRECTIONS.items():
        actual = directions[name]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise SelectionError(f"direction {name} has invalid {field}")
        if not isinstance(actual.get("listener"), str) or not isinstance(actual.get("port"), int):
            raise SelectionError(f"direction {name} lacks listener or port")
        _safe_file(root, actual.get("state_query", ""), "")
    if direction_filter and direction_filter not in directions:
        raise SelectionError(f"unknown cross-protocol boundary direction: {direction_filter}")
    if outcome_filter and outcome_filter not in {"success", "reject"}:
        raise SelectionError(f"unknown outcome filter: {outcome_filter}")
    if bool(case_from) != bool(case_to):
        raise SelectionError("both case range endpoints are required")
    if case_from and case_from > case_to:
        raise SelectionError("case range is reversed")

    cases = spec.get("cases")
    oracle_results = oracles.get("results")
    if not isinstance(cases, list) or len(cases) != spec.get("expected_cases"):
        raise SelectionError("cross-protocol boundary case count does not match expected_cases")
    case_ids = [case.get("id") for case in cases]
    if case_ids != [f"SQLT-XBND-{index:03d}" for index in range(1, 14)]:
        raise SelectionError("cross-protocol boundary case IDs must be SQLT-XBND-001 through 013")
    if not isinstance(oracle_results, dict) or set(case_ids) != set(oracle_results):
        raise SelectionError("cross-protocol boundary spec and oracle cases do not match")

    success_paths = 0
    reject_paths = 0
    state_profiles = oracles.get("state_profiles")
    if not isinstance(state_profiles, dict) or not state_profiles:
        raise SelectionError("cross-protocol boundary state profiles are invalid")
    selected: list[dict[str, Any]] = []
    direction_names = [direction_filter] if direction_filter else list(directions)
    for case in cases:
        case_id = case["id"]
        if case_from and not case_from <= case_id <= case_to:
            continue
        outcome = case.get("outcome")
        if outcome not in {"success", "reject"}:
            raise SelectionError(f"{case_id}: outcome must be success or reject")
        if outcome_filter and outcome != outcome_filter:
            continue
        sql = case.get("sql")
        if not isinstance(sql, dict) or set(sql) != set(directions):
            raise SelectionError(f"{case_id}: SQL paths must cover both directions")
        oracle = oracle_results[case_id]
        if not isinstance(oracle, dict) or set(oracle) != set(directions) | {
            "before_state", "after_state"
        }:
            raise SelectionError(f"{case_id}: oracle fields are invalid")
        for state_name in ("before_state", "after_state"):
            profile = state_profiles.get(oracle[state_name])
            if not isinstance(profile, list):
                raise SelectionError(f"{case_id}: {state_name} is invalid")
        for direction_name in direction_names:
            direction = directions[direction_name]
            path = _safe_file(root, sql[direction_name], "cases")
            _validate_header(path, case_id, direction["frontend_dialect"])
            backend_direction = next(
                name for name, candidate in directions.items()
                if candidate["frontend_dialect"] == direction["backend_dialect"]
            )
            backend_path = _safe_file(root, sql[backend_direction], "cases")
            _validate_header(backend_path, case_id, direction["backend_dialect"])
            _validate_lane(case_id, direction_name, oracle[direction_name])
            if outcome == "success":
                success_paths += 1
            else:
                reject_paths += 1
            selected.append({
                "case_id": case_id,
                "name": case.get("name"),
                "outcome": outcome,
                "direction": direction_name,
                "frontend": direction["frontend"],
                "backend": direction["backend"],
                "protocol": direction["protocol"],
                "port": direction["port"],
                "listener": direction["listener"],
                "backend_control_protocol": direction["backend_control_protocol"],
                "backend_control_port": direction["backend_control_port"],
                "backend_direction": backend_direction,
                "sql_file": sql[direction_name],
                "backend_sql_file": sql[backend_direction],
                "state_query": direction["state_query"],
                "before_state": state_profiles[oracle["before_state"]],
                "after_state": state_profiles[oracle["after_state"]],
                "gateway_steps": oracle[direction_name]["steps"],
                "backend_steps": oracle[backend_direction]["steps"],
                "backend_parameters": oracle[backend_direction].get("parameters", {}),
                "parameters": oracle[direction_name].get("parameters", {}),
            })

    if not selected:
        raise SelectionError("cross-protocol boundary selection is empty")
    unfiltered = not direction_filter and not case_from and not outcome_filter
    if unfiltered:
        if len(selected) != spec.get("expected_paths"):
            raise SelectionError("formal cross-protocol boundary selection does not match expected_paths")
        if success_paths != spec.get("expected_success_paths"):
            raise SelectionError("formal success path count does not match expected_success_paths")
        if reject_paths != spec.get("expected_reject_paths"):
            raise SelectionError("formal reject path count does not match expected_reject_paths")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--direction", default="")
    parser.add_argument("--case-from", default="")
    parser.add_argument("--case-to", default="")
    parser.add_argument("--outcome", default="")
    args = parser.parse_args()
    try:
        records = select_paths(
            _load(args.spec), _load(args.oracles), args.root,
            args.direction, args.case_from, args.case_to, args.outcome,
        )
    except (OSError, json.JSONDecodeError, SelectionError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    for record in records:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
