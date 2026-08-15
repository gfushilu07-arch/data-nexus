#!/usr/bin/env python3
"""Execute one SQLT-4B1 query over MySQL text or PostgreSQL simple wire."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


PG_TYPE_NAMES = {
    16: "bool",
    17: "bytea",
    20: "int8",
    21: "int2",
    23: "int4",
    25: "text",
    700: "float4",
    701: "float8",
    1043: "varchar",
    1082: "date",
    1083: "time",
    1114: "timestamp",
    1184: "timestamptz",
    1700: "numeric",
}


def read_sql(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    sql = "\n".join(lines[4:]).strip()
    if not sql:
        raise ValueError(f"SQL body is empty: {path}")
    return sql


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
        return value.hex().upper()
    return str(value)


def rows_text(rows: list[list[str | None]]) -> str:
    return "".join(
        "\t".join("NULL" if value is None else value for value in row) + "\n"
        for row in rows
    )


def result(protocol: str, columns: list[str], types: list[str], rows: list[list[Any]]) -> dict[str, Any]:
    normalized = [[normalize_cell(value) for value in row] for row in rows]
    return {
        "protocol": protocol,
        "columns": columns,
        "types": types,
        "rows": normalized,
        "rows_text": rows_text(normalized),
        "row_count": len(normalized),
    }


def run_mysql(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    from mysql.connector.connection import MySQLConnection
    from mysql.connector.constants import FieldType

    class QueryOnlyConnection(MySQLConnection):
        """Avoid connector session SET commands on SELECT-only translation lanes."""

        def _post_connection(self) -> None:
            self._autocommit = True

    connection = QueryOnlyConnection(
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
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            description = cursor.description or []
            columns = [str(column[0]) for column in description]
            types = [str(FieldType.get_info(int(column[1]))) for column in description]
            return result("mysql_text", columns, types, rows)
        finally:
            cursor.close()
    finally:
        connection.close()


def run_postgres(args: argparse.Namespace, sql: str) -> dict[str, Any]:
    from extended_client import PgWire, cstr, message

    wire = PgWire(args.host, args.port, args.user, args.password, args.database)
    try:
        wire.send(message(b"Q", cstr(sql)))
        events = wire.receive_until({b"Z"})
    finally:
        wire.close()
    errors = [event for event in events if event["tag"] == "ErrorResponse"]
    if errors:
        raise RuntimeError(json.dumps(errors, sort_keys=True))
    descriptions = [event["columns"] for event in events if event["tag"] == "RowDescription"]
    columns = descriptions[-1] if descriptions else []
    names = [str(column["name"]) for column in columns]
    types = [PG_TYPE_NAMES.get(int(column["type_oid"]), f"oid:{column['type_oid']}") for column in columns]
    rows = [event["row"] for event in events if event["tag"] == "DataRow"]
    return result("pg_simple", names, types, rows)


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
    sql = read_sql(args.sql)
    value = run_mysql(args, sql) if args.protocol == "mysql_text" else run_postgres(args, sql)
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
