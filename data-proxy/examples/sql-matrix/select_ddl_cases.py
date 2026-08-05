#!/usr/bin/env python3
"""Select ordinary DDL cases that have catalog-state oracles."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(
    manifest: dict[str, Any],
    oracles: dict[str, Any],
    first: str,
    last: str,
) -> Iterator[tuple[str, str, str]]:
    oracle_cases = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") != "ddl"
            or not isinstance(case_id, str)
            or case_id not in oracle_cases
            or not first <= case_id <= last
        ):
            continue
        for dialect in case.get("dialects", []):
            yield case_id, dialect, case["sql_file"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("first")
    parser.add_argument("last")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    oracles = json.loads(args.oracles.read_text(encoding="utf-8"))
    for row in select_cases(manifest, oracles, args.first, args.last):
        print(*row, sep="\t")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
