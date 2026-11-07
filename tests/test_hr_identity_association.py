# R3 CONTROLLED SOURCE
# File: tests/test_hr_identity_association.py
# Component: R3-HR-IDENTITY-CROSSWALK-REGRESSION
# File Revision: 1.1.0
# Created: 2026-11-06 UTC (exact time not independently established)
# Created By: Grace Autonomy engineering
# Purpose: Verify exact read-only identity resolution from HR without a local HR writer.
# Execution Model: unittest with an isolated fake HRStore.
# Observability: Resolution outcome and fail-closed ambiguity checks.
# Dependencies: runtime.hr_identity_association.
# Authority: HR owns associations; R3 only reads and consumes them.
# Changed: 2026-11-06T23:58:00Z | GRACE-AUTHORITY-ARCH-002 | Remove tests for resident-facing association operation and assert resolver-only boundary.
# Supersedes: Previous tests for the R3-local HR association writer.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md.
# Tests: This module.
# History/Predecessor: Current branch predecessor `cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf`.
from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from runtime.capabilities import CapabilityDenied


@dataclass
class FakeField:
    value: object
    classification: str = "confidential"


@dataclass
class FakeRecord:
    resident_id: str
    extensions: dict


class FakeHRStore:
    rows = {}

    def __init__(self, _database):
        pass

    def close(self):
        pass

    def resident_ids(self):
        return sorted(self.rows)

    def get(self, resident_id):
        return self.rows.get(resident_id)


class HRIdentityAssociationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        store = types.ModuleType("runtime.hr_store")
        store.HRStore = FakeHRStore
        with patch.dict(sys.modules, {"runtime.hr_store": store}):
            cls.module = importlib.import_module("runtime.hr_identity_association")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "hr.sqlite"
        self.database.touch()
        self.r3_principal = "resident:Grace"
        self.authority_principal = "resident:grace"
        FakeHRStore.rows = {"r3:grace": (FakeRecord("r3:grace", {
            "r3_principal": FakeField(self.r3_principal),
            "authority_principal": FakeField(self.authority_principal)}), 1)}

    def test_resolves_only_exact_explicit_hr_association(self):
        self.assertEqual(self.module.resolve_authority_principal(
            self.database, self.r3_principal), self.authority_principal)
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, "resident:grace")

    def test_missing_mapping_fails_closed(self):
        FakeHRStore.rows = {"r3:grace": (FakeRecord("r3:grace", {}), 1)}
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, self.r3_principal)

    def test_duplicate_or_malformed_mapping_fails_closed(self):
        FakeHRStore.rows["r3:other"] = (FakeRecord("r3:other", {
            "r3_principal": FakeField(self.r3_principal),
            "authority_principal": FakeField("resident:other")}), 1)
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, self.r3_principal)

        FakeHRStore.rows = {"r3:grace": (FakeRecord("r3:grace", {
            "r3_principal": FakeField(self.r3_principal),
            "authority_principal": FakeField("not-a-resident")}), 1)}
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, self.r3_principal)

    def test_r3_crosswalk_module_has_no_hr_mutation_operation(self):
        self.assertFalse(hasattr(self.module, "register_hr_identity_association"))


if __name__ == "__main__":
    unittest.main()
