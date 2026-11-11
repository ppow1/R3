"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_deployed_provider_artifact_bindings.py
Component: R3A-PROVIDER-ARTIFACT-DEPLOYMENT-REGRESSION
File Revision: 1.0.0
Created: 2026-11-10T01:31:53Z
Created By: Codex GPT-6
Purpose: Prevent deployed bootstrap manifests from pinning provider artifacts outside the runtime-imported checkout.
Execution Model: Offline configuration and source-path validation.
Observability: Reports the exact manifest entry whose import path and digest pin diverge.
Dependencies: R3A bootstrap JSON, provider manifests, active Python import path.
Authority: Coordinator V2 resident-chat incident remediation; does not authorize service changes.
Changed: 2026-11-10T01:31:53Z | R3A-WEBSITE-DIRECTORY-FAILURE-20261110 | Codex GPT-6 | Add deployment regression for provider artifact path drift.
Supersedes: None.
Contracts: r3a.module-manifest.v1; r3a.capability-operation.v1.
Tests: python -m unittest tests.test_r3a_deployed_provider_artifact_bindings.
History/Predecessor: New file.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import unittest
from pathlib import Path


class DeployedProviderArtifactBindingTests(unittest.TestCase):
    def test_configured_manifest_artifacts_match_runtime_import_paths(self):
        config_value = os.environ.get("R3A_PROVIDER_BINDING_CONFIG")
        if not config_value:
            self.skipTest("set R3A_PROVIDER_BINDING_CONFIG to verify a deployed R3A bootstrap")

        config_path = Path(config_value)
        bootstrap = json.loads(config_path.read_text(encoding="utf-8"))
        providers = bootstrap.get("capability_operations")
        self.assertIsInstance(providers, list)
        self.assertTrue(providers, "deployed bootstrap contains no configured capability providers")

        for index, configured in enumerate(providers):
            with self.subTest(provider_index=index):
                manifest_path = Path(configured["manifest"]).resolve(strict=True)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifact_path = (manifest_path.parent / manifest["artifact_ref"]).resolve(strict=True)
                self.assertEqual(
                    hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                    manifest["artifact_sha256"],
                    f"{manifest_path}: provider artifact digest does not match its manifest",
                )

                entrypoint_module = manifest["provider"]["entrypoint"].split(":", 1)[0]
                spec = importlib.util.find_spec(entrypoint_module)
                self.assertIsNotNone(spec, f"{manifest_path}: entrypoint is not importable")
                self.assertIsNotNone(spec.origin, f"{manifest_path}: entrypoint has no concrete source file")
                self.assertEqual(
                    artifact_path,
                    Path(spec.origin).resolve(),
                    f"{manifest_path}: runtime import resolves outside the pinned provider artifact",
                )


if __name__ == "__main__":
    unittest.main()
