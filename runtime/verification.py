# R3 CONTROLLED SOURCE
# File: runtime/verification.py
# Component: R3-VERIFICATION-LEARNING
# File Revision: 1.1.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Durable criterion-level independent review records and improvement candidates.
# Execution Model: Explicit library calls; no automatic reviews or policy changes.
# Observability: SQLite review findings and improvement candidate tables.
# Dependencies: Python 3.12 standard library; caller-owned SQLite connection.
# Authority: Steward verification and learning discussion; R3 charter revision 2.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-003 | Initial durable evidence and candidate records.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-004 | Add pending review requests.
# Supersedes: None
# Contracts: hints/verification-and-learning.md; hints/engineering-test-policy.md
# Tests: tests/test_verification.py
# History/Predecessor: Git blob b44eb005caa98af6efece2f950c4578daec397cd
"""Record evidence-based review findings and proposed improvements without applying changes."""
from __future__ import annotations

import json
import sqlite3
import time

RESULTS = frozenset(("PASS", "FAIL", "INSUFFICIENT_EVIDENCE"))
DISPOSITIONS = frozenset(("CANDIDATE", "EVALUATING", "DEFERRED", "REJECTED", "RECOMMENDED", "APPROVED", "IMPLEMENTED"))


class VerificationLedger:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.execute("""CREATE TABLE IF NOT EXISTS verification_findings (
            id INTEGER PRIMARY KEY, assignment_id TEXT NOT NULL,
            review_id TEXT NOT NULL, criterion_id TEXT NOT NULL,
            criterion_version TEXT NOT NULL, implementation_revision TEXT NOT NULL,
            result TEXT NOT NULL, reason TEXT NOT NULL,
            evidence TEXT NOT NULL, reviewer TEXT NOT NULL, at REAL NOT NULL,
            UNIQUE(review_id, criterion_id)
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY,
            source_event_id INTEGER NOT NULL UNIQUE,
            assignment_id TEXT NOT NULL,
            criteria TEXT NOT NULL,
            evidence TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at REAL NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS improvement_candidates (
            id INTEGER PRIMARY KEY, source_finding_id INTEGER,
            summary TEXT NOT NULL, hypothesis TEXT NOT NULL,
            evidence TEXT NOT NULL, expected_benefit TEXT NOT NULL,
            risks TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'CANDIDATE',
            decision_reason TEXT, authorized_by TEXT,
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            FOREIGN KEY(source_finding_id) REFERENCES verification_findings(id)
        )""")

    def submit_review(self, source_event_id: int, assignment_id: str,
                      criteria: list, evidence: object) -> int:
        """Persist an independent review request without granting acceptance."""
        if not assignment_id or not criteria:
            raise ValueError("Review requires assignment and acceptance criteria")
        ids = [item.get("id") for item in criteria if isinstance(item, dict)]
        if len(ids) != len(criteria) or any(not isinstance(i, str) or not i for i in ids):
            raise ValueError("Each criterion needs an identifier")
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate criterion")
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO verification_requests "
                "(source_event_id,assignment_id,criteria,evidence,created_at) "
                "VALUES (?,?,?,?,?)",
                (source_event_id, assignment_id, json.dumps(criteria),
                 json.dumps(evidence), time.time()))
            row = self.db.execute(
                "SELECT id FROM verification_requests WHERE source_event_id=?",
                (source_event_id,)).fetchone()
        return int(row[0])

    def record_finding(self, *, assignment_id: str, review_id: str,
                       criterion_id: str, criterion_version: str,
                       implementation_revision: str, result: str,
                       reason: str, evidence: dict | list | str,
                       reviewer: str) -> int:
        if result not in RESULTS:
            raise ValueError("Invalid verification result")
        if not all(isinstance(x, str) and x.strip() for x in
                   (assignment_id, review_id, criterion_id, criterion_version,
                    implementation_revision, reason, reviewer)):
            raise ValueError("Finding requires identifiers, reason and reviewer")
        if evidence is None:
            raise ValueError("Evidence must be explicit (empty is allowed for missing evidence)")
        with self.db:
            cursor = self.db.execute(
                """INSERT INTO verification_findings
                (assignment_id,review_id,criterion_id,criterion_version,
                 implementation_revision,result,reason,evidence,reviewer,at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (assignment_id, review_id, criterion_id, criterion_version,
                 implementation_revision, result, reason, json.dumps(evidence),
                 reviewer, time.time()))
        return int(cursor.lastrowid)

    def history(self, assignment_id: str, criterion_id: str | None = None) -> list[dict]:
        sql = """SELECT review_id,criterion_id,criterion_version,implementation_revision,
                        result,reason,evidence,reviewer,at
                 FROM verification_findings WHERE assignment_id=?"""
        params: tuple = (assignment_id,)
        if criterion_id is not None:
            sql += " AND criterion_id=?"
            params += (criterion_id,)
        sql += " ORDER BY id"
        return [dict(zip(("review_id","criterion_id","criterion_version",
                          "implementation_revision","result","reason","evidence",
                          "reviewer","at"),
                         (*row[:6], json.loads(row[6]), *row[7:])))
                for row in self.db.execute(sql, params)]

    def propose_improvement(self, *, summary: str, hypothesis: str,
                            evidence: dict | list | str, expected_benefit: str,
                            risks: str, source_finding_id: int | None = None) -> int:
        if not all(isinstance(x, str) and x.strip()
                   for x in (summary, hypothesis, expected_benefit, risks)):
            raise ValueError("Candidate requires rationale, benefit, and risks")
        now = time.time()
        with self.db:
            cursor = self.db.execute(
                """INSERT INTO improvement_candidates
                (source_finding_id,summary,hypothesis,evidence,expected_benefit,
                 risks,status,created_at,updated_at) VALUES (?,?,?,?,? ,?,'CANDIDATE',?,?)""",
                (source_finding_id, summary, hypothesis, json.dumps(evidence),
                 expected_benefit, risks, now, now))
        return int(cursor.lastrowid)

    def evaluate_candidate(self, candidate_id: int, *, disposition: str,
                           reason: str, actor: str) -> None:
        if disposition not in DISPOSITIONS or disposition == "IMPLEMENTED":
            raise ValueError("Implementation is not authorized by this ledger")
        if not reason.strip() or not actor.strip():
            raise ValueError("Evaluation requires actor and reason")
        with self.db:
            cursor = self.db.execute(
                """UPDATE improvement_candidates SET status=?,decision_reason=?,
                   authorized_by=?,updated_at=? WHERE id=?""",
                (disposition, reason, actor if disposition == "APPROVED" else None,
                 time.time(), candidate_id))
            if cursor.rowcount != 1:
                raise LookupError("Unknown candidate")

    def candidate(self, candidate_id: int) -> dict:
        row = self.db.execute(
            """SELECT id,source_finding_id,summary,hypothesis,evidence,
                      expected_benefit,risks,status,decision_reason,authorized_by
               FROM improvement_candidates WHERE id=?""", (candidate_id,)).fetchone()
        if row is None:
            raise LookupError("Unknown candidate")
        keys = ("id","source_finding_id","summary","hypothesis","evidence",
                "expected_benefit","risks","status","decision_reason","authorized_by")
        return {**dict(zip(keys,row)), "evidence": json.loads(row[4])}
