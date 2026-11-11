"""Package, integrity, staging and functional-operation regression for OctoMiner modules."""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import importlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from r3a_runtime.capability_contracts import CapabilityRegistry
from r3a_runtime.provider_runtime import ProviderProcessManager
from scripts.package_octominer_module import (build_package, install_package,
                                              verify_package)


ROOT = Path(__file__).resolve().parents[1]
GPU_SAMPLE = ("GPU-111, NVIDIA Tesla P100, 00000000:04:00.0, 550.144.03, "
              "16384, 1200, 15184, 35, 46, 82.5, 50\n")
DF_SAMPLE = "Filesystem  1B-blocks Used Available Use% Mounted on\n/dev/sda4 1000 400 600 40% /\n"
PROCESS_SAMPLE = "GPU-111, 321, llama-server, 256\n"


class ModuleReleasePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="r3a-module-package-test-")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_build_verify_and_install_are_versioned_and_idempotent(self):
        artifact = self.root / "octominer.tar.gz"
        built = build_package(artifact)
        release, entries = verify_package(artifact)
        self.assertEqual("r3a.module-release-package.v1", release["schema_id"])
        self.assertEqual("r3a.module-manifest.v1@1.1.0", release["manifest_contract"])
        self.assertEqual(["infrastructure.octominer.telemetry.read"], release["required_grants"])
        self.assertEqual("read", release["capabilities"][0]["effect_class"])
        self.assertNotIn("replacement_test_fixture.py", " ".join(entries))
        self.assertEqual(built["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())

        installed = install_package(artifact, self.root / "app")
        repeated = install_package(artifact, self.root / "app")
        self.assertFalse(installed["idempotent"])
        self.assertTrue(repeated["idempotent"])
        self.assertTrue((self.root / "app/r3a_plugins/octominer_telemetry_2_0_0/manifest.json").is_file())
        self.assertTrue((self.root / "app/.r3a-module-receipts/r3a.octominer-telemetry-2.0.0.json").is_file())

    def test_package_integrity_corruption_fails_closed(self):
        artifact = self.root / "octominer.tar.gz"
        build_package(artifact)
        with tarfile.open(artifact, "r:gz") as archive:
            entries = {member.name: archive.extractfile(member).read()
                       for member in archive.getmembers()}
        key = "r3a_plugins/octominer_telemetry_2_0_0/plugin.py"
        entries[key] += b"# altered after release\n"
        corrupted = self.root / "corrupted.tar.gz"
        with tarfile.open(corrupted, "w:gz") as archive:
            for name, data in entries.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "file digest mismatch"):
            verify_package(corrupted)

    def test_installed_provider_registers_discovers_and_returns_fresh_fixture_telemetry(self):
        artifact = self.root / "octominer.tar.gz"
        build_package(artifact)
        install_root = self.root / "app"
        install_package(artifact, install_root)
        import r3a_plugins
        r3a_plugins.__path__.append(str(install_root / "r3a_plugins"))
        importlib.invalidate_caches()

        manifest_path = install_root / "r3a_plugins/octominer_telemetry_2_0_0/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        config = json.loads((manifest_path.parent / "config.example.json").read_text(encoding="utf-8"))
        config.update({"ssh_host": "fixture.invalid", "ssh_user": "readonly_fixture",
                       "identity_file": "/fixture/identity", "known_hosts_file": "/fixture/known_hosts",
                       "history_path_env": "R3A_FIXTURE_TELEMETRY_HISTORY"})
        registry = CapabilityRegistry()
        registry.register(manifest["operation"], config, legacy_manifest=manifest)
        discovered = registry.discover()
        self.assertEqual("infrastructure.octominer.telemetry.read",
                         discovered[0]["descriptor"]["operation_id"])
        operation = registry.resolve("infrastructure.octominer.telemetry.read")
        provider = operation.load_provider()
        provider_module = sys.modules[provider.__class__.__module__]

        def fake_query(_config, remote_command):
            if remote_command.startswith("nvidia-smi --query-gpu"):
                return GPU_SAMPLE
            if remote_command.startswith("df -P"):
                return DF_SAMPLE
            if remote_command.startswith("nvidia-smi --query-compute-apps"):
                return PROCESS_SAMPLE
            raise AssertionError(f"unexpected telemetry command {remote_command}")

        with patch.dict("os.environ", {"R3A_FIXTURE_TELEMETRY_HISTORY":
                                      str(self.root / "telemetry-history.sqlite3")}), \
                patch.object(provider_module,
                             "_run_ssh_query", side_effect=lambda cfg, command: fake_query(cfg, command)):
            evidence = provider.invoke({}, context={"request_id": "package-test"})

        gpu = next(item for item in evidence if item["source_id"] == "gpu.telemetry.octo1")
        self.assertEqual("fresh", gpu["freshness"]["state"])
        self.assertEqual(35.0, gpu["content"]["gpus"][0]["utilization_percent"])
        self.assertEqual("MiB", gpu["units"]["memory_used_mib"])
        self.assertTrue(gpu["sha256"])

    def test_packaged_provider_activates_invokes_and_deactivates_through_module_runtime(self):
        artifact = self.root / "octominer.tar.gz"
        build_package(artifact)
        install_root = self.root / "app"
        install_package(artifact, install_root)
        manifest_path = install_root / "r3a_plugins/octominer_telemetry_2_0_0/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        package_root = manifest_path.parent
        config = json.loads((package_root / "config.example.json").read_text(encoding="utf-8"))
        identity = self.root / "fixture_identity"
        known_hosts = self.root / "fixture_known_hosts"
        identity.write_text("fixture-only identity marker", encoding="utf-8")
        known_hosts.write_text("fixture.invalid ssh-ed25519 FIXTURE_KEY", encoding="utf-8")
        config.update({"ssh_host": "${R3A_OCTOMINER_SSH_HOST}",
                       "ssh_user": "${R3A_OCTOMINER_SSH_USER}",
                       "identity_file": "${R3A_OCTOMINER_IDENTITY_FILE}",
                       "known_hosts_file": "${R3A_OCTOMINER_KNOWN_HOSTS}",
                       "history_path_env": "R3A_OCTOMINER_HISTORY_PATH"})

        registry = CapabilityRegistry()
        legacy = dict(manifest)
        legacy["_provider_artifact_path"] = str(package_root / "plugin.py")
        legacy["_pinned_artifact_paths"] = {
            str(package_root / item["artifact_ref"]): item["artifact_sha256"]
            for item in manifest.get("supporting_artifacts", [])
        }
        registry.register(manifest["operation"], config, legacy_manifest=legacy)
        operation = registry.resolve("infrastructure.octominer.telemetry.read")

        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_ssh = fake_bin / "ssh"
        fake_ssh.write_text(
            "#!/usr/bin/python3\n"
            "import sys\n"
            "query = sys.argv[-1]\n"
            f"if query.startswith({json.dumps('nvidia-smi --query-gpu=')}): print({json.dumps(GPU_SAMPLE)}, end='')\n"
            f"elif query.startswith({json.dumps('df -P')}): print({json.dumps(DF_SAMPLE)}, end='')\n"
            f"elif query.startswith({json.dumps('nvidia-smi --query-compute-apps=')}): print({json.dumps(PROCESS_SAMPLE)}, end='')\n"
            "else: sys.exit(2)\n", encoding="utf-8")
        fake_ssh.chmod(0o755)
        (install_root / "sitecustomize.py").write_text(
            "import r3a_plugins\n"
            f"r3a_plugins.__path__.insert(0, {str(install_root / 'r3a_plugins')!r})\n",
            encoding="utf-8")

        class Store:
            def __init__(self):
                self.modules = {}
                self.transitions = []

            async def register_module(self, manifest_value, lifecycle="INSTALLED", health="unknown",
                                      diagnostic=None):
                key = (manifest_value["module_id"], manifest_value["module_version"])
                self.modules[key] = {"manifest": manifest_value, "artifact_digest": manifest_value["artifact_digest"],
                                     "lifecycle_state": lifecycle, "health": health,
                                     "diagnostic": diagnostic or {}}

            async def rows(self, _query, key):
                row = self.modules.get(tuple(key))
                if row is None:
                    return []
                return [{"manifest": row["manifest"], "artifact_digest": row["artifact_digest"],
                         "lifecycle_state": row["lifecycle_state"], "diagnostic": row["diagnostic"]}]

            async def module_state(self, module_id, version, state, health, diagnostic=None, **_kwargs):
                row = self.modules[(module_id, version)]
                prior = row["lifecycle_state"]
                row.update({"lifecycle_state": state, "health": health, "diagnostic": diagnostic or {}})
                self.transitions.append((prior, state))

        async def lifecycle():
            import r3a_runtime.provider_runtime as provider_runtime
            store = Store()
            settings = SimpleNamespace(data_dir=self.root / "runtime-data", heartbeat_stale_after_seconds=1)
            manager = ProviderProcessManager(settings, store, registry)
            real_module_env = provider_runtime._module_environment

            def test_module_env(registered):
                env = real_module_env(registered)
                env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
                env["PYTHONPATH"] = os.pathsep.join((str(install_root), str(ROOT)))
                return env

            runtime_env = {
                "R3A_OCTOMINER_SSH_HOST": "fixture.invalid",
                "R3A_OCTOMINER_SSH_USER": "readonly_fixture",
                "R3A_OCTOMINER_IDENTITY_FILE": str(identity),
                "R3A_OCTOMINER_KNOWN_HOSTS": str(known_hosts),
                "R3A_OCTOMINER_HISTORY_PATH": str(self.root / "history.sqlite3"),
            }
            with patch.dict(os.environ, runtime_env), \
                    patch.object(provider_runtime, "_module_environment", side_effect=test_module_env):
                active = await manager.activate(operation)
                self.assertEqual("ACTIVE", active["state"])
                self.assertEqual("ACTIVE", registry.discover()[0]["registry_observation"]["state"])
                evidence = await manager.invoke(operation, {}, {
                    "effect_class": "read", "target": {"source_ids": [], "host_ids": ["octo1"]}})
                gpu = next(item for item in evidence if item["source_id"] == "gpu.telemetry.octo1")
                self.assertEqual("fresh", gpu["freshness"]["state"])
                self.assertEqual(35.0, gpu["content"]["gpus"][0]["utilization_percent"])
                stopped = await manager.stop("r3a.octominer-telemetry", "2.0.0")
                self.assertTrue(stopped["stopped"])
                self.assertEqual("STOPPED", store.modules[("r3a.octominer-telemetry", "2.0.0")]["lifecycle_state"])
            await manager.close()

        asyncio.run(lifecycle())


if __name__ == "__main__":
    unittest.main()
