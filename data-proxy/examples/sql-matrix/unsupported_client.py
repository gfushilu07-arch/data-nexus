#!/usr/bin/env python3
"""Run one SQLT-3F3 unsupported case without persisting sensitive SQL text."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extended_client import PgWire, cstr, message


STEP_RE = re.compile(r"^-- @step ([a-z][a-z0-9_]*) (mysql|postgres)$", re.MULTILINE)
CAPABILITY_RE = re.compile(r"unsupported capability: ([a-z0-9_.]+)")


def sql_steps(path: Path, dialect: str) -> list[tuple[str, str]]:
    body = "\n".join(path.read_text(encoding="utf-8").splitlines()[4:]).strip()
    matches = list(STEP_RE.finditer(body))
    if not matches:
        return [("main", body)]

    if body[: matches[0].start()].strip():
        raise ValueError("SQL before the first @step is not allowed")
    steps: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sql = body[match.end() : end].strip()
        if match.group(2) == dialect:
            if not sql:
                raise ValueError(f"empty SQL step: {match.group(1)}")
            steps.append((match.group(1), sql))
    if not steps:
        raise ValueError(f"no SQL steps for dialect {dialect}")
    return steps


def capability(message_text: str | None) -> str | None:
    match = CAPABILITY_RE.search(message_text or "")
    return match.group(1) if match else None


def normalize_rows(rows: list[Any]) -> list[list[str | None]]:
    return [
        [None if value is None else value.decode().hex() if isinstance(value, bytes) else str(value) for value in row]
        for row in rows
    ]


def mysql_connect(args: argparse.Namespace) -> Any:
    import mysql.connector

    return mysql.connector.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        ssl_disabled=args.path == "gateway",
        ssl_verify_cert=False,
        ssl_verify_identity=False,
        connection_timeout=15,
        autocommit=True,
        use_pure=True,
    )


def mysql_step(connection: Any, name: str, sql: str) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        try:
            cursor.execute(sql)
            rows = normalize_rows(cursor.fetchall()) if cursor.with_rows else []
            return {
                "name": name,
                "result": "success",
                "rows": rows,
                "affected_rows": max(cursor.rowcount, 0),
            }
        except BaseException as exc:
            return {
                "name": name,
                "result": "error",
                "error": {
                    "vendor": "mysql",
                    "code": getattr(exc, "errno", None),
                    "sqlstate": getattr(exc, "sqlstate", None),
                    "capability": capability(getattr(exc, "msg", None)),
                },
            }
    finally:
        cursor.close()


def mysql_session_state(connection: Any) -> list[list[str | None]]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT CURRENT_USER(), DATABASE(), @@session.sql_mode, "
            "@@session.time_zone, @@session.autocommit"
        )
        return normalize_rows(cursor.fetchall())
    finally:
        cursor.close()


def run_mysql(args: argparse.Namespace, steps: list[tuple[str, str]]) -> dict[str, Any]:
    connection = mysql_connect(args)
    try:
        before = mysql_session_state(connection)
        results = [mysql_step(connection, name, sql) for name, sql in steps]
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 42")
            recovery = normalize_rows(cursor.fetchall())
        finally:
            cursor.close()
        return {
            "steps": results,
            "recovery_rows": recovery,
            "session_before": before,
            "session_after": mysql_session_state(connection),
            "connection": "same",
        }
    finally:
        connection.close()


def pg_query(wire: PgWire, sql: str) -> list[dict[str, Any]]:
    wire.send(message(b"Q", cstr(sql)))
    return wire.receive_until({b"Z"})


def pg_step(wire: PgWire, name: str, sql: str) -> dict[str, Any]:
    events = pg_query(wire, sql)
    errors = [event for event in events if event["tag"] == "ErrorResponse"]
    ready = [event["status"] for event in events if event["tag"] == "ReadyForQuery"]
    if errors:
        error = errors[0]
        return {
            "name": name,
            "result": "error",
            "error": {
                "vendor": "postgres",
                "code": error.get("sqlstate"),
                "capability": capability(error.get("message")),
            },
            "ready": ready,
        }
    return {
        "name": name,
        "result": "success",
        "rows": [event["row"] for event in events if event["tag"] == "DataRow"],
        "commands": [event["command"] for event in events if event["tag"] == "CommandComplete"],
        "ready": ready,
    }


def pg_rows(wire: PgWire, sql: str) -> list[list[str | None]]:
    return [event["row"] for event in pg_query(wire, sql) if event["tag"] == "DataRow"]


def run_postgres(args: argparse.Namespace, steps: list[tuple[str, str]]) -> dict[str, Any]:
    wire = PgWire(args.host, args.port, args.user, args.password, args.database)
    try:
        session_query = (
            "SELECT current_user, current_role, current_database(), "
            "current_setting('work_mem'), current_setting('search_path')"
        )
        before = pg_rows(wire, session_query)
        results = [pg_step(wire, name, sql) for name, sql in steps]
        recovery = pg_rows(wire, "SELECT 42")
        return {
            "steps": results,
            "recovery_rows": recovery,
            "session_before": before,
            "session_after": pg_rows(wire, session_query),
            "connection": "same",
        }
    finally:
        wire.close()


def run(args: argparse.Namespace) -> dict[str, Any]:
    steps = sql_steps(args.sql, args.dialect)
    semantic = run_mysql(args, steps) if args.dialect == "mysql" else run_postgres(args, steps)
    return {
        "case_id": args.case_id,
        "dialect": args.dialect,
        "path": args.path,
        "semantic": semantic,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--dialect", choices=("mysql", "postgres"), required=True)
    parser.add_argument("--path", choices=("direct", "gateway"), required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    args = parser.parse_args()
    print(json.dumps(run(args), sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
