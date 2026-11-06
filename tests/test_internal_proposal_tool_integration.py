"""Native R3 proposal tools invoke the internal Riverview registry interface."""
import json
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.native_tools import NativeTools
from runtime.resident_identity import PREFIX, digest_secret
from runtime.tool_server import build_router, handler_for


class InternalProposalToolIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.authority_path = root / "authority.db"
        self.tool_path = root / "tools.db"
        initialize_empty_schema(self.authority_path)
        self.authority = R3Authority(self.authority_path)
        credential_id = uuid.uuid4().hex
        self.r3_token = PREFIX + "." + credential_id + "." + "A" * 43
        with sqlite3.connect(self.authority_path) as db:
            db.execute("""INSERT INTO resident_credentials
                (credential_id,principal,secret_hash,created_at,expires_at,revoked_at,issued_by,idempotency_key)
                VALUES (?,?,?,?,?,?,?,?)""", (credential_id, "resident:grace",
                digest_secret(credential_id, self.r3_token), time.time(), time.time()+3600,
                None, "human:steward:test", "resident-proposal-test"))

        self.institution_token = "institution-resident-test-credential"
        self.records = {}
        self.requests = []
        outer = self
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                outer.requests.append(("POST", self.path))
                if self.headers.get("Authorization") != "Bearer " + outer.institution_token:
                    return self.send_error(401)
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if data.get("expected_principal") != "resident:grace":
                    return self.send_error(403)
                key = data["idempotency_key"]
                digest = __import__("hashlib").sha256(json.dumps(data["content"],
                    sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                record = outer.records.get(key)
                if record and record["content_sha256"] != digest:
                    return self.send_error(409)
                if not record:
                    record = {"proposal_id": "proposal:" + str(uuid.uuid4()), "revision": 1,
                        "content_sha256": digest, "author_principal_id": "resident:grace",
                        "correlation_id": data["correlation_id"], "lifecycle_status": "DRAFT",
                        "persistence": "durably_persisted", "readback_verified": True}
                    outer.records[key] = record
                self._send(201, record)
            def do_GET(self):
                outer.requests.append(("GET", self.path))
                if self.headers.get("Authorization") != "Bearer " + outer.institution_token:
                    return self.send_error(401)
                proposal_id = self.path.rsplit("/", 1)[-1]
                record = next((r for r in outer.records.values() if r["proposal_id"] == proposal_id), None)
                if not record:
                    return self.send_error(404)
                self._send(200, {"proposal": {"proposal_id": proposal_id,
                    "created_by": "resident:grace", "lifecycle_status": "DRAFT"},
                    "revision": {"revision": 1, "content_sha256": record["content_sha256"]}})
            def _send(self, status, value):
                body = json.dumps(value).encode()
                self.send_response(status); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *_args):
                return
        self.registry_server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.registry_server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.registry_server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.registry_server.shutdown)
        resident_credential_file = root / "resident-credential"
        resident_credential_file.write_text(self.institution_token, encoding="ascii")
        resident_credential_file.chmod(0o600)
        router = build_router(audit_db=root / "tools.db", authority_db=self.authority_path,
            institutional_proposal_url=(
                f"http://127.0.0.1:{self.registry_server.server_port}"
                "/api/v1/internal/resident-proposals"),
            institutional_proposal_credential_file=resident_credential_file)
        self.tool_server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(router))
        tool_thread = threading.Thread(target=self.tool_server.serve_forever, daemon=True)
        tool_thread.start()
        self.addCleanup(self.tool_server.server_close)
        self.addCleanup(tool_thread.join, 2)
        self.addCleanup(self.tool_server.shutdown)
        self.native = NativeTools(f"http://127.0.0.1:{self.tool_server.server_port}",
            timeout=5, allowed_tools=("r3.proposal.submit", "r3.proposal.status"),
            credential=self.r3_token)
        with sqlite3.connect(self.authority_path) as db:
            db.executemany("""INSERT INTO capability_grants
                (grant_id,principal,resource_ref,action,operation,scope_ref,active,approved_by)
                VALUES (?,?,?,?,?,?,1,?)""", [
                ("grant:proposal-write", "resident:grace", "riverview:institutional-proposals",
                 "proposal.draft.submit", "write", "institution:proposal-drafts", "human:steward:test"),
                ("grant:proposal-read", "resident:grace", "riverview:institutional-proposals",
                 "proposal.status.read", "read", "institution:proposal-drafts", "human:steward:test")])

    def test_native_grace_tool_submits_and_reads_internal_proposal(self):
        descriptor = next(x for x in self.native.discover() if x["tool"] == "r3.proposal.submit")
        content = {"title": "Website clock", "summary": "Add a visible date/time clock.",
            "objective": "Display the current date and time on the Riverview website.",
            "scope": "Website change only after Steward approval.",
            "proposed_approach": "Use the browser's locale-aware date formatting and update at a bounded interval.",
            "constraints": ["Do not implement before approval."],
            "acceptance_criteria": ["Date and time are visible and update correctly."],
            "tags": ["website", "clock"]}
        result = json.loads(self.native.invoke(descriptor, {"content": content},
            correlation_id="clock-proposal-test"))["result"]
        self.assertTrue(result["persisted"])
        self.assertFalse(result["approval_granted"])
        self.assertEqual(result["author_principal_id"], "resident:grace")
        self.assertEqual([method for method, _ in self.requests], ["POST"])
        retry = json.loads(self.native.invoke(descriptor, {"content": content},
            correlation_id="clock-proposal-test"))["result"]
        self.assertEqual(retry["proposal_id"], result["proposal_id"])
        self.assertEqual(len(self.records), 1)
        status_tool = next(x for x in self.native.discover() if x["tool"] == "r3.proposal.status")
        status = json.loads(self.native.invoke(status_tool,
            {"proposal_id": result["proposal_id"]}, correlation_id="clock-status-test"))["result"]
        self.assertEqual(status["lifecycle_status"], "DRAFT")
        self.assertEqual([method for method, _ in self.requests], ["POST", "POST", "GET"])
        self.assertEqual(result["content_sha256"], status["content_sha256"])

    def test_r3_grant_and_internal_canonical_identity_are_both_required(self):
        from runtime.institutional_proposals import InstitutionalProposalClient, InstitutionalProposalError
        client = InstitutionalProposalClient(
            f"http://127.0.0.1:{self.registry_server.server_port}/api/v1/internal/resident-proposals",
            self.institution_token)
        content = {"title": "Clock", "summary": "Date and time display", "objective": "Display time",
            "scope": "Website", "proposed_approach": "Locale-aware clock", "constraints": [],
            "acceptance_criteria": ["Clock is visible"], "tags": []}
        with self.assertRaises(InstitutionalProposalError):
            client.submit(content, principal="resident:forged", correlation_id="forged-identity")
        descriptor = next(x for x in self.native.discover() if x["tool"] == "r3.proposal.submit")
        with sqlite3.connect(self.authority_path) as db:
            db.execute("DELETE FROM capability_grants WHERE grant_id='grant:proposal-write'")
        requests_before_denied_r3_call = len(self.requests)
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as denied:
            self.native.invoke(descriptor, {"content": content}, correlation_id="no-r3-grant")
        self.assertEqual(denied.exception.code, 403)
        self.assertEqual(len(self.requests), requests_before_denied_r3_call)


if __name__ == "__main__":
    unittest.main()
