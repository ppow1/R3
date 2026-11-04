# R3 CONTROLLED SOURCE
# File: tests/test_grace_continuation_audit.py
# Component: R3-GRACE-LINEAGE-AUDIT-TEST
# File Revision: 1.0.0
# Created: 2026-11-04 UTC
# Created By: ChatGPT GPT-6
# Purpose: Permanent regression coverage for read-only continuation lineage accounting.
# Execution Model: Python unittest using isolated temporary database.
# Observability: Exact lineage and tool-count assertions.
# Dependencies: Python 3 standard library.
# Authority: Steward engineering test policy.
# Changed: 2026-11-04 UTC | R3-GRACE-LINEAGE-AUDIT-TEST-001 | Initial tests.
# Supersedes: None
# Contracts: hints/engineering-test-policy.md
# Tests: This file.
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from scripts.audit_grace_continuation import audit


class GraceContinuationAuditTests(unittest.TestCase):
    def test_read_only_lineage_and_tool_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "institution.db")
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE resident_inbox (id INTEGER PRIMARY KEY, resident TEXT, event_type TEXT, payload TEXT, result TEXT, status TEXT)")
            db.execute("CREATE TABLE resident_turns (event_id INTEGER, kind TEXT)")
            rows = [
                (11, "Grace", "REVIEW_FEEDBACK", {}, {"decision": {"state": "continue"}}, "COMPLETED"),
                (12, "Grace", "REVIEW_FEEDBACK", {"previous_event_id": 11, "recovery_required": True},
                 {"decision": {"state": "blocked"}, "objective_status": "UNVERIFIED"}, "FAILED"),
                (13, "Grace", "RESIDENT_ACTIVITY", {}, {}, "COMPLETED"),
            ]
            for event_id, resident, event_type, payload, result, status in rows:
                db.execute("INSERT INTO resident_inbox VALUES (?,?,?,?,?,?)",
                           (event_id, resident, event_type, json.dumps(payload), json.dumps(result), status))
            db.executemany("INSERT INTO resident_turns VALUES (?,?)",
                           [(11, "ASSISTANT"), (11, "TOOL_INTENT"), (11, "TOOL_RESULT"),
                            (12, "ASSISTANT")])
            db.commit()
            db.close()
            before = open(path, "rb").read()
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                audit(path, "REVIEW_FEEDBACK")
            after = open(path, "rb").read()
            self.assertEqual(before, after)
            lines = output.getvalue().splitlines()
            self.assertIn("events= 2 roots= 1", lines[0])
            result = json.loads(lines[1])
            self.assertEqual(result["chain_length"], 2)
            self.assertEqual(result["terminal_status"], "FAILED")
            self.assertEqual(result["terminal_objective_status"], "UNVERIFIED")
            self.assertEqual(result["recovery_prompted"], 1)
            self.assertEqual(result["tool_intents"], 1)
            self.assertEqual(result["tool_results"], 1)
            self.assertEqual(result["assistant_turns"], 2)


if __name__ == "__main__":
    unittest.main()
