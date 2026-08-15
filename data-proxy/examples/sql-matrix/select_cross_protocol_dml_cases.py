#!/usr/bin/env python3
"""Validate and select SQLT-4B2 cross-protocol DML and transaction paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple


EXPECTED_DIRECTIONS = {
    "mysql_text_to_postgres": {
        "frontend": "mysql_text",
        "frontend_dialect": "mysql",
        "backend": "postgres",
        "backend_dialect": "postgres",
        "protocol": "mysql_text",
        "backend_control_protocol": "pg_simple",
        "backend_control_port": 25432,
    },
    "pg_simple_to_mysql": {
        "frontend": "pg_simple",
        "frontend_dialect": "postgres",
        "backend": "mysql",
        "backend_dialect": "mysql",
        "protocol": "pg_simple",
        "backend_control_protocol": "mysql_text",
        "backend_control_port": 23306,
    },
}


class SelectionError(ValueError):
    pass


class Step(NamedTuple):
    name: str
    sql: str
    expected_error: bool


def read_steps(path: Path) -> list[Step]:
    lines = path.read_text(encoding="utf-8").splitlines()[4:]
    steps: list[Step] = []
    name: str | None = None
    body: list[str] = []
    expected_error = False

    def flush() -> None:
        nonlocal name, body, expected_error
        sql = "\n".join(body).strip()
        if name is not None:
            if not sql:
                raise SelectionError(f"{path}: step {name} has no SQL")
            steps.append(Step(name, sql, expected_error))
        name, body, expected_error = None, [], False

    for line in lines:
        if line.startswith("-- @step "):
            flush()
            name = line.removeprefix("-- @step ").strip()
        elif line == "-- @expect error":
            if name is None or body:
                raise SelectionError(
                    f"{path}: @expect error must immediately follow @step"
                )
            expected_error = True
        elif name is not None:
            body.append(line)
    flush()
    if not steps or len({step.name for step in steps}) != len(steps):
        raise SelectionError(f"{path}: step names must be non-empty and unique")
    return steps


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


def _expand_step_oracle(
    case_id: str,
    direction: str,
    label: str,
    actual_steps: list[Any],
    expected_steps: Any,
    wire_profiles: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(expected_steps, list) or len(expected_steps) != len(actual_steps):
        raise SelectionError(f"{case_id}/{direction}: {label} step count mismatch")
    common_fields = {
        "name", "expected_error", "kind", "affected_rows", "rows",
        "gateway", "backend_control",
    }
    wire_fields = {"command_tag", "error_code", "sqlstate", "transaction_status"}
    expanded: list[dict[str, Any]] = []
    for actual, expected in zip(actual_steps, expected_steps, strict=True):
        if not isinstance(expected, dict) or set(expected) != common_fields:
            raise SelectionError(f"{case_id}/{direction}: {label} step fields are invalid")
        if expected["name"] != actual.name:
            raise SelectionError(f"{case_id}/{direction}: {label} step order mismatch")
        if expected["expected_error"] != actual.expected_error:
            raise SelectionError(f"{case_id}/{direction}: {label} error declaration mismatch")
        if expected["kind"] not in {"ok", "rows", "error"}:
            raise SelectionError(f"{case_id}/{direction}: {label} response kind is invalid")
        if not isinstance(expected["rows"], list):
            raise SelectionError(f"{case_id}/{direction}: {label} rows are invalid")
        channel = expected[label]
        if not isinstance(channel, dict) or set(channel) != set(EXPECTED_DIRECTIONS):
            raise SelectionError(f"{case_id}/{direction}: {label} wire map is invalid")
        wire = channel[direction]
        if isinstance(wire, str):
            wire = wire_profiles.get(label, {}).get(direction, {}).get(wire)
        if not isinstance(wire, dict) or set(wire) != wire_fields:
            raise SelectionError(f"{case_id}/{direction}: {label} wire fields are invalid")
        if wire["transaction_status"] not in {"I", "T", "E"}:
            raise SelectionError(f"{case_id}/{direction}: {label} transaction status is invalid")
        expanded.append({
            "name": expected["name"],
            "expected_error": expected["expected_error"],
            "kind": expected["kind"],
            "affected_rows": expected["affected_rows"],
            "command_tag": wire["command_tag"],
            "rows": expected["rows"],
            "error_code": wire["error_code"],
            "sqlstate": wire["sqlstate"],
            "transaction_status": wire["transaction_status"],
        })
    return expanded


def select_paths(
    spec: dict[str, Any],
    oracles: dict[str, Any],
    root: Path,
    direction_filter: str = "",
    case_from: str = "",
    case_to: str = "",
) -> list[dict[str, Any]]:
    if spec.get("schema_version") != 1 or spec.get("matrix_id") != "SQLT-4B2":
        raise SelectionError("cross-protocol DML spec identity is invalid")
    if oracles.get("schema_version") != 1 or oracles.get("matrix_id") != "SQLT-4B2":
        raise SelectionError("cross-protocol DML oracle identity is invalid")
    directions = spec.get("directions")
    if not isinstance(directions, dict) or set(directions) != set(EXPECTED_DIRECTIONS):
        raise SelectionError("cross-protocol DML directions must be the two SQLT-4B2 lanes")
    for name, expected in EXPECTED_DIRECTIONS.items():
        actual = directions[name]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise SelectionError(f"direction {name} has invalid {field}")
        if not isinstance(actual.get("listener"), str) or not isinstance(actual.get("port"), int):
            raise SelectionError(f"direction {name} lacks listener or port")
        _safe_file(root, actual.get("state_query", ""), "")
    if direction_filter and direction_filter not in directions:
        raise SelectionError(f"unknown cross-protocol DML direction: {direction_filter}")
    if bool(case_from) != bool(case_to):
        raise SelectionError("both case range endpoints are required")
    if case_from and case_from > case_to:
        raise SelectionError("case range is reversed")

    cases = spec.get("cases")
    oracle_results = oracles.get("results")
    state_profiles = oracles.get("state_profiles")
    wire_profiles = oracles.get("wire_profiles")
    if not isinstance(cases, list) or len(cases) != spec.get("expected_cases"):
        raise SelectionError("cross-protocol DML case count does not match expected_cases")
    case_ids = [case.get("id") for case in cases]
    if case_ids != [f"SQLT-XDML-{index:03d}" for index in range(1, 9)]:
        raise SelectionError("cross-protocol DML case IDs must be SQLT-XDML-001 through 008")
    if not isinstance(oracle_results, dict) or set(case_ids) != set(oracle_results):
        raise SelectionError("cross-protocol DML spec and oracle cases do not match")
    if not isinstance(state_profiles, dict) or not state_profiles:
        raise SelectionError("cross-protocol DML state profiles are invalid")
    if not isinstance(wire_profiles, dict) or set(wire_profiles) != {
        "gateway", "backend_control"
    }:
        raise SelectionError("cross-protocol DML wire profiles are invalid")

    selected: list[dict[str, Any]] = []
    direction_names = [direction_filter] if direction_filter else list(directions)
    for case in cases:
        case_id = case["id"]
        if case_from and not case_from <= case_id <= case_to:
            continue
        sql = case.get("sql")
        if not isinstance(sql, dict) or set(sql) != set(directions):
            raise SelectionError(f"{case_id}: SQL paths must cover both directions")
        oracle = oracle_results[case_id]
        if not isinstance(oracle, dict) or set(oracle) != {
            "before_state", "after_state", "steps"
        }:
            raise SelectionError(f"{case_id}: oracle fields are invalid")
        for direction_name in direction_names:
            direction = directions[direction_name]
            path = _safe_file(root, sql[direction_name], "cases")
            _validate_header(path, case_id, direction["frontend_dialect"])
            steps = read_steps(path)
            backend_direction = next(
                name for name, candidate in directions.items()
                if candidate["frontend_dialect"] == direction["backend_dialect"]
            )
            backend_path = _safe_file(root, sql[backend_direction], "cases")
            _validate_header(backend_path, case_id, direction["backend_dialect"])
            backend_steps = read_steps(backend_path)
            gateway_oracle = _expand_step_oracle(
                case_id, direction_name, "gateway", steps, oracle["steps"], wire_profiles
            )
            backend_oracle = _expand_step_oracle(
                case_id, direction_name, "backend_control", backend_steps,
                oracle["steps"], wire_profiles,
            )
            states: dict[str, list[Any]] = {}
            for state_name in ("before_state", "after_state"):
                profile = oracle[state_name]
                state = state_profiles.get(profile) if isinstance(profile, str) else profile
                if not isinstance(state, list):
                    raise SelectionError(f"{case_id}: {state_name} is invalid")
                states[state_name] = state
            selected.append({
                "case_id": case_id,
                "name": case.get("name"),
                "direction": direction_name,
                "frontend": direction["frontend"],
                "backend": direction["backend"],
                "protocol": direction["protocol"],
                "port": direction["port"],
                "listener": direction["listener"],
                "backend_control_protocol": direction["backend_control_protocol"],
                "backend_control_port": direction["backend_control_port"],
                "sql_file": sql[direction_name],
                "backend_sql_file": sql[backend_direction],
                "state_query": direction["state_query"],
                "gateway_steps": gateway_oracle,
                "backend_control_steps": backend_oracle,
                "before_state": states["before_state"],
                "after_state": states["after_state"],
            })

    if not selected:
        raise SelectionError("cross-protocol DML selection is empty")
    if not direction_filter and not case_from and len(selected) != spec.get("expected_paths"):
        raise SelectionError("formal cross-protocol DML selection does not match expected_paths")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--direction", default="")
    parser.add_argument("--case-from", default="")
    parser.add_argument("--case-to", default="")
    args = parser.parse_args()
    try:
        records = select_paths(
            _load(args.spec), _load(args.oracles), args.root,
            args.direction, args.case_from, args.case_to,
        )
    except (OSError, json.JSONDecodeError, SelectionError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    for record in records:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
