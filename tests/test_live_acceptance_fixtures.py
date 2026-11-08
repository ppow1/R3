"""Structural checks for acceptance-only module failure probes."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LiveAcceptanceFixtureTests(unittest.TestCase):
    def test_oversized_provider_manifest_pins_the_test_artifact(self):
        root = ROOT / "r3a_plugins" / "live_acceptance"
        manifest = json.loads((root / "manifest.json").read_text())
        artifact = (root / "oversized_result.py").read_bytes()
        digest = hashlib.sha256(artifact).hexdigest()
        self.assertEqual("r3a.acceptance-oversized-result", manifest["plugin_id"])
        self.assertEqual(digest, manifest["artifact_sha256"])
        self.assertEqual(digest, manifest["module_manifest"]["artifact"]["artifact_sha256"])
        self.assertEqual("acceptance.oversized-result.read", manifest["operation"]["operation_id"])

    def test_dependency_failure_manifests_express_distinct_rejections(self):
        fixtures = ROOT / "tests" / "fixtures" / "providers"
        missing = json.loads((fixtures / "missing_dependency_manifest.json").read_text())
        incompatible = json.loads((fixtures / "incompatible_dependency_manifest.json").read_text())
        self.assertEqual("^1.0.0", missing["module_manifest"]["dependencies"][0]["version_range"])
        self.assertEqual("r3a.missing.acceptance-dependency",
                         missing["module_manifest"]["dependencies"][0]["module_id"])
        self.assertEqual("^3.0.0", incompatible["module_manifest"]["dependencies"][0]["version_range"])
        self.assertEqual("r3a.octominer-telemetry",
                         incompatible["module_manifest"]["dependencies"][0]["module_id"])


if __name__ == "__main__":
    unittest.main()
