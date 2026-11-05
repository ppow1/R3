# R3 CONTROLLED SOURCE
# File: tests/test_hr_store.py
# Component: HR-PERSISTENCE-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Validate isolated persistent HR records and revision conflicts
# Execution Model: unittest; disposable temporary directory
# Observability: Test assertions
# Dependencies: Python 3.10+ standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-002 | Initial persistence regression tests
# Supersedes: None
# Contracts: runtime/hr_store.py; hints/file-provenance.md
# Tests: python -m unittest discover -s tests -p 'test_hr*.py'
# History/Predecessor: New file
import tempfile
import unittest
from pathlib import Path
from runtime.hr_records import HRField, initial_acceptance_records
from runtime.hr_store import HRStore

class HRStoreTests(unittest.TestCase):
    def test_round_trip_revision_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hr.sqlite"
            store = HRStore(path)
            grace, marie = initial_acceptance_records()
            self.assertEqual(store.put(grace), 1)
            self.assertEqual(store.put(marie), 1)
            grace.extensions["new_category"] = HRField({"training": ["A"]}, "request")
            self.assertEqual(store.put(grace, expected_revision=1), 2)
            with self.assertRaises(ValueError):
                store.put(grace, expected_revision=1)
            store.close()
            reopened = HRStore(path)
            saved, revision = reopened.get(grace.resident_id)
            self.assertEqual(revision, 2)
            self.assertEqual(saved.extensions["new_category"].value, {"training": ["A"]})
            self.assertEqual(reopened.get(marie.resident_id)[1], 1)
            self.assertIsNone(reopened.get("r3:unknown"))
            reopened.close()

if __name__ == "__main__":
    unittest.main()
