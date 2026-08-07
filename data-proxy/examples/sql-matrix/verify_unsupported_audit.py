#!/usr/bin/env python3
"""Close SQLT-3F3 gateway results against low-cardinality audit events."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


AUDIT_MESSAGE = "gateway rejected unsupported SQL capability"
FORBIDDEN_LOG_FRAGMENTS = (
    "sqlt-unreachable-sentinel",
    "sqlt-unreachable-outfile",
    "sqlt-unreachable-dumpfile",
    "sqlt-do-sentinel",
    "sqlt_missing_maintenance_target",
    "sqlt_missing_procedure",
    "sqlt_missing_role",
    "max_connections = 151",
    "pg_read_file(",
    "pg_authid",
    "mysql.user",
    "create extension",
    "/users/",
    "/volumes/",
    "/private/",
    "/tmp/",
)


def expected_capabilities(results: list[dict[str, Any]]) -> Counter[str]:
    expected: Counter[str] = Counter()
    for result in results:
        if result.get("path") != "gateway":
            continue
        semantic = result.get("semantic") or {}
        for step in semantic.get("steps", []):
            capability = (step.get("error") or {}).get("capability")
            if not isinstance(capability, str) or not capability:
                raise ValueError(
                    f"gateway step lacks capability: {result.get('case_id')} "
                    f"{result.get('dialect')} {step.get('name')}"
                )
            expected[capability] += 1
    if not expected:
        raise ValueError("no gateway capabilities found in results")
    return expected


def audit_capabilities(lines: list[str]) -> Counter[str]:
    actual: Counter[str] = Counter()
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"gateway log line {number} is not JSON: {exc}") from exc
        fields = event.get("fields") or {}
        if fields.get("message") != AUDIT_MESSAGE:
            continue
        capability = fields.get("capability")
        if not isinstance(capability, str) or not capability:
            raise ValueError(f"audit event on line {number} lacks capability")
        if fields.get("decision") != "reject" or fields.get("action") != "query":
            raise ValueError(f"audit event on line {number} has unstable identity")
        actual[capability] += 1
    return actual


def reject_sensitive_log_text(text: str) -> None:
    lowered = text.lower()
    leaked = [fragment for fragment in FORBIDDEN_LOG_FRAGMENTS if fragment in lowered]
    if leaked:
        raise ValueError("gateway audit log leaked sensitive SQL text: " + ", ".join(leaked))


def verify(results_path: Path, log_path: Path) -> dict[str, Any]:
    results = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    log_text = log_path.read_text(encoding="utf-8")
    reject_sensitive_log_text(log_text)
    expected = expected_capabilities(results)
    actual = audit_capabilities(log_text.splitlines())
    if actual != expected:
        raise ValueError(
            "gateway audit capability mismatch: "
            f"expected={dict(sorted(expected.items()))} actual={dict(sorted(actual.items()))}"
        )
    return {
        "audit_events": sum(actual.values()),
        "capabilities": dict(sorted(actual.items())),
        "sensitive_sql_leaks": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("gateway_log", type=Path)
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    summary = verify(args.results, args.gateway_log)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
