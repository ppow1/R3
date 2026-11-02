# R3 CONTROLLED SOURCE
# File: tests/test_inbox_cli.py
# Component: R3-DURABLE-EVENT-INTERFACE
# File Revision: 1.0.0
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
