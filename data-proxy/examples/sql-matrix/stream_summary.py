#!/usr/bin/env python3
"""Summarize SQL client output with bounded memory and exact byte semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import BinaryIO, Any


CHUNK_BYTES = 65536


def summarize_stream(source: BinaryIO, chunk_bytes: int = CHUNK_BYTES) -> dict[str, Any]:
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")

    full_hash = hashlib.sha256()
    line_hash = hashlib.sha256()
    total_bytes = 0
    line_bytes = 0
    lines = 0
    max_line_bytes = 0
    first_line_sha256: str | None = None
    last_line_sha256: str | None = None
    ends_with_lf = False

    def finish_line() -> None:
        nonlocal line_hash, line_bytes, lines, max_line_bytes
        nonlocal first_line_sha256, last_line_sha256
        digest = line_hash.hexdigest()
        lines += 1
        max_line_bytes = max(max_line_bytes, line_bytes)
        if first_line_sha256 is None:
            first_line_sha256 = digest
        last_line_sha256 = digest
        line_hash = hashlib.sha256()
        line_bytes = 0

    while chunk := source.read(chunk_bytes):
        full_hash.update(chunk)
        total_bytes += len(chunk)
        ends_with_lf = chunk.endswith(b"\n")
        start = 0
        while True:
            newline = chunk.find(b"\n", start)
            if newline < 0:
                segment = chunk[start:]
                line_hash.update(segment)
                line_bytes += len(segment)
                break
            segment = chunk[start:newline]
            line_hash.update(segment)
            line_bytes += len(segment)
            finish_line()
            start = newline + 1

    if total_bytes and not ends_with_lf:
        finish_line()

    return {
        "bytes": total_bytes,
        "lines": lines,
        "max_line_bytes": max_line_bytes,
        "ends_with_lf": ends_with_lf,
        "sha256": full_hash.hexdigest(),
        "first_line_sha256": first_line_sha256,
        "last_line_sha256": last_line_sha256,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--chunk-bytes", type=int, default=CHUNK_BYTES)
    args = parser.parse_args()
    with args.source.open("rb") as source:
        summary = summarize_stream(source, args.chunk_bytes)
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
