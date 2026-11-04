# R3 CONTROLLED SOURCE
# File: tests/test_real_authority_tool_roundtrip.py
# Component: R3-GRACE-REAL-AUTHORITY-ROUNDTRIP
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent HTTP tool roundtrip using real R3 auth DB, credential, grants and journal.
# Execution Model: Ephemeral loopback HTTP and isolated SQLite; no production state or R2 services.
# Observability: Live HTTP result, exact authorization evidence, audit and journal rows.
# Dependencies: Python stdlib, R3 native modules only.
# Authority: Steward unified release #16/#28, no synthetic production work.
# Changed: 2026-11-04 UTC | R3-GRACE-ID-007 | Verify full resident tool execution contract.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_real_authority_tool_roundtrip -v
# History/Predecessor: New permanent contract.
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError

from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.grant_management import R3GrantManagement
from runtime.governed_tools import ExecutionAttemptLedger, GovernedToolGateway
from runtime.grace_native_capabilities import EvidenceJournal, register_grace_operational_tools
from runtime.institution import Journal
from runtime.native_tools import NativeTools
from runtime.resident_identity import R3ResidentIdentity
from runtime.tool_server import ToolRouter, handler_for


class RealR3AuthorizationRoundtripTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.authority_path = root / "authority.db"
        initialize_empty_schema(self.authority_path)
        authority = R3Authority(self.authority_path)
        self.authority = authority
        def steward(context):
            if context != "session-steward":
                raise PermissionError("No authenticated human session")
            return "human:steward:unit"
        management = R3GrantManagement(authority, steward)
        self.management = management
        token = management.issue_resident_credential(
            steward_context="session-steward", resident_principal="resident:grace",
            expires_at=time.time()+3600, reason="R3 resident integration",
            idempotency_key="credential-integration")["credential"]
        self.token = token
        journal_path = root / "institution.db"
        self.journal = Journal(journal_path)
        self.addCleanup(self.journal.db.close)
        attempts_conn = sqlite3.connect(root / "attempts.db", check_same_thread=False)
        self.addCleanup(attempts_conn.close)
        gateway = GovernedToolGateway(
            identity_resolver=R3ResidentIdentity(authority).authenticate,
            verifier=authority, audit=authority.audit,
            write_ledger=ExecutionAttemptLedger(attempts_conn, threading.Lock()))
        register_grace_operational_tools(gateway, evidence_journal=EvidenceJournal(journal_path))
        router = ToolRouter(root / "tool-audit.db", governed=gateway)
        self.addCleanup(router.db.close)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(router))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.client = NativeTools(
            "http://127.0.0.1:" + str(server.server_port), timeout=3,
            allowed_tools=("r3.resources.local_snapshot", "r3.evidence.record"),
            credential_provider=lambda: self.token)

    def approve(self, resource_ref, action, operation, *, key):
        request = self.management.request(
            steward_context="session-steward", target_principal="resident:grace",
            resource_ref=resource_ref, action=action, operation=operation,
            scope_ref="institution:r3", reason="Test isolated canonical authority",
            idempotency_key=key)
        return self.management.decide(
            steward_context="session-steward", request_id=request["request_id"],
            approve=True, reason="Test verified Steward authorization")["grant_id"]

    def descriptor(self, name):
        return next(item for item in self.client.discover() if item["tool"] == name)

    def test_full_read_then_write_with_same_canonical_db(self):
        self.approve("registry:local", "inventory.snapshot", "read", key="read-approval")
        write_id = self.approve(
            "journal:institution", "evidence.record", "write", key="write-approval")
        read = self.client.invoke(
            self.descriptor("r3.resources.local_snapshot"),
            {"scope_ref": "institution:r3"}, correlation_id="read-1")
        self.assertEqual(json.loads(read)["authorization"]["operation"], "read")
        evidence = self.client.invoke(
            self.descriptor("r3.evidence.record"),
            {"scope_ref": "institution:r3", "objective_id": "objective-real",
             "statement": "Host capacity was observed"},
            correlation_id="write-1")
        result = json.loads(evidence)
        self.assertEqual(result["authorization"]["grant_id"], write_id)
        self.assertEqual(result["result"]["review_status"], "NOT_INDEPENDENTLY_VERIFIED")
        with sqlite3.connect(self.authority_path) as db:
            rows = db.execute(
                "SELECT operation,outcome FROM capability_audit ORDER BY id").fetchall()
            self.assertEqual(rows, [
                ("read", "AUTHORIZED"), ("read", "COMPLETED"),
                ("write", "AUTHORIZED"), ("write", "COMPLETED")])
        with sqlite3.connect(self.journal.db.execute("PRAGMA database_list").fetchone()[2]) as db:
            saved = db.execute(
                "SELECT detail FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()
        self.assertEqual(json.loads(saved[0])["acceptance"],
                         "NOT_INDEPENDENTLY_VERIFIED")

    def test_resident_inference_executes_real_governed_read_and_write(self):
        import asyncio
        from runtime.resident_inference import Inbox, ResidentInference
        self.approve("registry:local", "inventory.snapshot", "read", key="inference-read")
        self.approve("journal:institution", "evidence.record", "write", key="inference-write")
        self.client.allowed_tools = ("r3.resources.local_snapshot", "r3.evidence.record")
        class Endpoint:
            def __init__(self):
                self.turn = 0
            def complete(self, messages, tools):
                self.turn += 1
                if self.turn == 1:
                    message = {"role": "assistant", "content": None,
                               "tool_calls": [{"id": "read-resource", "type": "function",
                                 "function": {"name": "r3.resources.local_snapshot",
                                              "arguments": '{"scope_ref":"institution:r3"}'}}]}
                elif self.turn == 2:
                    observed = json.loads(messages[-1]["content"])
                    assert observed["authorization"]["operation"] == "read"
                    message = {"role": "assistant", "content": None,
                               "tool_calls": [{"id": "record-evidence", "type": "function",
                                 "function": {"name": "r3.evidence.record",
                                              "arguments": json.dumps({
                                                  "scope_ref": "institution:r3",
                                                  "objective_id": "objective-http-activity",
                                                  "statement": "Observed local registry from governed tool",
                                                  "evidence_refs": ["read-resource"]})}}]}
                else:
                    written = json.loads(messages[-1]["content"])
                    assert written["authorization"]["operation"] == "write"
                    message = {"role": "assistant",
                               "content": json.dumps({"state": "complete",
                                    "evidence": {"journal_event": written["result"]["event_id"]}})}
                return {"model": "contract-endpoint", "choices": [{"message": message}]}
        inbox = Inbox(self.journal.db)
        event = inbox.enqueue("Grace", "RESIDENT_ACTIVITY", {
            "assignment_id": "objective-http-activity",
            "objective": "Read local host inventory, then record observed evidence",
            "acceptance_criteria": [{"id": "inventory", "description": "Host observed"},
                                    {"id": "evidence", "description": "Evidence event persisted"}]})
        worker = ResidentInference(inbox, Endpoint(), tools=self.client, system_prompt="Grace",
                                   continuation_event_types=("RESIDENT_ACTIVITY",))
        asyncio.run(worker("Grace"))
        row = self.journal.db.execute(
            "SELECT status,result FROM resident_inbox WHERE id=?", (event,)).fetchone()
        self.assertEqual(row[0], "COMPLETED")
        self.assertEqual(json.loads(row[1])["objective_status"], "UNVERIFIED")
        self.assertEqual(self.journal.db.execute(
            "SELECT count(*) FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()[0], 1)
        review = self.journal.db.execute(
            "SELECT status FROM verification_requests WHERE source_event_id=?", (event,)).fetchone()
        self.assertEqual(review[0], "PENDING")
        self.assertEqual(self.journal.db.execute(
            "SELECT count(*) FROM resident_turns WHERE event_id=? AND kind='TOOL_RESULT'",(event,)).fetchone()[0],2)

    def test_revoked_grant_denies_new_http_invocation(self):
        grant_id = self.approve(
            "journal:institution", "evidence.record", "write", key="approve-before-revoke")
        self.management.revoke(
            steward_context="session-steward", grant_id=grant_id,
            reason="Revocation must stop execution")
        with self.assertRaises(HTTPError) as caught:
            self.client.invoke(
                self.descriptor("r3.evidence.record"),
                {"scope_ref": "institution:r3", "objective_id": "obj",
                 "statement": "Should not execute"}, correlation_id="write-revoked")
        self.assertEqual(caught.exception.code, 403)

    def test_credential_revocation_denies_even_granted_read(self):
        self.approve("registry:local", "inventory.snapshot", "read", key="approve-readable")
        with sqlite3.connect(self.authority_path) as db:
            db.execute("UPDATE resident_credentials SET revoked_at=?", (time.time(),))
        with self.assertRaises(HTTPError) as caught:
            self.client.invoke(
                self.descriptor("r3.resources.local_snapshot"),
                {"scope_ref": "institution:r3"}, correlation_id="read-revoked")
        self.assertEqual(caught.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
