# R3 CONTROLLED SOURCE
# File: tests/test_native_tools.py
# Component: R3-NATIVE-TOOLS-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent native tool authorization and contract regression.
# Contracts: docs/r3-native-tool-contract.md
import unittest
from unittest.mock import patch

from runtime.native_tools import NativeTools, ToolContractError


class NativeToolTests(unittest.TestCase):
    def setUp(self):
        self.client = NativeTools("http://127.0.0.1:9000", 5, ("status",))
        self.descriptor = {
            "tool": "status",
            "definition": {"type": "function", "function": {"name": "status", "parameters": {"type": "object"}}},
            "read_only": True,
        }

    def test_discovery_filters_allowlist(self):
        other = dict(self.descriptor, tool="other",
                     definition={"type": "function", "function": {"name": "other"}})
        with patch.object(NativeTools, "_request", return_value=[self.descriptor, other]):
            self.assertEqual(self.client.discover(), [self.descriptor])

    def test_rejects_mismatched_definition(self):
        wrong = dict(self.descriptor, definition={"function": {"name": "other"}})
        with patch.object(NativeTools, "_request", return_value=[wrong]):
            with self.assertRaises(ToolContractError):
                self.client.discover()

    def test_rejects_write_even_if_allowlisted(self):
        with patch.object(NativeTools, "_request") as request:
            with self.assertRaises(PermissionError):
                self.client.invoke(dict(self.descriptor, read_only=False), {})
            request.assert_not_called()

    def test_rejects_unlisted_tool(self):
        with patch.object(NativeTools, "_request") as request:
            with self.assertRaises(PermissionError):
                self.client.invoke(dict(self.descriptor, tool="other"), {})
            request.assert_not_called()

    def test_invokes_allowed_read_only_tool(self):
        with patch.object(NativeTools, "_request", return_value={"ok": True, "result": {"healthy": True}}) as request:
            self.assertEqual(self.client.invoke(self.descriptor, {}), '{"healthy": true}')
            request.assert_called_once()
            payload = request.call_args.args[2]
            self.assertEqual(payload["tool"], "status")
            self.assertEqual(payload["params"], {})
            self.assertRegex(payload["correlation_id"], r"^read-[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
