"""Regression checks for isolated managed-runtime acceptance preparation."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.measure_octominer_module_install import measure

ROOT = Path(__file__).resolve().parents[1]


class ModuleAcceptancePreparationTests(unittest.TestCase):
    def test_install_timing_repeats_package_integrity_in_an_isolated_root(self):
        result = measure()
        self.assertEqual("r3a.module-install-measurement.v1", result["schema_id"])
        self.assertEqual("r3a.octominer-telemetry", result["module_id"])
        self.assertEqual("2.0.0", result["module_version"])
        self.assertRegex(result["bundle_sha256"], r"^[a-f0-9]{64}$")
        self.assertGreater(result["size_bytes"], 0)
        self.assertTrue(result["isolated_temporary_root"])
        self.assertFalse(result["shared_services_touched"])
        self.assertEqual({"build", "verify", "install", "total"},
                         set(result["elapsed_seconds"]))
        for elapsed in result["elapsed_seconds"].values():
            self.assertGreaterEqual(elapsed, 0)
        self.assertGreaterEqual(result["elapsed_seconds"]["total"],
                                result["elapsed_seconds"]["install"])

    def test_managed_runbook_matches_telemetry_output_and_grace_invocation_contract(self):
        manifest = json.loads((ROOT / "r3a_plugins/octominer_telemetry/manifest.json").read_text())
        output_schema = manifest["operation"]["output_schema"]
        self.assertEqual("array", output_schema["type"])
        self.assertNotEqual("r3a.activity-intake.v1", output_schema.get("$id"))

        runbook = (ROOT / "docs/runbooks/R3A_LIVE_MODULAR_MODULE_LIFECYCLE.md").read_text()
        acceptance = runbook.split("## 4. Verify discovery, health, and one operation", 1)[1].split("## 5.", 1)[0]
        self.assertNotIn("activity-intake-accept", acceptance)
        self.assertIn("authenticated Steward asks Grace", acceptance)
        self.assertIn("canonical operation", acceptance)
        self.assertIn("CME performs authorization and scheduling", acceptance)


if __name__ == "__main__":
    unittest.main()
