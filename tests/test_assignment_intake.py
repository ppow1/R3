# R3 CONTROLLED SOURCE
# File: tests/test_assignment_intake.py
# Component: R3-ASSIGNMENT-INTAKE-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-03 UTC (exact time unverified)
# Created By: ChatGPT GPT-6 via GitHub API
# Purpose: Permanent contract coverage for authenticated durable assignment intake.
# Execution Model: Isolated loopback HTTP server and temporary SQLite database.
# Observability: HTTP assertions and durable inbox/assignment lineage inspection.
# Dependencies: Python standard library; runtime.assignment_intake.
# Authority: hints/engineering-test-policy.md; no production scheduler test events.
# Changed: 2026-11-03 UTC | R3-ASSIGNMENT-INTAKE-001 | ChatGPT GPT-6 | Add reusable assignment intake contracts.
# Supersedes: None
# Contracts: docs/r3-assignment-intake-contract.md
# Tests: python3 -m unittest discover -s tests
# History/Predecessor: New file.
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from runtime.assignment_intake import create_server


class AssignmentIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = self.root / "institution.db"
        self.token_file = self.root / "steward.token"
        self.token = "test-only-token-value-with-more-than-32-characters"
        self.token_file.write_text(self.token, encoding="utf-8")
        os.chmod(self.token_file, 0o600)
        self.server = create_server(
            self.database, self.token_file, {"Grace", "Helen"}, {"Grace"}, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temp.cleanup()

    @staticmethod
    def assignment(**overrides):
        body = {
            "resident": "Grace",
            "assignment_id": "R3-INTAKE-CONTRACT-001",
            "objective": "Review the configured read-only runtime capabilities and report observed results.",
            "acceptance_criteria": [
                {"id": "status", "version": "1", "description": "Report the observed R3 status response."},
                {"id": "evidence", "version": "1", "description": "Preserve observed tool results as evidence."},
            ],
        }
        body.update(overrides)
        return body

    def request(self, method, path, *, payload=None, idempotency_key=None, token=None):
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)

    def test_authenticated_assignment_is_durable_and_status_is_readable(self):
        code, submitted = self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="assignment-001", token=self.token)
        self.assertEqual(code, 202)
        self.assertEqual(submitted["status"], "PENDING")
        event_id = submitted["event_id"]

        code, status = self.request(
            "GET", f"/v1/assignments/{event_id}", token=self.token)
        self.assertEqual(code, 200)
        self.assertEqual(status["assignment_id"], "R3-INTAKE-CONTRACT-001")
        self.assertEqual(status["events"][0]["event_id"], event_id)
        self.assertEqual(status["events"][0]["status"], "PENDING")
        self.assertEqual(status["verification"]["verification_status"], "NOT_REQUESTED")

    def test_identical_retries_return_the_same_durable_event(self):
        first = self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="assignment-retry", token=self.token)
        second = self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="assignment-retry", token=self.token)
        self.assertEqual(first[0], 202)
        self.assertEqual(second[0], 200)
        self.assertEqual(second[1]["status"], "DUPLICATE")
        self.assertEqual(second[1]["event_id"], first[1]["event_id"])

    def test_reused_idempotency_key_with_changed_content_conflicts(self):
        self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="assignment-conflict", token=self.token)
        changed = self.assignment(objective="Changed objective")
        code, response = self.request(
            "POST", "/v1/assignments", payload=changed,
            idempotency_key="assignment-conflict", token=self.token)
        self.assertEqual(code, 409)
        self.assertIn("different content", response["error"])

    def test_assignment_id_cannot_be_reused_for_changed_content(self):
        self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="assignment-original", token=self.token)
        changed = self.assignment(objective="Changed objective")
        code, response = self.request(
            "POST", "/v1/assignments", payload=changed,
            idempotency_key="assignment-new-key", token=self.token)
        self.assertEqual(code, 409)
        self.assertIn("Assignment identifier", response["error"])

    def test_missing_or_wrong_bearer_token_cannot_enqueue_work(self):
        code, _ = self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="unauthorized", token=None)
        self.assertEqual(code, 401)
        code, _ = self.request(
            "POST", "/v1/assignments", payload=self.assignment(),
            idempotency_key="unauthorized", token="wrong-token")
        self.assertEqual(code, 401)

    def test_unregistered_resident_is_rejected(self):
        unknown = self.assignment(resident="Unknown")
        code, _ = self.request(
            "POST", "/v1/assignments", payload=unknown,
            idempotency_key="unknown-resident", token=self.token)
        self.assertEqual(code, 404)

    def test_registered_resident_without_continuation_support_is_rejected(self):
        assignment = self.assignment(resident="Helen")
        code, response = self.request(
            "POST", "/v1/assignments", payload=assignment,
            idempotency_key="noncontinuing-resident", token=self.token)
        self.assertEqual(code, 409)
        self.assertIn("durable assignment activities", response["error"])

    def test_token_permissions_and_loopback_binding_fail_closed(self):
        os.chmod(self.token_file, 0o644)
        with self.assertRaisesRegex(ValueError, "group- or world-accessible"):
            create_server(self.database, self.token_file, {"Grace"}, {"Grace"}, port=0)
        os.chmod(self.token_file, 0o600)
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            create_server(self.database, self.token_file, {"Grace"}, {"Grace"},
                          host="0.0.0.0", port=8766)


if __name__ == "__main__":
    unittest.main()
