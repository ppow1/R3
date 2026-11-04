# R3 CONTROLLED SOURCE
# File: tests/test_host_execution.py
# Component: R3-HOST-EXECUTION-TESTS
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent local host execution and native router regression.
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime.host_execution import HostExecutor, HostConfigurationError
from runtime.tool_server import ToolRouter


class HostExecutionTests(unittest.TestCase):
    def test_local_execution_and_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = root / "tools.json"
            catalog.write_text(json.dumps({"tools": [{
                "name": "r3.host.python", "description": "Python version",
                "argv": ["/usr/bin/python3", "--version"],
                "timeout_seconds": 5, "read_only": True,
            }]}))
            executor = HostExecutor(catalog)
            router = ToolRouter(root / "audit.db", executor)
            self.assertEqual(router.discover()[1]["tool"], "r3.host.python")
            code, response = router.invoke({"tool": "r3.host.python", "params": {}})
            self.assertEqual(code, 200)
            self.assertEqual(response["result"]["returncode"], 0)
            self.assertIn("Python", response["result"]["stdout"])
            code, _ = router.invoke({"tool": "r3.host.python", "params": {"cmd": "whoami"}})
            self.assertEqual(code, 403)
            with sqlite3.connect(root / "audit.db") as db:
                self.assertEqual(db.execute("SELECT outcome FROM tool_audit ORDER BY id").fetchall(),
                                 [("OK",), ("DENIED",)])

    def test_rejects_shell_and_write_capabilities(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog = Path(temp) / "tools.json"
            catalog.write_text(json.dumps({"tools": [{
                "name": "r3.bad", "argv": ["sh", "-c", "echo hi"],
                "timeout_seconds": 5, "read_only": True,
            }]}))
            with self.assertRaises(HostConfigurationError):
                HostExecutor(catalog)
            catalog.write_text(json.dumps({"tools": [{
                "name": "r3.bad", "argv": ["/usr/bin/python3", "--version"],
                "timeout_seconds": 5, "read_only": False,
            }]}))
            with self.assertRaises(HostConfigurationError):
                HostExecutor(catalog)


if __name__ == "__main__":
    unittest.main()
