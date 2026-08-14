#!/usr/bin/env python3
"""Identify SQLT-4A resources without claiming unrelated shared-host activity."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


SUITE_PROJECT_PREFIXES = {
    "prepared": "sqlt3eprep-",
    "extended": "sqlt3epgx-",
    "cursor": "sqlt3ecursor-",
    "tcl": "sqlt3etcl-",
    "dml": "sqlt3cdml-",
    "ddl": "sqlt3dddl-",
}


def run_token(run_id: str) -> str:
    token = "".join(
        character for character in run_id if character.isascii() and character.isalnum()
    )
    if not token:
        raise ValueError("protocol matrix run ID needs an ASCII alphanumeric character")
    return token


def ownership_rows(run_id: str, suite_filter: str = "") -> list[tuple[str, str, str]]:
    run_token(run_id)
    if suite_filter and suite_filter not in SUITE_PROJECT_PREFIXES:
        raise ValueError(f"unknown protocol matrix suite: {suite_filter}")
    suites = [suite_filter] if suite_filter else list(SUITE_PROJECT_PREFIXES)
    rows = []
    for suite in suites:
        child_run_id = f"{run_id}-{suite}"
        project = f"{SUITE_PROJECT_PREFIXES[suite]}{run_token(child_run_id)}"
        rows.append((suite, child_run_id, project))
    return rows


def owned_resource_lines(
    resource: str,
    lines: Iterable[str],
    run_id: str,
    suite_filter: str = "",
) -> list[str]:
    ownership = ownership_rows(run_id, suite_filter)
    child_run_ids = {row[1] for row in ownership}
    compose_projects = {row[2] for row in ownership}
    columns = {"containers": 4, "networks": 3, "volumes": 2}
    if resource not in columns:
        raise ValueError(f"unknown Docker resource type: {resource}")

    owned = []
    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n")
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != columns[resource]:
            raise ValueError(
                f"{resource} snapshot line {number} has {len(fields)} columns; "
                f"expected {columns[resource]}"
            )
        compose_project = fields[-2] if resource == "containers" else fields[-1]
        custom_run_id = fields[-1] if resource == "containers" else ""
        if compose_project in compose_projects or custom_run_id in child_run_ids:
            owned.append(line)
    return owned


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    projects = subparsers.add_parser("projects", help="print suite ownership metadata")
    projects.add_argument("--run-id", required=True)
    projects.add_argument("--suite", default="")

    filter_parser = subparsers.add_parser("filter", help="print resources owned by this run")
    filter_parser.add_argument("--run-id", required=True)
    filter_parser.add_argument("--suite", default="")
    filter_parser.add_argument(
        "--resource", required=True, choices=("containers", "networks", "volumes")
    )
    filter_parser.add_argument("--input", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "projects":
            for row in ownership_rows(args.run_id, args.suite):
                print("\t".join(row))
            return 0

        lines = args.input.read_text(encoding="utf-8").splitlines()
        for line in owned_resource_lines(args.resource, lines, args.run_id, args.suite):
            print(line)
        return 0
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
