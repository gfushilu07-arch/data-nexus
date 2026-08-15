#!/usr/bin/env python3
"""Execute one SQLT-4B2 step script on a single MySQL or PostgreSQL connection."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple


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
                raise ValueError(f"{path}: step {name} has no SQL")
            steps.append(Step(name, sql, expected_error))
        name, body, expected_error = None, [], False

    for line in lines:
        if line.startswith("-- @step "):
            flush()
            name = line.removeprefix("-- @step ").strip()
        elif line == "-- @expect error":
            if name is None or body:
                raise ValueError(f"{path}: @expect error must immediately follow @step")
            expected_error = True
        elif name is not None:
            body.append(line)
    flush()
    if not steps or len({step.name for step in steps}) != len(steps):
        raise ValueError(f"{path}: step names must be non-empty and unique")
    return steps


def normalize_cell(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, (dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def normalized_rows(rows: list[Any]) -> list[list[str | None]]:
    return [[normalize_cell(value) for value in row] for row in rows]


def mysql_status(connection: Any) -> str:
    return "T" if connection.in_transaction else "I"


def run_mysql(args: argparse.Namespace, steps: list[Step]) -> dict[str, Any]:
    from mysql.connector.connection import MySQLConnection

    class ScriptConnection(MySQLConnection):
        def _post_connection(self) -> None:
            self._autocommit = True

    connection = ScriptConnection(
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
    results: list[dict[str, Any]] = []
    try:
        for step in steps:
            cursor = connection.cursor()
            try:
                cursor.execute(step.sql)
                if cursor.with_rows:
                    value = {
                        "name": step.name,
                        "expected_error": step.expected_error,
                        "kind": "rows",
                        "affected_rows": None,
                        "command_tag": None,
                        "rows": normalized_rows(cursor.fetchall()),
                        "error_code": None,
                        "sqlstate": None,
                        "transaction_status": mysql_status(connection),
                    }
                else:
                    value = {
                        "name": step.name,
                        "expected_error": step.expected_error,
                        "kind": "ok",
                        "affected_rows": max(int(cursor.rowcount), 0),
                        "command_tag": None,
                        "rows": [],
                        "error_code": None,
                        "sqlstate": None,
                        "transaction_status": mysql_status(connection),
                    }
            except Exception as error:
                error_number = getattr(error, "errno", None)
                value = {
                    "name": step.name,
                    "expected_error": step.expected_error,
                    "kind": "error",
                    "affected_rows": None,
                    "command_tag": None,
                    "rows": [],
                    "error_code": str(error_number) if error_number is not None else None,
                    "sqlstate": getattr(error, "sqlstate", None),
                    "transaction_status": mysql_status(connection),
                }
            finally:
                cursor.close()
            value["expectation_met"] = (value["kind"] == "error") == step.expected_error
            results.append(value)
    finally:
        connection.close()
    return {"protocol": "mysql_text", "connection": "same", "steps": results}


def pg_affected(command: str | None) -> int | None:
    if command is None:
        return None
    fields = command.split()
    if fields[0] == "OK" and len(fields) == 2 and fields[1].isdigit():
        return int(fields[1])
    if fields[0] in {"UPDATE", "DELETE"} and fields[-1].isdigit():
        return int(fields[-1])
    if fields[0] == "INSERT" and fields[-1].isdigit():
        return int(fields[-1])
    if fields[0] in {"BEGIN", "COMMIT", "ROLLBACK"}:
        return 0
    return None


def run_postgres(args: argparse.Namespace, steps: list[Step]) -> dict[str, Any]:
    from extended_client import PgWire, cstr, message

    wire = PgWire(args.host, args.port, args.user, args.password, args.database)
    results: list[dict[str, Any]] = []
    try:
        for step in steps:
            wire.send(message(b"Q", cstr(step.sql)))
            events = wire.receive_until({b"Z"})
            errors = [event for event in events if event["tag"] == "ErrorResponse"]
            commands = [event["command"] for event in events if event["tag"] == "CommandComplete"]
            rows = [event["row"] for event in events if event["tag"] == "DataRow"]
            ready = [event["status"] for event in events if event["tag"] == "ReadyForQuery"]
            command = commands[-1] if commands else None
            if errors:
                error = errors[-1]
                value = {
                    "kind": "error",
                    "affected_rows": None,
                    "command_tag": None,
                    "rows": [],
                    "error_code": None,
                    "sqlstate": error.get("sqlstate"),
                }
            elif rows:
                value = {
                    "kind": "rows",
                    "affected_rows": None,
                    "command_tag": command,
                    "rows": rows,
                    "error_code": None,
                    "sqlstate": None,
                }
            else:
                value = {
                    "kind": "ok",
                    "affected_rows": pg_affected(command),
                    "command_tag": command,
                    "rows": [],
                    "error_code": None,
                    "sqlstate": None,
                }
            value.update({
                "name": step.name,
                "expected_error": step.expected_error,
                "transaction_status": ready[-1] if ready else None,
            })
            value["expectation_met"] = (value["kind"] == "error") == step.expected_error
            results.append(value)
    finally:
        wire.close()
    return {"protocol": "pg_simple", "connection": "same", "steps": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=("mysql_text", "pg_simple"), required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    args = parser.parse_args()
    steps = read_steps(args.sql)
    result = run_mysql(args, steps) if args.protocol == "mysql_text" else run_postgres(args, steps)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if all(step["expectation_met"] for step in result["steps"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
