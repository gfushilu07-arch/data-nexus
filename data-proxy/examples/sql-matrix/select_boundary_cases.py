#!/usr/bin/env python3
"""Select invalid SQL cases owned by the SQLT-3F2 boundary runner."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(
    manifest: dict[str, Any], oracles: dict[str, Any]
) -> Iterator[tuple[str, str, str, str]]:
    results = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") != "invalid"
            or not isinstance(case_id, str)
            or case_id not in results
        ):
            continue
        flow = results[case_id].get("flow")
        if not isinstance(flow, str):
            continue
        for dialect in case.get("dialects", []):
            yield case_id, dialect, case["sql_file"], flow


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
