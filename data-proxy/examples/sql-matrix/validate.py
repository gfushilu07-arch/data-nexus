#!/usr/bin/env python3
"""Validate the SQL capability registry, manifest, and SQL case files."""

from __future__ import annotations

import json
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
            and case.get("capability") != "ddl.temporary_table"
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
                if result != "success":
                        errors.append(f"{label} data probes require a success oracle")


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
    _validate_ddl_oracles(root, cases, errors)
    _validate_ddl_temp_oracles(root, cases, errors)
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
