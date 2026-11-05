# R3 CONTROLLED SOURCE
# File: tests/test_hr_stdio.py
# Component: HR-STDIO-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Verify stdio transport dispatch and no identity spoofing
# Execution Model: unittest; disposable SQLite and StringIO
# Observability: Assertions
# Dependencies: Python standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-004 | Initial stdio tests
# Supersedes: None
# Contracts: runtime/hr_stdio.py
# Tests: python -m unittest discover -s tests -p 'test_hr*.py'
# History/Predecessor: New file
import io
import json
import tempfile
import unittest
from pathlib import Path
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_store import HRStore
from runtime.hr_capability import HRCapability, VerifiedPrincipal
from runtime.hr_stdio import dispatch, serve

class StdioTests(unittest.TestCase):
    def test_no_identity_override_and_restricted_fields(self):
        with tempfile.TemporaryDirectory() as d:
            store = HRStore(Path(d) / "hr.db")
            store.put(ResidentHRRecord("r3:marie", "Marie", "Research",
                fields={"public": HRField("Research", "public"),
                        "secret": HRField("private", "confidential")}))
            capability = HRCapability(store, lambda p, a, s: a == "hr.read")
            principal = VerifiedPrincipal("r3:grace", "resident")
            self.assertEqual(dispatch(capability, principal, {
                "operation": "hr.read", "resident_id": "r3:marie", "role": "steward"})["error"],
                "identity_override_forbidden")
            response = dispatch(capability, principal, {
                "operation": "hr.read", "resident_id": "r3:marie"})
            self.assertEqual(response["result"]["fields"], {"public": "Research"})
            inp = io.StringIO('{"operation":"hr.read","resident_id":"r3:marie"}\nnot json\n')
            out = io.StringIO()
            serve(capability, principal, inp, out)
            results = [json.loads(x) for x in out.getvalue().splitlines()]
            self.assertTrue(results[0]["ok"])
            self.assertEqual(results[1]["error"], "invalid_json")
            store.close()

if __name__ == "__main__":
    unittest.main()
