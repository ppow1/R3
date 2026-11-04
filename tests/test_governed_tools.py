# R3 CONTROLLED SOURCE
# File: tests/test_governed_tools.py
# Component: R3-GRACE-GOVERNED-EXECUTION-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent resident read/write grant, identity, audit and no-replay tests.
# Execution Model: Local deterministic mock authority and temporary SQLite execution journal.
# Observability: Assertions on executor calls, audit evidence and durable ledger.
# Dependencies: Python stdlib; runtime/governed_tools.py, runtime/tool_server.py.
# Authority: Steward R3 unified integration, issues #16 and #28.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-004 | Add reusable authorization boundary tests.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_governed_tools -v
# History/Predecessor: New controlled test.
"""Tests independent operation grants at the actual R3 tool-router boundary."""
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runtime.capabilities import CapabilityDenied
from runtime.governed_tools import (
    ExecutionAttemptLedger, GovernedCapability, GovernedToolGateway)
from runtime.tool_server import ToolRouter, handler_for


class FakeCanonicalAuthority:
    """Test double only: Website's canonical production grant store is not created."""
    def __init__(self):
        self.grants = {}
        self.calls = []

    def provision(self, principal, operation, *, active=True, expires_at=None):
        key = (principal, "resource:operations", "report", operation, "office:operations")
        self.grants[key] = {"grant_id": "test:" + principal + ":" + operation,
                            "active": active, "expires_at": expires_at}

    def authorize(self, **request):
        self.calls.append(dict(request))
        key = (request["principal"], request["resource_id"], request["action"],
               request["operation"], request["scope_ref"])
        grant = self.grants.get(key)
        if (not grant or not grant["active"] or
                (grant["expires_at"] is not None and grant["expires_at"] <= time.time())):
            raise CapabilityDenied("No active exact canonical grant")
        return {"grant_id": grant["grant_id"]}


class GovernedToolTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        path = Path(self.directory.name)
        self.connection = sqlite3.connect(path / "attempts.db", check_same_thread=False)
        self.addCleanup(self.connection.close)
        self.events = []
        self.effects = []
        self.authority = FakeCanonicalAuthority()
        ledger = ExecutionAttemptLedger(self.connection, threading.Lock())
        def identity(token):
            principals = {"valid-grace": "resident:grace", "valid-helen": "resident:helen"}
            if token not in principals:
                raise CapabilityDenied("Invalid independent resident credential")
            return principals[token]

        self.gateway = GovernedToolGateway(
            identity_resolver=identity, verifier=self.authority,
            audit=self.events.append, write_ledger=ledger)
        self.gateway.register(GovernedCapability(
            "r3.operations.read", "resource:operations", "report", "read",
            "Read operations", {"type": "object", "required": ["scope_ref"]},
            lambda p: {"value": "ok"}))
        self.gateway.register(GovernedCapability(
            "r3.operations.write", "resource:operations", "report", "write",
            "Record operations", {"type": "object", "required": ["scope_ref"]},
            lambda p: self.effects.append(p["scope_ref"]) or {"changed": True}))
        self.router = ToolRouter(path / "tool_audit.db", governed=self.gateway)
        self.addCleanup(self.router.db.close)

    def call(self, operation, correlation="op-1", token="valid-grace", **other):
        payload = {"tool": "r3.operations." + operation,
                   "params": {"scope_ref": "office:operations"},
                   "correlation_id": correlation, **other}
        return self.router.invoke(payload, authorization=(
            "Bearer " + token if token is not None else None))

    def test_read_only_grant_denies_write_independently(self):
        self.authority.provision("resident:grace", "read")
        status, result = self.call("read")
        self.assertEqual(status, 200)
        self.assertEqual(result["result"]["authorization"]["operation"], "read")
        self.assertEqual(self.call("write")[0], 403)
        self.assertFalse(self.effects)

    def test_write_only_grant_denies_read_independently(self):
        self.authority.provision("resident:grace", "write")
        self.assertEqual(self.call("read")[0], 403)
        status, result = self.call("write")
        self.assertEqual(status, 200)
        self.assertEqual(result["result"]["authorization"]["principal_id"], "resident:grace")
        self.assertEqual(self.effects, ["office:operations"])

    def test_no_grants_deny_both_even_when_discoverable(self):
        self.assertIn("r3.operations.write", [d["tool"] for d in self.router.discover()])
        self.assertEqual(self.call("read")[0], 403)
        self.assertEqual(self.call("write")[0], 403)
        self.assertFalse(self.effects)

    def test_spoofed_principal_in_envelope_fails_closed(self):
        self.authority.provision("resident:grace", "write")
        self.assertEqual(self.call("write", principal="resident:grace")[0], 403)
        self.assertEqual(self.call("write", token=None)[0], 403)
        self.assertEqual(self.call("write", token="untrusted")[0], 403)
        self.assertFalse(self.effects)

    def test_cross_resident_isolation(self):
        self.authority.provision("resident:grace", "write")
        self.assertEqual(self.call("write", token="valid-helen")[0], 403)
        self.assertEqual(self.call("write", token="valid-grace")[0], 200)
        self.assertEqual(self.effects, ["office:operations"])

    def test_revoked_and_expired_grants_deny(self):
        self.authority.provision("resident:grace", "write", active=False)
        self.assertEqual(self.call("write")[0], 403)
        self.authority.provision("resident:grace", "write", expires_at=time.time() - 1)
        self.assertEqual(self.call("write")[0], 403)
        self.assertFalse(self.effects)

    def test_authorized_write_audited_and_reservation_persisted(self):
        self.authority.provision("resident:grace", "write")
        status, result = self.call("write")
        self.assertEqual(status, 200)
        self.assertEqual(result["result"]["authorization"]["grant_id"],
                         "test:resident:grace:write")
        self.assertEqual([x["outcome"] for x in self.events],
                         ["AUTHORIZED", "COMPLETED"])
        saved = self.connection.execute(
            "SELECT principal, state FROM governed_write_attempts").fetchone()
        self.assertEqual(saved, ("resident:grace", "COMPLETED"))
        self.assertEqual(self.call("write")[0], 409)
        self.assertEqual(len(self.effects), 1)

    def test_uncertain_write_is_not_replayed(self):
        self.authority.provision("resident:grace", "write")
        def uncertain(params):
            self.effects.append(params["scope_ref"])
            raise OSError("Result acknowledgement lost")
        self.gateway._capabilities["r3.operations.write"] = GovernedCapability(
            "r3.operations.write", "resource:operations", "report", "write",
            "Record operations", {}, uncertain)
        self.assertEqual(self.call("write")[0], 500)
        self.assertEqual(self.call("write")[0], 409)
        self.assertEqual(len(self.effects), 1)
        self.assertEqual(self.connection.execute(
            "SELECT state FROM governed_write_attempts").fetchone()[0], "UNCERTAIN")

    def test_audit_failure_prevents_any_write(self):
        self.authority.provision("resident:grace", "write")
        def unavailable(_event):
            raise OSError("Shared authority audit unavailable")
        self.gateway.audit = unavailable
        self.assertEqual(self.call("write")[0], 500)
        self.assertFalse(self.effects)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM governed_write_attempts").fetchone()[0], 0)

    def test_http_boundary_passes_resident_credential_to_verifier(self):
        self.authority.provision("resident:grace", "write")
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.router))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:%d/v1/tools/invoke" % server.server_port
        payload = json.dumps({"tool": "r3.operations.write",
            "params": {"scope_ref": "office:operations"},
            "correlation_id": "http-write"}).encode()
        try:
            with urlopen(Request(url, data=payload, method="POST",
                                 headers={"Content-Type": "application/json"}), timeout=3):
                self.fail("Anonymous write should be denied")
        except HTTPError as exc:
            self.assertEqual(exc.code, 403)
        with urlopen(Request(url, data=payload, method="POST", headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer valid-grace"}), timeout=3) as response:
            result = json.load(response)
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.effects), 1)


if __name__ == "__main__":
    unittest.main()
