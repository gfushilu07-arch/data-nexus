#!/usr/bin/env python3
"""Run one PostgreSQL simple-query cursor script on a raw v3 socket."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from extended_client import PgWire, cstr, i32, message


class CursorStep:
    def __init__(self, name: str, sql: str, action: str | None = None):
        self.name = name
        self.sql = sql.strip()
        self.action = action


def read_steps(path: Path) -> list[CursorStep]:
    lines = path.read_text(encoding="utf-8").splitlines()[4:]
    steps: list[CursorStep] = []
    name: str | None = None
    body: list[str] = []
    action: str | None = None

    def flush() -> None:
        nonlocal name, body, action
        sql = "\n".join(body).strip()
        if name is not None and sql:
            steps.append(CursorStep(name, sql, action))
        name, body, action = None, [], None

    for line in lines:
        if line.startswith("-- @step "):
            flush()
            name = line.removeprefix("-- @step ").strip()
        elif line.startswith("-- @action "):
            action = line.removeprefix("-- @action ").strip()
        elif name is not None:
            body.append(line)
    flush()
    return steps


def query(wire: PgWire, sql: str) -> list[dict[str, Any]]:
    wire.send(message(b"Q", cstr(sql)))
    return wire.receive_until({b"Z"})


def query_cleanup(wire: PgWire, sql: str, attempts: int = 50) -> tuple[list[dict[str, Any]], int]:
    latest: list[dict[str, Any]] = []
    for attempt in range(1, attempts + 1):
        latest = query(wire, sql)
        summary = event_summary(latest)
        if summary["rows"] == [["0"]]:
            return latest, attempt
        time.sleep(0.1)
    return latest, attempts


def event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "tags": [event["tag"] for event in events],
        "rows": [event["row"] for event in events if event["tag"] == "DataRow"],
        "commands": [event["command"] for event in events if event["tag"] == "CommandComplete"],
        "ready": [event["status"] for event in events if event["tag"] == "ReadyForQuery"],
        "errors": [
            {key: event[key] for key in ("sqlstate", "severity", "message") if key in event}
            for event in events
            if event["tag"] == "ErrorResponse"
        ],
    }
    descriptions = [event.get("columns", []) for event in events if event["tag"] == "RowDescription"]
    if descriptions:
        summary["columns"] = descriptions[-1]
    return summary


def compare_step(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    if expected.get("eof"):
        if not actual.get("eof"):
            raise AssertionError(f"{actual['name']}: expected EOF")
        return
    if actual.get("eof"):
        raise AssertionError(f"{actual['name']}: unexpected EOF")
    if "rows" in expected and actual.get("rows") != expected["rows"]:
        raise AssertionError(f"{actual['name']}: rows {actual.get('rows')!r} != {expected['rows']!r}")
    for field in ("commands", "ready"):
        if field in expected and actual.get(field) != expected[field]:
            raise AssertionError(f"{actual['name']}: {field} mismatch")
    if "sqlstates" in expected:
        actual_states = [error.get("sqlstate") for error in actual.get("errors", [])]
        if actual_states != expected["sqlstates"]:
            raise AssertionError(f"{actual['name']}: SQLSTATE {actual_states!r} != {expected['sqlstates']!r}")
    if "control_rows" in expected and actual.get("control", {}).get("rows") != expected["control_rows"]:
        raise AssertionError(f"{actual['name']}: control rows mismatch")


def reconnect(args: argparse.Namespace) -> PgWire:
    return PgWire(args.host, args.port, args.user, args.password, args.database)


def control_terminate(args: argparse.Namespace, backend_pid: str) -> dict[str, Any]:
    control = reconnect(args)
    try:
        events = query(control, f"SELECT pg_terminate_backend({int(backend_pid)});")
        return event_summary(events)
    finally:
        control.close()


def run_case(args: argparse.Namespace, steps: list[CursorStep]) -> dict[str, Any]:
    wire = reconnect(args)
    results: list[dict[str, Any]] = []
    backend_pid: str | None = None
    disconnect_after = args.disconnect_after
    try:
        for step in steps:
            if step.action == "backend_terminate":
                if backend_pid is None:
                    raise RuntimeError("backend_terminate requires a prior backend pid row")
                results.append({"name": step.name, "action": step.action,
                                "control": control_terminate(args, backend_pid)})
                continue

            try:
                if step.name == "cleanup_probe":
                    events, attempts = query_cleanup(wire, step.sql)
                else:
                    events, attempts = query(wire, step.sql), 1
                summary = event_summary(events)
                result = {"name": step.name, **summary}
                if step.name == "cleanup_probe":
                    result["attempts"] = attempts
                if step.name == "fetch_backend_pid" and summary["rows"]:
                    backend_pid = summary["rows"][0][0]
                results.append(result)
            except (OSError, RuntimeError) as exc:
                results.append({"name": step.name, "eof": True, "error": str(exc)})
                wire.close()
                wire = reconnect(args)

            if disconnect_after and step.name == disconnect_after:
                if args.disconnect_mode == "terminate":
                    wire.send(message(b"X"))
                wire.close()
                wire = reconnect(args)
        return {"case_id": args.case_id, "steps": results}
    finally:
        wire.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    parser.add_argument("--disconnect-after")
    parser.add_argument("--disconnect-mode", choices=("terminate", "eof"), default="eof")
    parser.add_argument("--oracle", type=Path)
    args = parser.parse_args()
    result = run_case(args, read_steps(args.sql))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")), flush=True)
    if args.oracle:
        oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
        if "results" in oracle:
            oracle = oracle["results"][args.case_id]
        expected_steps = oracle["steps"]
        actual_steps = {step["name"]: step for step in result["steps"]}
        if set(actual_steps) != set(expected_steps):
            raise AssertionError(f"step set mismatch: {sorted(actual_steps)} != {sorted(expected_steps)}")
        for name, expected in expected_steps.items():
            actual = actual_steps[name]
            if name == "fetch_backend_pid" and expected.get("rows") == [["$PID", "101"]]:
                expected = {**expected, "rows": [[actual["rows"][0][0], "101"]]}
            compare_step(actual, expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
