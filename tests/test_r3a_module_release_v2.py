"""Install/launch compatibility and immutable staging regressions for module package v2.

# R3 CONTROLLED SOURCE
# File: tests/test_r3a_module_release_v2.py
# Component: TEST-R3A-GENERIC-MODULE-RELEASE-V2
# File Revision: 1.0.3
# Created: 2026-11-11T18:59:02Z
# Created By: Codex GPT-6
# Purpose: Verify generic resident JSON-lines package integrity, installation, launch and candidate rollback.
# Execution Model: unittest with temporary archives/install roots and a local fixture worker process.
# Observability: Package/bundle digests, immutable install paths, protocol health and retained prior version.
# Dependencies: scripts.r3a_module_release_package; r3a_runtime.protocol; package fixture.
# Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Modular Plugins #46 Step 70/84.
# Changed: 2026-11-11T18:59:02Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Add generic module package and rollback tests.
# Changed: 2026-11-11T19:00:40Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Exercise generic launch CLI inputs and CME lifecycle-guarded candidate cleanup.
# Changed: 2026-11-11T19:04:46Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Check staged-byte integrity and resident role validation.
# Changed: 2026-11-11T19:11:23Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Verify symlink rejection and paired effective version/digest guard.
# Supersedes: None.
# Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0; r3a.module.v1.
# Tests: Self; python -m pytest -q tests/test_r3a_module_release_v2.py.
# History/Predecessor: New test file; interop payload fixture is in tests/fixtures/r3a_module_release_package_v2/.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from r3a_runtime.protocol import request
from scripts.r3a_module_release_package import (
    _tree_digest,
    build_package,
    discard_unactivated_candidate,
    install_package,
    verify_package,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/r3a_module_release_package_v2"


def _inputs(module_version: str = "1.0.0", *, worker_suffix: bytes = b""):
    files = {
        "orbit_worker/__init__.py": (FIXTURE / "orbit_worker/__init__.py").read_bytes(),
        "orbit_worker/worker.py": (FIXTURE / "orbit_worker/worker.py").read_bytes() + worker_suffix,
    }
    manifest = json.loads((FIXTURE / "module-manifest.json").read_text(encoding="utf-8"))
    manifest["module_version"] = module_version
    manifest["artifact_digest"] = _tree_digest(files)
    binding = json.loads((FIXTURE / "process-binding.json").read_text(encoding="utf-8"))
    return manifest, binding, files


class ModuleReleaseV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r3a-module-release-v2-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _package(self, name: str, module_version: str = "1.0.0", *, worker_suffix: bytes = b""):
        manifest, binding, files = _inputs(module_version, worker_suffix=worker_suffix)
        path = self.root / name
        built = build_package(manifest, binding, files, path)
        return path, built, manifest, binding, files

    def test_shared_fixture_builds_and_launches_generic_jsonl_worker(self):
        package, built, manifest, binding, files = self._package("orbit.tar.gz")
        descriptor, verified_files, verified_manifest = verify_package(
            package, expected_bundle_sha256=built["bundle_sha256"])
        interop_fixture = json.loads((ROOT / "tests/fixtures/r3a_module_release_package_v2.json").read_text())
        self.assertEqual(interop_fixture, descriptor)
        self.assertEqual("executor.orbit", descriptor["module_id"])
        self.assertEqual("resident_executor", descriptor["module_kind"])
        self.assertEqual(manifest, verified_manifest)
        self.assertEqual(files, verified_files)
        self.assertEqual(binding, descriptor["process_binding"])
        self.assertNotIn("grant", json.dumps(descriptor).lower())

        install_root = self.root / "install"
        installed = install_package(package, install_root, expected_bundle_sha256=built["bundle_sha256"])
        repeated = install_package(package, install_root, expected_bundle_sha256=built["bundle_sha256"])
        self.assertFalse(installed["idempotent"])
        self.assertTrue(repeated["idempotent"])
        artifact_root = Path(installed["artifact_root"])
        config = self.root / "orbit-config.json"
        config.write_text("{}\n", encoding="utf-8")
        socket_path = self.root / "orbit.sock"
        template = binding["arguments_template"]
        values = {"socket_path": str(socket_path), "module_id": descriptor["module_id"],
                  "module_version": descriptor["module_version"], "configuration_path": str(config)}
        args = [value.format_map(values) for value in template]
        environment = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": os.pathsep.join((str(artifact_root), str(ROOT)),),
                       "PYTHONUTF8": "1"}
        process = subprocess.Popen([sys.executable, "-m", binding["entrypoint"], *args],
                                   cwd=artifact_root, env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8
            health = None
            while time.monotonic() < deadline:
                try:
                    response = asyncio.run(request(socket_path, descriptor["module_id"],
                                                   descriptor["module_version"], "health", timeout=0.25))
                    health = response["result"]
                    break
                except (OSError, asyncio.TimeoutError, ConnectionError):
                    if process.poll() is not None:
                        raise AssertionError(f"fixture worker exited: {process.stderr.read()}")
                    time.sleep(0.05)
            self.assertIsNotNone(health, "fixture worker did not create its JSON-lines socket")
            self.assertEqual("executor.orbit", health["module"])
            stopped = asyncio.run(request(socket_path, descriptor["module_id"],
                                          descriptor["module_version"], "stop", timeout=1))
            self.assertTrue(stopped["result"]["stopped"])
            self.assertEqual(0, process.wait(timeout=5))
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_versioned_candidate_rollback_preserves_prior_immutable_artifact(self):
        v1, built1, manifest1, _, _ = self._package("orbit-1.0.0.tar.gz")
        root = self.root / "install"
        installed1 = install_package(v1, root, expected_bundle_sha256=built1["bundle_sha256"])
        v2, built2, _, _, _ = self._package("orbit-1.0.1.tar.gz", "1.0.1")
        installed2 = install_package(v2, root, expected_bundle_sha256=built2["bundle_sha256"])
        self.assertNotEqual(installed1["path"], installed2["path"])
        with self.assertRaises(PermissionError):
            discard_unactivated_candidate(root, manifest1["module_id"], "1.0.1",
                                          installed2["artifact_digest"],
                                          effective_artifact_digest=installed2["artifact_digest"],
                                          effective_module_version="1.0.1",
                                          module_lifecycle_state="ACTIVE")
        with self.assertRaises(PermissionError):
            discard_unactivated_candidate(root, manifest1["module_id"], "1.0.1",
                                          installed2["artifact_digest"],
                                          effective_artifact_digest=installed1["artifact_digest"],
                                          effective_module_version="1.0.0",
                                          module_lifecycle_state="ACTIVATING")
        self.assertTrue(discard_unactivated_candidate(
            root, manifest1["module_id"], "1.0.1", installed2["artifact_digest"],
            effective_artifact_digest=installed1["artifact_digest"], effective_module_version="1.0.0",
            module_lifecycle_state="FAILED"))
        self.assertFalse(Path(installed2["path"]).exists())
        self.assertTrue(Path(installed1["path"]).is_dir())
        self.assertEqual(manifest1["artifact_digest"], installed1["artifact_digest"])

    def test_bundle_pin_tamper_and_version_digest_drift_fail_before_staging(self):
        first, built1, manifest1, binding1, files1 = self._package("orbit.tar.gz")
        root = self.root / "install"
        installed = install_package(first, root, expected_bundle_sha256=built1["bundle_sha256"])
        with self.assertRaisesRegex(ValueError, "bundle digest"):
            install_package(first, root, expected_bundle_sha256="0" * 64)
        changed_manifest, changed_binding, changed_files = _inputs(worker_suffix=b"# changed\n")
        changed = self.root / "changed.tar.gz"
        changed_built = build_package(changed_manifest, changed_binding, changed_files, changed)
        with self.assertRaisesRegex(FileExistsError, "different immutable artifact"):
            install_package(changed, root, expected_bundle_sha256=changed_built["bundle_sha256"])
        self.assertTrue(Path(installed["path"]).is_dir())
        self.assertEqual(manifest1["artifact_digest"], installed["artifact_digest"])

    def test_invalid_process_binding_and_unsafe_source_paths_are_rejected(self):
        manifest, binding, files = _inputs()
        bad_binding = dict(binding)
        bad_binding["arguments_template"] = ["/bin/sh", "-c", "unsafe"]
        with self.assertRaises(ValueError):
            build_package(manifest, bad_binding, files, self.root / "bad.tar.gz")
        for unsafe in ("../escape.py", "/absolute.py", "orbit//worker.py", "orbit/../worker.py"):
            with self.subTest(path=unsafe), self.assertRaises(ValueError):
                build_package(manifest, binding, {unsafe: b"fixture"}, self.root / "bad.tar.gz")

    def test_release_manifest_digest_pins_and_binding_schema_validate(self):
        package, built, _, _, _ = self._package("orbit.tar.gz")
        descriptor, _, _ = verify_package(package, expected_bundle_sha256=built["bundle_sha256"])
        self.assertEqual("r3a.module-release-package.v2", descriptor["schema_id"])
        self.assertEqual(2, descriptor["schema_version"])
        self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(), built["bundle_sha256"])
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual("executor.orbit", descriptor["module_id"])

    def test_idempotent_install_rechecks_every_immutable_file(self):
        package, built, _, _, _ = self._package("orbit.tar.gz")
        root = self.root / "install"
        installed = install_package(package, root, expected_bundle_sha256=built["bundle_sha256"])
        payload = Path(installed["artifact_root"]) / "orbit_worker/worker.py"
        payload.chmod(0o644)
        payload.write_bytes(payload.read_bytes() + b"# tampered after staging")
        with self.assertRaisesRegex(ValueError, "artifact digest mismatch"):
            install_package(package, root, expected_bundle_sha256=built["bundle_sha256"])

    def test_idempotent_install_rejects_links_and_cleanup_requires_paired_effective_pin(self):
        package, built, manifest, _, _ = self._package("orbit.tar.gz")
        root = self.root / "install"
        installed = install_package(package, root, expected_bundle_sha256=built["bundle_sha256"])
        artifact_root = Path(installed["artifact_root"])
        artifact_root.chmod(0o755)
        link = artifact_root / "external.py"
        link.symlink_to(self.root / "outside.py")
        with self.assertRaisesRegex(ValueError, "link or special file"):
            install_package(package, root, expected_bundle_sha256=built["bundle_sha256"])
        link.unlink()
        with self.assertRaisesRegex(ValueError, "supplied together"):
            discard_unactivated_candidate(root, manifest["module_id"], "1.0.0",
                                          installed["artifact_digest"],
                                          effective_artifact_digest=None,
                                          effective_module_version="1.0.0",
                                          module_lifecycle_state="FAILED")


if __name__ == "__main__":
    unittest.main()
