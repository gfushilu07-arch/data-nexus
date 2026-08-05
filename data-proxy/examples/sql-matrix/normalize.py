#!/usr/bin/env python3
"""Normalize tab-separated SQL client output for backend oracle comparisons."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def normalize_text(text: str) -> str:
    """Normalize line endings and insignificant trailing whitespace, preserving row order."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def normalize_error_text(text: str, dialect: str) -> str:
    """Return a stable backend error identity without retaining query or data text."""
    if dialect == "mysql":
        match = re.search(r"ERROR\s+(\d+)\s+\(([0-9A-Z]{5})\)", text)
        if match:
            return f"mysql\t{match.group(1)}\t{match.group(2)}\n"
    elif dialect == "postgres":
        match = re.search(r"(?:ERROR|FATAL):\s+([0-9A-Z]{5})(?::|\s|$)", text)
        if match:
            return f"postgres\t{match.group(1)}\n"
    else:
        raise ValueError(f"unsupported error dialect: {dialect}")
    raise ValueError(f"cannot classify {dialect} error output")


def normalize_affected_rows(text: str, dialect: str) -> str:
    """Extract the one affected-row marker emitted by the fixed SQL clients."""
    if dialect == "mysql":
        matches = re.findall(r"Query OK, (\d+) row[s]? affected", text)
    elif dialect == "postgres":
        matches = re.findall(
            r"^(?:(?:UPDATE|DELETE|MERGE) (\d+)|INSERT \d+ (\d+))$",
            text,
            re.MULTILINE,
        )
        matches = [next(value for value in match if value) for match in matches]
    else:
        raise ValueError(f"unsupported affected-row dialect: {dialect}")
    if len(matches) != 1:
        raise ValueError(f"expected one affected-row marker, found {len(matches)}")
    return f"{matches[0]}\n"


def normalize_returned_rows(text: str, dialect: str) -> str:
    """Remove one optional command tag and normalize exact unaligned result rows."""
    if dialect != "postgres":
        raise ValueError(f"unsupported returned-row dialect: {dialect}")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    tag_pattern = re.compile(r"^(?:INSERT \d+ \d+|UPDATE \d+|DELETE \d+|MERGE \d+)$")
    tags = [line for line in lines if tag_pattern.fullmatch(line)]
    if len(tags) > 1:
        raise ValueError(f"expected at most one DML command tag, found {len(tags)}")
    return normalize_text("\n".join(line for line in lines if not tag_pattern.fullmatch(line)))


def normalize_transaction_markers(text: str) -> str:
    """Extract deterministic marker rows emitted after transaction recovery."""
    markers = [line.rstrip() for line in text.splitlines() if line.startswith("SQLT_TXN\t")]
    if not markers:
        raise ValueError("expected at least one SQLT_TXN marker row")
    return "\n".join(markers) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--error-dialect", choices=("mysql", "postgres"))
    parser.add_argument("--affected-dialect", choices=("mysql", "postgres"))
    parser.add_argument("--returned-dialect", choices=("postgres",))
    parser.add_argument("--transaction-markers", action="store_true")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    source = args.source.read_text(encoding="utf-8")
    modes = [args.error_dialect, args.affected_dialect, args.returned_dialect]
    if sum(value is not None for value in modes) + int(args.transaction_markers) > 1:
        parser.error("normalization dialect modes are mutually exclusive")
    if args.error_dialect:
        normalized = normalize_error_text(source, args.error_dialect)
    elif args.affected_dialect:
        normalized = normalize_affected_rows(source, args.affected_dialect)
    elif args.returned_dialect:
        normalized = normalize_returned_rows(source, args.returned_dialect)
    elif args.transaction_markers:
        normalized = normalize_transaction_markers(source)
    else:
        normalized = normalize_text(source)
    args.destination.write_text(normalized, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
