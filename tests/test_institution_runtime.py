# R3 CONTROLLED SOURCE
# File: tests/test_institution_runtime.py
# Component: R3-INSTITUTION-RUNTIME-TESTS
# File Revision: 1.0.3
# Created: 2026-11-01 UTC (exact time not verified)
# Created By: ChatGPT GPT-6
# Purpose: Verify durable transitions, scheduling, and failure recovery.
# Execution Model: Python unittest, no external services.
# Observability: unittest assertions and temporary SQLite event journal.
# Dependencies: Python 3.12 standard library; runtime/institution.py.
# Authority: R3 engineering branch only.
# Changed: 2026-11-02 UTC | R3-GATE-002 | Remove remaining wall-clock scheduler/failure qualification tests
# Changed: 2026-11-02 UTC | R3-GATE-001 | Remove one-time wall-clock watchdog qualification test
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
    async def test_numeric_transition_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = Journal(Path(tmp) / "runtime.db")
            journal.register("Grace")
            journal.transition("Grace", "RUNNING", "STARTED", "objective received")
            snap = journal.snapshot()
            self.assertEqual(snap["residents"][0]["state_number"], 200)
            self.assertEqual(snap["events"][0]["state_number"], 200)
            self.assertEqual(snap["events"][0]["reason"], "objective received")



if __name__ == "__main__":
    unittest.main()
