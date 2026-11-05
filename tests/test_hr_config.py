# R3 CONTROLLED SOURCE
# File: tests/test_hr_config.py
# Component: HR-CONFIG-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Verify JSON settings and invariant validation
# Execution Model: Python unittest
# Observability: Test assertions
# Dependencies: Python standard library
# Authority: Tests only
# Changed: 2026-11-05 UTC | HR-005 | Add configuration regression tests
# Supersedes: None
# Contracts: runtime/hr_config.py
# Tests: python -m unittest discover -s tests -p 'test_hr*.py'
# History/Predecessor: New file
import json
import tempfile
import unittest
from pathlib import Path
from runtime.hr_config import load_hr_config

class HRConfigTests(unittest.TestCase):
    def test_operational_settings_are_editable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "hr.json"
            config = {"schema_version": 1, "service": {}, "directory": {},
                      "storage": {}, "operations": {
                          "worker_concurrency": 32, "request_timeout_seconds": 120},
                      "authorization": {
                          "provider": "r3_comms", "require_verified_principal": True}}
            path.write_text(json.dumps(config), encoding="utf-8")
            self.assertEqual(load_hr_config(path)["operations"]["worker_concurrency"], 32)
            config["authorization"]["require_verified_principal"] = False
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_hr_config(path)

if __name__ == "__main__":
    unittest.main()
