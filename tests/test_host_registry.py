# R3 CONTROLLED SOURCE
# File: tests/test_host_registry.py
# Component: R3-HOST-REGISTRY-TESTS
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent external host profile and fail-closed regression.
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from runtime.host_execution import HostExecutor, HostConfigurationError


class HostRegistryTests(unittest.TestCase):
    def setup_files(self, root):
        catalog, hosts = root / "tools.json", root / "hosts.json"
        catalog.write_text(json.dumps({"tools": [{
            "name": "r3.remote.uptime", "transport": "ssh", "host": "compute-a",
            "argv": ["/usr/bin/uptime"], "timeout_seconds": 10, "read_only": True
        }]}))
        hosts.write_text(json.dumps({"hosts": {"compute-a": {
            "hostname": "192.0.2.20", "user": "operator", "port": 2222,
            "identity_file": "/home/operator/.ssh/automation",
            "known_hosts_file": "/home/operator/.ssh/known_hosts"
        }}}))
        return catalog, hosts

    def test_registry_controls_ssh_identity_and_target(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog, hosts = self.setup_files(Path(temp))
            executor = HostExecutor(catalog, hosts)
            with patch("runtime.host_execution.subprocess.run",
                       return_value=SimpleNamespace(returncode=0, stdout="ok", stderr="")) as run:
                executor.invoke("r3.remote.uptime", {})
            args = run.call_args.args[0]
            self.assertIn("operator@192.0.2.20", args)
            self.assertIn("/home/operator/.ssh/automation", args)
            self.assertIn("UserKnownHostsFile=/home/operator/.ssh/known_hosts", args)
            self.assertIn("2222", args)
            self.assertIn("StrictHostKeyChecking=yes", args)

    def test_unknown_host_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog, hosts = self.setup_files(Path(temp))
            hosts.write_text('{"hosts": {}}')
            with self.assertRaises(HostConfigurationError):
                HostExecutor(catalog, hosts)

    def test_invalid_profile_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            catalog, hosts = self.setup_files(Path(temp))
            hosts.write_text(json.dumps({"hosts": {"compute-a": {
                "hostname": "192.0.2.20;id", "user": "operator", "port": 22,
                "identity_file": "/tmp/id", "known_hosts_file": "/tmp/known_hosts"
            }}}))
            with self.assertRaises(HostConfigurationError):
                HostExecutor(catalog, hosts)


if __name__ == "__main__":
    unittest.main()
