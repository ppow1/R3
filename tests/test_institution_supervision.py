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
