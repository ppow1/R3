# R3 CONTROLLED SOURCE
# File: tests/test_configuration.py
# Component: R3-CONFIGURATION-REGRESSION
# File Revision: 1.0.1
# Created: 2026-11-02 UTC
# Purpose: Permanent external configuration validation regression.
# Created By: ChatGPT GPT-6
# Execution Model: Standard-library unittest with temporary and repository configuration.
# Observability: Configuration assertions.
# Dependencies: runtime/configuration.py; config/residents/grace.json
# Authority: hints/engineering-test-policy.md
# Changed: 2026-11-03T02:25:24.123Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Assert production Grace config enables review feedback continuity.
# Supersedes: None
# History/Predecessor: Git blob 49abb7d901a598346470e29824cf99c1ff2b650d
# Tests: This file.
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

    def test_production_grace_configuration_enables_review_feedback(self):
        config_root = Path(__file__).resolve().parent.parent / "config"
        result = load_configuration(config_root)
        grace = next(item for item in result["residents"]
                     if item["settings"]["name"] == "Grace")
        self.assertIn("RESIDENT_ACTIVITY",
                      grace["settings"].get("continuation_event_types", []))
        self.assertIn("REVIEW_FEEDBACK",
                      grace["settings"].get("continuation_event_types", []))
        self.assertIn("For RESIDENT_ACTIVITY and REVIEW_FEEDBACK events only",
                      grace["system_prompt"])

    def test_governed_credential_configuration_is_explicit_and_external(self):
        root = Path(__file__).resolve().parent.parent / "config"
        settings = load_configuration(root)
        grace = next(item["settings"] for item in settings["residents"] if item["settings"]["name"] == "Grace")
        self.assertIn("r3.resources.local_snapshot", grace["tools"]["allowed_tools"])
        self.assertIn("r3.evidence.record", grace["tools"]["allowed_tools"])
        self.assertTrue(Path(grace["tools"]["credential_file"]).is_absolute())

    def test_relative_credential_path_rejected(self):
        self.grace["tools"] = {"provider": "r3-native", "endpoint": "http://localhost:8080",
            "timeout_seconds": 3, "allowed_tools": ["r3.resources.local_snapshot"],
            "credential_file": "private/token.txt"}
        self.save()
        with self.assertRaises(ConfigurationError):
            load_configuration(self.root)

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
