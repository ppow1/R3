"""Permanent integration regressions: R2 adapter routed by R3 tool server."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from runtime.r2_capabilities import R2Capabilities
from runtime.tool_server import ToolRouter


class Registry:
    def __init__(self, authorized=True):
        self.authorized = authorized
        self.calls = []

    def tool_specs(self):
        return [{"tool": "grace.example", "definition": {
            "type": "function", "function": {"name": "grace.example",
            "parameters": {"type": "object"}}}, "read_only": False}]

    def invoke(self, name, params):
        self.calls.append((name, params))
        if not self.authorized:
            return {"status": "error", "code": "grant_denied"}
        return {"status": "ok", "authorization": {
            "status": "authorized", "principal_id": "resident:grace",
            "grant_id": "grant-1"}, "result": {"changed": True}}


class RouterBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "audit.db"
        self.registry = Registry()
        self.router = ToolRouter(self.db, capabilities=R2Capabilities(self.registry))
        self.addCleanup(self.router.db.close)

    def test_capability_discovered(self):
        self.assertIn("grace.example", [d["tool"] for d in self.router.discover()])

    def test_authorized_execution_audited(self):
        code, response = self.router.invoke({"tool": "grace.example",
            "params": {"scope_ref": "office:grace", "input": {}}})
        self.assertEqual(code, 200)
        self.assertTrue(response["ok"])
        row = self.router.db.execute(
            "SELECT principal_id,grant_id,scope_ref,outcome FROM capability_audit").fetchone()
        self.assertEqual(row, ("resident:grace", "grant-1", "office:grace", "OK"))

    def test_denied_execution_not_reported_success(self):
        self.registry.authorized = False
        code, response = self.router.invoke({"tool": "grace.example",
            "params": {"scope_ref": "office:other", "input": {}}})
        self.assertEqual(code, 403)
        self.assertFalse(response["ok"])
        self.assertEqual(self.router.db.execute(
            "SELECT outcome FROM capability_audit").fetchone()[0], "DENIED")


if __name__ == "__main__":
    unittest.main()
