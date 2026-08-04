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
