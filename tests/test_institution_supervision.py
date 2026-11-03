# R3 CONTROLLED SOURCE
# File: tests/test_institution_supervision.py
# Component: R3-INSTITUTION-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Verify long-running resident work is not cancelled by elapsed time.
# Execution Model: Python unittest, in-memory temporary SQLite journal.
# Observability: unittest assertions and journal state.
# Dependencies: Python 3.12 standard library; runtime.institution.
# Authority: Steward: no artificial autonomy duration limits.
# Changed: 2026-11-02 UTC | R3-RUNTIME-007 | Permanent supervision regression.
# Changed: 2026-11-03 UTC | R3-RUNTIME-009 | Graceful shutdown drains active work.
# Supersedes: None
# Contracts: hints/milestones/2026-11-02-r3-six-phase-roadmap-phase1.md
# Tests: python3 -m unittest tests.test_institution_supervision
# History/Predecessor: New file.
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from runtime.institution import Institution, Journal, Resident


class SupervisionTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_drains_current_work_before_returning(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "institution.db")
            institution = Institution(journal, tick_seconds=0.005)
            started = asyncio.Event()
            release = asyncio.Event()
            completed = asyncio.Event()
            cancelled = asyncio.Event()
            starts = 0

            async def work(name):
                nonlocal starts
                starts += 1
                started.set()
                try:
                    await release.wait()
                    completed.set()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise

            institution.add(Resident("Grace", work, interval=0.01))
            runner = asyncio.create_task(institution.run())
            stopping = None
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                stopping = asyncio.create_task(institution.stop())
                await asyncio.wait_for(
                    asyncio.gather(*institution._loop_tasks), timeout=2
                )
                self.assertFalse(stopping.done())
                self.assertFalse(cancelled.is_set())
                release.set()
                await asyncio.wait_for(stopping, timeout=2)
                await asyncio.wait_for(runner, timeout=2)
                self.assertTrue(completed.is_set())
                self.assertFalse(cancelled.is_set())
                self.assertEqual(starts, 1)
                self.assertEqual(
                    journal.db.execute(
                        "SELECT state FROM residents WHERE name='Grace'"
                    ).fetchone()[0],
                    "READY",
                )
            finally:
                release.set()
                institution._stop.set()
                if stopping is not None and not stopping.done():
                    await stopping
                if not runner.done():
                    await asyncio.wait_for(runner, timeout=2)
                journal.db.close()

    async def test_active_work_is_not_cancelled_by_elapsed_time(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "institution.db")
            institution = Institution(journal, tick_seconds=0.005)
            started = asyncio.Event()
            release = asyncio.Event()
            completed = asyncio.Event()

            async def work(name):
                started.set()
                await release.wait()
                completed.set()

            institution.add(Resident("Grace", work, interval=0.01))
            runner = asyncio.create_task(institution.run())
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                await asyncio.sleep(0.12)
                self.assertFalse(completed.is_set())
                self.assertIn("Grace", institution.health()["active"])
                row = journal.db.execute(
                    "SELECT state,failures FROM residents WHERE name='Grace'"
                ).fetchone()
                self.assertEqual(row, ("RUNNING", 0))
                self.assertFalse(
                    journal.db.execute(
                        "SELECT 1 FROM events WHERE kind='WATCHDOG_TIMEOUT'"
                    ).fetchone()
                )
                release.set()
                await asyncio.wait_for(completed.wait(), timeout=2)
            finally:
                await institution.stop()
                await asyncio.wait_for(runner, timeout=2)
                journal.db.close()


if __name__ == "__main__":
    unittest.main()
