#!/usr/bin/env python3
"""Select PostgreSQL extended-wire cases owned by the dedicated runner."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(
    manifest: dict[str, Any],
    oracles: dict[str, Any],
    case_from: str = "SQLT-PGX-001",
    case_to: str = "SQLT-PGX-008",
) -> Iterator[tuple[str, str, str]]:
    results = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") == "cursor"
            and case.get("capability") == "cursor.postgres_extended"
            and case.get("dialects") == ["postgres"]
            and case.get("frontends") == ["pg_extended"]
            and isinstance(case_id, str)
            and case_from <= case_id <= case_to
            and case_id in results
        ):
            yield case_id, "postgres", case["sql_file"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("case_from", nargs="?", default="SQLT-PGX-001")
    parser.add_argument("case_to", nargs="?", default="SQLT-PGX-008")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    oracles = json.loads(args.oracles.read_text(encoding="utf-8"))
    if args.case_from > args.case_to:
        parser.error("case_from must not be greater than case_to")
    for row in select_cases(manifest, oracles, args.case_from, args.case_to):
        print(*row, sep="\t")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
