# R3 CONTROLLED SOURCE
# File: tests/test_blocked_recovery.py
# Component: R3-AUTHORIZED-BLOCKED-RECOVERY-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date only; exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Verify fail-closed canonical authorization, resumptions, idempotency and lineage.
# Execution Model: Python unittest with temporary local SQLite databases.
# Observability: Assertions; no external services or network requests.
# Dependencies: runtime.blocked_recovery; runtime.assignment_intake; R3Authority.
# Authority: Steward R3 development governance and exact-grant contract.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-006 | Initial trusted-boundary recovery tests.
# Supersedes: None
# Superseded By: None
# Contracts: hints/file-provenance.md
# Tests: python -m unittest discover -s tests -p test_blocked_recovery.py -v
# History/Predecessor: New file; none
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.assignment_intake import AssignmentIntake
from runtime.blocked_recovery import BlockedResumptionService
from runtime.capabilities import CapabilityDenied
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.resident_inference import Inbox


class BlockedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.institution = root / "institution.sqlite3"
        self.grants = root / "authority.sqlite3"
        self.intake = AssignmentIntake(
            self.institution, "a" * 40, {"Grace"}, {"Grace"})
        self.root = self.intake.submit({
            "resident": "Grace", "assignment_id": "assignment-1",
            "objective": "Investigate blocked recovery",
            "acceptance_criteria": [{
                "id": "c1", "version": "1", "description": "Evidence reviewed"}],
        }, "original-request")["event_id"]
        with sqlite3.connect(self.institution) as db:
            inbox = Inbox(db)
            inbox.next("Grace")
            inbox.finish(self.root, "BLOCKED", {
                "objective_status": "BLOCKED", "dependency": "Missing grant"})
        initialize_empty_schema(self.grants)
        self.authority = R3Authority(self.grants)
        self.service = BlockedResumptionService(
            self.institution, self.authority,
            lambda ctx: "human:steward:one" if ctx == "trusted-session" else "")

    def grant(self):
        # Test fixtures are explicit only; production never issues default grants.
        with sqlite3.connect(self.grants) as db:
            db.execute(
                "INSERT INTO capability_grants "
                "(grant_id,principal,resource_ref,action,operation,scope_ref,"
                "active,approved_by) VALUES (?,?,?,?,?,?,?,?)",
                ("r3-grant:test", "human:steward:one",
                 "r3:assignment:assignment-1", "resident.activity.resume",
                 "write", "resident:Grace", 1, "human:steward:one"))

    def resume(self, event_id=None, evidence="Granted"):
        return self.service.resume(
            self.root, self.root if event_id is None else event_id,
            authenticated_context="trusted-session",
            resolution_evidence=evidence,
            correlation_id="test-correlation",
        )

    def test_no_grant_fails_closed_and_keeps_blocked(self):
        with self.assertRaises(CapabilityDenied):
            self.resume()
        with sqlite3.connect(self.institution) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM resident_inbox").fetchone()[0], 1)

    def test_untrusted_context_fails_closed(self):
        self.grant()
        with self.assertRaises(CapabilityDenied):
            self.service.resume(
                self.root, self.root, authenticated_context="untrusted",
                resolution_evidence="Granted", correlation_id="test")
        with sqlite3.connect(self.institution) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM resident_inbox").fetchone()[0], 1)

    def test_authorized_resume_is_idempotent_and_visible_in_status(self):
        self.grant()
        successor = self.resume()
        self.assertEqual(successor, self.resume())
        status = self.intake.status(self.root)
        self.assertEqual([event["event_id"] for event in status["events"]],
                         [self.root, successor])
        self.assertEqual([event["status"] for event in status["events"]],
                         ["BLOCKED", "PENDING"])
        with sqlite3.connect(self.institution) as db:
            row = db.execute(
                "SELECT payload FROM resident_inbox WHERE id=?",
                (successor,)).fetchone()
            payload = json.loads(row[0])
            self.assertEqual(payload["resumption_authority_ref"],
                             "r3-grant:test")
            self.assertEqual(payload["previous_result"]["dependency"],
                             "Missing grant")
        with sqlite3.connect(self.grants) as db:
            self.assertEqual(db.execute(
                "SELECT outcome FROM capability_audit WHERE grant_id=? "
                "ORDER BY at DESC LIMIT 1", ("r3-grant:test",)
            ).fetchone()[0], "AUTHORIZED")

    def test_conflicting_evidence_fails_closed(self):
        self.grant()
        self.resume()
        with self.assertRaisesRegex(ValueError, "different evidence"):
            self.resume(evidence="Different resolution evidence")

    def test_cross_assignment_resumption_rejected(self):
        self.grant()
        other_root = self.intake.submit({
            "resident": "Grace", "assignment_id": "assignment-2",
            "objective": "Second objective",
            "acceptance_criteria": [{
                "id": "c1", "version": "1", "description": "Completed"}],
        }, "second-request")["event_id"]
        with self.assertRaisesRegex(ValueError, "lineage"):
            self.resume(event_id=other_root)

    def test_nonblocked_resumption_rejected(self):
        self.grant()
        successor = self.resume()
        with self.assertRaisesRegex(ValueError, "Only BLOCKED"):
            self.resume(event_id=successor)


if __name__ == "__main__":
    unittest.main()
