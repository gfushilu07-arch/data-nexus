#!/usr/bin/env python3
"""Select the dedicated PostgreSQL named-cursor corpus."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def select_cases(manifest: dict[str, Any], oracles: dict[str, Any]) -> Iterator[tuple[str, str, str]]:
    results = oracles.get("results", {})
    for case in manifest.get("cases", []):
        case_id = case.get("id")
        if (
            case.get("family") == "cursor"
            and case.get("capability") == "cursor.named_forward"
            and case.get("dialects") == ["postgres"]
            and case.get("frontends") == ["pg_simple"]
            and case.get("protocols") == ["pg_simple"]
            and isinstance(case_id, str)
            and case_id in results
        ):
            yield case_id, "postgres", case["sql_file"]


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
