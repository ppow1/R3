"""Regression coverage for canonical resident principals versus executor modules."""
from __future__ import annotations

import unittest

from r3a_runtime.grace_module import validate_resident_profile
from r3a_runtime.resident_identity import (
    resident_module_id, resident_principal_id, validate_resident_identity_pair,
)


class ResidentIdentityKindTests(unittest.TestCase):
    def test_valid_principal_and_executable_module_are_distinct_types(self):
        principal, module = validate_resident_identity_pair("resident:grace", "resident.grace")
        self.assertEqual("resident:grace", principal)
        self.assertEqual("resident.grace", module)
        self.assertEqual("resident:grace", resident_principal_id(principal))
        self.assertEqual("resident.grace", resident_module_id(module))

    def test_wrong_kind_ids_are_rejected_by_boundary_parsers(self):
        with self.assertRaisesRegex(ValueError, "principal ID"):
            resident_principal_id("resident.grace")
        with self.assertRaisesRegex(ValueError, "module ID"):
            resident_module_id("resident:grace")
        with self.assertRaisesRegex(ValueError, "resident principal"):
            validate_resident_identity_pair("resident.grace", "resident.grace")

    def test_resident_profile_requires_canonical_directory_principal(self):
        profile = {
            "contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
            "resident_id": "resident:grace", "display_name": "Grace", "office_id": "office:grace",
            "office_role": "Director of Operations", "directory_evidence": {
                "source_id": "directory", "snapshot_sha256": "a" * 64,
                "observed_at": "2026-11-11T00:00:00Z"},
            "model_route_id": "route.grace", "config_revision": "config-1",
        }
        self.assertEqual(profile, validate_resident_profile(
            profile, resident_id="resident:grace", config_revision="config-1"))
        invalid = {**profile, "resident_id": "resident.grace"}
        with self.assertRaisesRegex(ValueError, "canonical principal"):
            validate_resident_profile(invalid, resident_id="resident.grace", config_revision="config-1")


if __name__ == "__main__":
    unittest.main()
