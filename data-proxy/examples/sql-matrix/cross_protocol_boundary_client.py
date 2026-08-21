#!/usr/bin/env python3
"""Execute one SQLT-4B3 cross-protocol prepared boundary case on one connection.

The MySQL lane drives real binary prepared statements (COM_STMT_PREPARE /
COM_STMT_EXECUTE / COM_STMT_CLOSE). The PostgreSQL lane drives a raw v3
extended-query wire (Parse / Bind / Describe / Execute / Close / Sync). Step
expectations come from cross-protocol-boundary-oracles.json keyed by direction.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


def read_steps(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()[4:]
    steps: dict[str, list[str]] = {}
    name: str | None = None
    for line in lines:
        if line.startswith("-- @step "):
            name = line.removeprefix("-- @step ").strip()
            steps[name] = []
        elif name is not None:
            steps[name].append(line)
    return {key: "\n".join(body).strip() for key, body in steps.items() if "\n".join(body).strip()}


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex().upper()}
    return str(value)


def expand_parameter(value: Any) -> Any:
    if isinstance(value, dict) and "decimal" in value:
        return Decimal(value["decimal"])
    if isinstance(value, dict) and "datetime" in value:
        return dt.datetime.fromisoformat(value["datetime"])
    return value


def expanded_parameters(values: list[Any]) -> tuple[Any, ...]:
    return tuple(expand_parameter(value) for value in values)


def base_step(name: str, expected_error: bool) -> dict[str, Any]:
    return {
        "name": name,
        "expected_error": expected_error,
        "kind": "ok",
        "rows": [],
        "columns": None,
        "affected_rows": None,
        "command_tag": None,
        "transaction_status": None,
        "error_code": None,
        "sqlstate": None,
        "classification": None,
        "wire": None,
    }


def classify_message_error(message: str) -> str:
    lowered = message.lower()
    if "translation policy" in lowered:
        return "translation_error"
    if "expects" in lowered and "parameters" in lowered:
        return "gateway_error"
    return "backend_error"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=("mysql_binary", "pg_extended"), required=True)
    parser.add_argument("--direction", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    args = parser.parse_args()

    steps_sql = read_steps(args.sql)
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    lane = oracle["results"][args.case_id][args.direction]
    expectations = {step["name"]: step for step in lane["steps"]}
    parameters = {
        name: [str(value) if isinstance(value, (int, float)) else value for value in values]
        for name, values in lane.get("parameters", {}).items()
    }

    if args.protocol == "mysql_binary":
        result = run_mysql(args, steps_sql, expectations, parameters)
    else:
        result = run_postgres(args, steps_sql, expectations, parameters)

    steps = result["steps"]
    for step in steps:
        expected = expectations.get(step["name"])
        if expected is not None:
            step["expected_error"] = expected["expected_error"]
        step["expectation_met"] = (step["kind"] == "error") == step["expected_error"]
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if all(step["expectation_met"] for step in steps) else 1


def run_mysql(
    args: argparse.Namespace,
    steps_sql: dict[str, str],
    expectations: dict[str, dict[str, Any]],
    parameters: dict[str, list[Any]],
) -> dict[str, Any]:
    import mysql.connector
    from mysql.connector import Error, errors

    def record(name: str, action) -> dict[str, Any]:
        expected = expectations.get(name, {})
        step = base_step(name, bool(expected.get("expected_error")))
        try:
            action(step)
        except Error as error:
            step["kind"] = "error"
            errno = getattr(error, "errno", None)
            step["error_code"] = str(errno) if errno is not None else None
            step["sqlstate"] = getattr(error, "sqlstate", None)
            message = getattr(error, "msg", None) or str(error)
            if errno is None and isinstance(error, errors.InterfaceError):
                step["classification"] = "client_closed_statement"
            else:
                step["classification"] = classify_message_error(message)
        return step

    connection = mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        ssl_disabled=True,
        connection_timeout=15,
        autocommit=True,
        use_pure=True,
    )
    steps: list[dict[str, Any]] = []
    cursor = connection.cursor(prepared=True)

    def prepared_execute(sql: str, params: list[Any]):
        def action(step: dict[str, Any]) -> None:
            cursor.execute(sql, expanded_parameters(params))
            rows = cursor.fetchall()
            step["columns"] = [item[0] for item in (cursor.description or [])] or None
            if cursor.with_rows:
                step["kind"] = "rows"
                step["rows"] = [[normalize(value) for value in row] for row in rows]
            else:
                step["kind"] = "ok"
                step["affected_rows"] = max(int(cursor.rowcount), 0)
            step["transaction_status"] = "T" if connection.in_transaction else "I"
        return action

    def text_execute(sql: str):
        def action(step: dict[str, Any]) -> None:
            text_cursor = connection.cursor()
            try:
                text_cursor.execute(sql)
                rows = text_cursor.fetchall()
                if text_cursor.with_rows:
                    step["kind"] = "rows"
                    step["rows"] = [[normalize(value) for value in row] for row in rows]
                else:
                    step["affected_rows"] = max(int(text_cursor.rowcount), 0)
            finally:
                text_cursor.close()
            step["transaction_status"] = "T" if connection.in_transaction else "I"
        return action

    case = args.case_id
    try:
        if case == "SQLT-XBND-001":
            steps.append(record("select", prepared_execute(steps_sql["select"], [])))
            cursor.close()
            steps.append(record("canary", text_execute(steps_sql["canary"])))
        elif case == "SQLT-XBND-002":
            steps.append(record("select", prepared_execute(steps_sql["select"], parameters["select"])))
            cursor.close()
            steps.append(record("canary", text_execute(steps_sql["canary"])))
        elif case in {"SQLT-XBND-003", "SQLT-XBND-004"}:
            steps.append(record("select", prepared_execute(steps_sql["select"], parameters["select"])))
        elif case == "SQLT-XBND-005":
            for name in ("execute_tenant_10", "execute_tenant_20", "execute_tenant_10_again"):
                steps.append(record(name, prepared_execute(steps_sql["select"], parameters[name])))
        elif case == "SQLT-XBND-006":
            steps.append(record("execute_paid", prepared_execute(steps_sql["select"], parameters["execute_paid"])))
            cursor.close()
            steps.append(record("close", lambda step: step.update(kind="closed")))
            cursor = connection.cursor(prepared=True)
            steps.append(record(
                "execute_refunded_after_recreate",
                prepared_execute(steps_sql["select"], parameters["execute_refunded_after_recreate"]),
            ))
        elif case == "SQLT-XBND-007":
            steps.append(record("execute", prepared_execute(steps_sql["select"], parameters["execute"])))
        elif case == "SQLT-XBND-008":
            for name, action in (
                ("begin", text_execute(steps_sql["begin"])),
                ("insert", prepared_execute(steps_sql["insert"], parameters["insert"])),
                ("commit", text_execute(steps_sql["commit"])),
                ("verify", prepared_execute(steps_sql["verify"], parameters["verify"])),
                ("begin_rollback", text_execute(steps_sql["begin_rollback"])),
                ("update", prepared_execute(steps_sql["update"], parameters["update"])),
                ("rollback", text_execute(steps_sql["rollback"])),
                ("verify_rollback", prepared_execute(steps_sql["verify_rollback"], parameters["verify_rollback"])),
            ):
                steps.append(record(name, action))
        elif case in {"SQLT-XBND-009", "SQLT-XBND-010", "SQLT-XBND-011"}:
            key = {"SQLT-XBND-009": "ddl", "SQLT-XBND-010": "vendor", "SQLT-XBND-011": "call"}[case]
            steps.append(record(key, prepared_execute(steps_sql[key], [])))
            steps.append(record("canary", text_execute(steps_sql["canary"])))
        elif case == "SQLT-XBND-012":
            steps.append(record("missing_binding", prepared_execute(steps_sql["select"], [])))
            steps.append(record("recovered", prepared_execute(steps_sql["select"], parameters["recovered"])))
        elif case == "SQLT-XBND-013":
            steps.append(record("execute", prepared_execute(steps_sql["select"], [])))
            cursor.close()
            steps.append(record("closed_reuse", prepared_execute(steps_sql["select"], [])))
            cursor = connection.cursor(prepared=True)
            steps.append(record("recovered", prepared_execute(steps_sql["select"], [])))
        else:
            raise ValueError(f"unsupported boundary case: {case}")
    finally:
        try:
            cursor.close()
        except Error:
            pass
        connection.close()
    return {"protocol": "mysql_binary", "case_id": args.case_id, "direction": args.direction, "steps": steps}


TAG_CHAR = {
    b"1": "1", b"2": "2", b"3": "3", b"C": "C", b"D": "D", b"E": "E",
    b"n": "n", b"s": "s", b"T": "T", b"t": "t", b"Z": "Z",
}


def run_postgres(
    args: argparse.Namespace,
    steps_sql: dict[str, str],
    expectations: dict[str, dict[str, Any]],
    parameters: dict[str, list[Any]],
) -> dict[str, Any]:
    from extended_client import PgWire, bind, close, describe, execute, message, parse

    wire = PgWire(args.host, args.port, args.user, args.password, args.database)

    def to_text(values: list[Any]) -> list[str | None]:
        return [None if value is None else str(expand_parameter(value)) for value in values]

    def summarize(events: list[dict[str, Any]], step: dict[str, Any]) -> None:
        chars = [TAG_CHAR.get(event["tag"].encode("latin1", "replace"), "?") for event in events]
        step["wire"] = " ".join(chars)
        errors = [event for event in events if event["tag"] == "ErrorResponse"]
        commands = [event["command"] for event in events if event["tag"] == "CommandComplete"]
        rows = [event["row"] for event in events if event["tag"] == "DataRow"]
        ready = [event["status"] for event in events if event["tag"] == "ReadyForQuery"]
        described = [event["columns"] for event in events if event["tag"] == "RowDescription"]
        if ready:
            step["transaction_status"] = ready[-1]
        if errors:
            error = errors[-1]
            step["kind"] = "error"
            step["sqlstate"] = error.get("sqlstate")
            message = error.get("message", "")
            if error.get("sqlstate") == "08P01":
                step["classification"] = "unknown_statement"
            else:
                step["classification"] = classify_message_error(message)
        elif rows:
            step["kind"] = "rows"
            step["rows"] = rows
            if commands:
                step["command_tag"] = commands[-1]
        elif described:
            step["kind"] = "describe"
            step["columns"] = [column["name"] for column in described[-1]]
        else:
            step["kind"] = "ok"
            if commands:
                step["command_tag"] = commands[-1]

    def unit(statement: str, sql: str, params: list[Any], formats: list[int] | None = None):
        def action(step: dict[str, Any]) -> None:
            frames = [parse(statement, sql), bind("", statement, to_text(params), formats), execute("")]
            wire.send(*frames, message(b"S"))
            summarize(wire.receive_until({b"Z"}), step)
        return action

    def rebind(statement: str, params: list[Any]):
        def action(step: dict[str, Any]) -> None:
            wire.send(bind("", statement, to_text(params)), execute(""), message(b"S"))
            summarize(wire.receive_until({b"Z"}), step)
        return action

    def simple(sql: str):
        def action(step: dict[str, Any]) -> None:
            wire.send(message(b"Q", sql.encode()))
            summarize(wire.receive_until({b"Z"}), step)
        return action

    def record(name: str, action) -> dict[str, Any]:
        expected = expectations.get(name, {})
        step = base_step(name, bool(expected.get("expected_error")))
        action(step)
        return step

    case = args.case_id
    steps: list[dict[str, Any]] = []
    try:
        if case == "SQLT-XBND-001":
            steps.append(record("select", unit("s1", steps_sql["select"], [])))
            steps.append(record("canary", unit("s2", steps_sql["canary"], [])))
        elif case == "SQLT-XBND-002":
            steps.append(record("select", unit("s1", steps_sql["select"], parameters["select"])))
            steps.append(record("canary", unit("s2", steps_sql["canary"], [])))
        elif case in {"SQLT-XBND-003", "SQLT-XBND-004"}:
            steps.append(record("select", unit("s1", steps_sql["select"], parameters["select"])))
        elif case == "SQLT-XBND-005":
            steps.append(record("execute_tenant_10", unit("s1", steps_sql["select"], parameters["execute_tenant_10"])))
            steps.append(record("execute_tenant_20", rebind("s1", parameters["execute_tenant_20"])))
            steps.append(record("execute_tenant_10_again", rebind("s1", parameters["execute_tenant_10_again"])))
        elif case == "SQLT-XBND-006":
            steps.append(record("execute_paid", unit("s1", steps_sql["select"], parameters["execute_paid"])))
            def close_action(step: dict[str, Any]) -> None:
                wire.send(close("S", "s1"), message(b"S"))
                summarize(wire.receive_until({b"Z"}), step)
                step["kind"] = "closed"
            steps.append(record("close", close_action))
            steps.append(record(
                "execute_refunded_after_recreate",
                unit("s1", steps_sql["select"], parameters["execute_refunded_after_recreate"]),
            ))
        elif case == "SQLT-XBND-007":
            def describe_action(step: dict[str, Any]) -> None:
                wire.send(parse("s1", steps_sql["select"]), describe("S", "s1"), message(b"S"))
                summarize(wire.receive_until({b"Z"}), step)
                step["kind"] = "describe"
            steps.append(record("describe", describe_action))
            # Binary result format for target_id only; text for the other columns.
            if wire.columns:
                wire.columns[0]["format_code"] = 1
            steps.append(record("execute", rebind("s1", parameters["execute"])))
        elif case == "SQLT-XBND-008":
            for name, action in (
                ("begin", simple(steps_sql["begin"])),
                ("insert", unit("ins", steps_sql["insert"], parameters["insert"])),
                ("commit", simple(steps_sql["commit"])),
                ("verify", unit("ver", steps_sql["verify"], parameters["verify"])),
                ("begin_rollback", simple(steps_sql["begin_rollback"])),
                ("update", unit("upd", steps_sql["update"], parameters["update"])),
                ("rollback", simple(steps_sql["rollback"])),
                ("verify_rollback", unit("vrb", steps_sql["verify_rollback"], parameters["verify_rollback"])),
            ):
                steps.append(record(name, action))
        elif case in {"SQLT-XBND-009", "SQLT-XBND-010", "SQLT-XBND-011"}:
            key = {"SQLT-XBND-009": "ddl", "SQLT-XBND-010": "vendor", "SQLT-XBND-011": "call"}[case]
            steps.append(record(key, unit("s1", steps_sql[key], [])))
            steps.append(record("canary", unit("s2", steps_sql["canary"], [])))
        elif case == "SQLT-XBND-012":
            steps.append(record("gap", unit("s1", steps_sql["gap"], parameters["gap"])))
            steps.append(record("recovered", unit("s2", steps_sql["recovered"], parameters["recovered"])))
        elif case == "SQLT-XBND-013":
            steps.append(record("execute", unit("s1", steps_sql["select"], [])))
            def closed_reuse(step: dict[str, Any]) -> None:
                events: list[dict[str, Any]] = []
                wire.send(close("S", "s1"), message(b"S"))
                events.extend(wire.receive_until({b"Z"}))  # CloseComplete + ReadyForQuery
                wire.send(bind("", "s1", []))
                events.extend(wire.receive_until({b"E"}))  # ErrorResponse: unknown statement
                wire.send(message(b"S"))
                events.extend(wire.receive_until({b"Z"}))
                summarize(events, step)
                step["kind"] = "error"
            steps.append(record("closed_reuse", closed_reuse))
            steps.append(record("recovered", unit("s1", steps_sql["select"], [])))
        else:
            raise ValueError(f"unsupported boundary case: {case}")
    finally:
        wire.close()
    return {"protocol": "pg_extended", "case_id": args.case_id, "direction": args.direction, "steps": steps}


if __name__ == "__main__":
    raise SystemExit(main())
