# R3 CONTROLLED SOURCE
# File: tests/test_native_tools.py
# Component: R3-NATIVE-TOOLS-REGRESSION
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: Permanent native tool catalog visibility and invocation regression.
# Authority: Local visibility never grants execution; the broker remains authoritative.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Verify no resident-local list is required for newly registered broker tools.
# Supersedes: Revision 1.0.0; existing explicit visibility filters remain testable.
# Contracts: docs/r3-native-tool-contract.md; docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md.
# Tests: This module.
# History/Predecessor: Git blob 51424b2e151925e490aa285fd3242d9b613188b8 at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
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

    def test_discovery_uses_central_catalog_without_resident_local_allowlist(self):
        other = dict(self.descriptor, tool="newly.registered",
                     definition={"type": "function", "function": {
                         "name": "newly.registered", "parameters": {"type": "object"}}})
        client = NativeTools("http://127.0.0.1:9000", 5, None)
        with patch.object(NativeTools, "_request", return_value=[self.descriptor, other]):
            self.assertEqual(client.discover(), [self.descriptor, other])

    def test_broker_receives_catalog_tool_without_local_visibility_list(self):
        client = NativeTools("http://127.0.0.1:9000", 5, None)
        other = dict(self.descriptor, tool="newly.registered",
                     definition={"type": "function", "function": {
                         "name": "newly.registered", "parameters": {"type": "object"}}})
        with patch.object(NativeTools, "_request", return_value={"ok": True, "result": "done"}) as request:
            client.invoke(other, {})
            self.assertEqual(request.call_args.args[2]["tool"], "newly.registered")

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
