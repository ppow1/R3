"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_resident_lifecycle_reconcile.py
Component: R3A-RESIDENT-LIFECYCLE-RECONCILIATION-TESTS
File Revision: 1.0.0
Created: 2026-11-08
Created By: R3A Coordinator
Purpose: Verify stale prior resident lifecycle records are reconciled without altering live versions.
Execution Model: Focused unit tests; no managed service or database is started.
Observability: Assertions cover durable failed transitions and exact resident process matching.
Dependencies: r3a_runtime.cme; unittest.
Authority: Steward Directive — R3A Unified Integration and Deployment.
Changed: 2026-11-08 | R3A-UNIFIED-INTEGRATION | Add primary-resident lifecycle recovery tests.
Supersedes: None.
Contracts: module.lifecycle v2.
Tests: tests/test_r3a_resident_lifecycle_reconcile.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from r3a_runtime.cme import CME


class _Store:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []
        self.transitions = []

    async def rows(self, query, params=()):
        self.queries.append((query, params))
        return self._rows

    async def module_state(self, *args, **kwargs):
        self.transitions.append((args, kwargs))


class ResidentLifecycleReconcileTests(unittest.TestCase):
    def test_reconciles_only_absent_superseded_primary_versions(self):
        store = _Store([
            {"module_version": "1.1.0", "lifecycle_state": "ACTIVE",
             "diagnostic": {"pid": 111}, "manifest": {"entrypoint": "r3a_runtime.grace_module"}},
            {"module_version": "1.1.2", "lifecycle_state": "STOPPING",
             "diagnostic": {}, "manifest": {"entrypoint": "r3a_runtime.grace_module"}},
            {"module_version": "1.1.3", "lifecycle_state": "ACTIVE",
             "diagnostic": {"pid": 222}, "manifest": {"entrypoint": "r3a_runtime.grace_module"}},
        ])
        cme = CME.__new__(CME)
        cme.module_id = "resident.test"
        cme.module_version = "2.0.0"
        cme.store = store

        async def run():
            with patch.object(cme, "_resident_process_matches",
                              side_effect=lambda pid, resident, version, entrypoint: pid == 222):
                return await cme._reconcile_stale_primary_resident_versions()

        reconciled = asyncio.run(run())
        self.assertEqual(2, reconciled)
        self.assertEqual(("resident.test", "2.0.0"), store.queries[0][1])
        self.assertEqual(2, len(store.transitions))
        first_args, first_kwargs = store.transitions[0]
        self.assertEqual(("resident.test", "1.1.0", "FAILED", "unavailable"), first_args[:4])
        self.assertEqual("superseded_resident_process_absent", first_args[4]["reason"])
        self.assertEqual(111, first_args[4]["recorded_pid"])
        self.assertFalse(first_args[4]["resume_on_start"])
        self.assertEqual(2, first_kwargs["machine_version"])

    def test_resident_process_identity_rejects_absent_pid(self):
        self.assertFalse(CME._resident_process_matches(
            2147483000, "resident.test", "1.0.0", "r3a_runtime.grace_module"))


if __name__ == "__main__":
    unittest.main()
