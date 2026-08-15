#!/usr/bin/env python3
"""Validate the SQL capability registry, manifest, and SQL case files."""

from __future__ import annotations

import json
import importlib.util
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


CASE_ID_RE = re.compile(r"^SQLT-[A-Z]+-[0-9]{3}$")
HEADER_FIELDS = ("case", "Purpose", "Expected", "Dialect")
FIXTURE_HEADER_FIELDS = ("Purpose", "Expected", "Dialect")
LIST_CAPABILITIES = (
    "dialects",
    "backends",
    "frontends",
    "protocols",
    "policies",
    "outcomes",
    "statement_modes",
    "transaction_modes",
    "parameter_modes",
)


def _load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing JSON file: {path.name}")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"cannot read {path.name}: {exc}")
    return None


def _string_set(value: Any, label: str, errors: list[str]) -> set[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{label} must be a non-empty array")
        return set()
    if any(not isinstance(item, str) or not item for item in value):
        errors.append(f"{label} must contain non-empty strings")
        return set()
    if len(value) != len(set(value)):
        errors.append(f"{label} contains duplicate values")
    return set(value)


def _validate_registry(capabilities: Any, errors: list[str]) -> dict[str, set[str]]:
    if not isinstance(capabilities, dict):
        errors.append("capabilities.json must contain an object")
        return {}
    if capabilities.get("schema_version") != 1:
        errors.append("capabilities.json schema_version must be 1")

    known = {
        name: _string_set(capabilities.get(name), f"capabilities.{name}", errors)
        for name in LIST_CAPABILITIES
    }
    known["side_effects"] = _string_set(
        capabilities.get("side_effects"), "capabilities.side_effects", errors
    )

    families = capabilities.get("families")
    if not isinstance(families, dict) or not families:
        errors.append("capabilities.families must be a non-empty object")
        known["families"] = set()
    else:
        known["families"] = set(families)
        for name, details in families.items():
            if not isinstance(name, str) or not name:
                errors.append("capabilities.families contains an invalid name")
            if not isinstance(details, dict) or not isinstance(details.get("description"), str):
                errors.append(f"capabilities.families.{name} needs a description")

    sql_capabilities = capabilities.get("sql_capabilities")
    if not isinstance(sql_capabilities, dict) or not sql_capabilities:
        errors.append("capabilities.sql_capabilities must be a non-empty object")
        known["sql_capabilities"] = set()
    else:
        known["sql_capabilities"] = set(sql_capabilities)
        for name, description in sql_capabilities.items():
            if not isinstance(name, str) or not name:
                errors.append("capabilities.sql_capabilities contains an invalid name")
            if not isinstance(description, str) or not description:
                errors.append(f"capabilities.sql_capabilities.{name} needs a description")

    profiles = capabilities.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        errors.append("capabilities.profiles must be a non-empty object")
        known["profiles"] = set()
        return known

    known["profiles"] = set(profiles)
    for name, profile in profiles.items():
        label = f"capabilities.profiles.{name}"
        if not isinstance(profile, dict):
            errors.append(f"{label} must be an object")
            continue
        if not isinstance(profile.get("purpose"), str) or not profile["purpose"]:
            errors.append(f"{label}.purpose must be a non-empty string")
        for field in ("frontends", "backends", "policies"):
            values = _string_set(profile.get(field), f"{label}.{field}", errors)
            unknown = values - known.get(field, set())
            if unknown:
                errors.append(f"{label}.{field} has unknown values: {sorted(unknown)}")
    return known


def _validate_sql_file(
    path: Path, case_id: str, dialects: list[str], errors: list[str]
) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        errors.append(f"{case_id}: SQL file does not exist: {path}")
        return
    except (OSError, UnicodeError) as exc:
        errors.append(f"{case_id}: cannot read SQL file {path}: {exc}")
        return

    if len(lines) < len(HEADER_FIELDS):
        errors.append(f"{case_id}: SQL file is missing the four-line comment header")
        return

    header: dict[str, str] = {}
    for index, field in enumerate(HEADER_FIELDS):
        prefix = f"-- {field}: "
        if not lines[index].startswith(prefix) or not lines[index][len(prefix) :].strip():
            errors.append(f"{case_id}: SQL line {index + 1} must start with {prefix!r}")
            continue
        header[field] = lines[index][len(prefix) :].strip()

    if header.get("case") and header["case"] != case_id:
        errors.append(
            f"{case_id}: SQL comment case ID is {header['case']!r}, expected {case_id!r}"
        )
    if header.get("Dialect"):
        comment_dialects = [item.strip() for item in header["Dialect"].split(",")]
        if comment_dialects != dialects:
            errors.append(
                f"{case_id}: SQL comment dialects {comment_dialects!r} "
                f"do not match manifest {dialects!r}"
            )

    sql_body = "\n".join(lines[len(HEADER_FIELDS) :]).strip()
    if not sql_body or all(
        not line.strip() or line.lstrip().startswith("--")
        for line in lines[len(HEADER_FIELDS) :]
    ):
        errors.append(f"{case_id}: SQL file has no statement body")


def _validate_fixture_sql_files(root: Path, errors: list[str]) -> None:
    fixture_root = root / "fixtures"
    if not fixture_root.is_dir():
        return
    seen_ids: set[str] = set()
    for path in sorted(fixture_root.glob("*/*.sql")):
        dialect = path.parent.name
        label = str(path.relative_to(root))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"{label}: cannot read fixture SQL: {exc}")
            continue
        if len(lines) < 4:
            errors.append(f"{label}: fixture SQL is missing the four-line comment header")
            continue
        identity = re.fullmatch(r"-- (fixture|oracle): ([A-Z0-9-]+)", lines[0])
        if not identity:
            errors.append(f"{label}: SQL line 1 must declare a fixture or oracle ID")
        else:
            fixture_id = identity.group(2)
            if fixture_id in seen_ids:
                errors.append(f"duplicate fixture SQL ID: {fixture_id}")
            seen_ids.add(fixture_id)
        for index, field in enumerate(FIXTURE_HEADER_FIELDS, start=1):
            prefix = f"-- {field}: "
            if not lines[index].startswith(prefix) or not lines[index][len(prefix) :].strip():
                errors.append(f"{label}: SQL line {index + 1} must start with {prefix!r}")
        if lines[3] != f"-- Dialect: {dialect}":
            errors.append(f"{label}: dialect comment must match parent directory {dialect!r}")
        if not any(line.strip() and not line.lstrip().startswith("--") for line in lines[4:]):
            errors.append(f"{label}: fixture SQL has no statement body")


