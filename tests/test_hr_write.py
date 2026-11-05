# R3 CONTROLLED SOURCE
# File: tests/test_hr_write.py
# Component: HR-WRITE-TEST
# File Revision: 1.0.0
# Created: 2026-11-05 UTC
# Created By: ChatGPT GPT-6
# Purpose: Verify create/update via stdio and field disclosure
# Execution Model: Python unittest with temporary SQLite
# Observability: Assertions
# Dependencies: Python standard library
# Authority: Test only
# Changed: 2026-11-05 UTC | HR-009 | Add write regressions
# Supersedes: None
# Contracts: runtime/hr_stdio.py
# Tests: python -m unittest discover -s tests -p 'test_hr*.py' -v
# History/Predecessor: New file
import tempfile
import unittest
from pathlib import Path
from runtime.hr_store import HRStore
from runtime.hr_capability import HRCapability, VerifiedPrincipal
from runtime.hr_stdio import dispatch

class HRWriteTests(unittest.TestCase):
    def test_create_update_and_privacy(self):
        with tempfile.TemporaryDirectory() as folder:
            store = HRStore(Path(folder) / "hr.db")
            try:
                steward = VerifiedPrincipal("steward", "steward")
                grace = VerifiedPrincipal("grace", "resident")
                def policy(principal, operation, scope):
                    return operation == "hr.read" or (
                        operation == "hr.write" and principal.role == "steward")
                cap = HRCapability(store, policy)
                payload = {"resident_id": "r3:new", "display_name": "New Resident",
                           "office": "Research", "fields": {
                               "title": {"value": "Research", "classification": "public"},
                               "note": {"value": "Private", "classification": "confidential"}}}
                first = dispatch(cap, steward, {"operation": "hr.save", "record": payload})
                self.assertEqual(first, {"ok": True, "revision": 1})
                self.assertEqual(dispatch(cap, grace, {"operation": "hr.save", "record": payload})["error"], "forbidden")
                found = dispatch(cap, grace, {"operation": "hr.directory"})
                self.assertEqual(found["result"][0]["fields"], {"title": "Research"})
                payload["office"] = "Engineering"
                second = dispatch(cap, steward, {"operation": "hr.save",
                                                 "record": payload, "expected_revision": 1})
                self.assertEqual(second["revision"], 2)
                conflict = dispatch(cap, steward, {"operation": "hr.save",
                                                   "record": payload, "expected_revision": 1})
                self.assertEqual(conflict["error"], "invalid_request")
            finally:
                store.close()

if __name__ == "__main__":
    unittest.main()
