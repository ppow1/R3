# R3 CONTROLLED SOURCE
# File: tests/test_lan_execution.py
# Component: R3-LAN-EXECUTION-TESTS
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent LAN SSH argument and authorization regression.
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from runtime.host_execution import HostExecutor, HostConfigurationError


class LanExecutionTests(unittest.TestCase):
    def catalog(self, path, argv=None, host="octominer1"):
        path.write_text(json.dumps({"tools": [{
            "name": "r3.host.octo1.uptime", "transport": "ssh", "host": host,
            "argv": argv or ["/usr/bin/uptime"], "timeout_seconds": 12,
            "read_only": True,
        }]}))

    def test_fixed_ssh_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tools.json"
            self.catalog(path)
            executor = HostExecutor(path)
            with patch("runtime.host_execution.subprocess.run",
                       return_value=SimpleNamespace(returncode=0, stdout="up", stderr="")) as run:
                result = executor.invoke("r3.host.octo1.uptime", {})
            self.assertEqual(result["stdout"], "up")
            args = run.call_args.args[0]
            self.assertEqual(args, ["/usr/bin/ssh", "-o", "BatchMode=yes",
                                    "-o", "StrictHostKeyChecking=yes",
                                    "-o", "ConnectTimeout=10", "--",
                                    "octominer1", "/usr/bin/uptime"])
            self.assertFalse(run.call_args.kwargs["shell"])

    def test_rejects_unsafe_host_and_command(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tools.json"
            self.catalog(path, host="octo1;id")
            with self.assertRaises(HostConfigurationError):
                HostExecutor(path)
            self.catalog(path, argv=["/usr/bin/uptime", ";id"])
            with self.assertRaises(HostConfigurationError):
                HostExecutor(path)

    def test_unlisted_arguments_never_execute(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "tools.json"
            self.catalog(path)
            with patch("runtime.host_execution.subprocess.run") as run:
                with self.assertRaises(PermissionError):
                    HostExecutor(path).invoke("r3.host.octo1.uptime", {"command": "id"})
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
