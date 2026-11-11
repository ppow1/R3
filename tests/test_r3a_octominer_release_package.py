"""Deterministic telemetry release package and staged rollback regressions.

R3 CONTROLLED SOURCE
File: tests/test_r3a_octominer_release_package.py
Component: TEST-R3A-OCTOMINER-TELEMETRY-RELEASE
File Revision: 1.0.0
Created: 2026-11-11T19:25:02Z
Created By: Codex GPT-6
Purpose: Verify immutable v2.1.1 provider archive and retain v2.1.0 during failed candidate validation.
Execution Model: Deterministic archive rebuild and temporary extraction with standard settings loader.
Observability: Externally pinned archive SHA, per-file digests, loader acceptance and prior-stage retention.
Dependencies: scripts.package_octominer_telemetry; r3a_runtime.config; telemetry fixtures.
Authority: AD-024; Modular Plugins #46 Step 98. No activation or authority change.
Changed: 2026-11-11T19:25:02Z | R3A-MODULAR-PLUGINS-STEP-98 | Codex GPT-6 | Add package reproducibility, standard-loader install and rollback tests.
Supersedes: None.
Contracts: r3a.module-release-package.v1; r3a.capability-provider.v1.
Tests: Self; python -m pytest -q tests/test_r3a_octominer_release_package.py.
History/Predecessor: New provider release-package regression, follows existing Knowledge module packaging tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_octominer_telemetry import ROOT, build_package


class OctoMinerReleasePackageTests(unittest.TestCase):
    def _bootstrap(self, install_root: Path, data_root: Path, version: str) -> Path:
        package = install_root / "r3a_plugins/octominer_telemetry"
        module_source = ROOT / "r3a_runtime/observer_module.py"
        data_root.mkdir(parents=True, exist_ok=True)
        value = {
            "schema_version": 1, "instance_id": "r3a_telemetry_package_fixture",
            "paths": {"data_dir": str(data_root), "postgres_socket_dir": str(data_root / "pg"),
                      "control_socket": str(data_root / "control.sock"),
                      "diagnostics_socket": str(data_root / "diagnostics.sock"),
                      "module_socket": str(data_root / "module.sock"),
                      "machine_catalog_dir": str(ROOT / "r3a_runtime/state_machines")},
            "postgres": {"database": "r3a_telemetry_package_fixture", "user": "r3a_runtime",
                         "socket_dir": str(data_root / "pg"), "port": 55432},
            "module": {"module_id": "foundation.observer", "version": "1.0.0",
                       "contract_id": "r3a.resident-module", "protocol_major": 1,
                       "protocol_minor": 0,
                       "capabilities": ["infrastructure.octominer.telemetry.read"],
                       "owner": "R3A", "entrypoint": "r3a_runtime.observer_module",
                       "source": str(module_source),
                       "sha256": hashlib.sha256(module_source.read_bytes()).hexdigest()},
            "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                       "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                       "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                       "restart_initial_seconds": 1, "restart_max_seconds": 5,
                       "worker_concurrency": 1},
            "capability_operations": [{
                "manifest": str(package / f"manifest.v{version}.json"),
                "configuration": str(ROOT / "r3a_plugins/octominer_telemetry/config.v3.example.json")}],
        }
        bootstrap = data_root / "bootstrap.json"
        bootstrap.write_text(json.dumps(value), encoding="utf-8")
        return bootstrap

    def _load(self, root: Path, bootstrap: Path) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        code = ("import sys; from r3a_runtime.config import load_settings; "
                "s=load_settings(sys.argv[1]); "
                "s.capability_registry.resolve('infrastructure.octominer.telemetry.read')")
        return subprocess.run([sys.executable, "-c", code, str(bootstrap)], cwd=root,
                              env=env, capture_output=True, text=True)

    def test_reproducible_v211_package_installs_and_failed_candidate_keeps_v210(self):
        with tempfile.TemporaryDirectory(prefix="r3a-octominer-package-") as temporary:
            temp = Path(temporary)
            built = {}
            archives = {}
            for version in ("2.1.0", "2.1.1"):
                first, second = temp / f"{version}-one.tar.gz", temp / f"{version}-two.tar.gz"
                digest1, size1 = build_package(version, first)
                digest2, size2 = build_package(version, second)
                self.assertEqual((digest1, size1), (digest2, size2))
                self.assertEqual(first.read_bytes(), second.read_bytes())
                built[version] = digest1
                archives[version] = first

            release_artifact = ROOT / "artifacts/r3a-octominer-telemetry-2.1.1.tar.gz"
            checksum = release_artifact.with_suffix(release_artifact.suffix + ".sha256")
            self.assertTrue(release_artifact.is_file())
            expected_pin = checksum.read_text(encoding="ascii").split()[0]
            self.assertEqual(built["2.1.1"], expected_pin)
            self.assertEqual(hashlib.sha256(release_artifact.read_bytes()).hexdigest(), expected_pin)

            previous = temp / "effective-v2.1.0"
            candidate = temp / "candidate-v2.1.1"
            previous.mkdir()
            candidate.mkdir()
            for version, archive, destination in (("2.1.0", archives["2.1.0"], previous),
                                                   ("2.1.1", release_artifact, candidate)):
                with tarfile.open(archive, "r:gz") as tar:
                    tar.extractall(destination, filter="data")
                release = json.loads((destination / "RELEASE_MANIFEST.json").read_text())
                self.assertEqual(version, release["module_version"])
                for item in release["files"]:
                    path = destination / item["path"]
                    payload = path.read_bytes()
                    self.assertEqual(item["sha256"], hashlib.sha256(payload).hexdigest(), item["path"])
                    self.assertEqual(item["size_bytes"], len(payload), item["path"])

            old_bootstrap = self._bootstrap(previous, temp / "previous-data", "2.1.0")
            new_bootstrap = self._bootstrap(candidate, temp / "candidate-data", "2.1.1")
            old_before = (previous / "r3a_plugins/octominer_telemetry/scope_provider.py").read_bytes()
            self.assertEqual(0, self._load(previous, old_bootstrap).returncode)
            self.assertEqual(0, self._load(candidate, new_bootstrap).returncode)

            candidate_artifact = candidate / "r3a_plugins/octominer_telemetry/scope_provider_v2_1_1.py"
            candidate_artifact.write_bytes(candidate_artifact.read_bytes() + b"\n# tampered\n")
            rejected = self._load(candidate, new_bootstrap)
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn("artifact digest does not match", rejected.stderr)
            self.assertEqual(old_before,
                             (previous / "r3a_plugins/octominer_telemetry/scope_provider.py").read_bytes())
            self.assertEqual(0, self._load(previous, old_bootstrap).returncode)


if __name__ == "__main__":
    unittest.main()
