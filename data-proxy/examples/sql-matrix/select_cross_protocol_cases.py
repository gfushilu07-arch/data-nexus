#!/usr/bin/env python3
"""Validate and select SQLT-4B1 cross-protocol DQL paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


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


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_sql_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.suffix != ".sql":
        raise SelectionError(f"unsafe SQL path: {relative!r}")
    path = root / "cases" / pure
    if not path.is_file():
        raise SelectionError(f"missing SQL file: {relative}")
    return path


def _validate_header(path: Path, case_id: str, dialect: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    expected = (
        f"-- case: {case_id}",
        "-- Purpose: ",
        "-- Expected: ",
        f"-- Dialect: {dialect}",
    )
    if len(lines) < 5 or lines[0] != expected[0]:
        raise SelectionError(f"{path.name}: case header must be {case_id}")
    if not lines[1].startswith(expected[1]) or not lines[1][len(expected[1]):].strip():
        raise SelectionError(f"{path.name}: missing Purpose header")
    if not lines[2].startswith(expected[2]) or not lines[2][len(expected[2]):].strip():
        raise SelectionError(f"{path.name}: missing Expected header")
    declared = [item.strip() for item in lines[3].removeprefix("-- Dialect: ").split(",")]
    if dialect not in declared:
        raise SelectionError(f"{path.name}: dialect {dialect!r} is not declared")
    if not any(line.strip() and not line.lstrip().startswith("--") for line in lines[4:]):
        raise SelectionError(f"{path.name}: SQL body is empty")


def select_paths(
    spec: dict[str, Any],
    manifest: dict[str, Any],
    oracles: dict[str, Any],
    dql_oracles: dict[str, Any],
    root: Path,
    direction_filter: str = "",
    case_from: str = "",
    case_to: str = "",
) -> list[dict[str, Any]]:
    if spec.get("schema_version") != 1 or spec.get("matrix_id") != "SQLT-4B1":
        raise SelectionError("cross-protocol spec identity is invalid")
    directions = spec.get("directions")
    if not isinstance(directions, dict) or set(directions) != set(EXPECTED_DIRECTIONS):
        raise SelectionError("cross-protocol directions must be the two SQLT-4B1 lanes")
    for name, expected in EXPECTED_DIRECTIONS.items():
        actual = directions[name]
        for field, value in expected.items():
            if actual.get(field) != value:
                raise SelectionError(f"direction {name} has invalid {field}")
        if not isinstance(actual.get("listener"), str) or not isinstance(actual.get("port"), int):
            raise SelectionError(f"direction {name} lacks listener or port")
    if direction_filter and direction_filter not in directions:
        raise SelectionError(f"unknown cross-protocol direction: {direction_filter}")
    if bool(case_from) != bool(case_to):
        raise SelectionError("both case range endpoints are required")
    if case_from and case_from > case_to:
        raise SelectionError("case range is reversed")

    manifest_cases = {case.get("id"): case for case in manifest.get("cases", [])}
    oracle_results = oracles.get("results")
    source_results = dql_oracles.get("results")
    if oracles.get("schema_version") != 1 or oracles.get("matrix_id") != "SQLT-4B1":
        raise SelectionError("cross-protocol oracle identity is invalid")
    if not isinstance(oracle_results, dict) or not isinstance(source_results, dict):
        raise SelectionError("cross-protocol or DQL oracle results are invalid")

    cases = spec.get("cases")
    if not isinstance(cases, list) or len(cases) != spec.get("expected_cases"):
        raise SelectionError("cross-protocol case count does not match expected_cases")
    case_ids = [case.get("id") for case in cases]
    if any(not isinstance(case_id, str) for case_id in case_ids) or len(set(case_ids)) != len(case_ids):
        raise SelectionError("cross-protocol case IDs must be unique strings")
    if set(case_ids) != set(oracle_results):
        raise SelectionError("cross-protocol spec and oracle cases do not match")

    selected = []
    direction_names = [direction_filter] if direction_filter else list(directions)
    for case in cases:
        case_id = case["id"]
        if case_from and not case_from <= case_id <= case_to:
            continue
        source_case_id = case.get("source_case_id")
        source_case = manifest_cases.get(source_case_id)
        if not isinstance(source_case, dict) or source_case.get("family") != "dql":
            raise SelectionError(f"{case_id}: source case is not canonical DQL")
        if set(source_case.get("dialects", [])) != {"mysql", "postgres"}:
            raise SelectionError(f"{case_id}: source case must support both dialects")
        oracle = oracle_results[case_id]
        if oracle.get("source_oracle_case") != source_case_id or source_case_id not in source_results:
            raise SelectionError(f"{case_id}: source oracle is not closed")
        columns = oracle.get("columns")
        frontend_types = oracle.get("frontend_types")
        rows_text = oracle.get("rows_text")
        if not isinstance(columns, list) or not columns or any(not isinstance(v, str) or not v for v in columns):
            raise SelectionError(f"{case_id}: columns are invalid")
        if not isinstance(frontend_types, dict) or set(frontend_types) != set(directions):
            raise SelectionError(f"{case_id}: frontend_types must cover both directions")
        if not isinstance(rows_text, dict) or set(rows_text) != set(directions):
            raise SelectionError(f"{case_id}: rows_text must cover both directions")

        sql = case.get("sql")
        if not isinstance(sql, dict) or set(sql) != set(directions):
            raise SelectionError(f"{case_id}: SQL paths must cover both directions")
        tags = case.get("rewrite_tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
            raise SelectionError(f"{case_id}: rewrite_tags are invalid")
        for direction_name in direction_names:
            direction = directions[direction_name]
            path = _safe_sql_path(root, sql[direction_name])
            _validate_header(path, case_id if case_id.startswith("SQLT-XDQL-") else source_case_id,
                             direction["frontend_dialect"])
            types = frontend_types[direction_name]
            if not isinstance(types, list) or len(types) != len(columns):
                raise SelectionError(f"{case_id}: frontend type count does not match columns")
            backend_dialect = direction["backend_dialect"]
            backend_rows = source_results[source_case_id].get(backend_dialect)
            gateway_rows = rows_text[direction_name]
            if not isinstance(backend_rows, str):
                raise SelectionError(f"{case_id}: missing {backend_dialect} row oracle")
            if not isinstance(gateway_rows, str):
                raise SelectionError(f"{case_id}: missing {direction_name} gateway row oracle")
            backend_sql_direction = next(
                name for name, candidate in directions.items()
                if candidate["frontend_dialect"] == backend_dialect
            )
            backend_path = _safe_sql_path(root, sql[backend_sql_direction])
            _validate_header(
                backend_path,
                case_id if case_id.startswith("SQLT-XDQL-") else source_case_id,
                backend_dialect,
            )
            selected.append({
                "case_id": case_id,
                "source_case_id": source_case_id,
                "direction": direction_name,
                "frontend": direction["frontend"],
                "frontend_dialect": direction["frontend_dialect"],
                "backend": direction["backend"],
                "backend_dialect": backend_dialect,
                "protocol": direction["protocol"],
                "listener": direction["listener"],
                "port": direction["port"],
                "backend_control_protocol": direction["backend_control_protocol"],
                "backend_control_port": direction["backend_control_port"],
                "sql_file": sql[direction_name],
                "backend_sql_file": sql[backend_sql_direction],
                "columns": columns,
                "frontend_types": types,
                "rows_text": gateway_rows,
                "backend_rows_text": backend_rows,
                "rewrite_tags": tags,
            })

    if not selected:
        raise SelectionError("cross-protocol selection is empty")
    if not direction_filter and not case_from and len(selected) != spec.get("expected_paths"):
        raise SelectionError("formal cross-protocol selection does not match expected_paths")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("dql_oracles", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--direction", default="")
    parser.add_argument("--case-from", default="")
    parser.add_argument("--case-to", default="")
    args = parser.parse_args()
    try:
        selected = select_paths(
            _load(args.spec), _load(args.manifest), _load(args.oracles),
            _load(args.dql_oracles), args.root, args.direction, args.case_from, args.case_to,
        )
    except (OSError, json.JSONDecodeError, SelectionError) as error:
        print(error, file=sys.stderr)
        return 1
    for record in selected:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
