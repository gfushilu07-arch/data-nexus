#!/usr/bin/env python3
"""Select MySQL binary prepared cases owned by the prepared runner."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(
    manifest: dict[str, Any],
    oracles: dict[str, Any],
    case_from: str = "SQLT-PRP-001",
    case_to: str = "SQLT-PRP-008",
) -> Iterator[tuple[str, str, str]]:
    results = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") != "cursor"
            or case.get("capability") != "cursor.mysql_prepared"
            or case.get("frontends") != ["mysql_binary"]
            or not isinstance(case_id, str)
            or not case_from <= case_id <= case_to
            or case_id not in results
        ):
            continue
        if case.get("dialects") == ["mysql"]:
            yield case_id, "mysql", case["sql_file"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("oracles", type=Path)
    parser.add_argument("case_from", nargs="?", default="SQLT-PRP-001")
    parser.add_argument("case_to", nargs="?", default="SQLT-PRP-008")
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
