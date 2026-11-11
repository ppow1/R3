"""Immutable notification provider package build regressions."""
from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_notification_module import build_entries, build_package


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


if __name__ == "__main__":
    unittest.main()
