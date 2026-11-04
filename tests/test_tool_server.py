# R3 CONTROLLED SOURCE
# File: tests/test_tool_server.py
# Component: R3-NATIVE-TOOL-SERVER-TESTS
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent authorization and audit contract tests.
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.tool_server import ToolRouter


class ToolServerTests(unittest.TestCase):
    def test_discover_invoke_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.db"
            router = ToolRouter(path)
            self.assertEqual(router.discover()[0]["tool"], "r3.status")
            code, response = router.invoke({"tool": "r3.status", "params": {}})
            self.assertEqual(code, 200)
            self.assertTrue(response["ok"])
            code, response = router.invoke({"tool": "r3.other", "params": {}})
            self.assertEqual(code, 403)
            self.assertFalse(response["ok"])
            code, response = router.invoke({"tool": "r3.status", "params": {"extra": 1}})
            self.assertEqual(code, 403)
            self.assertFalse(response["ok"])
            with sqlite3.connect(path) as db:
                outcomes = db.execute("SELECT outcome FROM tool_audit ORDER BY id").fetchall()
            self.assertEqual(outcomes, [("OK",), ("DENIED",), ("DENIED",)])


if __name__ == "__main__":
    unittest.main()
