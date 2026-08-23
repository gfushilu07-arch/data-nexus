#!/usr/bin/env python3
"""SQLT-5C-c Remote PDP mock: denies SELECT on sqlt_dml_targets, allows the rest."""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def _log(self, fmt, *args):
        print(f"[remote-pdp-mock] {fmt % args}", flush=True)

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            req = {}
        subject = req.get("subject_id", "")
        action = req.get("action", "")
        tables = req.get("tables") or []
        self._log("authorize subject=%s action=%s tables=%s", subject, action, tables)
        if action == "select" and "sqlt_dml_targets" in tables:
            resp = {
                "allow": False,
                "rule": "remote-deny-targets-select",
                "message": "remote PDP denies SELECT on sqlt_dml_targets",
            }
        else:
            resp = {"allow": True, "rule": "remote-allow"}
        payload = json.dumps(resp).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        self._log(fmt, *args)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18181
    print(f"[remote-pdp-mock] listening on 127.0.0.1:{port}", flush=True)
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