def _validate_dql_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    oracles = _load_json(root / "dql-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("dql-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("dql-oracles.json schema_version must be 1")
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("dql-oracles.json results must be an object")
        return

    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "dql"
            and case.get("transaction_mode") == "autocommit"
            and case.get("capability") != "dql.boundary"
        ):
            case_id = case.get("id")
            dialects = case.get("dialects")
            if isinstance(case_id, str) and isinstance(dialects, list):
                expected[case_id] = {item for item in dialects if isinstance(item, str)}

    if set(results) != set(expected):
        missing = sorted(set(expected) - set(results))
        extra = sorted(set(results) - set(expected))
        if missing:
            errors.append(f"dql-oracles.json is missing cases: {missing}")
        if extra:
            errors.append(f"dql-oracles.json has unknown cases: {extra}")

    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict):
            errors.append(f"dql-oracles.json results.{case_id} must be an object")
            continue
        if set(values) != dialects:
            errors.append(
                f"dql-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
        for dialect, output in values.items():
            if not isinstance(output, str):
                errors.append(
                    f"dql-oracles.json results.{case_id}.{dialect} must be a string"
                )
            elif output and not output.endswith("\n"):
                errors.append(
                    f"dql-oracles.json results.{case_id}.{dialect} must end with LF"
                )


def _validate_dql_lock_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate multi-connection row-lock contracts for explicit DQL cases."""
    oracles = _load_json(root / "dql-lock-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("dql-lock-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("dql-lock-oracles.json schema_version must be 1")
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("dql-lock-oracles.json results must be an object")
        return

    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "dql"
            and case.get("transaction_mode") == "explicit"
        ):
            case_id = case.get("id")
            dialects = case.get("dialects")
            if isinstance(case_id, str) and isinstance(dialects, list):
                expected[case_id] = {item for item in dialects if isinstance(item, str)}

    if set(results) != set(expected):
        errors.append(
            "dql-lock-oracles.json cases must be "
            f"{sorted(expected)}, got {sorted(results)}"
        )

    required_fields = {
        "block_then_complete": {"during_lock", "after_rollback"},
        "shared_compatible": {"during_lock", "conflict_error", "after_rollback"},
        "fail_nowait": {"during_lock_error", "after_rollback"},
        "skip_locked": {"during_lock", "after_rollback"},
    }
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict):
            errors.append(f"dql-lock-oracles.json results.{case_id} must be an object")
            continue
        if set(values) != dialects:
            errors.append(
                f"dql-lock-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
        for dialect, contract in values.items():
            label = f"dql-lock-oracles.json results.{case_id}.{dialect}"
            if not isinstance(contract, dict):
                errors.append(f"{label} must be an object")
                continue
            behavior = contract.get("behavior")
            fields = required_fields.get(behavior)
            if fields is None:
                errors.append(f"{label}.behavior is unknown: {behavior!r}")
                continue
            if set(contract) != fields | {"behavior"}:
                errors.append(f"{label} fields must be {sorted(fields | {'behavior'})}")
            for field in fields:
                output = contract.get(field)
                if not isinstance(output, str):
                    errors.append(f"{label}.{field} must be a string")
                elif output and not output.endswith("\n"):
                    errors.append(f"{label}.{field} must end with LF")


def _validate_dql_boundary_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate bounded-memory summary contracts for large DQL outputs."""
    oracles = _load_json(root / "dql-boundary-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("dql-boundary-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("dql-boundary-oracles.json schema_version must be 1")
    chunk_bytes = oracles.get("chunk_bytes")
    if chunk_bytes != 65536 or isinstance(chunk_bytes, bool):
        errors.append("dql-boundary-oracles.json chunk_bytes must be 65536")
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("dql-boundary-oracles.json results must be an object")
        return

    expected: dict[str, set[str]] = {}
    for case in cases:
        if isinstance(case, dict) and case.get("capability") == "dql.boundary":
            case_id = case.get("id")
            dialects = case.get("dialects")
            if isinstance(case_id, str) and isinstance(dialects, list):
                expected[case_id] = {item for item in dialects if isinstance(item, str)}

    if set(results) != set(expected):
        errors.append(
            "dql-boundary-oracles.json cases must be "
            f"{sorted(expected)}, got {sorted(results)}"
        )

    fields = {
        "bytes",
        "lines",
        "max_line_bytes",
        "ends_with_lf",
        "sha256",
        "first_line_sha256",
        "last_line_sha256",
    }
    hash_fields = {"sha256", "first_line_sha256", "last_line_sha256"}
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict):
            errors.append(f"dql-boundary-oracles.json results.{case_id} must be an object")
            continue
        if set(values) != dialects:
            errors.append(
                f"dql-boundary-oracles.json results.{case_id} dialects must be "
                f"{sorted(dialects)}"
            )
        for dialect, summary in values.items():
            label = f"dql-boundary-oracles.json results.{case_id}.{dialect}"
            if not isinstance(summary, dict):
                errors.append(f"{label} must be an object")
                continue
            if set(summary) != fields:
                errors.append(f"{label} fields must be {sorted(fields)}")
            for field in ("bytes", "lines", "max_line_bytes"):
                value = summary.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    errors.append(f"{label}.{field} must be a non-negative integer")
            if not isinstance(summary.get("ends_with_lf"), bool):
                errors.append(f"{label}.ends_with_lf must be a boolean")
            for field in hash_fields:
                value = summary.get(field)
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                    errors.append(f"{label}.{field} must be a lowercase SHA-256")


def _validate_dml_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate per-case state, affected-row, and error contracts for DML tranches."""
    oracles = _load_json(root / "dml-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("dml-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("dml-oracles.json schema_version must be 1")
    state_queries = oracles.get("state_queries")
    if not isinstance(state_queries, dict) or not state_queries:
        errors.append("dml-oracles.json state_queries must define at least one query group")
    else:
        for group, queries in state_queries.items():
            if not isinstance(queries, dict) or set(queries) != {"mysql", "postgres"}:
                errors.append(
                    f"dml-oracles.json state_queries.{group} must define mysql and postgres"
                )
                continue
            for dialect, relative in queries.items():
                label = f"dml-oracles.json state_queries.{group}.{dialect}"
                if not isinstance(relative, str) or not relative.endswith(".sql"):
                    errors.append(f"{label} must be an SQL path")
                    continue
                path = root / PurePosixPath(relative)
                try:
                    path.resolve().relative_to(root.resolve())
                except ValueError:
                    errors.append(f"{label} escapes matrix root")
                if not path.is_file():
                    errors.append(f"{label} does not exist: {relative}")

    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "dml"
            and isinstance(case.get("id"), str)
            and case["id"] in {f"SQLT-DML-{index:03d}" for index in range(3, 44)}
        ):
            expected[case["id"]] = set(case.get("dialects", []))
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("dml-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"dml-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(f"dml-oracles.json results.{case_id} dialects must be {sorted(dialects)}")
            continue
        for dialect, value in values.items():
            label = f"dml-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict) or value.get("result") not in {
                "success",
                "error",
                "recovered_error",
            }:
                errors.append(f"{label}.result must be success, error, or recovered_error")
                continue
            query_group = value.get("state_query")
            if not isinstance(query_group, str) or query_group not in state_queries:
                errors.append(f"{label}.state_query must name a registered query group")
            if value["result"] in {"success", "recovered_error"}:
                if not isinstance(value.get("state"), str) or not value["state"].endswith("\n"):
                    errors.append(f"{label}.state must be a newline-terminated string")
                if value["result"] == "success" and "error" in value:
                    errors.append(f"{label} success oracle cannot define error")
                if value["result"] == "recovered_error" and (
                    not isinstance(value.get("error"), str) or not value["error"].endswith("\n")
                ):
                    errors.append(f"{label}.error must be a newline-terminated string")
                if "affected_rows" in value and type(value["affected_rows"]) is not int:
                    errors.append(f"{label}.affected_rows must be an integer")
                returned_rows = value.get("returned_rows")
                if "returned_rows" in value and (
                    not isinstance(returned_rows, str)
                    or (returned_rows and not returned_rows.endswith("\n"))
                ):
                    errors.append(f"{label}.returned_rows must be a normalized string")
                if case_id >= "SQLT-DML-015" and not {
                    "affected_rows",
                    "returned_rows",
                    "transaction_markers",
                } & set(value):
                    errors.append(
                        f"{label} must define affected_rows, returned_rows, or transaction_markers"
                    )
                markers = value.get("transaction_markers")
                if "transaction_markers" in value and (
                    not isinstance(markers, str)
                    or not markers.startswith("SQLT_TXN\t")
                    or not markers.endswith("\n")
                ):
                    errors.append(f"{label}.transaction_markers must contain marker rows")
            else:
                if not isinstance(value.get("error"), str) or not value["error"].endswith("\n"):
                    errors.append(f"{label}.error must be a newline-terminated string")
                if value.get("state") != "":
                    errors.append(f"{label}.state must be empty for an error oracle")
                if "affected_rows" in value:
                    errors.append(f"{label} error oracle cannot define affected_rows")
                if "returned_rows" in value:
                    errors.append(f"{label} error oracle cannot define returned_rows")


def _validate_tcl_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate the strict per-dialect contract owned by the explicit TCL runner."""
    oracles = _load_json(root / "tcl-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("tcl-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("tcl-oracles.json schema_version must be 1")

    state_queries = oracles.get("state_queries")
    if not isinstance(state_queries, dict) or set(state_queries) != {"tcl", "tcl_ddl"}:
        errors.append("tcl-oracles.json state_queries must contain tcl and tcl_ddl")
        state_queries = {}
    for group, queries in state_queries.items():
        if not isinstance(queries, dict) or set(queries) != {"mysql", "postgres"}:
            errors.append(f"tcl-oracles.json state_queries.{group} must define mysql and postgres")
            continue
        for dialect, relative in queries.items():
            label = f"tcl-oracles.json state_queries.{group}.{dialect}"
            if not isinstance(relative, str) or not relative.endswith(".sql"):
                errors.append(f"{label} must be an SQL path")
                continue
            path = root / PurePosixPath(relative)
            try:
                path.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"{label} escapes matrix root")
            if not path.is_file():
                errors.append(f"{label} does not exist: {relative}")

    expected: dict[str, set[str]] = {}
    for case in cases:
        if isinstance(case, dict) and case.get("family") == "tcl":
            case_id = case.get("id")
            dialects = case.get("dialects")
            if isinstance(case_id, str) and isinstance(dialects, list):
                expected[case_id] = {item for item in dialects if isinstance(item, str)}

    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("tcl-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"tcl-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    required = {"result", "state_query", "state", "transaction_markers"}
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(
                f"tcl-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
            continue
        for dialect, value in values.items():
            label = f"tcl-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict):
                errors.append(f"{label} must be an object")
                continue
            result = value.get("result")
            if result not in {"success", "recovered_error"}:
                errors.append(f"{label}.result must be success or recovered_error")
                continue
            expected_fields = required | ({"error"} if result == "recovered_error" else set())
            if set(value) != expected_fields:
                errors.append(f"{label} fields must be {sorted(expected_fields)}")
            if value.get("state_query") not in state_queries:
                errors.append(f"{label}.state_query must name a registered query group")
            state = value.get("state")
            if not isinstance(state, str) or (state and not state.endswith("\n")):
                errors.append(f"{label}.state must be an empty or newline-terminated string")
            markers = value.get("transaction_markers")
            if (
                not isinstance(markers, str)
                or not markers.startswith("SQLT_TXN\t")
                or not markers.endswith("\n")
            ):
                errors.append(f"{label}.transaction_markers must contain marker rows")
            if result == "recovered_error":
                error = value.get("error")
                if not isinstance(error, str) or not error.endswith("\n"):
                    errors.append(f"{label}.error must be a newline-terminated string")


def _validate_prepared_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate the strict MySQL binary-prepared corpus contract."""
    oracles = _load_json(root / "prepared-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("prepared-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("prepared-oracles.json schema_version must be 1")
    state_query = oracles.get("state_query")
    if not isinstance(state_query, str) or not state_query.endswith(".sql"):
        errors.append("prepared-oracles.json state_query must be an SQL path")
    else:
        state_path = root / PurePosixPath(state_query)
        try:
            state_path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append("prepared-oracles.json state_query escapes matrix root")
        if not state_path.is_file():
            errors.append(f"prepared-oracles.json state_query does not exist: {state_query}")

    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "cursor"
            and case.get("capability") == "cursor.mysql_prepared"
        ):
            case_id = case.get("id")
            if isinstance(case_id, str):
                expected[case_id] = set(case.get("dialects", []))
                if expected[case_id] != {"mysql"}:
                    errors.append(f"{case_id} must declare only mysql dialect")
                if case.get("backends") != ["mysql"]:
                    errors.append(f"{case_id} must declare only mysql backend")
                if case.get("frontends") != ["mysql_binary"] or case.get("protocols") != ["mysql_binary"]:
                    errors.append(f"{case_id} must use mysql_binary frontend and protocol")

    results = oracles.get("results")
    if not isinstance(results, dict) or set(results) != set(expected):
        errors.append(
            f"prepared-oracles.json cases must be {sorted(expected)}, got {sorted(results or {})}"
        )
        return
    for case_id, dialects in expected.items():
        value = results[case_id]
        label = f"prepared-oracles.json results.{case_id}"
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        required = {"sql_file", "parameters", "expected", "state"}
        allowed = required | {"control_sql"}
        if set(value) - allowed or not required <= set(value):
            errors.append(f"{label} fields must be a subset of {sorted(allowed)} and include {sorted(required)}")
        sql_file = value.get("sql_file")
        manifest_case = next((case for case in cases if isinstance(case, dict) and case.get("id") == case_id), {})
        if not isinstance(sql_file, str) or not (root / "cases" / PurePosixPath(sql_file)).is_file():
            errors.append(f"{label}.sql_file must name an existing case SQL")
        elif sql_file != manifest_case.get("sql_file"):
            errors.append(f"{label}.sql_file must match manifest sql_file")
        else:
            sql_path = root / "cases" / PurePosixPath(sql_file)
            try:
                sql_path.resolve().relative_to((root / "cases").resolve())
            except ValueError:
                errors.append(f"{label}.sql_file escapes case root")
            else:
                sql_text = "\n".join(sql_path.read_text(encoding="utf-8").splitlines()[4:])
                placeholder_count = len(re.findall(r"(?<!%)%s", sql_text))
                parameters = value.get("parameters")
                if case_id == "SQLT-PRP-007":
                    if isinstance(parameters, list):
                        for index, binding in enumerate(parameters):
                            if not isinstance(binding, list) or len(binding) != placeholder_count:
                                errors.append(f"{label}.parameters[{index}] must bind {placeholder_count} placeholders")
                elif isinstance(parameters, list) and len(parameters) != placeholder_count:
                    errors.append(f"{label}.parameters must bind {placeholder_count} placeholders")
        parameters = value.get("parameters")
        if not isinstance(parameters, list):
            errors.append(f"{label}.parameters must be an array")
        else:
            for index, parameter in enumerate(parameters):
                bindings = parameter if case_id == "SQLT-PRP-007" and isinstance(parameter, list) else [parameter]
                for binding in bindings:
                    if isinstance(binding, dict):
                        if len(binding) != 1 or next(iter(binding), "") not in {"string", "bytes_hex", "decimal", "date", "time", "datetime"}:
                            errors.append(f"{label}.parameters[{index}] has an unknown typed binding")
                        elif "string" in binding:
                            spec = binding["string"]
                            if not isinstance(spec, dict) or set(spec) != {"prefix", "repeat", "count", "suffix"} or not isinstance(spec["count"], int) or spec["count"] < 0 or not all(isinstance(spec[key], str) for key in ("prefix", "repeat", "suffix")):
                                errors.append(f"{label}.parameters[{index}].string has an invalid description")
                        elif "bytes_hex" in binding:
                            if not isinstance(binding["bytes_hex"], str) or re.fullmatch(r"[0-9A-Fa-f]*", binding["bytes_hex"]) is None or len(binding["bytes_hex"]) % 2:
                                errors.append(f"{label}.parameters[{index}].bytes_hex must be even-length hexadecimal")
                        else:
                            key = next(iter(binding))
                            if not isinstance(binding[key], str) or not binding[key]:
                                errors.append(f"{label}.parameters[{index}].{key} must be a non-empty string")
        expected_value = value.get("expected")
        if not isinstance(expected_value, dict):
            errors.append(f"{label}.expected must be an object")
        else:
            required_expected = {"columns", "rows", "errors", "close_recovery"}
            if case_id == "SQLT-PRP-008":
                required_expected |= {"columns_before", "rows_before"}
            if set(expected_value) != required_expected:
                errors.append(f"{label}.expected fields must be {sorted(required_expected)}")
            if not isinstance(expected_value.get("columns"), list) or any(not isinstance(item, str) for item in expected_value.get("columns", [])):
                errors.append(f"{label}.expected.columns must be a string array")
            if not isinstance(expected_value.get("rows"), list) or any(not isinstance(row, list) for row in expected_value.get("rows", [])):
                errors.append(f"{label}.expected.rows must be an array")
            if not isinstance(expected_value.get("errors"), list) or any(not isinstance(item, str) for item in expected_value.get("errors", [])):
                errors.append(f"{label}.expected.errors must be a string array")
            if expected_value.get("close_recovery") != "closed":
                errors.append(f"{label}.expected.close_recovery must be closed")
        state = value.get("state")
        if not isinstance(state, str) or not state.endswith("\n"):
            errors.append(f"{label}.state must be newline-terminated")
        if "control_sql" in value:
            control = value["control_sql"]
            control_path = root / PurePosixPath(control) if isinstance(control, str) else root
            try:
                control_path.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"{label}.control_sql escapes matrix root")
            if not isinstance(control, str) or not control.endswith(".sql") or not control_path.is_file():
                errors.append(f"{label}.control_sql must name an existing SQL fixture")
        elif case_id == "SQLT-PRP-008":
            errors.append(f"{label} must define control_sql")


def _validate_extended_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate PostgreSQL extended-wire actions and exact protocol expectations."""
    oracles = _load_json(root / "extended-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("extended-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("extended-oracles.json schema_version must be 1")
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("extended-oracles.json results must be an object")
        return

    expected_cases: dict[str, dict[str, Any]] = {}
    for case in cases:
        if isinstance(case, dict) and case.get("capability") == "cursor.postgres_extended":
            case_id = case.get("id")
            if isinstance(case_id, str):
                expected_cases[case_id] = case
    if set(results) != set(expected_cases):
        errors.append(
            f"extended-oracles.json cases must be {sorted(expected_cases)}, got {sorted(results)}"
        )

    flows = {
        "SQLT-PGX-001": "lifecycle",
        "SQLT-PGX-002": "parameters",
        "SQLT-PGX-003": "rebind",
        "SQLT-PGX-004": "multiple_portals",
        "SQLT-PGX-005": "paging",
        "SQLT-PGX-006": "binary_description",
        "SQLT-PGX-007": "error_recovery",
        "SQLT-PGX-008": "transaction_status",
    }
    expected_fields = {
        "lifecycle": {"rows", "ready"},
        "parameters": {"rows", "ready"},
        "rebind": {"rows", "ready"},
        "multiple_portals": {"rows", "ready"},
        "paging": {"rows", "page_end", "ready"},
        "binary_description": {"columns", "type_oids", "format_codes", "rows", "ready"},
        "error_recovery": {
            "sqlstate", "rows", "ignored_value_absent", "ignored_messages_absent", "ready"
        },
        "transaction_status": {"sqlstate", "rows", "ready"},
    }
    for case_id, case in expected_cases.items():
        label = f"extended-oracles.json results.{case_id}"
        value = results.get(case_id)
        if not isinstance(value, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(value) != {"sql_file", "flow", "parameters", "expected"}:
            errors.append(f"{label} fields must be ['expected', 'flow', 'parameters', 'sql_file']")
            continue
        if value.get("sql_file") != case.get("sql_file"):
            errors.append(f"{label}.sql_file must match manifest sql_file")
        flow = value.get("flow")
        if flow != flows.get(case_id):
            errors.append(f"{label}.flow must be {flows.get(case_id)!r}")
        parameters = value.get("parameters")
        if not isinstance(parameters, list):
            errors.append(f"{label}.parameters must be an array")
        elif any(
            item is not None and not isinstance(item, (str, list))
            or isinstance(item, list) and any(v is not None and not isinstance(v, str) for v in item)
            for item in parameters
        ):
            errors.append(f"{label}.parameters must contain strings, nulls, or string/null arrays")
        expected = value.get("expected")
        if not isinstance(expected, dict):
            errors.append(f"{label}.expected must be an object")
            continue
        required = expected_fields.get(flow, set())
        if set(expected) != required:
            errors.append(f"{label}.expected fields must be {sorted(required)}")
        rows = expected.get("rows")
        if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
            errors.append(f"{label}.expected.rows must be an array of arrays")
        ready = expected.get("ready")
        if not isinstance(ready, list) or any(status not in {"I", "T", "E"} for status in ready):
            errors.append(f"{label}.expected.ready must contain only I, T, or E")
        if "sqlstate" in expected and re.fullmatch(r"[0-9A-Z]{5}", str(expected["sqlstate"])) is None:
            errors.append(f"{label}.expected.sqlstate must be a five-character SQLSTATE")

        if case.get("family") != "cursor":
            errors.append(f"{case_id} must use cursor family")
        if case.get("dialects") != ["postgres"] or case.get("backends") != ["postgres"]:
            errors.append(f"{case_id} must declare only postgres dialect and backend")
        if case.get("frontends") != ["pg_extended"] or case.get("protocols") != ["pg_extended"]:
            errors.append(f"{case_id} must use only pg_extended frontend and protocol")


def _sql_step_names(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[4:]
    except (OSError, UnicodeError):
        return []
    return [line.removeprefix("-- @step ").strip() for line in lines if line.startswith("-- @step ")]


def _validate_cursor_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate the simple-query named-cursor step contract."""
    oracles = _load_json(root / "cursor-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("cursor-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("cursor-oracles.json schema_version must be 1")
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("cursor-oracles.json results must be an object")
        return
    expected: dict[str, dict[str, Any]] = {}
    for case in cases:
        if isinstance(case, dict) and case.get("capability") == "cursor.named_forward":
            case_id = case.get("id")
            if isinstance(case_id, str):
                expected[case_id] = case
    if set(results) != set(expected):
        errors.append(f"cursor-oracles.json cases must be {sorted(expected)}, got {sorted(results)}")
    observable_fields = {"rows", "commands", "ready", "sqlstates", "control_rows", "eof"}
    allowed_step_fields = observable_fields | {"action", "direct", "gateway"}
    allowed_actions = {"backend_terminate", "reconnect_after_backend_failure"}
    for case_id, case in expected.items():
        label = f"cursor-oracles.json results.{case_id}"
        value = results.get(case_id)
        if not isinstance(value, dict) or set(value) != {"sql_file", "cleanup", "steps"}:
            errors.append(f"{label} fields must be ['cleanup', 'sql_file', 'steps']")
            continue
        if value["sql_file"] != case.get("sql_file"):
            errors.append(f"{label}.sql_file must match manifest")
        sql_path = root / "cases" / PurePosixPath(value["sql_file"])
        try:
            sql_path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label}.sql_file escapes matrix root")
            continue
        if not sql_path.is_file():
            errors.append(f"{label}.sql_file does not exist")
            continue
        steps = value["steps"]
        if not isinstance(steps, dict) or not steps:
            errors.append(f"{label}.steps must be a non-empty object")
            continue
        names = _sql_step_names(sql_path)
        if names != list(steps):
            errors.append(f"{label}.steps must match SQL @step order {names}")
        if value["cleanup"] not in {"none", "session_disconnect", "backend_disconnect"}:
            errors.append(f"{label}.cleanup is unknown")
        for name, step in steps.items():
            step_label = f"{label}.steps.{name}"
            if not isinstance(step, dict) or not set(step) <= allowed_step_fields:
                errors.append(f"{step_label} has unknown fields")
                continue
            if not (set(step) & (observable_fields | {"direct", "gateway"})):
                errors.append(f"{step_label} needs an observable contract")
            if "direct" in step or "gateway" in step:
                if set(step) - {"action", "direct", "gateway"} or not {"direct", "gateway"} <= set(step):
                    errors.append(f"{step_label} path-specific fields must be action, direct, and gateway")
                else:
                    for path_name in ("direct", "gateway"):
                        path_value = step[path_name]
                        if not isinstance(path_value, dict) or not path_value or not set(path_value) <= observable_fields:
                            errors.append(f"{step_label}.{path_name} has invalid fields")
                            continue
                        if "sqlstates" in path_value and (
                            not isinstance(path_value["sqlstates"], list)
                            or any(
                                not isinstance(state, str)
                                or not re.fullmatch(r"[0-9A-Z]{5}", state)
                                for state in path_value["sqlstates"]
                            )
                        ):
                            errors.append(f"{step_label}.{path_name}.sqlstates must contain SQLSTATE values")
                        if "ready" in path_value and (
                            not isinstance(path_value["ready"], list)
                            or any(status not in {"I", "T", "E"} for status in path_value["ready"])
                        ):
                            errors.append(f"{step_label}.{path_name}.ready must contain I, T, or E")
                        if "eof" in path_value and path_value["eof"] is not True:
                            errors.append(f"{step_label}.{path_name}.eof must be true")
                continue
            for field in ("rows", "control_rows"):
                if field in step and (
                    not isinstance(step[field], list)
                    or any(
                        not isinstance(row, list)
                        or any(not isinstance(cell, str) and cell is not None for cell in row)
                        for row in step[field]
                    )
                ):
                    errors.append(f"{step_label}.{field} must be an array of string/null arrays")
            for field in ("commands", "ready", "sqlstates"):
                if field in step and (
                    not isinstance(step[field], list)
                    or any(not isinstance(value, str) for value in step[field])
                ):
                    errors.append(f"{step_label}.{field} must be an array of strings")
            if "sqlstates" in step and any(not re.fullmatch(r"[0-9A-Z]{5}", v) for v in step["sqlstates"]):
                errors.append(f"{step_label}.sqlstates must contain SQLSTATE values")
            if "eof" in step and step["eof"] is not True:
                errors.append(f"{step_label}.eof must be true")
            if "action" in step and step["action"] not in allowed_actions:
                errors.append(f"{step_label}.action is unknown")
        sql_lines = sql_path.read_text(encoding="utf-8").splitlines()[4:]
        actions: dict[str, str] = {}
        current_step: str | None = None
        for line in sql_lines:
            if line.startswith("-- @step "):
                current_step = line.removeprefix("-- @step ").strip()
            elif line.startswith("-- @action "):
                action = line.removeprefix("-- @action ").strip()
                if current_step is None:
                    errors.append(f"{label}: @action must follow @step")
                elif action not in allowed_actions:
                    errors.append(f"{label}.steps.{current_step}: unknown action {action!r}")
                elif current_step in actions:
                    errors.append(f"{label}.steps.{current_step}: duplicate action")
                else:
                    actions[current_step] = action
        if case_id == "SQLT-CURSOR-008":
            if actions.get("terminate_backend") != "backend_terminate":
                errors.append(f"{label}.steps.terminate_backend must declare backend_terminate")
            elif steps.get("terminate_backend", {}).get("action") != "backend_terminate":
                errors.append(f"{label}.steps.terminate_backend.action must match SQL @action")
            if actions.get("fetch_after_terminate") != "reconnect_after_backend_failure":
                errors.append(f"{label}.steps.fetch_after_terminate must declare reconnect action")
        elif actions:
            errors.append(f"{label}: actions are only allowed for SQLT-CURSOR-008")
        if case.get("frontends") != ["pg_simple"] or case.get("protocols") != ["pg_simple"]:
            errors.append(f"{case_id} must use only pg_simple frontend and protocol")
        if case.get("dialects") != ["postgres"] or case.get("backends") != ["postgres"]:
            errors.append(f"{case_id} must declare only postgres dialect and backend")


def _validate_ddl_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate exact catalog and stable error contracts for canonical DDL cases."""
    oracles = _load_json(root / "ddl-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("ddl-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("ddl-oracles.json schema_version must be 1")

    catalog_queries = oracles.get("catalog_queries")
    if not isinstance(catalog_queries, dict) or set(catalog_queries) != {"mysql", "postgres"}:
        errors.append("ddl-oracles.json catalog_queries must define mysql and postgres")
        catalog_queries = {}
    for dialect, relative in catalog_queries.items():
        label = f"ddl-oracles.json catalog_queries.{dialect}"
        if not isinstance(relative, str) or not relative.endswith(".sql"):
            errors.append(f"{label} must be an SQL path")
            continue
        path = root / PurePosixPath(relative)
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label} escapes matrix root")
            continue
        if not path.is_file():
            errors.append(f"{label} does not exist: {relative}")

    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "ddl"
            and case.get("capability") not in {"ddl.temporary_table", "ddl.database_boundary"}
            and isinstance(case.get("id"), str)
        ):
            expected[case["id"]] = {
                dialect for dialect in case.get("dialects", []) if isinstance(dialect, str)
            }

    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("ddl-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"ddl-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(
                f"ddl-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
            continue
        for dialect, value in values.items():
            label = f"ddl-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict):
                errors.append(f"{label} must be an object")
                continue
            result = value.get("result")
            if result not in {"success", "error"}:
                errors.append(f"{label}.result must be success or error")
            state = value.get("state")
            if not isinstance(state, str) or (state and not state.endswith("\n")):
                errors.append(f"{label}.state must be an empty or newline-terminated string")
            setup = value.get("setup")
            if setup is not None:
                if not isinstance(setup, str) or not setup.endswith(".sql"):
                    errors.append(f"{label}.setup must be null or an SQL path")
                else:
                    path = root / PurePosixPath(setup)
                    try:
                        path.resolve().relative_to(root.resolve())
                    except ValueError:
                        errors.append(f"{label}.setup escapes matrix root")
                        continue
                    if not path.is_file():
                        errors.append(f"{label}.setup does not exist: {setup}")
            unchanged = value.get("unchanged")
            if "unchanged" in value and type(unchanged) is not bool:
                errors.append(f"{label}.unchanged must be a boolean")
            error = value.get("error")
            if result == "success" and "error" in value:
                errors.append(f"{label} success oracle cannot define error")
            if result == "error":
                if not isinstance(error, str) or not error.endswith("\n"):
                    errors.append(f"{label}.error must be a newline-terminated string")
                if unchanged is not True:
                    errors.append(f"{label} error oracle must define unchanged=true")
            data_fields = {"data_query", "before_data", "after_data"}
            present_data_fields = data_fields & set(value)
            if present_data_fields and present_data_fields != data_fields:
                errors.append(
                    f"{label} must define data_query, before_data, and after_data together"
                )
            if present_data_fields == data_fields:
                data_query = value["data_query"]
                if not isinstance(data_query, str) or not data_query.endswith(".sql"):
                    errors.append(f"{label}.data_query must be an SQL path")
                else:
                    path = root / PurePosixPath(data_query)
                    try:
                        path.resolve().relative_to(root.resolve())
                    except ValueError:
                        errors.append(f"{label}.data_query escapes matrix root")
                    else:
                        if not path.is_file():
                            errors.append(f"{label}.data_query does not exist: {data_query}")
                for field in ("before_data", "after_data"):
                    output = value[field]
                    if not isinstance(output, str) or (output and not output.endswith("\n")):
                        errors.append(
                            f"{label}.{field} must be an empty or newline-terminated string"
                        )
            error_probe_fields = {"error_probe", "probe_error"}
            present_error_probe_fields = error_probe_fields & set(value)
            if present_error_probe_fields and present_error_probe_fields != error_probe_fields:
                errors.append(
                    f"{label} must define error_probe and probe_error together"
                )
            if present_error_probe_fields == error_probe_fields:
                error_probe = value["error_probe"]
                if not isinstance(error_probe, str) or not error_probe.endswith(".sql"):
                    errors.append(f"{label}.error_probe must be an SQL path")
                else:
                    path = root / PurePosixPath(error_probe)
                    try:
                        path.resolve().relative_to(root.resolve())
                    except ValueError:
                        errors.append(f"{label}.error_probe escapes matrix root")
                    else:
                        if not path.is_file():
                            errors.append(
                                f"{label}.error_probe does not exist: {error_probe}"
                            )
                probe_error = value["probe_error"]
                if not isinstance(probe_error, str) or not probe_error.endswith("\n"):
                    errors.append(
                        f"{label}.probe_error must be a newline-terminated string"
                    )
                if result != "success":
                    errors.append(f"{label} error probes require a success oracle")


def _validate_ddl_temp_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate connection-scoped temporary-table behavior contracts."""
    oracles = _load_json(root / "ddl-temp-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("ddl-temp-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("ddl-temp-oracles.json schema_version must be 1")
    expected = {
        case["id"]: {dialect for dialect in case.get("dialects", []) if isinstance(dialect, str)}
        for case in cases
        if isinstance(case, dict)
        and case.get("capability") == "ddl.temporary_table"
        and isinstance(case.get("id"), str)
    }
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("ddl-temp-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"ddl-temp-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    fields = {"same_session", "isolated_session_error", "after_disconnect_error"}
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(
                f"ddl-temp-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
            continue
        for dialect, value in values.items():
            label = f"ddl-temp-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict) or set(value) != fields:
                errors.append(f"{label} fields must be {sorted(fields)}")
                continue
            for field, output in value.items():
                if not isinstance(output, str) or not output.endswith("\n"):
                    errors.append(f"{label}.{field} must be a newline-terminated string")


def _validate_ddl_database_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate the restricted-account MySQL database privilege boundary contract."""
    oracles = _load_json(root / "ddl-database-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("ddl-database-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("ddl-database-oracles.json schema_version must be 1")

    expected = {
        case["id"]: {dialect for dialect in case.get("dialects", []) if isinstance(dialect, str)}
        for case in cases
        if isinstance(case, dict)
        and case.get("family") == "ddl"
        and case.get("capability") == "ddl.database_boundary"
        and isinstance(case.get("id"), str)
    }
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("ddl-database-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"ddl-database-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    for case_id, dialects in expected.items():
        if dialects != {"mysql"}:
            errors.append(f"{case_id} must be MySQL-only")

    for field in ("catalog_query", "restricted_catalog_query", "identity_query"):
        relative = oracles.get(field)
        label = f"ddl-database-oracles.json {field}"
        if not isinstance(relative, str) or not relative.endswith(".sql"):
            errors.append(f"{label} must be an SQL path")
            continue
        path = root / PurePosixPath(relative)
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label} escapes matrix root")
        else:
            if not path.is_file():
                errors.append(f"{label} does not exist: {relative}")

    fields = {"result", "setup", "error", "root_state", "restricted_state", "identity", "unchanged"}
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(
                f"ddl-database-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
            continue
        for dialect, value in values.items():
            label = f"ddl-database-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict) or set(value) != fields:
                errors.append(f"{label} fields must be {sorted(fields)}")
                continue
            if value["result"] != "error":
                errors.append(f"{label}.result must be error")
            setup = value["setup"]
            if not isinstance(setup, str) or not setup.endswith(".sql"):
                errors.append(f"{label}.setup must be an SQL path")
            else:
                path = root / PurePosixPath(setup)
                try:
                    path.resolve().relative_to(root.resolve())
                except ValueError:
                    errors.append(f"{label}.setup escapes matrix root")
                else:
                    if not path.is_file():
                        errors.append(f"{label}.setup does not exist: {setup}")
            for field in ("error", "root_state", "restricted_state", "identity"):
                output = value[field]
                if not isinstance(output, str) or (output and not output.endswith("\n")):
                    errors.append(f"{label}.{field} must be an empty or newline-terminated string")
            if value["unchanged"] is not True:
                errors.append(f"{label}.unchanged must be true")


def _validate_invalid_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate stable error identities and unchanged probes for invalid SQL."""
    oracles = _load_json(root / "invalid-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("invalid-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("invalid-oracles.json schema_version must be 1")

    probe_queries = oracles.get("probe_queries")
    if not isinstance(probe_queries, dict) or set(probe_queries) != {"mysql", "postgres"}:
        errors.append("invalid-oracles.json probe_queries must define mysql and postgres")
        probe_queries = {}
    for dialect, relative in probe_queries.items():
        label = f"invalid-oracles.json probe_queries.{dialect}"
        if not isinstance(relative, str) or not relative.endswith(".sql"):
            errors.append(f"{label} must be an SQL path")
            continue
        path = root / PurePosixPath(relative)
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label} escapes matrix root")
            continue
        if not path.is_file():
            errors.append(f"{label} does not exist: {relative}")

    probe_state = oracles.get("probe_state")
    if not isinstance(probe_state, dict) or set(probe_state) != {"mysql", "postgres"}:
        errors.append("invalid-oracles.json probe_state must define mysql and postgres")
    else:
        for dialect, value in probe_state.items():
            if not isinstance(value, str) or not value.endswith("\n"):
                errors.append(
                    f"invalid-oracles.json probe_state.{dialect} must be newline-terminated"
                )

    deterministic_capabilities = {
        "invalid.syntax",
        "invalid.name_resolution",
        "invalid.type_assignment",
        "invalid.numeric_range",
        "invalid.expression",
    }
    expected: dict[str, set[str]] = {}
    for case in cases:
        if (
            isinstance(case, dict)
            and case.get("family") == "invalid"
            and case.get("capability") in deterministic_capabilities
            and isinstance(case.get("id"), str)
        ):
            allowed_frontends = {"mysql_text", "pg_simple"}
            if set(case.get("frontends", [])) - allowed_frontends:
                errors.append(
                    f"{case['id']} invalid corpus supports only mysql_text and pg_simple frontends"
                )
            if set(case.get("protocols", [])) != set(case.get("frontends", [])):
                errors.append(
                    f"{case['id']} invalid corpus protocols must match frontends"
                )
            expected[case["id"]] = {
                dialect
                for dialect in case.get("dialects", [])
                if isinstance(dialect, str)
            }

    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("invalid-oracles.json results must be an object")
        return
    if set(results) != set(expected):
        errors.append(
            f"invalid-oracles.json cases must be {sorted(expected)}, got {sorted(results)}"
        )
    fields = {"class", "error", "unchanged"}
    for case_id, dialects in expected.items():
        values = results.get(case_id)
        if not isinstance(values, dict) or set(values) != dialects:
            errors.append(
                f"invalid-oracles.json results.{case_id} dialects must be {sorted(dialects)}"
            )
            continue
        for dialect, value in values.items():
            label = f"invalid-oracles.json results.{case_id}.{dialect}"
            if not isinstance(value, dict) or set(value) != fields:
                errors.append(f"{label} fields must be {sorted(fields)}")
                continue
            if value["class"] != "backend_error":
                errors.append(f"{label}.class must be backend_error")
            error = value["error"]
            pattern = (
                r"mysql\t[0-9]+\t[0-9A-Z]{5}\n"
                if dialect == "mysql"
                else r"postgres\t[0-9A-Z]{5}\n"
            )
            if not isinstance(error, str) or re.fullmatch(pattern, error) is None:
                errors.append(f"{label}.error must be a stable {dialect} error identity")
            if value["unchanged"] is not True:
                errors.append(f"{label}.unchanged must be true")


def _validate_boundary_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate SQLT-3F2 protocol/lexical/resource boundary ownership and exact results."""
    oracles = _load_json(root / "boundary-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("boundary-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("boundary-oracles.json schema_version must be 1")

    for field in ("probe_queries", "probe_state"):
        values = oracles.get(field)
        if not isinstance(values, dict) or set(values) != {"mysql", "postgres"}:
            errors.append(f"boundary-oracles.json {field} must define mysql and postgres")
            continue
        for dialect, value in values.items():
            label = f"boundary-oracles.json {field}.{dialect}"
            if field == "probe_state":
                if not isinstance(value, str) or not value.endswith("\n"):
                    errors.append(f"{label} must be newline-terminated")
                continue
            if not isinstance(value, str) or not value.endswith(".sql"):
                errors.append(f"{label} must be an SQL path")
                continue
            path = root / PurePosixPath(value)
            try:
                path.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"{label} escapes matrix root")
            else:
                if not path.is_file():
                    errors.append(f"{label} does not exist: {value}")

    capabilities = {
        "invalid.protocol_bind",
        "invalid.lexical_boundary",
        "invalid.resource_boundary",
    }
    expected_cases: dict[str, dict[str, Any]] = {}
    for case in cases:
        if isinstance(case, dict) and case.get("family") == "invalid" and case.get("capability") in capabilities:
            case_id = case.get("id")
            if isinstance(case_id, str):
                expected_cases[case_id] = case
    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("boundary-oracles.json results must be an object")
        return
    if set(results) != set(expected_cases):
        errors.append(
            f"boundary-oracles.json cases must be {sorted(expected_cases)}, got {sorted(results)}"
        )

    flows = {
        "SQLT-INVALID-014": ("mysql_bind", {"mysql_binary"}),
        "SQLT-INVALID-015": ("pg_bind", {"pg_extended"}),
        "SQLT-INVALID-016": ("multi_statement", {"pg_simple"}),
        "SQLT-INVALID-017": ("comments", {"mysql_text", "pg_simple"}),
        "SQLT-INVALID-018": ("bound_value", {"mysql_binary", "pg_extended"}),
        "SQLT-INVALID-019": ("identifier", {"mysql_text", "pg_simple"}),
        "SQLT-INVALID-020": ("nested_in", {"mysql_text", "pg_simple"}),
        "SQLT-INVALID-021": ("message_limit", {"pg_simple"}),
    }
    generation_limits = {
        "SQLT-INVALID-020": {"nesting": 64, "in_items": 2048},
        "SQLT-INVALID-021": {"message_bytes": 16 * 1024 * 1024, "over_bytes": 16 * 1024 * 1024 + 1},
    }
    for case_id, case in expected_cases.items():
        value = results.get(case_id)
        label = f"boundary-oracles.json results.{case_id}"
        if not isinstance(value, dict) or set(value) != {"sql_file", "flow", "expected"}:
            errors.append(f"{label} fields must be ['expected', 'flow', 'sql_file']")
            continue
        if value.get("sql_file") != case.get("sql_file"):
            errors.append(f"{label}.sql_file must match manifest sql_file")
        flow, frontends = flows.get(case_id, (None, set()))
        if value.get("flow") != flow:
            errors.append(f"{label}.flow must be {flow!r}")
        if set(case.get("frontends", [])) != frontends or set(case.get("protocols", [])) != frontends:
            errors.append(f"{case_id} frontends and protocols must be {sorted(frontends)}")
        if case.get("side_effect") != "none":
            errors.append(f"{case_id}.side_effect must be none")

        dialects = {dialect for dialect in case.get("dialects", []) if isinstance(dialect, str)}
        expected = value.get("expected")
        if not isinstance(expected, dict) or set(expected) != dialects:
            errors.append(f"{label}.expected dialects must be {sorted(dialects)}")
        else:
            for dialect, paths in expected.items():
                path_label = f"{label}.expected.{dialect}"
                if not isinstance(paths, dict) or set(paths) != {"direct", "gateway"}:
                    errors.append(f"{path_label} must define direct and gateway")
                    continue
                for path, semantic in paths.items():
                    if not isinstance(semantic, dict) or not semantic:
                        errors.append(f"{path_label}.{path} must be a non-empty exact semantic object")
                    elif _contains_fuzzy_any(semantic):
                        errors.append(f"{path_label}.{path} must not contain fuzzy any values")

        sql_path = root / "cases" / PurePosixPath(str(case.get("sql_file", "")))
        directives: dict[str, int] = {}
        if sql_path.is_file():
            for line in sql_path.read_text(encoding="utf-8").splitlines()[4:]:
                if line.startswith("-- @generate "):
                    try:
                        directives = {
                            key: int(number)
                            for key, number in (field.split("=", 1) for field in line.removeprefix("-- @generate ").split())
                        }
                    except (TypeError, ValueError):
                        errors.append(f"{case_id} has an invalid @generate directive")
        required_generation = generation_limits.get(case_id, {})
        if directives != required_generation:
            errors.append(f"{case_id} @generate values must be {required_generation}")


def _unsupported_sql_steps(path: Path, dialect: str, label: str, errors: list[str]) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()[4:]
    body = "\n".join(lines).strip()
    marker = re.compile(r"^-- @step ([a-z][a-z0-9_]*) (mysql|postgres)$", re.MULTILINE)
    matches = list(marker.finditer(body))
    if not matches:
        return ["main"]
    if body[: matches[0].start()].strip():
        errors.append(f"{label} must not contain SQL before the first @step")
    names: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, match in enumerate(matches):
        name, step_dialect = match.groups()
        key = (name, step_dialect)
        if key in seen:
            errors.append(f"{label} repeats @step {name} for {step_dialect}")
        seen.add(key)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        if not body[match.end() : end].strip():
            errors.append(f"{label} @step {name} for {step_dialect} has no SQL")
        if step_dialect == dialect:
            names.append(name)
    if not names:
        errors.append(f"{label} has no @step for {dialect}")
    return names


def _validate_unsupported_oracles(root: Path, cases: list[Any], errors: list[str]) -> None:
    """Validate SQLT-3F3 exact dangerous capability and vendor calibration contracts."""
    oracles = _load_json(root / "unsupported-oracles.json", errors)
    if not isinstance(oracles, dict):
        errors.append("unsupported-oracles.json must contain an object")
        return
    if oracles.get("schema_version") != 1:
        errors.append("unsupported-oracles.json schema_version must be 1")

    probe_queries = oracles.get("probe_queries")
    if not isinstance(probe_queries, dict) or set(probe_queries) != {"mysql", "postgres"}:
        errors.append("unsupported-oracles.json probe_queries must define mysql and postgres")
    else:
        for dialect, relative in probe_queries.items():
            label = f"unsupported-oracles.json probe_queries.{dialect}"
            if not isinstance(relative, str) or not relative.endswith(".sql"):
                errors.append(f"{label} must be an SQL path")
                continue
            path = root / PurePosixPath(relative)
            try:
                path.resolve().relative_to(root.resolve())
            except ValueError:
                errors.append(f"{label} escapes matrix root")
            else:
                if not path.is_file():
                    errors.append(f"{label} does not exist: {relative}")

    expected_ids = {f"SQLT-UNSUPPORTED-{index:03d}" for index in range(1, 10)}
    unsupported_cases = {
        case.get("id"): case
        for case in cases
        if isinstance(case, dict) and case.get("family") == "unsupported"
    }
    if set(unsupported_cases) != expected_ids:
        errors.append(
            "unsupported manifest cases must be "
            f"{sorted(expected_ids)}, got {sorted(unsupported_cases)}"
        )

    results = oracles.get("results")
    if not isinstance(results, dict):
        errors.append("unsupported-oracles.json results must be an object")
        return
    if set(results) != expected_ids:
        errors.append(
            "unsupported-oracles.json cases must be "
            f"{sorted(expected_ids)}, got {sorted(results)}"
        )

    allowed_capabilities = {
        "postgres.copy_program",
        "postgres.copy_file",
        "postgres.do",
        "stored_procedure.call",
        "mysql.load_data",
        "mysql.outfile",
        "postgres.maintenance",
        "sql.cross_dialect",
        "sql.privileged_catalog_session",
    }
    forbidden_payloads = (
        "/Users/", "/Volumes/", "/private/", "/tmp/", "/etc/",
        "printf ", "bash ", "sh -c", "curl ", "wget ", "password", "secret",
    )

    for case_id in sorted(expected_ids):
        case = unsupported_cases.get(case_id)
        value = results.get(case_id)
        if not isinstance(case, dict) or not isinstance(value, dict):
            continue
        label = f"unsupported-oracles.json results.{case_id}"
        dialects = {item for item in case.get("dialects", []) if isinstance(item, str)}
        expected_frontends = {
            "mysql_text" if dialect == "mysql" else "pg_simple" for dialect in dialects
        }
        if set(case.get("frontends", [])) != expected_frontends:
            errors.append(f"{case_id}.frontends must be {sorted(expected_frontends)}")
        if set(case.get("protocols", [])) != expected_frontends:
            errors.append(f"{case_id}.protocols must be {sorted(expected_frontends)}")
        if set(case.get("backends", [])) != dialects:
            errors.append(f"{case_id}.backends must match dialects")
        if case.get("side_effect") != "none":
            errors.append(f"{case_id}.side_effect must be none")
        if case.get("transaction_mode") != "autocommit" or case.get("parameter_mode") != "none":
            errors.append(f"{case_id} must use autocommit without parameters")
        if case.get("expectations") != [{"policy": "security_off", "outcome": "unsupported"}]:
            errors.append(f"{case_id}.expectations must contain only security_off unsupported")

        flow = value.get("flow")
        if not isinstance(flow, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", flow):
            errors.append(f"{label}.flow must be a stable lowercase identifier")
        expected = value.get("expected")
        if not isinstance(expected, dict) or set(expected) != dialects:
            errors.append(f"{label}.expected dialects must be {sorted(dialects)}")
            continue

        sql_path = root / "cases" / PurePosixPath(str(case.get("sql_file", "")))
        if sql_path.is_file():
            sql_text = sql_path.read_text(encoding="utf-8")
            lowered = sql_text.lower()
            for forbidden in forbidden_payloads:
                if forbidden.lower() in lowered:
                    errors.append(f"{case_id} SQL contains forbidden sensitive payload {forbidden!r}")

        for dialect, paths in expected.items():
            path_label = f"{label}.expected.{dialect}"
            if not isinstance(paths, dict) or set(paths) != {"direct", "gateway"}:
                errors.append(f"{path_label} must define direct and gateway")
                continue
            step_names = _unsupported_sql_steps(sql_path, dialect, case_id, errors) if sql_path.is_file() else []
            for path_name, steps in paths.items():
                steps_label = f"{path_label}.{path_name}"
                if not isinstance(steps, list) or not steps:
                    errors.append(f"{steps_label} must be a non-empty exact step array")
                    continue
                if _contains_fuzzy_any(steps):
                    errors.append(f"{steps_label} must not contain fuzzy any values")
                if [step.get("name") for step in steps if isinstance(step, dict)] != step_names:
                    errors.append(f"{steps_label} step names must be {step_names}")
                for index, step in enumerate(steps):
                    step_label = f"{steps_label}[{index}]"
                    if not isinstance(step, dict):
                        errors.append(f"{step_label} must be an object")
                        continue
                    required = {"name", "result", "error"}
                    if dialect == "postgres":
                        required.add("ready")
                    if set(step) != required:
                        errors.append(f"{step_label} fields must be {sorted(required)}")
                    if step.get("result") != "error":
                        errors.append(f"{step_label}.result must be error")
                    error = step.get("error")
                    error_fields = {"vendor", "code", "capability"}
                    if dialect == "mysql":
                        error_fields.add("sqlstate")
                    if not isinstance(error, dict) or set(error) != error_fields:
                        errors.append(f"{step_label}.error fields must be {sorted(error_fields)}")
                        continue
                    if error.get("vendor") != dialect:
                        errors.append(f"{step_label}.error.vendor must be {dialect}")
                    code = error.get("code")
                    if dialect == "mysql":
                        if not isinstance(code, int) or isinstance(code, bool) or code <= 0:
                            errors.append(f"{step_label}.error.code must be a positive MySQL error number")
                        if not isinstance(error.get("sqlstate"), str) or not re.fullmatch(r"[0-9A-Z]{5}", error["sqlstate"]):
                            errors.append(f"{step_label}.error.sqlstate must be a five-character SQLSTATE")
                    else:
                        if not isinstance(code, str) or not re.fullmatch(r"[0-9A-Z]{5}", code):
                            errors.append(f"{step_label}.error.code must be a five-character SQLSTATE")
                        if step.get("ready") != ["I"]:
                            errors.append(f"{step_label}.ready must be ['I']")
                    capability = error.get("capability")
                    if path_name == "direct" and capability is not None:
                        errors.append(f"{step_label}.error.capability must be null for direct")
                    if path_name == "gateway":
                        if capability not in allowed_capabilities:
                            errors.append(f"{step_label}.error.capability is not an allowed stable capability")
                        if dialect == "mysql" and (code, error.get("sqlstate")) != (1105, "HY000"):
                            errors.append(f"{step_label} gateway MySQL identity must be 1105/HY000")
                        if dialect == "postgres" and code != "0A000":
                            errors.append(f"{step_label} gateway PostgreSQL identity must be 0A000")


def _contains_fuzzy_any(value: Any) -> bool:
    if value == "any":
        return True
    if isinstance(value, dict):
        return any(_contains_fuzzy_any(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_fuzzy_any(item) for item in value)
    return False


def _validate_string_array(
    case: dict[str, Any],
    field: str,
    known: dict[str, set[str]],
    case_id: str,
    errors: list[str],
) -> list[str]:
    values = case.get(field)
    value_set = _string_set(values, f"{case_id}.{field}", errors)
    unknown = value_set - known.get(field, set())
    if unknown:
        errors.append(f"{case_id}.{field} has unknown values: {sorted(unknown)}")
    return values if isinstance(values, list) else []


def _validate_case(
    case: Any,
    index: int,
    root: Path,
    case_root: Path,
    known: dict[str, set[str]],
    errors: list[str],
) -> tuple[str | None, Path | None]:
    label = f"cases[{index}]"
    if not isinstance(case, dict):
        errors.append(f"{label} must be an object")
        return None, None

    case_id = case.get("id")
    if not isinstance(case_id, str) or not CASE_ID_RE.fullmatch(case_id):
        errors.append(f"{label}.id must match {CASE_ID_RE.pattern}")
        case_id = label

    for field in ("family", "capability", "side_effect"):
        if not isinstance(case.get(field), str) or not case[field]:
            errors.append(f"{case_id}.{field} must be a non-empty string")

    if case.get("family") not in known.get("families", set()):
        errors.append(f"{case_id}.family is unknown: {case.get('family')!r}")
    if case.get("side_effect") not in known.get("side_effects", set()):
        errors.append(f"{case_id}.side_effect is unknown: {case.get('side_effect')!r}")
    if case.get("capability") not in known.get("sql_capabilities", set()):
        errors.append(f"{case_id}.capability is unknown: {case.get('capability')!r}")

    dialects = _validate_string_array(case, "dialects", known, case_id, errors)
    for field in ("frontends", "backends", "protocols", "profiles"):
        _validate_string_array(case, field, known, case_id, errors)

    for field, registry_field in (
        ("statement_mode", "statement_modes"),
        ("transaction_mode", "transaction_modes"),
        ("parameter_mode", "parameter_modes"),
    ):
        value = case.get(field)
        if value not in known.get(registry_field, set()):
            errors.append(f"{case_id}.{field} is unknown: {value!r}")

    if "outcome" in case:
        errors.append(
            f"{case_id}.outcome is ambiguous; map each policy in expectations instead"
        )
    expectations = case.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        errors.append(f"{case_id}.expectations must be a non-empty array")
    else:
        seen_policies: set[str] = set()
        for expectation_index, expectation in enumerate(expectations):
            expectation_label = f"{case_id}.expectations[{expectation_index}]"
            if not isinstance(expectation, dict):
                errors.append(f"{expectation_label} must be an object")
                continue
            policy = expectation.get("policy")
            outcome = expectation.get("outcome")
            if policy not in known.get("policies", set()):
                errors.append(f"{expectation_label}.policy is unknown: {policy!r}")
            if outcome not in known.get("outcomes", set()):
                errors.append(f"{expectation_label}.outcome is unknown: {outcome!r}")
            if isinstance(policy, str) and policy in seen_policies:
                errors.append(f"{case_id}.expectations repeats policy {policy!r}")
            if isinstance(policy, str):
                seen_policies.add(policy)

    skip = case.get("skip")
    if skip is not None:
        if not isinstance(skip, dict):
            errors.append(f"{case_id}.skip must be an object")
        else:
            for field in ("reason", "issue", "expires_when"):
                if not isinstance(skip.get(field), str) or not skip[field].strip():
                    errors.append(f"{case_id}.skip.{field} must be a non-empty string")

    sql_file = case.get("sql_file")
    if not isinstance(sql_file, str) or not sql_file:
        errors.append(f"{case_id}.sql_file must be a non-empty string")
        return case.get("id"), None
    relative_path = PurePosixPath(sql_file)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        errors.append(f"{case_id}.sql_file must stay below the case root")
        return case.get("id"), None
    if relative_path.suffix != ".sql":
        errors.append(f"{case_id}.sql_file must end in .sql")
        return case.get("id"), None

    sql_path = case_root.joinpath(*relative_path.parts)
    try:
        sql_path.resolve().relative_to(case_root.resolve())
    except ValueError:
        errors.append(f"{case_id}.sql_file resolves outside the case root")
        return case.get("id"), None
    _validate_sql_file(sql_path, str(case_id), dialects, errors)
    return case.get("id"), sql_path


def _validate_cross_protocol_matrix(
    root: Path, manifest: dict[str, Any], errors: list[str]
) -> set[Path]:
    spec_path = root / "cross-protocol-matrix.json"
    if not spec_path.is_file():
        return set()
    selector_spec = importlib.util.spec_from_file_location(
        "sql_matrix_cross_protocol_selector", root / "select_cross_protocol_cases.py"
    )
    if not selector_spec or not selector_spec.loader:
        errors.append("cannot load select_cross_protocol_cases.py")
        return set()
    selector = importlib.util.module_from_spec(selector_spec)
    selector_spec.loader.exec_module(selector)
    spec = _load_json(spec_path, errors)
    oracles = _load_json(root / "cross-protocol-oracles.json", errors)
    dql_oracles = _load_json(root / "dql-oracles.json", errors)
    if spec is None or oracles is None or dql_oracles is None:
        return set()
    try:
        selected = selector.select_paths(spec, manifest, oracles, dql_oracles, root)
    except (OSError, ValueError) as error:
        errors.append(f"cross-protocol matrix: {error}")
        return set()
    referenced: set[Path] = set()
    for record in selected:
        for field in ("sql_file", "backend_sql_file"):
            value = record.get(field)
            if isinstance(value, str):
                referenced.add(root / "cases" / PurePosixPath(value))
    return referenced


def validate_repository(root: Path) -> list[str]:
    """Return all validation errors for a SQL matrix repository."""
    root = root.resolve()
    errors: list[str] = []
    capabilities = _load_json(root / "capabilities.json", errors)
    manifest = _load_json(root / "manifest.json", errors)
    if capabilities is None or manifest is None:
        return errors

    known = _validate_registry(capabilities, errors)
    if not isinstance(manifest, dict):
        errors.append("manifest.json must contain an object")
        return errors
    if manifest.get("schema_version") != capabilities.get("schema_version"):
        errors.append("manifest and capability schema versions must match")

    case_root_value = manifest.get("case_root")
    if not isinstance(case_root_value, str) or not case_root_value:
        errors.append("manifest.case_root must be a non-empty relative path")
        return errors
    case_root_relative = PurePosixPath(case_root_value)
    if case_root_relative.is_absolute() or ".." in case_root_relative.parts:
        errors.append("manifest.case_root must stay below the matrix root")
        return errors
    case_root = root.joinpath(*case_root_relative.parts)

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("manifest.cases must be a non-empty array")
        return errors

    seen_ids: set[str] = set()
    referenced_files: set[Path] = set()
    for index, case in enumerate(cases):
        case_id, sql_path = _validate_case(
            case, index, root, case_root, known, errors
        )
        if case_id in seen_ids:
            errors.append(f"duplicate case ID: {case_id}")
        if case_id:
            seen_ids.add(case_id)
        if sql_path in referenced_files:
            errors.append(f"SQL file is referenced more than once: {sql_path}")
        if sql_path:
            referenced_files.add(sql_path)

    referenced_files.update(_validate_cross_protocol_matrix(root, manifest, errors))

    if case_root.is_dir():
        actual_files = set(case_root.rglob("*.sql"))
        for unreferenced in sorted(actual_files - referenced_files):
            errors.append(f"unreferenced SQL file: {unreferenced.relative_to(root)}")
    else:
        errors.append(f"case root does not exist: {case_root}")
    _validate_fixture_sql_files(root, errors)
    _validate_dql_oracles(root, cases, errors)
    _validate_dql_lock_oracles(root, cases, errors)
    _validate_dql_boundary_oracles(root, cases, errors)
    _validate_dml_oracles(root, cases, errors)
    _validate_tcl_oracles(root, cases, errors)
    _validate_prepared_oracles(root, cases, errors)
    _validate_extended_oracles(root, cases, errors)
    _validate_cursor_oracles(root, cases, errors)
    _validate_invalid_oracles(root, cases, errors)
    _validate_boundary_oracles(root, cases, errors)
    _validate_unsupported_oracles(root, cases, errors)
    _validate_ddl_oracles(root, cases, errors)
    _validate_ddl_temp_oracles(root, cases, errors)
    _validate_ddl_database_oracles(root, cases, errors)
    matrix_path = root / "protocol-matrix.json"
    if matrix_path.is_file():
        matrix_module_spec = importlib.util.spec_from_file_location(
            "sql_matrix_protocol_matrix", root / "protocol_matrix.py"
        )
        if matrix_module_spec and matrix_module_spec.loader:
            matrix_module = importlib.util.module_from_spec(matrix_module_spec)
            matrix_module_spec.loader.exec_module(matrix_module)
            matrix = _load_json(matrix_path, errors)
            errors.extend(matrix_module.validate_spec(matrix, manifest, root))
        else:
            errors.append("cannot load protocol_matrix.py")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent
    errors = validate_repository(root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"SQL matrix validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    print(f"SQL matrix validation passed: {len(manifest['cases'])} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
