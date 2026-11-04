# R3 CONTROLLED SOURCE
# File: tests/test_inbox_cli.py
# Component: R3-DURABLE-EVENT-INTERFACE
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: Permanent CLI submission, inspection and safety regression.
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime.inbox_cli import run


class InboxCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "institution.db"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE residents(name TEXT PRIMARY KEY)")
            db.execute("INSERT INTO residents(name) VALUES ('Grace')")
            from runtime.resident_inference import Inbox
            Inbox(db)

    def tearDown(self):
        self.tmp.cleanup()

    def invoke(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            run(["--db", str(self.db), *args])
        return json.loads(output.getvalue())

    def test_submit_and_inspect_durable_event(self):
        event = self.invoke("submit", "--resident", "Grace", "--event-type", "HOST_CHECK",
                            "--payload", '{"request":"Check uptime"}')
        self.assertEqual(event["status"], "PENDING")
        observed = self.invoke("inspect", "--id", str(event["event_id"]))
        self.assertEqual(observed["resident"], "Grace")
        self.assertEqual(observed["turns"], [])

    def test_review_status_is_read_only_and_preserves_genuine_findings(self):
        with sqlite3.connect(self.db) as db:
            from runtime.verification import VerificationLedger
            ledger = VerificationLedger(db)
            req = ledger.submit_review(7, "real-assignment", [
                {"id": "observed", "description": "Independent host observation"}
            ], {"executor_claim": "done"})
        pending = self.invoke("review", "--assignment-id", "real-assignment")
        self.assertEqual(pending["verification_status"], "PENDING")
        self.assertEqual(pending["findings"], [])
        with sqlite3.connect(self.db) as db:
            VerificationLedger(db).decide_review(
                req, reviewer="independent-reviewer", implementation_revision="observed:7",
                findings=[{"criterion_id":"observed", "result":"INSUFFICIENT_EVIDENCE",
                           "reason":"No independent observation available",
                           "evidence":{"independent_observation":False}}])
        inspected = self.invoke("review", "--assignment-id", "real-assignment")
        self.assertEqual(inspected["verification_status"], "INCONCLUSIVE")
        self.assertEqual(inspected["review_count"], 1)
        self.assertEqual(inspected["findings"][0]["result"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(inspected["findings"][0]["reviewer"], "independent-reviewer")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM verification_requests").fetchone()[0], 1)

    def test_unknown_assignment_does_not_invent_acceptance(self):
        observed = self.invoke("review", "--assignment-id", "not-submitted")
        self.assertEqual(observed["verification_status"], "NOT_REQUESTED")
        self.assertEqual(observed["review_count"], 0)
        self.assertEqual(observed["findings"], [])

    def test_refuses_unknown_resident(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke("submit", "--resident", "Unknown", "--event-type", "CHECK", "--payload", "{}")
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM resident_inbox").fetchone()[0], 0)

    def test_refuses_non_object_payload(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.invoke("submit", "--resident", "Grace", "--event-type", "CHECK", "--payload", "[]")

    def test_refuses_missing_database(self):
        missing = self.db.with_name("missing.db")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run(["--db", str(missing), "submit", "--resident", "Grace", "--event-type", "CHECK", "--payload", "{}"])
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
