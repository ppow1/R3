# R3 CONTROLLED SOURCE
# File: tests/test_hr_local.py
# Component: HR-LOCAL-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Validate repeated local HR stdio requests
# Execution Model: unittest
# Observability: Assertions
# Dependencies: Python standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-006 | Add local host regression
# Supersedes: None
# Contracts: runtime/hr_local.py
# Tests: python -m unittest discover -s tests -p test_hr_local.py
# History/Predecessor: New file
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_store import HRStore
from runtime.hr_capability import VerifiedPrincipal
from runtime.hr_local import run_local_stdio

class LocalHRTests(unittest.TestCase):
    def test_multiple_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "hr.db"
            store = HRStore(db)
            store.put(ResidentHRRecord("resident1", "Resident", "Research",
                fields={"title": HRField("Research", "public")}))
            store.close()
            config = {"schema_version": 1,
                "service": {"transports": {"stdio": True}},
                "directory": {},
                "storage": {"database_path_env": "R3_HR_DB_PATH"},
                "operations": {"worker_concurrency": 4, "request_timeout_seconds": 60},
                "authorization": {"provider": "local", "require_verified_principal": True}}
            path = Path(folder) / "hr.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            request = json.dumps({"operation": "hr.read", "resident_id": "resident1"})
            output = io.StringIO()
            with patch.dict(os.environ, {"R3_HR_DB_PATH": str(db)}):
                run_local_stdio(config_path=path,
                    principal=VerifiedPrincipal("grace", "resident"),
                    authorize=lambda principal, action, scope: action == "hr.read",
                    input_stream=io.StringIO((request + "\n") * 3),
                    output_stream=output)
            responses = [json.loads(x) for x in output.getvalue().splitlines()]
            self.assertEqual(len(responses), 3)
            self.assertTrue(all(x["ok"] for x in responses))
            self.assertTrue(all(x["result"]["fields"] == {"title": "Research"} for x in responses))

if __name__ == "__main__":
    unittest.main()
