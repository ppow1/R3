# R3 CONTROLLED SOURCE
# File: runtime/tool_server.py
# Component: R3-NATIVE-TOOL-SERVER
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: Independent read-only R3 tool router and durable audit.
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_tool_server.py
"""R3 native tool server: initial read-only status capability."""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import threading
import time
from runtime.host_execution import HostExecutor

STATUS = {"tool": "r3.status", "read_only": True, "definition": {
    "type": "function", "function": {"name": "r3.status",
    "description": "Return R3 tool-server status",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}}


class ToolRouter:
    def __init__(self, database: Path, executor: HostExecutor | None = None):
        self.executor = executor
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(database), check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS tool_audit (id INTEGER PRIMARY KEY, at REAL NOT NULL, tool TEXT NOT NULL, outcome TEXT NOT NULL)")
        self.db.commit()

    def discover(self):
        return [STATUS] + (self.executor.discover() if self.executor else [])

    def invoke(self, payload):
        name = payload.get("tool") if isinstance(payload, dict) else None
        params = payload.get("params") if isinstance(payload, dict) else None
        allowed = (name == "r3.status" and params == {}) or (self.executor is not None and name in self.executor.tools and params == {})
        with self.lock:
            self.db.execute("INSERT INTO tool_audit(at,tool,outcome) VALUES (?,?,?)",
                            (time.time(), name if isinstance(name, str) else "<invalid>",
                             "OK" if allowed else "DENIED"))
            self.db.commit()
        if not allowed:
            return 403, {"ok": False, "error": "Tool or arguments not authorized"}
        if name == "r3.status":
            return 200, {"ok": True, "result": {"service": "r3-tools", "healthy": True}}
        try:
            return 200, {"ok": True, "result": self.executor.invoke(name, params)}
        except Exception:
            return 500, {"ok": False, "error": "Host execution failed"}


def handler_for(router):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, code, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/v1/tools":
                return self.respond(404, {"error": "Not found"})
            self.respond(200, router.discover())

        def do_POST(self):
            if self.path != "/v1/tools/invoke":
                return self.respond(404, {"error": "Not found"})
            try:
                size = int(self.headers.get("Content-Length", "-1"))
                if size < 0 or size > 65536:
                    return self.respond(413, {"error": "Invalid request size"})
                payload = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeError):
                return self.respond(400, {"error": "Invalid JSON"})
            code, result = router.invoke(payload)
            self.respond(code, result)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--audit-db", type=Path, required=True)
    parser.add_argument("--catalog", type=Path)
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost"):
        parser.error("Initial native tool server is loopback-only")
    ThreadingHTTPServer((args.host, args.port), handler_for(ToolRouter(args.audit_db, HostExecutor(args.catalog) if args.catalog else None))).serve_forever()


if __name__ == "__main__":
    main()
