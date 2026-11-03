# R3 CONTROLLED SOURCE
# File: runtime/institution.py
# Component: R3-INSTITUTION-RUNTIME
# File Revision: 1.0.7
# Created: 2026-11-01 UTC (exact time not verified)
# Created By: ChatGPT GPT-6
# Purpose: Durable resident scheduling, supervision, and observable state transitions.
# Execution Model: Async continuous scheduler and independent watchdog.
# Observability: SQLite event journal and current-state snapshots; PostgreSQL adapter pending.
# Dependencies: Python 3.12 standard library.
# Authority: Steward-approved R3 Charter Revision 2; no production deployment.
# Changed: 2026-11-01 UTC | R3-RUNTIME-001 | Initial isolated runtime prototype; record task start for watchdog
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/file-provenance.md
# Tests: tests/test_institution_supervision.py (permanent regression)
# Changed: 2026-11-02 UTC | R3-RUNTIME-003 | Gate execution on durable pending work; prevent idle false completion
# Changed: 2026-11-02 UTC | R3-RUNTIME-007 | Remove elapsed-work cancellation; retain crash and loop supervision.
# Changed: 2026-11-03 UTC | R3-RUNTIME-009 | Drain active resident work on graceful shutdown.
# History/Predecessor: Git blob 3509a6762be59170c761e86c416d44230a9b6c19
"""R3 institutional scheduler and supervisor; resident work has no elapsed-time ceiling."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

STATE_NUMBERS = {'READY': 100, 'RUNNING': 200, 'RECOVERING': 900}

Work = Callable[[str], Awaitable[None]]


class Journal:
    """Single-process durable event journal; state and event commit atomically."""

    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS residents (
            name TEXT PRIMARY KEY, state TEXT NOT NULL,
            heartbeat REAL, next_due REAL NOT NULL, failures INTEGER NOT NULL DEFAULT 0
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at REAL NOT NULL, resident TEXT NOT NULL,
            kind TEXT NOT NULL, detail TEXT NOT NULL
        )""")

    def register(self, name: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO residents(name,state,next_due) VALUES (?, 'READY', 0)",
                (name,),
            )

    def transition(self, name: str, state: str, kind: str, detail: str = "",
                   next_due: float | None = None, failure: bool = False) -> None:
        now = time.time()
        with self.db:
            if next_due is None:
                self.db.execute(
                    "UPDATE residents SET state=?, heartbeat=?, failures=failures+? WHERE name=?",
                    (state, now, int(failure), name),
                )
            else:
                self.db.execute(
                    "UPDATE residents SET state=?, heartbeat=?, next_due=?, failures=failures+? WHERE name=?",
                    (state, now, next_due, int(failure), name),
                )
            self.db.execute(
                "INSERT INTO events(at,resident,kind,detail) VALUES (?,?,?,?)",
                (now, name, kind, json.dumps({"state": state, "state_number": STATE_NUMBERS[state], "reason": detail}, sort_keys=True)),
            )

    def snapshot(self) -> dict:
        rows = self.db.execute(
            "SELECT name,state,heartbeat,next_due,failures FROM residents ORDER BY name"
        ).fetchall()
        last = self.db.execute(
            "SELECT id,at,resident,kind,detail FROM events ORDER BY id DESC LIMIT 30"
        ).fetchall()
        residents = [dict(zip(("name","state","heartbeat","next_due","failures"), row))
                     for row in rows]
        for resident in residents:
            resident["state_number"] = STATE_NUMBERS[resident["state"]]
        events = [dict(zip(("id","at","resident","kind","detail"), row)) for row in last]
        for event in events:
            try:
                data = json.loads(event["detail"])
                if isinstance(data, dict) and "state_number" in data:
                    event.update(data)
            except (ValueError, TypeError):
                pass
        return {
            "residents": residents,
            "events": events,
            "state_catalog": STATE_NUMBERS,
        }


@dataclass
class Resident:
    name: str
    work: Work
    interval: float = 5.0
    ready: Callable[[str], bool] | None = None


class Institution:
    def __init__(self, journal: Journal, *, tick_seconds: float = 0.25):
        self.journal = journal
        self.tick_seconds = tick_seconds
        self.residents: dict[str, Resident] = {}
        self.active: dict[str, asyncio.Task] = {}
        self._stop = asyncio.Event()
        self._loop_tasks: tuple[asyncio.Task, ...] = ()
        self._main_heartbeat = time.monotonic()
        self._supervisor_heartbeat = time.monotonic()

    def add(self, resident: Resident) -> None:
        if resident.name in self.residents:
            raise ValueError("Duplicate resident")
        if resident.interval <= 0:
            raise ValueError("Interval must be positive")
        self.residents[resident.name] = resident
        self.journal.register(resident.name)

    async def _execute(self, resident: Resident) -> None:
        name = resident.name
        self.journal.transition(name, "RUNNING", "STARTED")
        try:
            await resident.work(name)
        except asyncio.CancelledError:
            self.journal.transition(name, "READY", "INTERRUPTED",
                                        next_due=time.time())
            raise
        except Exception as exc:
            self.journal.transition(name, "RECOVERING", "FAILED",
                                    detail=repr(exc)[:500], failure=True,
                                    next_due=time.time()+resident.interval)
        else:
            self.journal.transition(name, "READY", "COMPLETED",
                                    next_due=time.time()+resident.interval)

    async def main_loop(self) -> None:
        while not self._stop.is_set():
            self._main_heartbeat = time.monotonic()
            for name, resident in tuple(self.residents.items()):
                task = self.active.get(name)
                if task is not None and not task.done():
                    continue
                row = self.journal.db.execute(
                    "SELECT state,next_due FROM residents WHERE name=?", (name,)
                ).fetchone()
                if row and row[1] <= time.time() and (resident.ready is None or resident.ready(name)):
                    task = asyncio.create_task(self._execute(resident), name=f"resident:{name}")
                    self.active[name] = task
            await asyncio.sleep(self.tick_seconds)

    async def supervisory_loop(self) -> None:
        while not self._stop.is_set():
            self._supervisor_heartbeat = time.monotonic()
            for name, task in tuple(self.active.items()):
                if task.done():
                    if not task.cancelled() and task.exception() is not None:
                        self.journal.transition(name, "RECOVERING", "TASK_CRASH",
                                                repr(task.exception())[:500],
                                                next_due=time.time(), failure=True)
                    self.active.pop(name, None)
            await asyncio.sleep(self.tick_seconds)

    async def run(self) -> None:
        # An interrupted process cannot leave stale RUNNING state authoritative.
        for name in self.residents:
            row = self.journal.db.execute(
                "SELECT state FROM residents WHERE name=?", (name,)
            ).fetchone()
            if row and row[0] in ("RUNNING", "RECOVERING"):
                self.journal.transition(name, "READY", "RESTART_RECOVERY",
                                        next_due=time.time())
        async with asyncio.TaskGroup() as group:
            self._loop_tasks = (
                group.create_task(self.main_loop(), name="r3-main"),
                group.create_task(self.supervisory_loop(), name="r3-supervisor"),
            )

    async def stop(self) -> None:
        """Stop new scheduling and drain already admitted work without cancellation."""
        self._stop.set()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks, return_exceptions=True)
        active = tuple(self.active.values())
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    def health(self) -> dict:
        return {
            "main_age_seconds": time.monotonic() - self._main_heartbeat,
            "supervisor_age_seconds": time.monotonic() - self._supervisor_heartbeat,
            "active": sorted(name for name, task in self.active.items() if not task.done()),
            "state": self.journal.snapshot(),
        }
