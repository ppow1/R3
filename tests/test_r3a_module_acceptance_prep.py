"""Regression checks for isolated managed-runtime acceptance preparation."""
from __future__ import annotations

import unittest

from scripts.measure_octominer_module_install import measure


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


if __name__ == "__main__":
    unittest.main()
