"""Exact-scope, revisioned, idempotent HR identity association tests."""
from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.capabilities import CapabilityDenied


@dataclass
class FakeField:
    value: object
    classification: str = "confidential"


@dataclass
class FakeRecord:
    resident_id: str
    extensions: dict = field(default_factory=dict)


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

    def put(self, record, *, expected_revision=None):
        current = self.rows[record.resident_id]
        if current[1] != expected_revision:
            raise ValueError("revision conflict")
        revision = current[1] + 1
        self.rows[record.resident_id] = (record, revision)
        return revision


class FakeGateway:
    def __init__(self):
        self.capabilities = {}

    def register(self, capability):
        self.capabilities[capability.name] = capability


class HRIdentityAssociationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        records = types.ModuleType("runtime.hr_records")
        records.HRField = FakeField
        store = types.ModuleType("runtime.hr_store")
        store.HRStore = FakeHRStore
        governed = types.ModuleType("runtime.governed_tools")

        @dataclass
        class GovernedCapability:
            name: str
            resource_id: str
            action: str
            operation: str
            description: str
            parameters: dict
            executor: object

        governed.GovernedCapability = GovernedCapability
        with patch.dict(sys.modules, {
                "runtime.hr_records": records,
                "runtime.hr_store": store,
                "runtime.governed_tools": governed}):
            cls.module = importlib.import_module("runtime.hr_identity_association")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        database = Path(self.temp.name) / "hr.sqlite"
        database.touch()
        FakeHRStore.rows = {"r3:grace": (FakeRecord("r3:grace"), 1)}
        self.gateway = FakeGateway()
        self.database = database
        self.module.register_hr_identity_association(self.gateway, str(database))
        self.capability = self.gateway.capabilities["hr.associate_principal"]
        self.r3 = "resident:Grace"
        self.authority = "resident:grace"
        self.scope = self.module.association_scope("r3:grace", self.r3, self.authority)
        self.context = SimpleNamespace(principal=self.r3, resource_id="r3:hr",
            action="hr.associate_principal", operation="write", scope_ref=self.scope)
        self.params = {"scope_ref": self.scope, "resident_id": "r3:grace",
            "r3_principal": self.r3, "authority_principal": self.authority,
            "expected_revision": 1}

    def test_associates_both_identities_once_and_preserves_revisioned_hr_record(self):
        result = self.capability.executor(self.params, self.context)
        self.assertEqual(result["revision"], 2)
        self.assertTrue(result["persisted"])
        record, revision = FakeHRStore.rows["r3:grace"]
        self.assertEqual(revision, 2)
        self.assertEqual(record.extensions["r3_principal"].value, self.r3)
        self.assertEqual(record.extensions["authority_principal"].value, self.authority)
        self.assertEqual(self.module.resolve_authority_principal(self.database, self.r3),
                         self.authority)

    def test_same_association_is_idempotent_and_does_not_increment_revision(self):
        first = self.capability.executor(self.params, self.context)
        replay = self.capability.executor(self.params, self.context)
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(replay["revision"], 2)
        self.assertEqual(FakeHRStore.rows["r3:grace"][1], 2)

    def test_wrong_scope_or_principal_is_rejected(self):
        wrong_scope = dict(self.params, scope_ref="r3:hr:identity-association/r3:grace")
        with self.assertRaises(CapabilityDenied):
            self.capability.executor(wrong_scope, self.context)
        wrong_context = SimpleNamespace(**{**vars(self.context), "principal": "resident:other"})
        with self.assertRaises(CapabilityDenied):
            self.capability.executor(self.params, wrong_context)
        self.assertEqual(FakeHRStore.rows["r3:grace"][1], 1)

    def test_identity_resolution_requires_one_explicit_mapping(self):
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, self.r3)
        self.capability.executor(self.params, self.context)
        FakeHRStore.rows["r3:other"] = (FakeRecord("r3:other", extensions={
            "r3_principal": FakeField(self.r3),
            "authority_principal": FakeField("resident:other")}), 1)
        with self.assertRaises(CapabilityDenied):
            self.module.resolve_authority_principal(self.database, self.r3)


if __name__ == "__main__":
    unittest.main()
