#!/usr/bin/env python3
"""Validate and select SQLT-5 governance policy matrix paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_PROTOCOLS = {
    "mysql_text_to_mysql": {
        "frontend": "mysql_text",
        "frontend_dialect": "mysql",
        "backend": "mysql",
        "backend_dialect": "mysql",
        "protocol": "mysql_text",
        "port": 29120,
        "listener": "sqlt-governance-mysql",
    },
    "pg_simple_to_postgres": {
        "frontend": "pg_simple",
        "frontend_dialect": "postgres",
        "backend": "postgres",
        "backend_dialect": "postgres",
        "protocol": "pg_simple",
        "port": 29121,
        "listener": "sqlt-governance-postgresql",
    },
}

EXPECTED_POLICIES = {
    "security_off": {"enabled": False},
    "deny_dml": {"enabled": True},
    "deny_select_targets": {"enabled": True},
    "row_filter_tenant10": {"enabled": True},
    "column_strip_amount": {"enabled": True},
    "mask_pii": {"enabled": True},
    "watermark_column": {"enabled": True},
    "max_rows_1": {"enabled": True},
    "audit_l0": {"enabled": True},
    "audit_l1": {"enabled": True},
    "audit_l2": {"enabled": True},
}

STEP_KINDS = {"ok", "rows", "error"}
STEP_FIELDS = {
    "name", "expected_error", "kind", "affected_rows", "command_tag", "rows",
    "error_code", "sqlstate", "transaction_status",
}


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


def _safe_config(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".toml":
        raise SelectionError(f"unsafe config path: {relative!r}")
    path = root / pure
    if not path.is_file():
        raise SelectionError(f"missing policy config: {relative}")
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


def _validate_steps(case_key: str, steps: Any) -> None:
    if not isinstance(steps, list) or not steps:
        raise SelectionError(f"{case_key}: steps must be a non-empty list")
    names: set[str] = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) - STEP_FIELDS or not {
            "name", "expected_error", "kind"
        } <= set(step):
            raise SelectionError(f"{case_key}: step fields are invalid")
        if step["name"] in names:
            raise SelectionError(f"{case_key}: duplicate step name {step['name']!r}")
        names.add(step["name"])
        if step["kind"] not in STEP_KINDS:
            raise SelectionError(f"{case_key}: step kind {step['kind']!r} is invalid")
        if not isinstance(step["expected_error"], bool):
            raise SelectionError(f"{case_key}: expected_error must be boolean")
        if (step["kind"] == "error") != step["expected_error"]:
            raise SelectionError(
                f"{case_key}: step {step['name']!r} kind/expected_error disagree"
            )
        if "rows" in step and not isinstance(step["rows"], list):
            raise SelectionError(f"{case_key}: step rows must be a list")


def select_paths(
    spec: dict[str, Any],
    oracles: dict[str, Any],
    root: Path,
    protocol_filter: str = "",
    policy_filter: str = "",
    case_from: str = "",
    case_to: str = "",
) -> list[dict[str, Any]]:
    if spec.get("schema_version") != 1 or spec.get("matrix_id") != "SQLT-5":
        raise SelectionError("governance spec identity is invalid")
    if oracles.get("schema_version") != 1 or oracles.get("matrix_id") != "SQLT-5":
        raise SelectionError("governance oracle identity is invalid")
    protocols = spec.get("protocols")
    if not isinstance(protocols, dict) or set(protocols) != set(EXPECTED_PROTOCOLS):
        raise SelectionError("governance protocols must be the two SQLT-5A lanes")
    for name, expected in EXPECTED_PROTOCOLS.items():
        actual = protocols[name]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise SelectionError(f"protocol {name} has invalid {field}")
        _safe_file(root, actual.get("state_query", ""), "")
    policies = spec.get("policies")
    if not isinstance(policies, dict) or set(policies) != set(EXPECTED_POLICIES):
        raise SelectionError("governance policies must be the eight SQLT-5 policies")
    for name, expected in EXPECTED_POLICIES.items():
        actual = policies[name]
        if actual.get("enabled") != expected["enabled"]:
            raise SelectionError(f"policy {name} has invalid enabled flag")
        _safe_config(root, actual.get("config", ""))
    if protocol_filter and protocol_filter not in protocols:
        raise SelectionError(f"unknown governance protocol: {protocol_filter}")
    if policy_filter and policy_filter not in policies:
        raise SelectionError(f"unknown governance policy: {policy_filter}")
    if bool(case_from) != bool(case_to):
        raise SelectionError("both case range endpoints are required")
    if case_from and case_from > case_to:
        raise SelectionError("case range is reversed")

    cases = spec.get("cases")
    oracle_results = oracles.get("results")
    state_profiles = oracles.get("state_profiles")
    if not isinstance(cases, list) or len(cases) != spec.get("expected_cases"):
        raise SelectionError("governance case count does not match expected_cases")
    case_ids = [case.get("id") for case in cases]
    if case_ids != [f"SQLT-GOV-{index:03d}" for index in range(1, 6)]:
        raise SelectionError("governance case IDs must be SQLT-GOV-001 through 004")
    if not isinstance(oracle_results, dict) or set(case_ids) != set(oracle_results):
        raise SelectionError("governance spec and oracle cases do not match")
    if not isinstance(state_profiles, dict) or not state_profiles:
        raise SelectionError("governance state profiles are invalid")

    selected: list[dict[str, Any]] = []
    protocol_names = [protocol_filter] if protocol_filter else list(protocols)
    policy_names = [policy_filter] if policy_filter else list(policies)
    for case in cases:
        case_id = case["id"]
        if case_from and not case_from <= case_id <= case_to:
            continue
        sql = case.get("sql")
        if not isinstance(sql, dict) or set(sql) != set(protocols):
            raise SelectionError(f"{case_id}: SQL paths must cover both protocols")
        oracle = oracle_results[case_id]
        if not isinstance(oracle, dict) or set(oracle) != set(protocols) | {"state"}:
            raise SelectionError(f"{case_id}: oracle fields are invalid")
        case_states = oracle["state"]
        if not isinstance(case_states, dict) or set(case_states) != set(policies):
            raise SelectionError(f"{case_id}: state expectations must cover all policies")
        for protocol_name in protocol_names:
            lanes = oracle[protocol_name]
            if not isinstance(lanes, dict) or set(lanes) != set(policies):
                raise SelectionError(f"{case_id}/{protocol_name}: oracle lanes are invalid")
        for policy_name in policy_names:
            policy = policies[policy_name]
            state_oracle = case_states[policy_name]
            if not isinstance(state_oracle, dict) or set(state_oracle) != {
                "before_state", "after_state"
            }:
                raise SelectionError(f"{case_id}/{policy_name}: state fields are invalid")
            states: dict[str, list[Any]] = {}
            for state_name in ("before_state", "after_state"):
                profile = state_profiles.get(state_oracle[state_name])
                if not isinstance(profile, list):
                    raise SelectionError(f"{case_id}/{policy_name}: {state_name} is invalid")
                states[state_name] = profile
            for protocol_name in protocol_names:
                protocol = protocols[protocol_name]
                path = _safe_file(root, sql[protocol_name], "cases")
                _validate_header(path, case_id, protocol["frontend_dialect"])
                backend_protocol = next(
                    name for name, candidate in protocols.items()
                    if candidate["frontend_dialect"] == protocol["backend_dialect"]
                )
                backend_path = _safe_file(root, sql[backend_protocol], "cases")
                _validate_header(backend_path, case_id, protocol["backend_dialect"])
                lane_oracle = oracle[protocol_name][policy_name]
                if not isinstance(lane_oracle, dict) or set(lane_oracle) != {"steps"}:
                    raise SelectionError(f"{case_id}/{policy_name}/{protocol_name}: lane fields are invalid")
                _validate_steps(
                    f"{case_id}/{policy_name}/{protocol_name}", lane_oracle["steps"]
                )
                selected.append({
                    "case_id": case_id,
                    "name": case.get("name"),
                    "policy": policy_name,
                    "policy_config": policy["config"],
                    "policy_enabled": policy["enabled"],
                    "protocol": protocol_name,
                    "frontend": protocol["frontend"],
                    "backend": protocol["backend"],
                    "client_protocol": protocol["protocol"],
                    "port": protocol["port"],
                    "listener": protocol["listener"],
                    "sql_file": sql[protocol_name],
                    "backend_sql_file": sql[backend_protocol],
                    "state_query": protocol["state_query"],
                    "before_state": states["before_state"],
                    "after_state": states["after_state"],
                    "gateway_steps": lane_oracle["steps"],
                "audit_file": policy.get("audit_file"),
                "audit_level": policy.get("audit_level"),
                })

    if not selected:
        raise SelectionError("governance selection is empty")
    unfiltered = not protocol_filter and not policy_filter and not case_from
    if unfiltered and len(selected) != spec.get("expected_paths"):
        raise SelectionError("formal governance selection does not match expected_paths")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--protocol", default="")
    parser.add_argument("--policy", default="")
    parser.add_argument("--case-from", default="")
    parser.add_argument("--case-to", default="")
    args = parser.parse_args()
    try:
        records = select_paths(
            _load(args.spec), _load(args.oracles), args.root,
            args.protocol, args.policy, args.case_from, args.case_to,
        )
    except (OSError, json.JSONDecodeError, SelectionError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    for record in records:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
