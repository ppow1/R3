"""Conformance checks for the isolated live telemetry replacement fixture."""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from r3a_plugins.octominer_telemetry.replacement_test_fixture import create_provider


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "r3a_plugins" / "octominer_telemetry"


class LiveModularReplacementFixtureTests(unittest.TestCase):
    def test_manifest_pins_replacement_and_all_telemetry_artifacts(self):
        manifest = json.loads((PLUGIN_DIR / "replacement_test_manifest.json").read_text())
        self.assertEqual("2.0.1", manifest["provider"]["provider_version"])
        self.assertEqual("infrastructure.octominer.telemetry.read",
                         manifest["operation"]["operation_id"])
        for item in [{"artifact_ref": manifest["artifact_ref"],
                      "artifact_sha256": manifest["artifact_sha256"]},
                     *manifest["supporting_artifacts"]]:
            path = PLUGIN_DIR / item["artifact_ref"]
            self.assertEqual(item["artifact_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_wrapper_runs_real_provider_and_marks_its_fixture_version(self):
        samples = [{"source_id": "gpu.telemetry.test", "content": {"available": True}}]
        provider = Mock()
        provider.invoke.return_value = samples
        with patch(
                "r3a_plugins.octominer_telemetry.replacement_test_fixture.create_telemetry_provider",
                return_value=provider) as factory:
            wrapped = create_provider({"host_id": "test-host"})
        arguments, context = {}, {"invocation_id": "fixture-invocation"}
        result = wrapped.invoke(arguments, context=context)
        factory.assert_called_once_with({"host_id": "test-host"})
        provider.invoke.assert_called_once_with(arguments, context=context)
        self.assertEqual(samples[0], {k: v for k, v in result[0].items() if k != "provider_revision"})
        self.assertEqual("2.0.1-live-acceptance-fixture", result[0]["provider_revision"])


if __name__ == "__main__":
    unittest.main()
