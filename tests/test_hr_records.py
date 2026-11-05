# R3 CONTROLLED SOURCE
# File: tests/test_hr_records.py
# Component: HR-FOUNDATION-TESTS
# File Revision: 0.1.0
# Created: 2026-11-05 UTC
# Created By: ChatGPT GPT-6
# Purpose: Validate isolated HR record confidentiality and extensibility
# Execution Model: Python unittest
# Observability: unittest results
# Dependencies: Python 3.10+ standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-001 | Initial tests
# Supersedes: None
# Contracts: runtime/hr_records.py; hints/file-provenance.md
# Tests: python -m unittest discover -s tests -p test_hr_records.py
# History/Predecessor: New file
import unittest
from runtime.hr_records import HRField, ResidentHRRecord, initial_acceptance_records

class HRRecordsTests(unittest.TestCase):
    def test_grace_marie_distinct(self):
        grace, marie = initial_acceptance_records()
        self.assertNotEqual(grace.resident_id, marie.resident_id)
        self.assertEqual(grace.view(role="resident")["fields"]["role"], "Director of Operations")

    def test_confidentiality_and_request(self):
        r = ResidentHRRecord("r3:test", "Test", "Office", fields={
            "title": HRField("Engineer", "public"),
            "assessment": HRField("restricted", "request"),
            "private_note": HRField("secret", "confidential")})
        self.assertEqual(r.view(role="resident")["fields"], {"title": "Engineer"})
        self.assertEqual(r.view(role="approved_requester", approved_fields=frozenset({"assessment"}))["fields"],
                         {"title": "Engineer", "assessment": "restricted"})
        self.assertEqual(len(r.view(role="helen")["fields"]), 3)
        self.assertEqual(len(r.view(role="steward")["fields"]), 3)

    def test_unknown_classification_and_role_fail_closed(self):
        with self.assertRaises(ValueError):
            HRField("x", "unclassified")
        with self.assertRaises(PermissionError):
            initial_acceptance_records()[0].view(role="grace")

    def test_extensions_and_history(self):
        r = ResidentHRRecord("r3:x", "X", "Research")
        r.extensions["training"] = HRField({"course": "A"}, "request")
        r.history_refs.append("estate://historical/example")
        self.assertNotIn("training", r.view(role="resident")["fields"])
        self.assertEqual(r.view(role="helen")["fields"]["training"], {"course": "A"})

if __name__ == "__main__":
    unittest.main()
