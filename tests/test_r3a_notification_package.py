"""Immutable notification provider package build regressions."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.config import load_settings
from scripts.package_notification_module import build_entries, build_package

ROOT = Path(__file__).resolve().parents[1]


def _load_manifest_in_standard_registry(manifest: Path, temp_root: Path) -> None:
    data_dir = temp_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = temp_root / "notification-config.json"
    config_path.write_text(json.dumps({"dsn_env": "R3A_NOTIFICATION_DATABASE_DSN",
                                       "presentation_timezone": "UTC"}), encoding="utf-8")
    module_source = ROOT / "r3a_runtime" / "observer_module.py"
    config = {
        "schema_version": 1,
        "instance_id": "r3a_notification_autocrlf_fixture",
        "paths": {"data_dir": str(data_dir), "postgres_socket_dir": str(data_dir / "pg"),
                  "control_socket": str(data_dir / "control.sock"),
                  "diagnostics_socket": str(data_dir / "diagnostics.sock"),
                  "module_socket": str(data_dir / "module.sock"),
                  "machine_catalog_dir": str(temp_root / "catalog")},
        "postgres": {"database": "r3a_notification_autocrlf_fixture", "user": "r3a_runtime",
                     "socket_dir": str(data_dir / "pg"), "port": 55432},
        "module": {"module_id": "foundation.observer", "version": "1.0.0",
                   "contract_id": "r3a.resident-module", "protocol_major": 1,
                   "protocol_minor": 0, "capabilities": ["notification.delivery.read"],
                   "owner": "R3A", "entrypoint": "r3a_runtime.observer_module",
                   "source": str(module_source),
                   "sha256": hashlib.sha256(module_source.read_bytes()).hexdigest()},
        "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                   "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                   "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                   "restart_initial_seconds": 1, "restart_max_seconds": 5,
                   "worker_concurrency": 1},
        "capability_operations": [{"manifest": str(manifest), "configuration": str(config_path)}],
    }
    bootstrap = temp_root / "bootstrap.json"
    bootstrap.write_text(json.dumps(config), encoding="utf-8")
    settings = load_settings(bootstrap)
    registered = settings.capability_registry.resolve("notification.delivery.read", "1.0.0")
    if registered.descriptor["required_grants"] != ["notification.delivery.read"]:
        raise AssertionError("installed notification operation has unexpected grants")


class NotificationPackageTests(unittest.TestCase):
    def test_release_package_is_deterministic_hashed_and_installable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "notification.tar.gz"
            second = root / "notification-copy.tar.gz"
            digest, _ = build_package(first)
            second_digest, _ = build_package(second)
            self.assertEqual(digest, second_digest)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(
                f"{digest}  notification.tar.gz\n",
                first.with_suffix(first.suffix + ".sha256").read_text(encoding="ascii"),
            )

            with tarfile.open(first, "r:gz") as archive:
                entries = {member.name: archive.extractfile(member).read()
                           for member in archive.getmembers() if member.isfile()}
            release = json.loads(entries["RELEASE_MANIFEST.json"])
            self.assertEqual("r3a.module-release-package.v1", release["schema_id"])
            self.assertEqual("r3a.notification-delivery", release["module_id"])
            self.assertEqual("1.0.0", release["module_version"])
            self.assertFalse(release["write_operations_registered"])
            for item in release["files"]:
                self.assertEqual(item["sha256"], hashlib.sha256(entries[item["path"]]).hexdigest())
            self.assertEqual(build_entries(), entries)

    def test_autocrlf_true_git_checkout_keeps_all_pinned_files_loadable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seed = root / "seed"
            seed.mkdir()
            for relative, content in build_entries().items():
                target = seed / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            (seed / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())

            def git(*args: str, cwd: Path) -> None:
                subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

            git("init", "--quiet", cwd=seed)
            git("config", "user.name", "Notification Package Test", cwd=seed)
            git("config", "user.email", "notification-package-test@example.invalid", cwd=seed)
            git("add", "--all", cwd=seed)
            git("commit", "--quiet", "-m", "fixture", cwd=seed)
            for checkout_name, autocrlf in (("windows-checkout", "true"),
                                            ("linux-checkout", "false")):
                checkout = root / checkout_name
                subprocess.run(["git", "clone", "--quiet", "-c",
                                f"core.autocrlf={autocrlf}", str(seed), str(checkout)],
                               check=True, capture_output=True, text=True)
                package_dir = checkout / "r3a_plugins" / "notification_service"
                manifest = json.loads((package_dir / "manifest.read.json").read_text(encoding="utf-8"))
                for reference, expected in (
                    (manifest["artifact_ref"], manifest["artifact_sha256"]),
                    *[(item["artifact_ref"], item["artifact_sha256"])
                      for item in manifest["supporting_artifacts"]],
                ):
                    actual = hashlib.sha256((package_dir / reference).read_bytes()).hexdigest()
                    self.assertEqual(expected, actual, f"{checkout_name}:{reference}")
                _load_manifest_in_standard_registry(
                    package_dir / "manifest.read.json", root / f"loader-{checkout_name}")


if __name__ == "__main__":
    unittest.main()
