#!/usr/bin/env python3
"""Verify and aggregate SQLT-4B1 cross-protocol path evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class MatrixError(ValueError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def expected_row_count(text: str) -> int:
    return len(text.splitlines())


def verify_path(
    selection: dict[str, Any],
    backend: dict[str, Any],
    gateway: dict[str, Any],
    backend_evidence: str,
    gateway_evidence: str,
    reproduction: str,
) -> dict[str, Any]:
    case_id = selection["case_id"]
    direction = selection["direction"]
    label = f"{case_id}/{direction}"
    for name, value in (("backend", backend), ("gateway", gateway)):
        required = {"protocol", "columns", "types", "rows", "rows_text", "row_count"}
        if not isinstance(value, dict) or set(value) != required:
            raise MatrixError(f"{label}: {name} evidence fields must be {sorted(required)}")
        if len(value["columns"]) != len(value["types"]):
            raise MatrixError(f"{label}: {name} column/type count mismatch")

    if backend["protocol"] != selection["backend_control_protocol"]:
        raise MatrixError(f"{label}: backend control protocol mismatch")
    if backend["columns"] != selection["columns"]:
        raise MatrixError(f"{label}: backend control columns mismatch")
    if backend["rows_text"] != selection["backend_rows_text"]:
        raise MatrixError(f"{label}: backend control rows mismatch")
    if backend["row_count"] != expected_row_count(selection["backend_rows_text"]):
        raise MatrixError(f"{label}: backend control row count mismatch")

    if gateway["protocol"] != selection["protocol"]:
        raise MatrixError(f"{label}: gateway protocol mismatch")
    if gateway["columns"] != selection["columns"]:
        raise MatrixError(f"{label}: gateway columns mismatch")
    if gateway["types"] != selection["frontend_types"]:
        raise MatrixError(f"{label}: gateway frontend types mismatch")
    if gateway["rows_text"] != selection["rows_text"]:
        raise MatrixError(f"{label}: gateway rows mismatch")
    if gateway["row_count"] != expected_row_count(selection["rows_text"]):
        raise MatrixError(f"{label}: gateway row count mismatch")

    return {
        "case_id": case_id,
        "source_case_id": selection["source_case_id"],
        "direction": direction,
        "frontend": selection["frontend"],
        "backend": selection["backend"],
        "protocol": selection["protocol"],
        "status": "passed",
        "backend_control_evidence": backend_evidence,
        "gateway_evidence": gateway_evidence,
        "type_map": {"backend_control": backend["types"], "gateway": gateway["types"]},
        "rewrite_tags": selection["rewrite_tags"],
        "row_count": gateway["row_count"],
        "reproduction": reproduction,
    }


def aggregate(
    selections: list[dict[str, Any]],
    results: list[dict[str, Any]],
    run_id: str,
    run_dir: str,
    filtered: bool,
) -> dict[str, Any]:
    expected = {(item["case_id"], item["direction"]) for item in selections}
    actual = [(item.get("case_id"), item.get("direction")) for item in results]
    if len(actual) != len(set(actual)):
        raise MatrixError("duplicate cross-protocol result path")
    if set(actual) != expected:
        raise MatrixError("cross-protocol result paths do not match selection")
    if any(item.get("status") != "passed" for item in results):
        raise MatrixError("cross-protocol results contain a non-passed path")
    lanes: dict[str, int] = {}
    for item in results:
        lanes[item["direction"]] = lanes.get(item["direction"], 0) + 1
    cases = len({item["case_id"] for item in results})
    complete = not filtered
    if complete and (len(results), cases, lanes) != (
        24,
        12,
        {"mysql_text_to_postgres": 12, "pg_simple_to_mysql": 12},
    ):
        raise MatrixError("formal SQLT-4B1 acceptance must be 24 paths, 12 cases, and 2 lanes")
    return {
        "suite": "SQLT-4B1",
        "run_id": run_id,
        "run_dir": run_dir,
        "acceptance_complete": complete,
        "paths": len(results),
        "cases": cases,
        "lanes": dict(sorted(lanes.items())),
        "passed": len(results),
        "failed": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--selection", type=Path, required=True)
    compare.add_argument("--backend", type=Path, required=True)
    compare.add_argument("--gateway", type=Path, required=True)
    compare.add_argument("--backend-evidence", required=True)
    compare.add_argument("--gateway-evidence", required=True)
    compare.add_argument("--reproduction", required=True)
    summary = subparsers.add_parser("aggregate")
    summary.add_argument("--selection", type=Path, required=True)
    summary.add_argument("--results", type=Path, required=True)
    summary.add_argument("--output", type=Path, required=True)
    summary.add_argument("--run-id", required=True)
    summary.add_argument("--run-dir", required=True)
    summary.add_argument("--filtered", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "compare":
            value = verify_path(
                load(args.selection), load(args.backend), load(args.gateway),
                args.backend_evidence, args.gateway_evidence, args.reproduction,
            )
            print(json.dumps(value, sort_keys=True, separators=(",", ":")))
            return 0
        value = aggregate(
            load_jsonl(args.selection), load_jsonl(args.results), args.run_id, args.run_dir,
            args.filtered,
        )
        args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(value, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, MatrixError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
