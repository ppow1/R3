# R3 CONTROLLED SOURCE
# File: tests/test_service_configuration.py
# Component: R3-SERVICE-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent isolated service startup and generic resident registration regression.
# Contracts: hints/engineering-test-policy.md
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


class ServiceConfigurationTests(unittest.TestCase):
    def test_service_starts_with_external_configuration(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "config"
            (config / "residents/prompts").mkdir(parents=True)
            (config / "residents/prompts/grace.md").write_text("Grace test prompt")
            (config / "residents/prompts/jessica.md").write_text("Jessica test prompt")
            runtime = {
                "scheduler_tick_seconds": 0.05,
                "health_interval_seconds": 0.05,
                "sqlite_busy_timeout_ms": 5000,
                "residents": {"grace": "residents/grace.json", "jessica": "residents/jessica.json"},
            }
            (config / "runtime.json").write_text(json.dumps(runtime))
            for name in ("Grace", "Jessica"):
                resident = {
                    "name": name, "role": "Test resident", "enabled": True,
                    "inference": {"endpoint": "http://127.0.0.1:1/v1", "model": "test", "timeout_seconds": 2},
                    "schedule_interval_seconds": 0.1,
                    "system_prompt_file": f"residents/prompts/{name.lower()}.md",
                    "tools": {"provider": "none"},
                }
                (config / f"residents/{name.lower()}.json").write_text(json.dumps(resident))
            health = root / "health.json"
            process = subprocess.Popen(
                [sys.executable, "-m", "runtime.serve", "--db", str(root / "institution.db"),
                 "--health-file", str(health), "--config-dir", str(config)],
                cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline and not health.exists() and process.poll() is None:
                    time.sleep(0.05)
                if process.poll() is not None:
                    out, err = process.communicate()
                    self.fail(f"Service exited early: {process.returncode}; {err.decode(errors='replace')}")
                self.assertTrue(health.exists(), "Service never produced health snapshot")
                snapshot = json.loads(health.read_text())
                self.assertEqual(snapshot["registered_residents"], 2)
                self.assertEqual(snapshot["resident_inbox_pending"], 0)
                self.assertEqual({r["name"] for r in snapshot["state"]["residents"]}, {"Grace", "Jessica"})
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                try:
                    process.communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()


if __name__ == "__main__":
    unittest.main()
