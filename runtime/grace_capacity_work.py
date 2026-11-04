# R3 CONTROLLED SOURCE
# File: runtime/grace_capacity_work.py
# Component: R3-GRACE-DURABLE-CAPACITY-WORK
# File Revision: 1.0.1
# Purpose: Durable event-driven capacity review; assessment is not execution.
# Authority: Grace #28 and unified Website #16; no grants or production actions.
# Tests: tests/test_grace_capacity_work.py
"""Durable capacity work queue; completion requires independent review evidence."""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path
from runtime.capacity_assessment import assess_gpu_capacity

class CapacityWork:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS grace_capacity_work (
            work_id TEXT PRIMARY KEY, required_vram_bytes INTEGER NOT NULL,
            state TEXT NOT NULL, result TEXT, updated_at REAL NOT NULL,
            review_ref TEXT)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS grace_capacity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, work_id TEXT NOT NULL,
            kind TEXT NOT NULL, detail TEXT NOT NULL, at REAL NOT NULL)""")

    def _event(self, work_id, kind, detail):
        self.db.execute("INSERT INTO grace_capacity_events(work_id,kind,detail,at) VALUES (?,?,?,?)",
                        (work_id,kind,json.dumps(detail,sort_keys=True),time.time()))

    def enqueue(self, work_id: str, required_vram_bytes: int):
        if not isinstance(work_id,str) or not work_id or len(work_id)>200:
            raise ValueError("Stable work ID required")
        if isinstance(required_vram_bytes,bool) or not isinstance(required_vram_bytes,int) or required_vram_bytes<=0:
            raise ValueError("Positive integer VRAM requirement needed")
        with self.db:
            old=self.db.execute("SELECT required_vram_bytes FROM grace_capacity_work WHERE work_id=?",
                                (work_id,)).fetchone()
            if old:
                if old[0]!=required_vram_bytes:
                    raise ValueError("Work ID reused with different requirement")
                return False
            self.db.execute("INSERT INTO grace_capacity_work VALUES (?,?,?,?,?,?)",
                            (work_id,required_vram_bytes,"PENDING",None,time.time(),None))
            self._event(work_id,"ENQUEUED",{"required_vram_bytes":required_vram_bytes})
            return True

    def assess_next(self, snapshot_provider):
        """One event-driven unit of work; no scheduling or model execution."""
        if not callable(snapshot_provider):
            raise ValueError("Snapshot provider required")
        row=self.db.execute("""SELECT work_id,required_vram_bytes FROM grace_capacity_work
                               WHERE state IN ('PENDING','BLOCKED') ORDER BY updated_at,work_id LIMIT 1""").fetchone()
        if row is None:
            return None
        work_id,required=row
        try:
            assessment=assess_gpu_capacity(snapshot_provider(),required_vram_bytes=required)
        except Exception as exc:
            # Observational failure is retryable, not an invented completion.
            with self.db:
                self.db.execute("UPDATE grace_capacity_work SET state='BLOCKED',updated_at=? WHERE work_id=?",
                                (time.time(),work_id))
                self._event(work_id,"OBSERVATION_FAILED",{"error_type":type(exc).__name__})
            return {"work_id":work_id,"state":"BLOCKED"}
        state="AWAITING_INDEPENDENT_REVIEW" if assessment["candidates"] else "BLOCKED"
        with self.db:
            self.db.execute("UPDATE grace_capacity_work SET state=?,result=?,updated_at=? WHERE work_id=?",
                            (state,json.dumps(assessment,sort_keys=True),time.time(),work_id))
            self._event(work_id,"ASSESSED" if assessment["candidates"] else "NO_OBSERVED_FIT",
                        {"candidate_count":len(assessment["candidates"]),"state":state})
        return {"work_id":work_id,"state":state,"assessment":assessment}

    def accept_review(self, work_id: str, review_ref: str, *, verify_review):
        if not isinstance(review_ref,str) or not review_ref.strip() or not callable(verify_review):
            raise ValueError("Independent review verifier and reference required")
        # The caller cannot assert independence with a boolean. A trusted
        # integration adapter must validate review provenance and acceptance.
        evidence=verify_review(work_id,review_ref)
        if not isinstance(evidence,dict) or evidence.get("accepted") is not True or evidence.get("independent") is not True or evidence.get("review_ref") != review_ref:
            raise ValueError("Independent review not accepted")
        with self.db:
            row=self.db.execute("SELECT state FROM grace_capacity_work WHERE work_id=?",
                                (work_id,)).fetchone()
            if row is None or row[0]!="AWAITING_INDEPENDENT_REVIEW":
                raise ValueError("Work not awaiting independent review")
            self.db.execute("""UPDATE grace_capacity_work
                               SET state='VERIFIED',review_ref=?,updated_at=? WHERE work_id=?""",
                            (review_ref,time.time(),work_id))
            self._event(work_id,"REVIEW_ACCEPTED",{"review_ref":review_ref})

    def status(self, work_id):
        row=self.db.execute("""SELECT work_id,required_vram_bytes,state,result,review_ref
                               FROM grace_capacity_work WHERE work_id=?""",(work_id,)).fetchone()
        if row is None: return None
        return {"work_id":row[0],"required_vram_bytes":row[1],"state":row[2],
                "assessment":json.loads(row[3]) if row[3] else None,"review_ref":row[4]}
