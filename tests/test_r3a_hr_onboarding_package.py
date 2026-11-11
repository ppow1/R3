"""Deterministic package manifest, digest, and traversal safety regressions."""
from __future__ import annotations

import unittest

from scripts.package_r3a_hr_onboarding import build_bundle, verify_bundle


class HROnboardingPackageTests(unittest.TestCase):
    def test_bundle_is_reproducible_and_every_in_band_digest_verifies(self):
        payloads = {
            "docs/contract.md": b"versioned contract\n",
            "r3a_runtime/migrations/019.sql": b"CREATE TABLE packet (id text);\n",
        }
        first = build_bundle(payloads, source_revision="a" * 40)
        second = build_bundle(payloads, source_revision="a" * 40)
        self.assertEqual(first.archive, second.archive)
        self.assertEqual("SOURCE_CANDIDATE_NOT_DEPLOYABLE", first.manifest["readiness"])
        verified = verify_bundle(first.archive)
        self.assertEqual(first.manifest, verified)
        self.assertEqual(["docs/contract.md", "r3a_runtime/migrations/019.sql"],
                         [entry["path"] for entry in verified["files"]])

    def test_bundle_rejects_absolute_and_traversal_paths(self):
        for path in ("/etc/passwd", "../outside", "docs/../../outside"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                build_bundle({path: b"not permitted"}, source_revision="a" * 40)


if __name__ == "__main__":
    unittest.main()
