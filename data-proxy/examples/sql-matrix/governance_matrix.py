#!/usr/bin/env python3
"""Verify and aggregate SQLT-5A governance policy path evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


class MatrixError(ValueError):
    pass


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
    evidence: dict[str, Any],
    expected_protocol: str,
    expected_steps: list[dict[str, Any]],
    selection_requires_single_connection: bool = False,
) -> list[dict[str, Any]]:
    required = {"protocol", "connection", "steps"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise MatrixError(f"{label}: transcript fields must be {sorted(required)}")
    if evidence["protocol"] != expected_protocol:
        raise MatrixError(f"{label}: protocol mismatch")
    # Ticket dual-control spans three connections (deny, issued, replay).
    if evidence["connection"] not in ("same", "orchestrated"):
        raise MatrixError(f"{label}: unexpected connection mode {evidence['connection']!r}")
    if selection_requires_single_connection and evidence["connection"] != "same":
        raise MatrixError(f"{label}: non-orchestrated path reused connections unexpectedly")
    actual_steps = evidence["steps"]
    if not isinstance(actual_steps, list) or len(actual_steps) != len(expected_steps):
        raise MatrixError(f"{label}: step count mismatch")
    emitted_step = {
        "name", "expected_error", "kind", "affected_rows", "command_tag", "rows",
        "error_code", "sqlstate", "transaction_status", "expectation_met",
    }
    compared_fields = {
        "kind", "affected_rows", "command_tag", "rows",
        "error_code", "sqlstate", "transaction_status",
    }
    for index, (actual, expected) in enumerate(zip(actual_steps, expected_steps, strict=True)):
        if not isinstance(actual, dict) or set(actual) != emitted_step:
            raise MatrixError(f"{label}: step {index} fields must be {sorted(emitted_step)}")
        if not {"name", "kind"} <= set(expected) or set(expected) > compared_fields | {"name", "expected_error"}:
            raise MatrixError(f"{label}: oracle step {index} fields are invalid")
        # Case SQL files are shared across policies: the client's own
        # expectation flag (and our oracle's documentation copy of it) is
        # meaningless here — kind/error identity oracle fields are authoritative.
        skip = {"name", "expected_error"}
        comparable = {field: actual[field] for field in expected if field not in skip}
        if comparable != {field: expected[field] for field in expected if field not in skip}:
            raise MatrixError(f"{label}: step {actual['name']} mismatch")
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


AUDIT_LEVEL_RULES = {
    # level -> (sql_text_required_on_all_events, sample_required_on_row_events)
    "L0": (False, False),
    "L1": (True, False),
    "L2": (True, True),
}


def _verify_audit(
    label: str,
    level: str,
    audit_lines: list[str],
) -> list[dict[str, Any]]:
    if not audit_lines:
        raise MatrixError(f"{label}: audit evidence is empty for level {level}")
    events = []
    for line in audit_lines:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise MatrixError(f"{label}: malformed audit line: {error}") from error
    sql_required, sample_required = AUDIT_LEVEL_RULES[level]
    for event in events:
        # Deny decisions audit rule identity rather than SQL payload, so the
        # sql_text presence requirement applies to executed commands only.
        requires_sql = sql_required and event.get("decision") == "execute"
        if requires_sql and not event.get("sql_text"):
            raise MatrixError(f"{label}: {level} event lacks sql_text")
        if not sql_required and event.get("sql_text"):
            raise MatrixError(f"{label}: {level} event leaks sql_text")
        if event.get("sample_body") and level != "L2":
            raise MatrixError(f"{label}: {level} event leaks sample_body")
    row_events = [e for e in events if e.get("outcome") in ("resultset", "xproto_stream")]
    if sample_required and not any(e.get("sample_body") for e in row_events):
        raise MatrixError(f"{label}: {level} row events lack sample_body")
    return [{
        "decision": event.get("decision"),
        "outcome": event.get("outcome"),
        "has_sql_text": bool(event.get("sql_text")),
        "has_sample": bool(event.get("sample_body")),
    } for event in events]


def verify_path(
    selection: dict[str, Any],
    gateway_before: dict[str, Any],
    gateway_transcript: dict[str, Any],
    gateway_after: dict[str, Any],
    evidence_paths: dict[str, str],
    reproduction: str,
    audit_lines: list[str] | None = None,
) -> dict[str, Any]:
    case_id = selection["case_id"]
    policy = selection["policy"]
    label = f"{case_id}/{policy}"
    state_protocol = state_protocol_for(selection["backend"])

    before_rows = _verify_state(
        label, "gateway before", gateway_before, state_protocol, selection["before_state"],
    )
    steps = _verify_transcript(
        label, gateway_transcript, selection["client_protocol"], selection["gateway_steps"],
        selection_requires_single_connection=not selection.get("requires_ticket_orchestration", False),
    )
    after_rows = _verify_state(
        label, "gateway after", gateway_after, state_protocol, selection["after_state"],
    )
    error_steps = [step for step in steps if step["kind"] == "error"]
    if (
        selection["policy_enabled"]
        and error_steps
        and before_rows != after_rows
        and not selection.get("authorized_state_change")
    ):
        # Deny decisions must never reach the backend unless the oracle marks
        # the state change as authorized (e.g. an approved ticket DDL).
        raise MatrixError(f"{label}: denied policy mutated backend state")
    required_paths = {"gateway_before", "gateway_transcript", "gateway_after"}
    if set(evidence_paths) != required_paths or not all(
        isinstance(value, str) and value for value in evidence_paths.values()
    ):
        raise MatrixError(f"{label}: evidence path map is invalid")

    return {
        "case_id": case_id,
        "name": selection["name"],
        "policy": policy,
        "policy_enabled": selection["policy_enabled"],
        "protocol": selection["protocol"],
        "frontend": selection["frontend"],
        "backend": selection["backend"],
        "status": "passed",
        "step_transcript": {"gateway": steps},
        "state_evidence": {
            "paths": {
                "before": evidence_paths["gateway_before"],
                "transcript": evidence_paths["gateway_transcript"],
                "after": evidence_paths["gateway_after"],
            },
            "before_state": before_rows,
            "after_state": after_rows,
        },
        "denied_steps": [
            {
                "step": step["name"],
                "error_code": step["error_code"],
                "sqlstate": step["sqlstate"],
            }
            for step in error_steps
        ],
        "reproduction": reproduction,
    }
    if selection.get("audit_level"):
        result["audit_evidence"] = _verify_audit(
            f"{case_id}/{policy}", selection["audit_level"], audit_lines or [],
        )
    return result


def aggregate(
    selections: list[dict[str, Any]],
    results: list[dict[str, Any]],
    run_id: str,
    run_dir: str,
    filtered: bool,
) -> dict[str, Any]:
    expected = {(item["case_id"], item["policy"], item["protocol"]) for item in selections}
    actual = [
        (item.get("case_id"), item.get("policy"), item.get("protocol")) for item in results
    ]
    if len(actual) != len(set(actual)):
        raise MatrixError("duplicate governance result path")
    if set(actual) != expected:
        raise MatrixError("governance result paths do not match selection")
    if any(item.get("status") != "passed" for item in results):
        raise MatrixError("governance results contain a non-passed path")
    policies: dict[str, int] = {}
    protocols: dict[str, int] = {}
    for item in results:
        policies[item["policy"]] = policies.get(item["policy"], 0) + 1
        protocols[item["protocol"]] = protocols.get(item["protocol"], 0) + 1
    cases = len({item["case_id"] for item in results})
    complete = not filtered
    if complete and (len(results), cases) != (144, 6):
        raise MatrixError("formal SQLT-5 acceptance must be 144 paths: 6 cases x 12 policies x 2 protocols")
    expected_policies = {
        "audit_l0": 12, "audit_l1": 12, "audit_l2": 12,
        "column_strip_amount": 12, "deny_dml": 12, "deny_select_targets": 12,
        "mask_pii": 12, "max_rows_1": 12, "row_filter_tenant10": 12,
        "security_off": 12, "ticket_ddl": 12, "watermark_column": 12,
    }
    if complete and (policies != expected_policies or protocols != {
        "mysql_text_to_mysql": 72, "pg_simple_to_postgres": 72,
    }):
        raise MatrixError("formal SQLT-5 lane distribution mismatch")
    return {
        "suite": "SQLT-5",
        "run_id": run_id,
        "run_dir": run_dir,
        "acceptance_complete": complete,
        "paths": len(results),
        "cases": cases,
        "policies": dict(sorted(policies.items())),
        "protocols": dict(sorted(protocols.items())),
        "passed": len(results),
        "failed": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--selection", type=Path, required=True)
    compare.add_argument("--gateway-before", type=Path, required=True)
    compare.add_argument("--gateway-transcript", type=Path, required=True)
    compare.add_argument("--gateway-after", type=Path, required=True)
    compare.add_argument("--audit-evidence", type=Path)
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
                load(args.selection),
                load(args.gateway_before),
                load(args.gateway_transcript),
                load(args.gateway_after),
                {
                    "gateway_before": str(args.gateway_before),
                    "gateway_transcript": str(args.gateway_transcript),
                    "gateway_after": str(args.gateway_after),
                },
                args.reproduction,
                [
                    line
                    for line in (
                        args.audit_evidence.read_text(encoding="utf-8").splitlines()
                        if args.audit_evidence and args.audit_evidence.is_file()
                        else []
                    )
                    if line
                ],
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
