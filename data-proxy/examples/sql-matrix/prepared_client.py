#!/usr/bin/env python3
"""Run one canonical MySQL binary-prepared case and emit one normalized JSON object."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import mysql.connector
from mysql.connector import Error, errors


def normalize(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(sep=" ") if isinstance(value, dt.datetime) else value.isoformat()
    if isinstance(value, dt.timedelta):
        sign = "-" if value.total_seconds() < 0 else ""
        seconds = abs(int(value.total_seconds()))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex().upper()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return str(value)


def connect(args: argparse.Namespace, host: str, port: int, user: str, password: str):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=args.database,
        ssl_disabled=port == 29088,
        ssl_verify_cert=False,
        ssl_verify_identity=False,
        connection_timeout=10,
        autocommit=True,
    )


def expand_parameter(value: Any) -> Any:
    if isinstance(value, dict) and "string" in value:
        spec = value["string"]
        return f"{spec['prefix']}{spec['repeat'] * spec['count']}{spec['suffix']}"
    if isinstance(value, dict) and "bytes_hex" in value:
        return bytes.fromhex(value["bytes_hex"])
    if isinstance(value, dict) and "decimal" in value:
        return Decimal(value["decimal"])
    if isinstance(value, dict) and "date" in value:
        return dt.date.fromisoformat(value["date"])
    if isinstance(value, dict) and "time" in value:
        return dt.time.fromisoformat(value["time"])
    if isinstance(value, dict) and "datetime" in value:
        return dt.datetime.fromisoformat(value["datetime"])
    return value


def expanded_parameters(values: list[Any]) -> tuple[Any, ...]:
    return tuple(expand_parameter(value) for value in values)


def execute_rows(cursor, sql: str, parameters: list[Any]) -> tuple[list[str], list[list[Any]]]:
    cursor.execute(sql, expanded_parameters(parameters))
    rows = cursor.fetchall()
    columns = [item[0] for item in (cursor.description or [])]
    return columns, [normalize(row) for row in rows]


def classify_count_error(exc: BaseException) -> str:
    if isinstance(exc, (errors.ProgrammingError, errors.InterfaceError)):
        return "client_parameter_count"
    if isinstance(exc, Error):
        return "backend_error"
    return "client_error"


def classify_schema_change_error(exc: BaseException) -> str:
    if isinstance(exc, Error) and getattr(exc, "errno", None) == 2057:
        if getattr(exc, "sqlstate", None) == "HY000":
            return "result_rebind_required"
    raise exc


def run_case(args: argparse.Namespace, oracle: dict[str, Any]) -> dict[str, Any]:
    connection = connect(args, args.host, args.port, args.user, args.password)
    cursor = connection.cursor(prepared=True)
    result: dict[str, Any] = {"columns": [], "rows": [], "errors": []}
    close_recovery = "not_checked"
    try:
        sql = "\n".join(Path(args.sql).read_text(encoding="utf-8").splitlines()[4:]).strip()
        parameters = oracle["parameters"]
        if args.case_id == "SQLT-PRP-001":
            result["columns"], result["rows"] = execute_rows(cursor, sql, parameters)
        elif args.case_id in {"SQLT-PRP-002", "SQLT-PRP-003", "SQLT-PRP-004", "SQLT-PRP-005"}:
            result["columns"], result["rows"] = execute_rows(cursor, sql, parameters)
        elif args.case_id == "SQLT-PRP-006":
            for label, bad_parameters in (
                ("missing_binding", []),
                ("extra_binding", [parameters[0], parameters[0]]),
            ):
                try:
                    cursor.execute(sql, expanded_parameters(bad_parameters))
                    probe_rows = cursor.fetchall()
                except BaseException as exc:  # driver error is part of this boundary case
                    result["errors"].append(classify_count_error(exc))
                else:
                    if label == "missing_binding" and probe_rows == []:
                        result["errors"].append("missing_binding_accepted_empty_result")
                    else:
                        result["errors"].append(f"{label}_unexpected_success")
            result["columns"], result["rows"] = execute_rows(cursor, sql, parameters)
        elif args.case_id == "SQLT-PRP-007":
            for bind in parameters:
                columns, rows = execute_rows(cursor, sql, bind)
                if not result["columns"]:
                    result["columns"] = columns
                result["rows"].extend(rows)
        elif args.case_id == "SQLT-PRP-008":
            result["columns_before"], result["rows_before"] = execute_rows(cursor, sql, parameters)
            if args.control_sql:
                control = connect(args, args.control_host, args.control_port, args.control_user, args.control_password)
                try:
                    control_sql = "\n".join(
                        Path(args.control_sql).read_text(encoding="utf-8").splitlines()[4:]
                    ).strip()
                    control.cursor().execute(control_sql)
                    control.commit()
                finally:
                    control.close()
            try:
                result["columns"], result["rows"] = execute_rows(cursor, sql, parameters)
            except Error as exc:
                result["errors"].append(classify_schema_change_error(exc))
                cursor.close()
                cursor = connection.cursor(prepared=True)
                result["columns"], result["rows"] = execute_rows(cursor, sql, parameters)
        else:
            raise ValueError(f"unsupported prepared case: {args.case_id}")
    finally:
        cursor.close()
        try:
            cursor.execute("SELECT 1")
        except (Error, ValueError, AttributeError):
            close_recovery = "closed"
        else:
            close_recovery = "reusable"
        connection.close()
    result["close_recovery"] = close_recovery
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--sql", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    parser.add_argument("--control-sql", type=Path)
    parser.add_argument("--control-host", default="host.docker.internal")
    parser.add_argument("--control-port", type=int, default=23306)
    parser.add_argument("--control-user", default="root")
    parser.add_argument("--control-password", default="root")
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    print(json.dumps(run_case(args, oracle), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
