# R3 CONTROLLED SOURCE
# File: runtime/tool_server.py
# Component: R3-NATIVE-TOOL-SERVER
# File Revision: 1.2.1
# Created: 2026-11-02 UTC
# Created By: Unknown (legacy source)
# Purpose: Independent R3 tool router, exact-grant capabilities, and durable audit.
# Execution Model: Loopback HTTP server with fail-closed resident authentication and capability authorization.
# Observability: tool_audit and canonical authority audit; no credentials or proposal payloads logged.
# Dependencies: runtime.capabilities; runtime.capability_authority; optional Comms5 MCP SDK client.
# Authority: R3 exact-grant contract; narrow Comms5 draft submission requires a separate authenticated Comms5 transport.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add opt-in, single-operation Comms5 proposal adapter.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Report authorized backend failures separately from authorization denials.
# Supersedes: Revision 1.1.0; preserves existing routes and capabilities.
# Contracts: docs/r3-native-tool-contract.md; riverview-comms-contract:5.0
# Tests: tests/test_tool_server.py; tests/test_proposal_submission_integration.py
# History/Predecessor: Git blob 36e9f176584d51b98f86ff3c88c30582712687e0
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
            except CapabilityDenied:
                code, outcome, response = (
                    403, "DENIED",
                    {"ok": False, "error": "Capability authorization or execution failed"})
            except Exception:
                code, outcome, response = (
                    502, "FAILED",
                    {"ok": False, "error": "Authorized capability backend failed; reconcile before retry"})
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


def build_router(*, audit_db, catalog=None, hosts=None, authority_db=None,
                 comms5_proposal_url=None, comms5_proposal_token_file=None,
                 comms5_proposal_classification="internal"):
    if hosts is not None and catalog is None:
        raise ValueError("Hosts require a catalog")
    if (comms5_proposal_url is None) != (comms5_proposal_token_file is None):
        raise ValueError("Comms5 proposal integration requires both endpoint and credential file")
    authority = R3Authority(authority_db) if authority_db is not None else None
    executor = HostExecutor(catalog, hosts) if catalog else None
    capabilities = ()
    if comms5_proposal_url is not None:
        from runtime.comms5_proposals import (
            Comms5DraftClient, proposal_submission_capability, read_bearer_token,
        )
        client = Comms5DraftClient(
            comms5_proposal_url,
            read_bearer_token(comms5_proposal_token_file),
            classification=comms5_proposal_classification,
        )
        capabilities = (proposal_submission_capability(client),)
    return ToolRouter(audit_db, executor, authority=authority, capabilities=capabilities)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--audit-db", type=Path, required=True)
    parser.add_argument("--authority-db", type=Path)
    parser.add_argument("--comms5-proposal-url")
    parser.add_argument("--comms5-proposal-token-file", type=Path)
    parser.add_argument("--comms5-proposal-classification", choices=("internal", "river"),
                        default="internal")
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
        comms5_proposal_url=args.comms5_proposal_url,
        comms5_proposal_token_file=args.comms5_proposal_token_file,
        comms5_proposal_classification=args.comms5_proposal_classification,
    )
    ThreadingHTTPServer((args.host, args.port), handler_for(router)).serve_forever()


if __name__ == "__main__":
    main()
