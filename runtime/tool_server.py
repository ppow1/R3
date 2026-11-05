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
from runtime.capabilities import CapabilityDenied, CapabilityRegistry
from runtime.resident_identity import R3ResidentIdentity
from runtime.capability_authority import R3Authority


STATUS = {"tool": "r3.status", "read_only": True, "definition": {
    "type": "function", "function": {"name": "r3.status",
    "description": "Return R3 tool-server status",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}}}


class ToolRouter:
    def __init__(self, database: Path, executor: HostExecutor | None = None,
                 *, authority: R3Authority | None = None,
                 capabilities: tuple = ()):
        self.executor = executor
        self.authority = authority
        self.identity = R3ResidentIdentity(authority) if authority else None
        self.capabilities = tuple(capabilities)
        self.capability_map = {cap.name: cap for cap in self.capabilities}
        if len(self.capability_map) != len(self.capabilities):
            raise ValueError("Duplicate capabilities")
        if self.capabilities and authority is None:
            raise ValueError("Canonical authority required for capabilities")
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(database), check_same_thread=False)
        self.lock = threading.Lock()
        self.db.execute("CREATE TABLE IF NOT EXISTS tool_audit (id INTEGER PRIMARY KEY, at REAL NOT NULL, tool TEXT NOT NULL, outcome TEXT NOT NULL)")
        self.db.commit()

    def discover(self):
        result = [STATUS] + (self.executor.discover() if self.executor else [])
        for cap in self.capabilities:
            result.append({
                "tool": cap.name,
                "read_only": cap.read_only,
                "definition": {"type": "function", "function": {
                    "name": cap.name,
                    "description": cap.description,
                    "parameters": cap.parameters,
                }},
            })
        return result

    def invoke(self, payload, *, credential=None):
        name = payload.get("tool") if isinstance(payload, dict) else None
        if name in self.capability_map:
            try:
                if self.identity is None or not isinstance(credential, str):
                    raise CapabilityDenied("Resident credential required")
                principal = self.identity.authenticate(credential)
                params = payload.get("params")
                correlation_id = payload.get("correlation_id")
                registry = CapabilityRegistry(
                    principal=principal,
                    verifier=self.authority,
                    audit=self.authority.audit,
                )
                registry.register(self.capability_map[name])
                result = registry.invoke(
                    name, params, correlation_id=correlation_id)
                code, outcome, response = (
                    200, "OK", {"ok": True, "result": result})
            except Exception:
                code, outcome, response = (
                    403, "DENIED",
                    {"ok": False, "error": "Capability authorization or execution failed"})
            with self.lock:
                self.db.execute(
                    "INSERT INTO tool_audit(at,tool,outcome) VALUES (?,?,?)",
                    (time.time(), name, outcome))
                self.db.commit()
            return code, response

        name = payload.get("tool") if isinstance(payload, dict) else None
        params = payload.get("params") if isinstance(payload, dict) else None
        allowed = (name == "r3.status" and params == {}) or (
            self.executor is not None and name in self.executor.tools and params == {})
        if not allowed:
            code, outcome, result = 403, "DENIED", {"ok": False, "error": "Tool or arguments not authorized"}
        elif name == "r3.status":
            code, outcome, result = 200, "OK", {"ok": True, "result": {"service": "r3-tools", "healthy": True}}
        else:
            try:
                output = self.executor.invoke(name, params)
                code, outcome, result = 200, "OK", {"ok": True, "result": output}
            except Exception:
                code, outcome, result = 500, "FAILED", {"ok": False, "error": "Host execution failed"}
        with self.lock:
            self.db.execute("INSERT INTO tool_audit(at,tool,outcome) VALUES (?,?,?)",
                            (time.time(), name if isinstance(name, str) else "<invalid>", outcome))
            self.db.commit()
        return code, result


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
            authorization = self.headers.get("Authorization", "")
            credential = (
                authorization[7:] if authorization.startswith("Bearer ")
                else None
            )
            code, result = router.invoke(payload, credential=credential)
            self.respond(code, result)

    return Handler


def build_router(*, audit_db, catalog=None, hosts=None, authority_db=None):
    if hosts is not None and catalog is None:
        raise ValueError("Hosts require a catalog")
    authority = R3Authority(authority_db) if authority_db is not None else None
    executor = HostExecutor(catalog, hosts) if catalog else None
    return ToolRouter(audit_db, executor, authority=authority)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--audit-db", type=Path, required=True)
    parser.add_argument("--authority-db", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--hosts", type=Path)
    args = parser.parse_args()
    if args.hosts and not args.catalog:
        parser.error("--hosts requires --catalog")
    if args.host not in ("127.0.0.1", "::1", "localhost"):
        parser.error("Initial native tool server is loopback-only")
    router = build_router(
        audit_db=args.audit_db,
        catalog=args.catalog,
        hosts=args.hosts,
        authority_db=args.authority_db,
    )
    ThreadingHTTPServer((args.host, args.port), handler_for(router)).serve_forever()


if __name__ == "__main__":
    main()
