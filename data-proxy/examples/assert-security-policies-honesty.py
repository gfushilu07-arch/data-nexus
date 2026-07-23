#!/usr/bin/env python3
"""UI63: shared assert for GET /admin/security-policies honesty fields.

Pins A10/H05/A06 not-delivered flags and adjacent cursor/streaming honesty.
Used by L0 / security smokes so remainders asserts do not drift.

Usage:
  python3 examples/assert-security-policies-honesty.py --file /tmp/policies.json
  python3 examples/assert-security-policies-honesty.py --url http://127.0.0.1:8082/admin/security-policies
  python3 examples/assert-security-policies-honesty.py --url ... --bearer "$TOKEN"
  python3 examples/assert-security-policies-honesty.py --file ... --expect-enabled false
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def load_json(args: argparse.Namespace) -> dict[str, Any]:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            return json.load(f)
    if not args.url:
        raise SystemExit("need --file or --url")
    req = urllib.request.Request(args.url)
    if args.bearer:
        req.add_header("Authorization", f"Bearer {args.bearer}")
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} fetching {args.url}") from e


def assert_honesty(data: dict[str, Any], expect_enabled: str | None) -> None:
    if "enabled" not in data:
        raise AssertionError(f"missing enabled: {sorted(data.keys())}")
    if expect_enabled == "true":
        assert data["enabled"] is True, data.get("enabled")
    elif expect_enabled == "false":
        assert data["enabled"] is False, data.get("enabled")
    # else: any

    assert data.get("star_expands_wildcard") is False, data.get("star_expands_wildcard")

    st = data.get("streaming") or {}
    assert st.get("peak_is_process_rss") is False, st
    assert st.get("obligations_force_streaming") is True, st
    # Config mirror: always false until A10 backend WITH HOLD ships (validate rejects true).
    if "backend_sql_with_hold" in st:
        assert st.get("backend_sql_with_hold") is False, st

    sc = data.get("sql_cursor") or {}
    assert sc.get("process_local") is True, sc
    assert sc.get("backend_with_hold") is False, sc
    # forward_fetch_only / session_end_clears are always true when present
    if "forward_fetch_only" in sc:
        assert sc.get("forward_fetch_only") is True, sc
    if "session_end_clears" in sc:
        assert sc.get("session_end_clears") is True, sc

    rem = data.get("remainders") or {}
    assert rem.get("backend_sql_with_hold") is False, rem
    assert rem.get("crdt_merge") is False, rem
    assert rem.get("mlock") is False, rem
    assert rem.get("process_rss_window_byte_ci") is False, rem


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", help="path to security-policies JSON")
    ap.add_argument("--url", help="admin security-policies URL")
    ap.add_argument("--bearer", help="JWT for Authorization: Bearer")
    ap.add_argument(
        "--expect-enabled",
        choices=("true", "false", "any"),
        default="any",
        help="optional security.enabled expectation",
    )
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--label", default="security-policies honesty", help="log label")
    args = ap.parse_args()
    if not args.file and not args.url:
        ap.error("need --file or --url")

    data = load_json(args)
    expect = None if args.expect_enabled == "any" else args.expect_enabled
    assert_honesty(data, expect)
    rem = data.get("remainders") or {}
    print(
        f"OK {args.label}: enabled={data.get('enabled')} "
        f"remainders={rem} star_expands_wildcard={data.get('star_expands_wildcard')}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"FAIL {e}", file=sys.stderr)
        raise SystemExit(1)
