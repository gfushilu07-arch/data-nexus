#!/usr/bin/env python3
"""Verify and aggregate SQLT-4B2 DML and transaction path evidence."""

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


def _verify_transcript(
    label: str,
    name: str,
    evidence: dict[str, Any],
    expected_protocol: str,
    expected_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    required = {"protocol", "connection", "steps"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise MatrixError(f"{label}: {name} transcript fields must be {sorted(required)}")
    if evidence["protocol"] != expected_protocol:
        raise MatrixError(f"{label}: {name} protocol mismatch")
    if evidence["connection"] != "same":
        raise MatrixError(f"{label}: {name} must use one connection")
    actual_steps = evidence["steps"]
    if not isinstance(actual_steps, list) or len(actual_steps) != len(expected_steps):
        raise MatrixError(f"{label}: {name} step count mismatch")
    required_step = {
        "name", "expected_error", "kind", "affected_rows", "command_tag", "rows",
        "error_code", "sqlstate", "transaction_status", "expectation_met",
    }
    expected_fields = required_step - {"expectation_met"}
    for index, (actual, expected) in enumerate(zip(actual_steps, expected_steps, strict=True)):
        if not isinstance(actual, dict) or set(actual) != required_step:
            raise MatrixError(
                f"{label}: {name} step {index} fields must be {sorted(required_step)}"
            )
        if set(expected) != expected_fields:
            raise MatrixError(f"{label}: {name} oracle step {index} fields are invalid")
        if actual["expectation_met"] is not True:
            raise MatrixError(f"{label}: {name} step {actual['name']} expectation was not met")
        comparable = {field: actual[field] for field in expected_fields}
        if comparable != expected:
            raise MatrixError(f"{label}: {name} step {actual['name']} mismatch")
    return actual_steps


def _verify_state(
    label: str,
    name: str,
    evidence: dict[str, Any],
    expected_protocol: str,
    expected_rows: list[list[str | None]],
) -> list[list[str | None]]:
    required = {"protocol", "columns", "types", "rows", "rows_text", "row_count"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise MatrixError(f"{label}: {name} state fields must be {sorted(required)}")
    if evidence["protocol"] != expected_protocol:
        raise MatrixError(f"{label}: {name} state protocol mismatch")
    if evidence["columns"] != ["entity", "entity_id", "description", "amount", "status"]:
        raise MatrixError(f"{label}: {name} state columns mismatch")
    if evidence["rows"] != expected_rows:
        raise MatrixError(f"{label}: {name} state rows mismatch")
    if evidence["row_count"] != len(expected_rows):
        raise MatrixError(f"{label}: {name} state row count mismatch")
    return evidence["rows"]


def _affected_map(steps: list[dict[str, Any]]) -> dict[str, int]:
    return {
        step["name"]: step["affected_rows"]
        for step in steps
        if step["affected_rows"] is not None
    }


def _error_transaction_map(steps: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        step["name"]: {
            "error_code": step["error_code"],
            "sqlstate": step["sqlstate"],
            "transaction_status": step["transaction_status"],
        }
        for step in steps
    }


def verify_path(
    selection: dict[str, Any],
    backend_before: dict[str, Any],
    backend_transcript: dict[str, Any],
    backend_after: dict[str, Any],
    gateway_before: dict[str, Any],
    gateway_transcript: dict[str, Any],
    gateway_after: dict[str, Any],
    evidence_paths: dict[str, str],
    reproduction: str,
) -> dict[str, Any]:
    case_id = selection["case_id"]
    direction = selection["direction"]
    label = f"{case_id}/{direction}"
    backend_protocol = selection["backend_control_protocol"]

    backend_before_rows = _verify_state(
        label, "backend control before", backend_before, backend_protocol,
        selection["before_state"],
    )
    backend_steps = _verify_transcript(
        label, "backend control", backend_transcript, backend_protocol,
        selection["backend_control_steps"],
    )
    backend_after_rows = _verify_state(
        label, "backend control after", backend_after, backend_protocol,
        selection["after_state"],
    )
    gateway_before_rows = _verify_state(
        label, "gateway before", gateway_before, backend_protocol,
        selection["before_state"],
    )
    gateway_steps = _verify_transcript(
        label, "gateway", gateway_transcript, selection["protocol"],
        selection["gateway_steps"],
    )
    gateway_after_rows = _verify_state(
        label, "gateway after", gateway_after, backend_protocol,
        selection["after_state"],
    )
    required_paths = {
        "backend_before", "backend_transcript", "backend_after",
        "gateway_before", "gateway_transcript", "gateway_after",
    }
    if set(evidence_paths) != required_paths or not all(
        isinstance(value, str) and value for value in evidence_paths.values()
    ):
        raise MatrixError(f"{label}: evidence path map is invalid")

    return {
        "case_id": case_id,
        "name": selection["name"],
        "direction": direction,
        "frontend": selection["frontend"],
        "backend": selection["backend"],
        "protocol": selection["protocol"],
        "status": "passed",
        "step_transcript": {
            "backend_control": backend_steps,
            "gateway": gateway_steps,
        },
        "backend_control_evidence": {
            "paths": {
                "before": evidence_paths["backend_before"],
                "transcript": evidence_paths["backend_transcript"],
                "after": evidence_paths["backend_after"],
            },
            "before_state": backend_before_rows,
            "after_state": backend_after_rows,
        },
        "gateway_evidence": {
            "paths": {
                "before": evidence_paths["gateway_before"],
                "transcript": evidence_paths["gateway_transcript"],
                "after": evidence_paths["gateway_after"],
            },
            "before_state": gateway_before_rows,
            "after_state": gateway_after_rows,
        },
        "affected_map": {
            "backend_control": _affected_map(backend_steps),
            "gateway": _affected_map(gateway_steps),
        },
        "error_transaction_map": {
            "backend_control": _error_transaction_map(backend_steps),
            "gateway": _error_transaction_map(gateway_steps),
        },
        "final_state_evidence": {
            "backend_control": backend_after_rows,
            "gateway": gateway_after_rows,
        },
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
        raise MatrixError("duplicate cross-protocol DML result path")
    if set(actual) != expected:
        raise MatrixError("cross-protocol DML result paths do not match selection")
    if any(item.get("status") != "passed" for item in results):
        raise MatrixError("cross-protocol DML results contain a non-passed path")
    lanes: dict[str, int] = {}
    for item in results:
        lanes[item["direction"]] = lanes.get(item["direction"], 0) + 1
    cases = len({item["case_id"] for item in results})
    complete = not filtered
    if complete and (len(results), cases, lanes) != (
        16,
        8,
        {"mysql_text_to_postgres": 8, "pg_simple_to_mysql": 8},
    ):
        raise MatrixError("formal SQLT-4B2 acceptance must be 16 paths, 8 cases, and 2 lanes")
    return {
        "suite": "SQLT-4B2",
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
    for name in (
        "backend-before", "backend-transcript", "backend-after",
        "gateway-before", "gateway-transcript", "gateway-after",
    ):
        compare.add_argument(f"--{name}", type=Path, required=True)
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
            paths = {
                "backend_before": str(args.backend_before),
                "backend_transcript": str(args.backend_transcript),
                "backend_after": str(args.backend_after),
                "gateway_before": str(args.gateway_before),
                "gateway_transcript": str(args.gateway_transcript),
                "gateway_after": str(args.gateway_after),
            }
            value = verify_path(
                load(args.selection),
                load(args.backend_before), load(args.backend_transcript),
                load(args.backend_after), load(args.gateway_before),
                load(args.gateway_transcript), load(args.gateway_after),
                paths, args.reproduction,
            )
            print(json.dumps(value, sort_keys=True, separators=(",", ":")))
            return 0
        value = aggregate(
            load_jsonl(args.selection), load_jsonl(args.results), args.run_id,
            args.run_dir, args.filtered,
        )
        args.output.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(value, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, MatrixError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
