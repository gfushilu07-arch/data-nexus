#!/usr/bin/env python3
"""Verify and aggregate SQLT-4B3 cross-protocol prepared boundary evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class MatrixError(ValueError):
    pass


TRANSCRIPT_FIELDS = {
    "protocol", "case_id", "direction", "steps",
}


def state_protocol_for(backend: str) -> str:
    if backend == "postgres":
        return "pg_simple"
    if backend == "mysql":
        return "mysql_text"
    raise MatrixError(f"unknown backend for state evidence: {backend!r}")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _verify_transcript(
    label: str,
    name: str,
    evidence: dict[str, Any],
    expected_protocol: str,
    expected_direction: str,
    expected_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(evidence, dict) or set(evidence) != TRANSCRIPT_FIELDS:
        raise MatrixError(f"{label}: {name} transcript fields must be {sorted(TRANSCRIPT_FIELDS)}")
    if evidence["protocol"] != expected_protocol:
        raise MatrixError(f"{label}: {name} protocol mismatch")
    if evidence["direction"] != expected_direction:
        raise MatrixError(f"{label}: {name} direction mismatch")
    actual_steps = evidence["steps"]
    if not isinstance(actual_steps, list) or len(actual_steps) != len(expected_steps):
        raise MatrixError(f"{label}: {name} step count mismatch")
    for index, (actual, expected) in enumerate(zip(actual_steps, expected_steps, strict=True)):
        if not isinstance(actual, dict) or actual.get("name") != expected["name"]:
            raise MatrixError(f"{label}: {name} step {index} name mismatch")
        if actual.get("expectation_met") is not True:
            raise MatrixError(f"{label}: {name} step {actual['name']} expectation was not met")
        for field, value in expected.items():
            # `wire` is the pg_extended lane's phase transcript; MySQL binary
            # transcripts have no wire tags to compare.
            if field == "wire" and expected_protocol != "pg_extended":
                continue
            if actual.get(field) != value:
                raise MatrixError(
                    f"{label}: {name} step {actual['name']} {field} mismatch: "
                    f"expected {value!r}, got {actual.get(field)!r}"
                )
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
    if evidence["columns"] != ["entity", "cnt"]:
        raise MatrixError(f"{label}: {name} state columns mismatch")
    if evidence["rows"] != expected_rows:
        raise MatrixError(f"{label}: {name} state rows mismatch")
    if evidence["row_count"] != len(expected_rows):
        raise MatrixError(f"{label}: {name} state row count mismatch")
    return evidence["rows"]


def verify_success_path(
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
    state_protocol = state_protocol_for(selection["backend"])

    backend_before_rows = _verify_state(
        label, "backend control before", backend_before, state_protocol,
        selection["before_state"],
    )
    backend_steps = _verify_transcript(
        label, "backend control", backend_transcript, backend_protocol,
        selection["backend_direction"], selection["backend_steps"],
    )
    backend_after_rows = _verify_state(
        label, "backend control after", backend_after, state_protocol,
        selection["after_state"],
    )
    gateway_before_rows = _verify_state(
        label, "gateway before", gateway_before, state_protocol,
        selection["before_state"],
    )
    gateway_steps = _verify_transcript(
        label, "gateway", gateway_transcript, selection["protocol"],
        direction, selection["gateway_steps"],
    )
    gateway_after_rows = _verify_state(
        label, "gateway after", gateway_after, state_protocol,
        selection["after_state"],
    )
    if backend_after_rows != gateway_after_rows:
        raise MatrixError(f"{label}: backend control and gateway final states diverge")
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
        "outcome": "success",
        "direction": direction,
        "frontend": selection["frontend"],
        "backend": selection["backend"],
        "protocol": selection["protocol"],
        "status": "passed",
        "step_transcript": {"backend_control": backend_steps, "gateway": gateway_steps},
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
        "reproduction": reproduction,
    }


def verify_reject_path(
    selection: dict[str, Any],
    backend_before: dict[str, Any],
    gateway_transcript: dict[str, Any],
    backend_after: dict[str, Any],
    evidence_paths: dict[str, str],
    reproduction: str,
) -> dict[str, Any]:
    case_id = selection["case_id"]
    direction = selection["direction"]
    label = f"{case_id}/{direction}"
    state_protocol = state_protocol_for(selection["backend"])

    backend_before_rows = _verify_state(
        label, "backend canary before", backend_before, state_protocol,
        selection["before_state"],
    )
    gateway_steps = _verify_transcript(
        label, "gateway", gateway_transcript, selection["protocol"],
        direction, selection["gateway_steps"],
    )
    backend_after_rows = _verify_state(
        label, "backend canary after", backend_after, state_protocol,
        selection["after_state"],
    )
    if backend_before_rows != backend_after_rows:
        raise MatrixError(f"{label}: reject path mutated backend state")
    error_steps = [step for step in gateway_steps if step["kind"] == "error"]
    if not error_steps:
        raise MatrixError(f"{label}: reject path has no frontend-visible error step")
    required_paths = {"backend_before", "gateway_transcript", "backend_after"}
    if set(evidence_paths) != required_paths or not all(
        isinstance(value, str) and value for value in evidence_paths.values()
    ):
        raise MatrixError(f"{label}: evidence path map is invalid")

    return {
        "case_id": case_id,
        "name": selection["name"],
        "outcome": "reject",
        "direction": direction,
        "frontend": selection["frontend"],
        "backend": selection["backend"],
        "protocol": selection["protocol"],
        "status": "passed",
        "step_transcript": {"gateway": gateway_steps},
        "backend_control_evidence": {
            "paths": {
                "before": evidence_paths["backend_before"],
                "after": evidence_paths["backend_after"],
            },
            "before_state": backend_before_rows,
            "after_state": backend_after_rows,
        },
        "gateway_evidence": {
            "paths": {"transcript": evidence_paths["gateway_transcript"]},
        },
        "reject_evidence": {
            "frontend_errors": [
                {
                    "step": step["name"],
                    "error_code": step["error_code"],
                    "sqlstate": step["sqlstate"],
                    "classification": step["classification"],
                }
                for step in error_steps
            ],
            "backend_execute_count": 0,
            "backend_state_unchanged": True,
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
        raise MatrixError("duplicate cross-protocol boundary result path")
    if set(actual) != expected:
        raise MatrixError("cross-protocol boundary result paths do not match selection")
    if any(item.get("status") != "passed" for item in results):
        raise MatrixError("cross-protocol boundary results contain a non-passed path")
    lanes: dict[str, int] = {}
    success = 0
    reject = 0
    for item in results:
        lanes[item["direction"]] = lanes.get(item["direction"], 0) + 1
        if item["outcome"] == "success":
            success += 1
        else:
            reject += 1
    cases = len({item["case_id"] for item in results})
    complete = not filtered
    if complete and (len(results), cases, success, reject, lanes) != (
        26,
        13,
        16,
        10,
        {"mysql_binary_to_postgres": 13, "pg_extended_to_mysql": 13},
    ):
        raise MatrixError(
            "formal SQLT-4B3 acceptance must be 26 paths, 13 cases, 16 success, "
            "10 reject, and 2 lanes of 13"
        )
    return {
        "suite": "SQLT-4B3",
        "run_id": run_id,
        "run_dir": run_dir,
        "acceptance_complete": complete,
        "paths": len(results),
        "cases": cases,
        "success_paths": success,
        "reject_paths": reject,
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
        compare.add_argument(f"--{name}", type=Path)
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
            selection = load(args.selection)
            paths = {
                "backend_before": str(args.backend_before),
                "backend_transcript": str(args.backend_transcript),
                "backend_after": str(args.backend_after),
                "gateway_before": str(args.gateway_before),
                "gateway_transcript": str(args.gateway_transcript),
                "gateway_after": str(args.gateway_after),
            }
            if selection["outcome"] == "success":
                for name in paths.values():
                    if not name or name == "None":
                        raise MatrixError("success path requires all six evidence files")
                value = verify_success_path(
                    selection,
                    load(args.backend_before), load(args.backend_transcript),
                    load(args.backend_after), load(args.gateway_before),
                    load(args.gateway_transcript), load(args.gateway_after),
                    {key: value for key, value in paths.items() if value != "None"},
                    args.reproduction,
                )
            else:
                value = verify_reject_path(
                    selection,
                    load(args.backend_before),
                    load(args.gateway_transcript),
                    load(args.backend_after),
                    {
                        "backend_before": str(args.backend_before),
                        "gateway_transcript": str(args.gateway_transcript),
                        "backend_after": str(args.backend_after),
                    },
                    args.reproduction,
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
        print(json.dumps({"summary": str(args.output), "paths": value["paths"]}))
    except (OSError, json.JSONDecodeError, MatrixError) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
