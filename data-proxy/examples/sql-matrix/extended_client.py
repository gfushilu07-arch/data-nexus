#!/usr/bin/env python3
"""Run one PostgreSQL extended-wire case and emit normalized JSON evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import socket
import struct
from pathlib import Path
from typing import Any

TAGS = {
    b"1": "ParseComplete", b"2": "BindComplete", b"3": "CloseComplete",
    b"C": "CommandComplete", b"D": "DataRow", b"E": "ErrorResponse",
    b"n": "NoData", b"s": "PortalSuspended", b"T": "RowDescription",
    b"t": "ParameterDescription", b"Z": "ReadyForQuery",
}


def i16(value: int) -> bytes:
    return struct.pack("!h", value)


def i32(value: int) -> bytes:
    return struct.pack("!i", value)


def cstr(value: str) -> bytes:
    return value.encode() + b"\0"


def message(tag: bytes, body: bytes = b"") -> bytes:
    return tag + i32(len(body) + 4) + body


def parse(statement: str, sql: str) -> bytes:
    return message(b"P", cstr(statement) + cstr(sql) + i16(0))


def bind(portal: str, statement: str, params: list[str | None], formats: list[int] | None = None) -> bytes:
    body = cstr(portal) + cstr(statement) + i16(0) + i16(len(params))
    for value in params:
        if value is None:
            body += i32(-1)
        else:
            encoded = value.encode()
            body += i32(len(encoded)) + encoded
    result_formats = formats or []
    body += i16(len(result_formats)) + b"".join(i16(value) for value in result_formats)
    return message(b"B", body)


def describe(target: str, name: str) -> bytes:
    return message(b"D", target.encode() + cstr(name))


def execute(portal: str, max_rows: int = 0) -> bytes:
    return message(b"E", cstr(portal) + i32(max_rows))


def close(target: str, name: str) -> bytes:
    return message(b"C", target.encode() + cstr(name))


def error_fields(body: bytes) -> dict[str, str]:
    names = {"S": "severity", "V": "severity_nonlocalized", "C": "sqlstate", "M": "message"}
    result: dict[str, str] = {}
    offset = 0
    while offset < len(body) and body[offset]:
        code = chr(body[offset])
        end = body.index(0, offset + 1)
        if code in names:
            result[names[code]] = body[offset + 1:end].decode("utf-8", "replace")
        offset = end + 1
    return result


def row_description(body: bytes) -> list[dict[str, int | str]]:
    count = struct.unpack_from("!h", body)[0]
    offset = 2
    columns = []
    for _ in range(count):
        end = body.index(0, offset)
        name = body[offset:end].decode("utf-8", "replace")
        offset = end + 1
        table_oid, attribute, type_oid, type_size, modifier, format_code = struct.unpack_from(
            "!ihihih", body, offset
        )
        offset += 18
        columns.append({"name": name, "table_oid": table_oid, "attribute": attribute,
                        "type_oid": type_oid, "type_size": type_size,
                        "type_modifier": modifier, "format_code": format_code})
    return columns


def data_row(body: bytes, columns: list[dict[str, Any]]) -> list[str | None]:
    count = struct.unpack_from("!h", body)[0]
    offset = 2
    values: list[str | None] = []
    for index in range(count):
        length = struct.unpack_from("!i", body, offset)[0]
        offset += 4
        if length == -1:
            values.append(None)
            continue
        raw = body[offset:offset + length]
        offset += length
        column = columns[index] if index < len(columns) else {"format_code": 0, "type_oid": 25}
        oid = int(column["type_oid"])
        if column["format_code"] == 1 and oid in {20, 23, 21}:
            values.append(str(struct.unpack({20: "!q", 23: "!i", 21: "!h"}[oid], raw)[0]))
        else:
            values.append(raw.decode("utf-8", "replace"))
    return values


class PgWire:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.sock = socket.create_connection((host, port), timeout=15)
        self.sock.settimeout(15)
        self.user = user
        self.password = password
        self.database = database
        self.columns: list[dict[str, Any]] = []
        self.startup_events: list[dict[str, Any]] = []
        self._startup()

    def _recv_exact(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise RuntimeError("unexpected PostgreSQL socket EOF")
            data += chunk
        return data

    def read_message(self) -> tuple[bytes, bytes]:
        tag = self._recv_exact(1)
        length = struct.unpack("!i", self._recv_exact(4))[0]
        return tag, self._recv_exact(length - 4)

    def send(self, *frames: bytes) -> None:
        self.sock.sendall(b"".join(frames))

    def _startup(self) -> None:
        params = cstr("user") + cstr(self.user) + cstr("database") + cstr(self.database)
        params += cstr("client_encoding") + cstr("UTF8") + b"\0"
        self.sock.sendall(i32(8 + len(params)) + i32(196608) + params)
        client_first_bare = ""
        expected_signature = b""
        while True:
            tag, body = self.read_message()
            if tag == b"R":
                auth_type = struct.unpack_from("!i", body)[0]
                if auth_type == 0:
                    continue
                if auth_type == 10:
                    if b"SCRAM-SHA-256" not in body[4:].split(b"\0"):
                        raise RuntimeError("server does not offer SCRAM-SHA-256")
                    nonce = base64.b64encode(os.urandom(18)).decode()
                    username = self.user.replace("=", "=3D").replace(",", "=2C")
                    client_first_bare = f"n={username},r={nonce}"
                    initial = f"n,,{client_first_bare}".encode()
                    self.send(message(b"p", cstr("SCRAM-SHA-256") + i32(len(initial)) + initial))
                    continue
                if auth_type == 11:
                    server_first = body[4:].decode()
                    attrs = dict(item.split("=", 1) for item in server_first.split(","))
                    salted = hashlib.pbkdf2_hmac(
                        "sha256", self.password.encode(), base64.b64decode(attrs["s"]), int(attrs["i"])
                    )
                    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
                    stored_key = hashlib.sha256(client_key).digest()
                    final_without_proof = f"c=biws,r={attrs['r']}"
                    auth_message = f"{client_first_bare},{server_first},{final_without_proof}".encode()
                    client_signature = hmac.new(stored_key, auth_message, hashlib.sha256).digest()
                    proof = bytes(a ^ b for a, b in zip(client_key, client_signature, strict=True))
                    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
                    expected_signature = hmac.new(server_key, auth_message, hashlib.sha256).digest()
                    final = f"{final_without_proof},p={base64.b64encode(proof).decode()}".encode()
                    self.send(message(b"p", final))
                    continue
                if auth_type == 12:
                    final = body[4:].decode()
                    attrs = dict(item.split("=", 1) for item in final.split(","))
                    if not hmac.compare_digest(base64.b64decode(attrs["v"]), expected_signature):
                        raise RuntimeError("invalid SCRAM server signature")
                    continue
                raise RuntimeError(f"unsupported PostgreSQL auth type {auth_type}")
            if tag == b"E":
                raise RuntimeError(f"startup failed: {error_fields(body)}")
            if tag == b"Z":
                self.startup_events.append({"tag": "ReadyForQuery", "status": chr(body[0])})
                return

    def event(self, tag: bytes, body: bytes) -> dict[str, Any]:
        event: dict[str, Any] = {"tag": TAGS.get(tag, tag.decode("latin1"))}
        if tag == b"T":
            self.columns = row_description(body)
            event["columns"] = self.columns
        elif tag == b"D":
            event["row"] = data_row(body, self.columns)
        elif tag == b"E":
            event.update(error_fields(body))
        elif tag == b"Z":
            event["status"] = chr(body[0])
        elif tag == b"t":
            count = struct.unpack_from("!h", body)[0]
            event["type_oids"] = [struct.unpack_from("!i", body, 2 + 4 * index)[0] for index in range(count)]
        elif tag == b"C":
            event["command"] = body.rstrip(b"\0").decode("utf-8", "replace")
        return event

    def receive_until(self, terminal: set[bytes]) -> list[dict[str, Any]]:
        events = []
        while True:
            tag, body = self.read_message()
            events.append(self.event(tag, body))
            if tag in terminal:
                return events

    def unit(self, *frames: bytes) -> list[dict[str, Any]]:
        self.send(*frames, message(b"S"))
        return self.receive_until({b"Z"})

    def close(self) -> None:
        try:
            self.send(message(b"X"))
        finally:
            self.sock.close()


def read_statements(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()[4:]
    statements: dict[str, list[str]] = {"main": []}
    current = "main"
    for line in lines:
        if line.startswith("-- @statement "):
            current = line.removeprefix("-- @statement ").strip()
            statements[current] = []
        else:
            statements[current].append(line)
    return {name: "\n".join(body).strip() for name, body in statements.items() if "\n".join(body).strip()}


def rows(events: list[dict[str, Any]]) -> list[list[str | None]]:
    return [event["row"] for event in events if event["tag"] == "DataRow"]


def ready(events: list[dict[str, Any]]) -> list[str]:
    return [event["status"] for event in events if event["tag"] == "ReadyForQuery"]


def ignored_messages_absent(events: list[dict[str, Any]]) -> bool:
    """Require queued extended messages after the first error to stay silent until Sync."""
    tags = [event["tag"] for event in events]
    try:
        error_index = tags.index("ErrorResponse")
        ready_index = tags.index("ReadyForQuery", error_index + 1)
    except ValueError:
        return False
    return ready_index == error_index + 1


def run_flow(wire: PgWire, statements: dict[str, str], oracle: dict[str, Any]) -> dict[str, Any]:
    flow = oracle["flow"]
    params = oracle["parameters"]
    all_events: list[dict[str, Any]] = []
    result: dict[str, Any] = {"flow": flow, "rows": [], "ready": []}
    sql = statements.get("main", "")

    if flow == "lifecycle":
        events = wire.unit(parse("s1", sql), describe("S", "s1"), bind("p1", "s1", params),
                           describe("P", "p1"), execute("p1"), close("P", "p1"), close("S", "s1"))
        all_events += events
        required = ["ParseComplete", "ParameterDescription", "RowDescription", "BindComplete",
                    "RowDescription", "DataRow", "CommandComplete", "CloseComplete", "CloseComplete",
                    "ReadyForQuery"]
        tags = [event["tag"] for event in events]
        cursor = 0
        for tag in required:
            cursor = tags.index(tag, cursor) + 1
    elif flow == "parameters":
        all_events += wire.unit(parse("s2", sql), bind("p2", "s2", params), execute("p2"))
    elif flow == "rebind":
        first = wire.unit(parse("s3", sql), bind("p3", "s3", params[0]), execute("p3"))
        second = wire.unit(bind("p3", "s3", params[1]), execute("p3"), close("S", "s3"))
        all_events += first + second
    elif flow == "multiple_portals":
        all_events += wire.unit(parse("s4", sql), bind("p4a", "s4", params[0]),
                                bind("p4b", "s4", params[1]), execute("p4a"), execute("p4b"))
    elif flow == "paging":
        wire.send(parse("s5", sql), bind("p5", "s5", []))
        page_end = []
        for _ in range(5):
            wire.send(execute("p5", 1), message(b"H"))
            page = wire.receive_until({b"s", b"C", b"E"})
            all_events += page
            page_end.append(page[-1]["tag"])
        wire.send(message(b"S"))
        sync = wire.receive_until({b"Z"})
        all_events += sync
        result["page_end"] = page_end
    elif flow == "binary_description":
        all_events += wire.unit(parse("s6", sql), describe("S", "s6"),
                                bind("p6", "s6", params, [1]), describe("P", "p6"), execute("p6"))
        descriptions = [event["columns"] for event in all_events if event["tag"] == "RowDescription"]
        binary = next((value for value in reversed(descriptions)
                       if value and all(column["format_code"] == 1 for column in value)), [])
        result["columns"] = [column["name"] for column in binary]
        result["type_oids"] = [column["type_oid"] for column in binary]
        result["format_codes"] = [column["format_code"] for column in binary]
    elif flow == "error_recovery":
        wire.send(parse("bad", statements["failing"]), bind("badp", "bad", params[0]), execute("badp"),
                  parse("ignored", statements["ignored"]), bind("ignoredp", "ignored", []),
                  execute("ignoredp"), message(b"S"))
        failed = wire.receive_until({b"Z"})
        recovered = wire.unit(parse("good", statements["recovered"]),
                              bind("goodp", "good", params[1]), execute("goodp"))
        all_events += failed + recovered
        errors = [event for event in failed if event["tag"] == "ErrorResponse"]
        result["sqlstate"] = errors[0].get("sqlstate") if errors else None
        result["ignored_value_absent"] = all(event.get("row") != ["999"] for event in failed)
        result["ignored_messages_absent"] = ignored_messages_absent(failed)
    elif flow == "transaction_status":
        units = [
            ("begin", [], statements["begin"]),
            ("success", params[0], statements["success"]),
            ("failing", params[1], statements["failing"]),
            ("rollback", [], statements["rollback"]),
        ]
        for name, values, unit_sql in units:
            all_events += wire.unit(parse(name, unit_sql), bind(name + "p", name, values), execute(name + "p"))
        errors = [event for event in all_events if event["tag"] == "ErrorResponse"]
        result["sqlstate"] = errors[0].get("sqlstate") if errors else None
    else:
        raise ValueError(f"unknown extended flow {flow!r}")

    result["rows"] = rows(all_events)
    result["ready"] = ready(all_events)
    result["events"] = all_events
    semantic = {key: value for key, value in result.items() if key not in {"events", "flow"}}
    if semantic != oracle["expected"]:
        raise AssertionError(json.dumps({"expected": oracle["expected"], "actual": semantic}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--oracle", type=Path, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--database", default="sqlt")
    args = parser.parse_args()
    oracle = json.loads(args.oracle.read_text(encoding="utf-8"))
    wire = PgWire(args.host, args.port, args.user, args.password, args.database)
    try:
        result = run_flow(wire, read_statements(args.sql), oracle)
    finally:
        wire.close()
    print(json.dumps({"case_id": args.case_id, **result}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
