# R3 CONTROLLED SOURCE
# File: tests/test_native_governed_client.py
# Component: R3-GRACE-NATIVE-CLIENT-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent client-side governed envelope and server-evidence contract tests.
# Execution Model: Deterministic mock HTTP boundary; no production grants.
# Observability: Assert outbound credential/correlation and fail-closed response parsing.
# Dependencies: Python stdlib, runtime/native_tools.py
# Authority: Steward R3 unified integration; issues #16 and #28.
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-005 | Test governed client contract.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_native_governed_client -v
# History/Predecessor: New controlled test.
import unittest
from unittest.mock import patch
from runtime.native_tools import NativeTools, ToolContractError


class NativeGovernedClientTests(unittest.TestCase):
    def setUp(self):
        self.descriptor = {
            "tool": "r3.operations.write", "read_only": False,
            "resource_id": "resource:operations", "operation": "write",
            "definition": {"type": "function", "function": {
                "name": "r3.operations.write", "parameters": {"type": "object"}}},
        }

    def test_no_credential_never_forwards_write(self):
        client = NativeTools("http://127.0.0.1:9000", 5, ("r3.operations.write",))
        with patch.object(NativeTools, "_request") as request:
            with self.assertRaises(PermissionError):
                client.invoke(self.descriptor, {"scope_ref": "office:operations"},
                              correlation_id="work-1")
            request.assert_not_called()

    def test_authenticated_governed_write_passes_scope_and_correlation(self):
        client = NativeTools("http://127.0.0.1:9000", 5, ("r3.operations.write",),
                             credential_provider=lambda: "resident-secret")
        response = {"ok": True, "result": {
            "status": "ok", "correlation_id": "work-1",
            "authorization": {"principal_id": "resident:grace",
                              "grant_id": "grant-1", "resource_id": "resource:operations",
                              "operation": "write"},
            "result": {"changed": True}}}
        with patch.object(NativeTools, "_request", return_value=response) as request:
            output = client.invoke(self.descriptor, {"scope_ref": "office:operations"},
                                   correlation_id="work-1")
            self.assertIn('"changed": true', output)
            request.assert_called_once_with(
                "POST", "/v1/tools/invoke",
                {"tool": "r3.operations.write", "params": {"scope_ref": "office:operations"},
                 "correlation_id": "work-1"},
                headers={"Authorization": "Bearer resident-secret"})

    def test_server_evidence_required_even_for_success_response(self):
        client = NativeTools("http://127.0.0.1:9000", 5, ("r3.operations.write",),
                             credential_provider=lambda: "resident-secret")
        with patch.object(NativeTools, "_request", return_value={
                "ok": True, "result": {"changed": True}}):
            with self.assertRaises(ToolContractError):
                client.invoke(self.descriptor, {"scope_ref": "office:operations"},
                              correlation_id="work-2")

    def test_scope_and_correlation_required(self):
        client = NativeTools("http://127.0.0.1:9000", 5, ("r3.operations.write",),
                             credential_provider=lambda: "resident-secret")
        with patch.object(NativeTools, "_request") as request:
            with self.assertRaises(PermissionError):
                client.invoke(self.descriptor, {"scope_ref": "office:operations"})
            with self.assertRaises(PermissionError):
                client.invoke(self.descriptor, {}, correlation_id="work-3")
            request.assert_not_called()

    def test_legacy_non_governed_write_still_rejected(self):
        client = NativeTools("http://127.0.0.1:9000", 5, ("r3.operations.write",),
                             credential_provider=lambda: "resident-secret")
        descriptor = dict(self.descriptor)
        descriptor.pop("resource_id")
        descriptor.pop("operation")
        with patch.object(NativeTools, "_request") as request:
            with self.assertRaises(PermissionError):
                client.invoke(descriptor, {"scope_ref": "office:operations"},
                              correlation_id="work-4")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
