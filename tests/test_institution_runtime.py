# R3 CONTROLLED SOURCE
# File: tests/test_institution_runtime.py
# Component: R3-INSTITUTION-RUNTIME-TESTS
# File Revision: 1.0.0
# Created: 2026-11-01 UTC (exact time not verified)
# Created By: ChatGPT GPT-6
# Purpose: Verify durable transitions, scheduling, and failure recovery.
# Execution Model: Python unittest, no external services.
# Observability: unittest assertions and temporary SQLite event journal.
# Dependencies: Python 3.12 standard library; runtime/institution.py.
# Authority: R3 engineering branch only.
# Changed: 2026-11-01 UTC | R3-RUNTIME-001 | Initial runtime tests
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
# Tests: python -m unittest discover -s tests
# History/Predecessor: New file
import asyncio
import tempfile
import unittest
from pathlib import Path

from runtime.institution import Institution, Journal, Resident


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduling_and_durable_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(Path(tmp) / "runtime.db")
            seen = []

            async def work(name):
                seen.append(name)

            institution = Institution(journal, tick_seconds=0.01)
            institution.add(Resident("Grace", work, interval=0.05))
            runner = asyncio.create_task(institution.run())
            await asyncio.sleep(0.15)
            await institution.stop()
            await runner
            self.assertGreaterEqual(len(seen), 1)
            self.assertTrue(any(e["kind"] == "COMPLETED"
                                for e in journal.snapshot()["events"]))
            self.assertEqual(journal.snapshot()["residents"][0]["name"], "Grace")

    async def test_failure_is_recorded_without_killing_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(Path(tmp) / "runtime.db")

            async def work(name):
                raise RuntimeError("test failure")

            institution = Institution(journal, tick_seconds=0.01)
            institution.add(Resident("Helen", work, interval=0.05))
            runner = asyncio.create_task(institution.run())
            await asyncio.sleep(0.1)
            await institution.stop()
            await runner
            self.assertGreaterEqual(journal.snapshot()["residents"][0]["failures"], 1)
            self.assertTrue(any(e["kind"] == "FAILED"
                                for e in journal.snapshot()["events"]))


if __name__ == "__main__":
    unittest.main()
