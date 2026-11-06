# R3 CONTROLLED TEST
# File: tests/test_proposal_submission_integration.py
# Component: R3-PROPOSAL-SUBMISSION-INTEGRATION-TESTS
# File Revision: 1.0.2
# Created: 2026-11-06T01:39:36Z
# Created By: Codex GPT-6, acting on Steward instruction
# Purpose: Exercise resident discovery, exact R3 authorization, tool routing, and Comms5 draft/status calls.
# Execution Model: Isolated temporary SQLite stores and local loopback R3 tool HTTP server.
# Observability: Native audit and authority audit assertions; fake Comms5 responses remain in memory.
# Dependencies: runtime.capability_authority; runtime.native_tools; runtime.tool_server; runtime.comms5_proposals.
# Authority: Grace Autonomy P1; no production service or institutional database is used.
# Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add permanent authorized-path regression tests.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Assert router-wrapped proposal result metadata.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Assert authorized backend failures retain FAILED audit status.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md; riverview-comms-contract:5.0
# Tests: `python -m unittest tests.test_proposal_submission_integration -v`
# History/Predecessor: New file; no predecessor.
import json
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.comms5_proposals import Comms5DraftClient, proposal_submission_capability
from runtime.native_tools import NativeTools
from runtime.resident_identity import PREFIX, digest_secret
from runtime.tool_server import ToolRouter, handler_for


class ProposalSubmissionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.authority_path = root / "authority.db"
        initialize_empty_schema(self.authority_path)
        self.authority = R3Authority(self.authority_path)
        credential_id = uuid.uuid4().hex
        self.token = PREFIX + "." + credential_id + "." + "A" * 43
        now = time.time()
        with sqlite3.connect(self.authority_path) as db:
            db.execute(
                """INSERT INTO resident_credentials
                   (credential_id,principal,secret_hash,created_at,expires_at,
                    revoked_at,issued_by,idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (credential_id, "resident:Grace", digest_secret(credential_id, self.token),
                 now, now + 3600, None, "human:steward:test", "proposal-test-credential"),
            )

        self.comms_calls = []
        self.fail_submission = False

        def fake_comms5(operation, arguments):
            self.comms_calls.append((operation, dict(arguments)))
            if operation == "submit_steward_seed":
                if self.fail_submission:
                    raise OSError("private Comms5 transport detail")
                return {
                    "status": "submitted", "executed": True,
                    "seed_id": "seed:integration-1", "proposal_id": "proposal:integration-1",
                    "revision": 1, "lifecycle_status": "DRAFT",
                }
            if operation == "seed_status":
                return {
                    "status": "available", "executed": True,
                    "seed_id": "seed:integration-1", "proposal_id": "proposal:integration-1",
                    "revision": 1, "lifecycle_status": "DRAFT",
                    "revision_record": {"title": "Clock", "objective": "Show date and time"},
                }
            raise AssertionError("No approval or work-order operation may be called")

        comms_client = Comms5DraftClient(
            "https://comms.example/mcp", "test-bearer", call_tool=fake_comms5,
        )
        proposal_capability = proposal_submission_capability(comms_client)
        self.tool_db = root / "tools.db"
        self.router = ToolRouter(
            self.tool_db,
            authority=self.authority,
            capabilities=(proposal_capability,),
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.router))
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(thread.join, 3)
        self.addCleanup(self.server.shutdown)
        self.client = NativeTools(
            f"http://127.0.0.1:{self.server.server_port}",
            timeout=5,
            allowed_tools=("r3.proposal.submit",),
            credential=self.token,
        )
        self.fail_submission = False

    def descriptor(self):
        matches = [x for x in self.client.discover() if x["tool"] == "r3.proposal.submit"]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def grant(self):
        with sqlite3.connect(self.authority_path) as db:
            db.execute(
                """INSERT INTO capability_grants
                   (grant_id,principal,resource_ref,action,operation,scope_ref,active,approved_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("grant:proposal-test", "resident:Grace", "comms5:steward-proposals",
                 "proposal.draft.submit", "write", "institution:proposal-drafts", 1,
                 "human:steward:test"),
            )

    def test_authorized_discovery_submission_and_readback(self):
        self.grant()
        descriptor = self.descriptor()
        self.assertFalse(descriptor["read_only"])
        params = descriptor["definition"]["function"]["parameters"]
        self.assertEqual(params["required"], ["proposal_text"])
        self.assertNotIn("authenticated_principal", params["properties"])

        output = json.loads(self.client.invoke(
            descriptor,
            {"proposal_text": "Title: Clock\nApproach: Add a timezone-aware display."},
            correlation_id="call-clock-test",
        ))
        submission = output["result"]
        self.assertEqual(submission["status"], "persisted")
        self.assertEqual(submission["proposal_id"], "proposal:integration-1")
        self.assertEqual(submission["lifecycle_status"], "DRAFT")
        self.assertFalse(submission["approval_granted"])
        self.assertEqual([name for name, _ in self.comms_calls], [
            "submit_steward_seed", "seed_status",
        ])
        self.assertEqual(self.comms_calls[0][1]["authenticated_principal"], "resident:Grace")
        with self.authority._connect() as db:
            audit = db.execute(
                """SELECT outcome FROM capability_audit
                   WHERE correlation_id='call-clock-test' ORDER BY id"""
            ).fetchall()
        self.assertEqual(audit, [("AUTHORIZED",), ("COMPLETED",)])
        with sqlite3.connect(self.tool_db) as db:
            self.assertEqual(db.execute("SELECT tool,outcome FROM tool_audit").fetchall(),
                             [("r3.proposal.submit", "OK")])

    def test_no_grant_or_scope_tampering_never_calls_comms5(self):
        descriptor = self.descriptor()
        with self.assertRaises(HTTPError) as denied:
            self.client.invoke(
                descriptor, {"proposal_text": "Clock"}, correlation_id="call-no-grant",
            )
        self.assertEqual(denied.exception.code, 403)
        self.assertEqual(self.comms_calls, [])

        self.grant()
        with self.assertRaises(HTTPError) as tampered:
            self.client.invoke(
                descriptor,
                {"proposal_text": "Clock", "scope_ref": "institution:other"},
                correlation_id="call-tampered-scope",
            )
        self.assertEqual(tampered.exception.code, 403)
        self.assertEqual(self.comms_calls, [])

    def test_authorized_backend_failure_is_not_reported_as_permission_denial(self):
        self.grant()
        self.fail_submission = True
        with self.assertRaises(HTTPError) as failure:
            self.client.invoke(
                self.descriptor(), {"proposal_text": "Clock"},
                correlation_id="call-comms-failure",
            )
        self.assertEqual(failure.exception.code, 502)
        with self.authority._connect() as db:
            outcomes = db.execute(
                """SELECT outcome FROM capability_audit
                   WHERE correlation_id='call-comms-failure' ORDER BY id"""
            ).fetchall()
        self.assertEqual(outcomes, [("AUTHORIZED",), ("FAILED",)])
        with sqlite3.connect(self.tool_db) as db:
            self.assertEqual(db.execute("SELECT outcome FROM tool_audit").fetchall(), [("FAILED",)])


if __name__ == "__main__":
    unittest.main()
