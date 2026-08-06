#!/usr/bin/env python3
"""Run one SQLT-3F2 protocol, lexical, or resource boundary case."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import struct
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extended_client import PgWire, bind, cstr, execute, message, parse


PAYLOAD = "quote=' backslash=\\ semicolon=; line=-- block=/* */ sql=SELECT 9918"


def sql_body(path: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[4:]).strip()


def statement_for_dialect(path: Path, dialect: str) -> str:
    body = sql_body(path)
    marker = re.compile(r"^-- @statement (mysql|postgres)$", re.MULTILINE)
    matches = list(marker.finditer(body))
    if not matches:
        return "\n".join(line for line in body.splitlines() if not line.startswith("-- @generate ")).strip()
    statements: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        statements[match.group(1)] = body[match.end():end].strip()
    return statements[dialect]


def generation(path: Path) -> dict[str, int]:
    for line in path.read_text(encoding="utf-8").splitlines()[4:]:
        if line.startswith("-- @generate "):
            values: dict[str, int] = {}
            for field in line.removeprefix("-- @generate ").split():
                key, value = field.split("=", 1)
                values[key] = int(value)
            return values
    return {}


def generated_nested_sql(nesting: int, in_items: int) -> str:
    if not 1 <= nesting <= 128 or not 1 <= in_items <= 4096:
        raise ValueError("generated nesting or IN-list size exceeds fixed SQLT-3F2 limit")
    expression = "1 IN (" + ",".join(str(value) for value in range(in_items)) + ")"
    return "SELECT " + "(" * nesting + expression + ")" * nesting + " AS generated_boundary;"


def generated_query_frame(total_bytes: int) -> bytes:
    if not 64 <= total_bytes <= 16 * 1024 * 1024 + 1:
        raise ValueError("generated PostgreSQL message exceeds fixed SQLT-3F2 bounds")
    prefix = b"SELECT 1 /*"
    suffix = b"*/;"
    sql_length = total_bytes - 6
    padding = sql_length - len(prefix) - len(suffix)
    if padding < 0:
        raise ValueError("message size is too small for generated SQL")
    sql = prefix + b"x" * padding + suffix
    frame = b"Q" + struct.pack("!i", len(sql) + 5) + sql + b"\0"
    if len(frame) != total_bytes:
        raise AssertionError(f"generated frame is {len(frame)} bytes, expected {total_bytes}")
    return frame


def compact_pg(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": [event["row"] for event in events if event["tag"] == "DataRow"],
        "errors": [f"postgres\t{event['sqlstate']}" for event in events if event["tag"] == "ErrorResponse"],
        "ready": [event["status"] for event in events if event["tag"] == "ReadyForQuery"],
        "commands": [event["command"] for event in events if event["tag"] == "CommandComplete"],
    }


def pg_query(wire: PgWire, sql: str) -> list[dict[str, Any]]:
    wire.send(message(b"Q", cstr(sql)))
    return wire.receive_until({b"Z"})


def pg_connect(args: argparse.Namespace) -> PgWire:
    return PgWire(args.host, args.port, args.user, args.password, args.database)


def mysql_connect(args: argparse.Namespace):
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


def mysql_error(exc: BaseException) -> str:
    errno = getattr(exc, "errno", None)
    sqlstate = getattr(exc, "sqlstate", None)
    return f"mysql\t{errno}\t{sqlstate}"


def mysql_query(connection: Any, sql: str, params: tuple[Any, ...] = (), prepared: bool = False) -> list[list[Any]]:
    cursor = connection.cursor(prepared=prepared)
    try:
        cursor.execute(sql, params)
        return [[value.decode() if isinstance(value, bytes) else value for value in row] for row in cursor.fetchall()]
    finally:
        cursor.close()


def consume_mysql_raw(connection: Any, packet: bytes) -> list[list[Any]]:
    result = connection._handle_binary_result(packet)
    if isinstance(result, dict):
        return []
    _, columns, _ = result
    rows, _ = connection.get_rows(binary=True, columns=columns)
    return [[value.decode() if isinstance(value, bytes) else value for value in row] for row in rows]


def mysql_execute_body(statement_id: int, kind: str) -> bytes:
    header = struct.pack("<IBI", statement_id, 0, 1)
    if kind == "missing":
        return header
    if kind == "extra":
        return header + b"\0\1" + b"\x03\0\x03\0" + struct.pack("<ii", 41, 99)
    if kind == "invalid_type":
        return header + b"\0\1" + b"\x29\0" + struct.pack("<i", 41)
    raise ValueError(f"unknown mysql malformed execute kind {kind}")


def run_mysql_bind(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    from mysql.connector.constants import ServerCmd
    from mysql.connector.errors import get_exception

    connection = mysql_connect(args)
    malformed: list[dict[str, Any]] = []
    try:
        prepared = connection.cmd_stmt_prepare(sql.encode())
        statement_id = int(prepared["statement_id"])
        for kind in ("missing", "extra", "invalid_type"):
            packet = connection._send_cmd(
                ServerCmd.STMT_EXECUTE,
                packet=mysql_execute_body(statement_id, kind),
            )
            if packet and packet[4] == 0xFF:
                outcome = {"kind": kind, "error": mysql_error(get_exception(packet))}
            else:
                outcome = {"kind": kind, "unexpected_rows": consume_mysql_raw(connection, packet)}
            outcome["recovery_rows"] = mysql_query(connection, "SELECT 42")
            malformed.append(outcome)
        connection.cmd_stmt_close(statement_id)
        return {"malformed": malformed, "connection": "same", "recovery_rows": mysql_query(connection, "SELECT 43")}
    finally:
        connection.close()


def run_pg_bind(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    wire = pg_connect(args)
    attempts: list[dict[str, Any]] = []
    try:
        frames = [
            ("missing", parse("missing", sql), bind("missingp", "missing", []), execute("missingp")),
            ("extra", parse("extra", sql), bind("extrap", "extra", ["41", "99"]), execute("extrap")),
            ("invalid_type", parse("badtype", sql), bind("badtypep", "badtype", ["not-an-integer"]), execute("badtypep")),
        ]
        for kind, parsed, bound, executed in frames:
            failed = wire.unit(parsed, bound, executed)
            recovered = wire.unit(parse(f"recover_{kind}", "SELECT 42"), bind(f"recover_{kind}p", f"recover_{kind}", []), execute(f"recover_{kind}p"))
            attempts.append({"kind": kind, "failed": compact_pg(failed), "recovered": compact_pg(recovered)})
        return {"attempts": attempts, "connection": "same"}
    finally:
        wire.close()


def run_simple(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    if args.dialect == "mysql":
        connection = mysql_connect(args)
        try:
            try:
                rows = mysql_query(connection, sql)
                result: dict[str, Any] = {"rows": rows, "errors": []}
            except BaseException as exc:
                result = {"rows": [], "errors": [mysql_error(exc)]}
            result["recovery_rows"] = mysql_query(connection, "SELECT 42")
            return result
        finally:
            connection.close()
    wire = pg_connect(args)
    try:
        result = compact_pg(pg_query(wire, sql))
        result["recovery"] = compact_pg(pg_query(wire, "SELECT 42"))
        return result
    finally:
        wire.close()


def run_bound_value(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    if args.dialect == "mysql":
        connection = mysql_connect(args)
        try:
            return {"rows": mysql_query(connection, sql, (PAYLOAD,), prepared=True), "connection": "same"}
        finally:
            connection.close()
    wire = pg_connect(args)
    try:
        events = wire.unit(parse("bound", sql), bind("boundp", "bound", [PAYLOAD]), execute("boundp"))
        return {**compact_pg(events), "connection": "same"}
    finally:
        wire.close()


def run_nested(args: argparse.Namespace, spec: dict[str, int]) -> dict[str, Any]:
    sql = generated_nested_sql(spec["nesting"], spec["in_items"])
    result = run_simple(args, sql)
    return {**result, "generated": {**spec, "bytes": len(sql.encode()), "sha256": hashlib.sha256(sql.encode()).hexdigest()}}


def receive_pg_frame(wire: PgWire) -> dict[str, Any]:
    try:
        events = wire.receive_until({b"Z"})
        return {"eof": False, **compact_pg(events)}
    except (OSError, RuntimeError, socket.timeout) as exc:
        return {"eof": True, "error_kind": type(exc).__name__}


def run_message_limit(args: argparse.Namespace, spec: dict[str, int]) -> dict[str, Any]:
    phases: dict[str, Any] = {}
    for name, total in (("at_limit", spec["message_bytes"]), ("over_limit", spec["over_bytes"])):
        frame = generated_query_frame(total)
        wire = pg_connect(args)
        try:
            try:
                wire.send(frame)
                outcome = receive_pg_frame(wire)
            except (OSError, RuntimeError, socket.timeout) as exc:
                outcome = {"eof": True, "error_kind": type(exc).__name__}
            phases[name] = {
                **outcome,
                "bytes": len(frame),
                "sha256": hashlib.sha256(frame).hexdigest(),
            }
        finally:
            try:
                wire.close()
            except OSError:
                pass
    recovery = pg_connect(args)
    try:
        phases["new_connection"] = compact_pg(pg_query(recovery, "SELECT 42"))
    finally:
        recovery.close()
    return phases


def run(args: argparse.Namespace) -> dict[str, Any]:
    sql = statement_for_dialect(args.sql, args.dialect)
    spec = generation(args.sql)
    if args.flow == "mysql_bind":
        semantic = run_mysql_bind(args, sql)
    elif args.flow == "pg_bind":
        semantic = run_pg_bind(args, sql)
    elif args.flow in {"multi_statement", "comments", "identifier"}:
        semantic = run_simple(args, sql)
    elif args.flow == "bound_value":
        semantic = run_bound_value(args, sql)
    elif args.flow == "nested_in":
        semantic = run_nested(args, spec)
    elif args.flow == "message_limit":
        semantic = run_message_limit(args, spec)
    else:
        raise ValueError(f"unsupported boundary flow {args.flow}")
    return {"case_id": args.case_id, "dialect": args.dialect, "path": args.path, "flow": args.flow, "semantic": semantic}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--dialect", choices=("mysql", "postgres"), required=True)
    parser.add_argument("--path", choices=("direct", "gateway"), required=True)
    parser.add_argument("--flow", required=True)
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
