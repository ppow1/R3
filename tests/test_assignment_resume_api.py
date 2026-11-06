# R3 CONTROLLED TEST
# File: tests/test_assignment_resume_api.py
# Component: R3-AUTHORIZED-ASSIGNMENT-RESUMPTION-TESTS
# File Revision: 1.0.0
# Created: 2026-11-06T02:45:00Z
# Created By: Codex GPT-6, acting on Steward instruction
# Purpose: Verify resident-authenticated, exact-grant resumption through assignment intake.
# Execution Model: Isolated temporary SQLite stores and loopback HTTP service.
# Observability: Durable assignment lineage and canonical capability audit assertions.
# Dependencies: runtime.assignment_intake; runtime.capability_authority; runtime.resident_identity.
# Authority: Grace Autonomy recovery; tests never use production services, records, or credentials.
# Tests: `python -m unittest tests.test_assignment_resume_api -v`
# History/Predecessor: New file; no predecessor.
from __future__ import annotations

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
from urllib.request import Request, urlopen

from runtime.assignment_intake import AssignmentIntake, create_server
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.resident_identity import PREFIX, digest_secret


class AssignmentResumeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.inbox_db = root / "institution.db"
        self.authority_db = root / "authority.db"
        initialize_empty_schema(self.authority_db)
        self.authority = R3Authority(self.authority_db)
        credential_id = uuid.uuid4().hex
        self.resident_credential = PREFIX + "." + credential_id + "." + "A" * 43
        self.service_credential = "service-intake-test-credential-with-more-than-32-bytes"
        now = time.time()
        with sqlite3.connect(self.authority_db) as db:
            db.execute(
                """INSERT INTO resident_credentials
                   (credential_id,principal,secret_hash,created_at,expires_at,
                    revoked_at,issued_by,idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (credential_id, "resident:Grace", digest_secret(credential_id, self.resident_credential),
                 now, now + 3600, None, "human:steward:test", "resume-test-credential"),
            )
        token_file = root / "assignment-intake.token"
        token_file.write_text(self.service_credential + "\n", encoding="utf-8")
        token_file.chmod(0o600)
        self.server = create_server(
            self.inbox_db, token_file, {"Grace"}, {"Grace"},
            host="127.0.0.1", port=0, authority_db=self.authority_db,
        )
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server_thread.join, 3)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        intake = AssignmentIntake(self.inbox_db, self.service_credential, {"Grace"}, {"Grace"})
        result = intake.submit({
            "resident": "Grace",
            "assignment_id": "resume-test",
            "objective": "Finish the accepted objective",
            "acceptance_criteria": [{"id": "criterion", "version": "1", "description": "Verified"}],
        }, "resume-intake-key")
        self.root_event_id = result["event_id"]
        with sqlite3.connect(self.inbox_db) as db:
            db.execute(
                "UPDATE resident_inbox SET status='BLOCKED',result=? WHERE id=?",
                (json.dumps({"decision": {"state": "blocked"}, "dependency": "Test dependency"}),
                 self.root_event_id),
            )
        self.grant()

    def grant(self, principal="resident:Grace"):
        with sqlite3.connect(self.authority_db) as db:
            db.execute(
                """INSERT INTO capability_grants
                   (grant_id,principal,resource_ref,action,operation,scope_ref,active,approved_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("grant:resume-test", principal, "assignment:resume-test",
                 "resident.activity.resume", "write", "assignment:resume-test", 1,
                 "human:steward:test"),
            )

    def post_resume(self, *, resident_credential=None, evidence="Dependency was resolved"):
        headers = {
            "Authorization": "Bearer " + self.service_credential,
            "Content-Type": "application/json",
        }
        if resident_credential is not None:
            headers["X-R3-Resident-Credential"] = resident_credential
        request = Request(
            f"{self.base_url}/v1/assignments/{self.root_event_id}/resume",
            data=json.dumps({"resolution_evidence": evidence}).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        return urlopen(request, timeout=3)

    def grant_dispatch(self, *, resource="work-order:work-77", scope="objective:objective-33"):
        with sqlite3.connect(self.authority_db) as db:
            db.execute(
                """INSERT INTO capability_grants
                   (grant_id,principal,resource_ref,action,operation,scope_ref,active,approved_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("grant:dispatch-test", "resident:Grace", resource,
                 "resident.assignment.dispatch", "write", scope, 1,
                 "human:steward:test"),
            )

    @staticmethod
    def dispatch_payload():
        return {
            "schema_version": "riverview-comms-work-order-dispatch:1",
            "resident": "Grace", "assignment_id": "assignment-work-77",
            "objective": "Add a date/time clock to the Riverview website",
            "acceptance_criteria": [{
                "id": "clock-visible", "version": "1",
                "description": "Clock renders the current date and time accurately",
            }],
            "proposal_id": "proposal-11", "objective_id": "objective-33",
            "work_order_id": "work-77", "owner": "website-engineering",
            "constraints": ["Do not deploy before Steward approval"],
            "authority_id": "objective-authority-5",
            "evidence_lineage": ["proposal-11", "objective-33", "work-77"],
            "correlation_id": "comms5-work-77",
        }

    def post_dispatch(self, payload, *, resident_credential=None):
        headers = {
            "Authorization": "Bearer " + self.service_credential,
            "Content-Type": "application/json",
            "Idempotency-Key": "work-order-dispatch-77",
        }
        if resident_credential is not None:
            headers["X-R3-Resident-Credential"] = resident_credential
        request = Request(
            f"{self.base_url}/v2/work-orders/dispatch",
            data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
        )
        return urlopen(request, timeout=3)

    def test_authorized_work_order_dispatch_is_durable_and_idempotent(self):
        self.grant_dispatch()
        payload = self.dispatch_payload()
        with self.post_dispatch(payload, resident_credential=self.resident_credential) as response:
            self.assertEqual(response.status, 202)
            accepted = json.load(response)
        with self.post_dispatch(payload, resident_credential=self.resident_credential) as response:
            self.assertEqual(response.status, 200)
            duplicate = json.load(response)
        self.assertEqual(duplicate, {"event_id": accepted["event_id"], "status": "DUPLICATE"})
        with sqlite3.connect(self.inbox_db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM assignment_intake_assignments "
                "WHERE assignment_id='assignment-work-77'"
            ).fetchone()[0], 1)
            stored = json.loads(db.execute(
                "SELECT payload FROM resident_inbox WHERE id=?", (accepted["event_id"],)
            ).fetchone()[0])
        workflow = stored["institutional_workflow"]
        self.assertEqual(workflow["proposal_id"], "proposal-11")
        self.assertEqual(workflow["objective_id"], "objective-33")
        self.assertEqual(workflow["work_order_id"], "work-77")
        self.assertEqual(workflow["authority_id"], "objective-authority-5")
        self.assertEqual(workflow["constraints"], payload["constraints"])
        self.assertEqual(workflow["evidence_lineage"], payload["evidence_lineage"])
        status_request = Request(
            f"{self.base_url}/v1/assignments/{accepted['event_id']}",
            headers={"Authorization": "Bearer " + self.service_credential},
        )
        with urlopen(status_request, timeout=3) as response:
            status = json.load(response)
        self.assertEqual(status["institutional_workflow"], workflow)
        with self.authority._connect() as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM capability_audit WHERE capability='assignment-intake' "
                "AND action='resident.assignment.dispatch' AND outcome='AUTHORIZED'"
            ).fetchone()[0], 2)

    def test_work_order_dispatch_requires_exact_grant_and_resident_identity(self):
        payload = self.dispatch_payload()
        with self.assertRaises(HTTPError) as missing_credential:
            self.post_dispatch(payload)
        self.assertEqual(missing_credential.exception.code, 401)
        self.grant_dispatch(resource="work-order:other-work-order")
        with self.assertRaises(HTTPError) as wrong_resource:
            self.post_dispatch(payload, resident_credential=self.resident_credential)
        self.assertEqual(wrong_resource.exception.code, 403)
        with sqlite3.connect(self.inbox_db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM assignment_intake_assignments "
                "WHERE assignment_id='assignment-work-77'"
            ).fetchone()[0], 0)

    def test_exact_grant_resumes_once_and_preserves_blocked_lineage(self):
        with self.post_resume(resident_credential=self.resident_credential) as response:
            self.assertEqual(response.status, 202)
            result = json.load(response)
        self.assertEqual(result["status"], "PENDING")
        resumed_event = result["event_id"]
        with self.post_resume(resident_credential=self.resident_credential) as response:
            duplicate = json.load(response)
        self.assertEqual(duplicate["event_id"], resumed_event)
        with sqlite3.connect(self.inbox_db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM resident_inbox WHERE id<>?", (self.root_event_id,)
            ).fetchone()[0], 1)
            self.assertEqual(db.execute(
                "SELECT status FROM resident_inbox WHERE id=?", (self.root_event_id,)
            ).fetchone()[0], "BLOCKED")
            payload = json.loads(db.execute(
                "SELECT payload FROM resident_inbox WHERE id=?", (resumed_event,)
            ).fetchone()[0])
            self.assertEqual(payload["resumed_from_blocked_event_id"], self.root_event_id)
            self.assertEqual(payload["resumption_principal"], "resident:Grace")
            self.assertEqual(payload["resumption_evidence"], "Dependency was resolved")
            self.assertEqual(payload["resumption_grant_id"], "grant:resume-test")
        with self.authority._connect() as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM capability_audit WHERE capability='resident-inbox' "
                "AND action='resident.activity.resume' AND outcome='AUTHORIZED'"
            ).fetchone()[0], 2)

    def test_missing_resident_credential_or_exact_grant_does_not_resume(self):
        with self.assertRaises(HTTPError) as missing:
            self.post_resume(resident_credential=None)
        self.assertEqual(missing.exception.code, 401)

        with sqlite3.connect(self.authority_db) as db:
            db.execute("DELETE FROM capability_grants WHERE grant_id='grant:resume-test'")
        with self.assertRaises(HTTPError) as denied:
            self.post_resume(resident_credential=self.resident_credential)
        self.assertEqual(denied.exception.code, 403)
        with sqlite3.connect(self.inbox_db) as db:
            self.assertEqual(db.execute(
                "SELECT status FROM resident_inbox WHERE id=?", (self.root_event_id,)
            ).fetchone()[0], "BLOCKED")
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM resident_inbox WHERE id<>?", (self.root_event_id,)
            ).fetchone()[0], 0)

    def test_changed_resolution_evidence_conflicts_with_existing_resume(self):
        with self.post_resume(resident_credential=self.resident_credential):
            pass
        with self.assertRaises(HTTPError) as conflict:
            self.post_resume(resident_credential=self.resident_credential,
                             evidence="A different resolution")
        self.assertEqual(conflict.exception.code, 409)


if __name__ == "__main__":
    unittest.main()
