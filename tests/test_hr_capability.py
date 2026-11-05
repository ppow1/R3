# R3 CONTROLLED SOURCE
# File: tests/test_hr_capability.py
# Component: HR-CAPABILITY-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Verify transport-neutral authorization and field filtering
# Execution Model: unittest; disposable SQLite
# Observability: Assertions
# Dependencies: Python standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-003 | Add capability tests
# Supersedes: None
# Contracts: runtime/hr_capability.py
# Tests: python -m unittest discover -s tests -p 'test_hr*.py'
# History/Predecessor: New file
import tempfile
import unittest
from pathlib import Path
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_store import HRStore
from runtime.hr_capability import HRCapability, VerifiedPrincipal

class CapabilityTests(unittest.TestCase):
    def test_grants_and_confidentiality(self):
        with tempfile.TemporaryDirectory() as d:
            store = HRStore(Path(d) / "hr.db")
            store.put(ResidentHRRecord("r3:marie", "Marie", "Research", fields={
                "public": HRField("research", "public"),
                "restricted": HRField("private request", "request"),
                "secret": HRField("Helen only", "confidential")}))
            def grant(principal, action, scope):
                return (action == "hr.read" and scope == "r3:marie" or
                        action == "hr.field.read" and scope == "r3:marie:restricted")
            service = HRCapability(store, grant)
            grace = service.read(VerifiedPrincipal("r3:grace", "approved_requester"),
                                 "r3:marie", approved_fields=frozenset({"restricted"}))
            self.assertEqual(grace["fields"], {"public": "research", "restricted": "private request"})
            self.assertEqual(len(service.read(VerifiedPrincipal("r3:helen", "helen"), "r3:marie")["fields"]), 3)
            with self.assertRaises(PermissionError):
                HRCapability(store, lambda *_: False).read(VerifiedPrincipal("r3:grace", "resident"), "r3:marie")
            store.close()

if __name__ == "__main__":
    unittest.main()
