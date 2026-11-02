# R3 CONTROLLED SOURCE
# File: tests/test_configuration.py
# Component: R3-CONFIGURATION-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent external configuration validation regression.
# Contracts: hints/engineering-test-policy.md
import json
import tempfile
import unittest
from pathlib import Path

from runtime.configuration import ConfigurationError, load_configuration


class ConfigurationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "residents/prompts").mkdir(parents=True)
        self.runtime = {
            "scheduler_tick_seconds": 0.25,
            "health_interval_seconds": 2,
            "sqlite_busy_timeout_ms": 5000,
            "residents": {"grace": "residents/grace.json"},
        }
        self.grace = {
            "name": "Grace", "role": "Director of Operations", "enabled": True,
            "inference": {"endpoint": "http://localhost:8080/v1", "model": "test-model", "timeout_seconds": 120},
            "schedule_interval_seconds": 5,
            "system_prompt_file": "residents/prompts/grace.md",
            "tools": {"provider": "none"},
        }
        (self.root / "residents/prompts/grace.md").write_text("Original personality")
        self.save()

    def save(self):
        (self.root / "runtime.json").write_text(json.dumps(self.runtime))
        (self.root / "residents/grace.json").write_text(json.dumps(self.grace))

    def test_prompt_and_model_are_external(self):
        result = load_configuration(self.root)
        self.assertEqual(result["residents"][0]["system_prompt"], "Original personality")
        self.assertEqual(result["residents"][0]["settings"]["inference"]["model"], "test-model")
        (self.root / "residents/prompts/grace.md").write_text("Revised personality")
        self.grace["inference"]["model"] = "another-model"
        self.save()
        result = load_configuration(self.root)
        self.assertEqual(result["residents"][0]["system_prompt"], "Revised personality")
        self.assertEqual(result["residents"][0]["settings"]["inference"]["model"], "another-model")

    def test_invalid_timeout_fails_closed(self):
        self.grace["inference"]["timeout_seconds"] = 0
        self.save()
        with self.assertRaises(ConfigurationError):
            load_configuration(self.root)

    def test_missing_prompt_fails_closed(self):
        self.grace["system_prompt_file"] = "residents/prompts/missing.md"
        self.save()
        with self.assertRaises(ConfigurationError):
            load_configuration(self.root)

    def test_path_escape_rejected(self):
        self.grace["system_prompt_file"] = "../../outside.md"
        self.save()
        with self.assertRaises(ConfigurationError):
            load_configuration(self.root)


if __name__ == "__main__":
    unittest.main()
