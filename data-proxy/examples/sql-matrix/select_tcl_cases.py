#!/usr/bin/env python3
"""Select explicit transaction cases owned by the TCL corpus runner."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(
    manifest: dict[str, Any], oracles: dict[str, Any]
) -> Iterator[tuple[str, str, str]]:
    oracle_cases = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") != "tcl"
            or not isinstance(case_id, str)
            or case_id not in oracle_cases
        ):
            continue
        for dialect in case.get("dialects", []):
            if dialect in oracle_cases[case_id]:
                yield case_id, dialect, case["sql_file"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("oracles", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    oracles = json.loads(args.oracles.read_text(encoding="utf-8"))
    for row in select_cases(manifest, oracles):
        print(*row, sep="\t")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
