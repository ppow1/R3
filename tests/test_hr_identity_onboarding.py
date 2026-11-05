# R3 CONTROLLED SOURCE
# File: tests/test_hr_identity_onboarding.py
# Component: HR-IDENTITY-ONBOARDING-REGRESSION-TESTS
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: Codex
# Purpose: Verify secure HR principal assignment, revision handling, uniqueness and disclosure
# Execution Model: Python unittest using isolated SQLite fixtures and real HR modules
# Observability: Assertions over persisted records, authorized operations and directory views
# Dependencies: runtime.hr_records; runtime.hr_store; runtime.hr_capability; runtime.hr_stdio
# Authority: Tests only; does not access production HR or authority databases
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Add onboarding and directory security regressions
# Supersedes: None
# Contracts: confidential extensions.authority_principal; authenticated hr.write
# Tests: /home/admin1/R3/.venv/bin/python -m unittest discover -s tests -p test_hr_identity_onboarding.py
# History/Predecessor: New file

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime.hr_capability import HRCapability, VerifiedPrincipal
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_stdio import dispatch
from runtime.hr_store import HRStore


class HRIdentityOnboardingTests(unittest.TestCase):
    ESTABLISHED = {
        "r3:grace": "resident:Grace",
        "r3:gm": "resident:GM",
        "r3:chloe": "resident:Chloe",
        "r3:marie": "resident:Marie",
    }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "hr.sqlite3"
        self.store = HRStore(self.database)
        self.addCleanup(self.store.close)
        self.calls = []

        def authorize(principal, action, scope):
            self.calls.append((principal.principal_id, action, scope))
            return action in {"hr.read", "hr.write"}

        self.authorize = authorize
        self.capability = HRCapability(self.store, authorize)
        self.helen = VerifiedPrincipal("resident:Helen", "helen")
        self.resident = VerifiedPrincipal("resident:directory-reader", "resident")

    @staticmethod
    def request(record, *, expected_revision=None):
        payload = {
            "resident_id": record.resident_id,
            "display_name": record.display_name,
            "office": record.office,
            "status": record.status,
            "schema_version": record.schema_version,
            "fields": {
                key: {"value": item.value, "classification": item.classification}
                for key, item in record.fields.items()
            },
            "extensions": {
                key: {"value": item.value, "classification": item.classification}
                for key, item in record.extensions.items()
            },
            "history_refs": list(record.history_refs),
        }
        request = {"operation": "hr.save", "record": payload}
        if expected_revision is not None:
            request["expected_revision"] = expected_revision
        return request

    def test_onboarding_saves_explicit_confidential_association_without_source_change(self):
        record = ResidentHRRecord(
            resident_id="r3:new-resident",
            display_name="New Resident",
            office="Research",
            fields={"role": HRField("Researcher", "public")},
            extensions={"authority_principal": HRField(
                "resident:reviewer-7", "confidential"
            )},
        )

        response = dispatch(self.capability, self.helen, self.request(record))

        self.assertEqual(response, {"ok": True, "revision": 1})
        saved, revision = self.store.get("r3:new-resident")
        self.assertEqual(revision, 1)
        self.assertEqual(
            saved.extensions["authority_principal"],
            HRField("resident:reviewer-7", "confidential"),
        )
        self.assertEqual(self.calls, [("resident:Helen", "hr.write", "r3:new-resident")])

    def test_existing_associations_are_preserved(self):
        for resident_id, principal in self.ESTABLISHED.items():
            initial = ResidentHRRecord(
                resident_id=resident_id,
                display_name=resident_id,
                office="Existing office",
                fields={"classification": HRField("protected", "confidential")},
                history_refs=["hr-history-1"],
            )
            self.assertEqual(self.store.put(initial), 1)
            result = dispatch(self.capability, self.helen, {
                "operation": "hr.associate_principal",
                "resident_id": resident_id,
                "authority_principal": principal,
                "expected_revision": 1,
            })
            self.assertEqual(result, {"ok": True, "revision": 2})
            saved, revision = self.store.get(resident_id)
            self.assertEqual(revision, 2)
            self.assertEqual(saved.extensions["authority_principal"].value, principal)
            self.assertEqual(saved.fields["classification"].value, "protected")
            self.assertEqual(saved.history_refs, ["hr-history-1"])

    def test_existing_link_cannot_be_rotated_and_repeat_is_idempotent(self):
        record = ResidentHRRecord(
            "r3:grace", "Grace", "Operations",
            extensions={"authority_principal": HRField("resident:Grace", "confidential")},
        )
        self.store.put(record)

        same = dispatch(self.capability, self.helen, {
            "operation": "hr.associate_principal", "resident_id": "r3:grace",
            "authority_principal": "resident:Grace", "expected_revision": 1,
        })
        self.assertEqual(same, {"ok": True, "revision": 1})
        different = dispatch(self.capability, self.helen, {
            "operation": "hr.associate_principal", "resident_id": "r3:grace",
            "authority_principal": "resident:grace", "expected_revision": 1,
        })
        self.assertEqual(different, {"ok": False, "error": "invalid_request"})
        self.assertEqual(self.store.get("r3:grace")[0].extensions[
            "authority_principal"].value, "resident:Grace")

    def test_generic_record_updates_preserve_link_and_reject_replacement(self):
        linked = ResidentHRRecord(
            "r3:grace", "Grace", "Operations",
            extensions={"authority_principal": HRField("resident:Grace", "confidential")},
        )
        self.store.put(linked)

        without_link = ResidentHRRecord(
            "r3:grace", "Grace Updated", "Operations",
            fields={"role": HRField("Director", "public")},
        )
        saved_revision = self.capability.save(
            self.helen, without_link, expected_revision=1
        )
        self.assertEqual(saved_revision, 2)
        saved, _ = self.store.get("r3:grace")
        self.assertEqual(saved.display_name, "Grace Updated")
        self.assertEqual(
            saved.extensions["authority_principal"].value, "resident:Grace"
        )

        replacement = ResidentHRRecord(
            "r3:grace", "Grace Updated", "Operations",
            extensions={"authority_principal": HRField("resident:grace", "confidential")},
        )
        with self.assertRaisesRegex(ValueError, "cannot be changed"):
            self.capability.save(self.helen, replacement, expected_revision=2)
        self.assertEqual(self.store.get("r3:grace")[1], 2)

    def test_invalid_or_public_association_is_rejected(self):
        for principal, classification in (
            ("resident: bad", "confidential"),
            ("resident:bad principal", "confidential"),
            ("resident:Chloe", "public"),
            ("resident:Chloe", "request"),
        ):
            with self.subTest(principal=principal, classification=classification):
                with self.assertRaises(ValueError):
                    ResidentHRRecord(
                        "r3:invalid", "Invalid", "Office",
                        extensions={"authority_principal": HRField(principal, classification)},
                    )

        with self.assertRaises(ValueError):
            ResidentHRRecord(
                "r3:invalid", "Invalid", "Office",
                fields={"authority_principal": HRField("resident:Chloe", "public")},
            )

    def test_duplicate_association_is_rejected_atomically(self):
        first = ResidentHRRecord(
            "r3:first", "First", "Office",
            extensions={"authority_principal": HRField("resident:Chloe", "confidential")},
        )
        second = ResidentHRRecord(
            "r3:second", "Second", "Office",
            extensions={"authority_principal": HRField("resident:Chloe", "confidential")},
        )
        self.assertEqual(self.store.put(first), 1)
        response = dispatch(self.capability, self.helen, self.request(second))
        self.assertEqual(response, {"ok": False, "error": "invalid_request"})
        self.assertIsNone(self.store.get("r3:second"))

    def test_hr_save_rejects_invalid_or_public_association(self):
        for principal, classification in (
            ("not-a-principal", "confidential"),
            ("resident:public", "public"),
        ):
            request = {
                "operation": "hr.save",
                "record": {
                    "resident_id": "r3:invalid",
                    "display_name": "Invalid",
                    "office": "Office",
                    "extensions": {
                        "authority_principal": {
                            "value": principal,
                            "classification": classification,
                        }
                    },
                },
            }
            self.assertEqual(
                dispatch(self.capability, self.helen, request),
                {"ok": False, "error": "invalid_request"},
            )
        self.assertIsNone(self.store.get("r3:invalid"))

    def test_resident_directory_and_public_view_suppress_association(self):
        record = ResidentHRRecord(
            "r3:chloe", "Chloe", "Chief Architect",
            fields={"role": HRField("Architect", "public")},
            extensions={"authority_principal": HRField("resident:Chloe", "confidential")},
        )
        self.store.put(record)

        response = dispatch(self.capability, self.resident, {
            "operation": "hr.directory",
        })
        directory = response["result"]

        self.assertTrue(response["ok"])
        self.assertNotIn("authority_principal", directory[0]["fields"])
        self.assertEqual(directory[0]["display_name"], "Chloe")
        for role in ("resident", "steward", "helen"):
            with self.subTest(role=role):
                self.assertNotIn(
                    "authority_principal", record.view(role=role)["fields"]
                )

    def test_association_requires_authorized_revision_checked_write(self):
        record = ResidentHRRecord("r3:new", "New", "Office")
        self.store.put(record)
        denied = HRCapability(self.store, lambda principal, action, scope: False)
        with self.assertRaises(PermissionError):
            denied.associate_authority_principal(
                self.helen, "r3:new", "resident:new", expected_revision=1
            )
        with self.assertRaisesRegex(ValueError, "revision conflict"):
            self.capability.associate_authority_principal(
                self.helen, "r3:new", "resident:new", expected_revision=2
            )
        self.assertEqual(self.store.get("r3:new")[1], 1)

    def test_trusted_server_can_resolve_link_without_directory_disclosure(self):
        record = ResidentHRRecord(
            "r3:grace", "Grace", "Operations",
            extensions={"authority_principal": HRField("resident:Grace", "confidential")},
        )
        self.store.put(record)

        self.assertEqual(
            self.capability.resolve_authority_principal(self.helen, "r3:grace"),
            "resident:Grace",
        )
        denied = HRCapability(self.store, lambda principal, action, scope: False)
        with self.assertRaises(PermissionError):
            denied.resolve_authority_principal(self.helen, "r3:grace")

        response = dispatch(self.capability, self.resident, {"operation": "hr.directory"})
        self.assertNotIn(
            "authority_principal", response["result"][0]["fields"]
        )

    def test_trusted_resolver_rejects_missing_and_legacy_duplicate_links(self):
        self.store.put(ResidentHRRecord("r3:missing", "Missing", "Office"))
        with self.assertRaisesRegex(ValueError, "association missing"):
            self.capability.resolve_authority_principal(self.helen, "r3:missing")

        self.store.put(ResidentHRRecord(
            "r3:first", "First", "Office",
            extensions={"authority_principal": HRField("resident:Grace", "confidential")},
        ))
        self.store.put(ResidentHRRecord(
            "r3:second", "Second", "Office",
            extensions={"authority_principal": HRField("resident:Chloe", "confidential")},
        ))
        with sqlite3.connect(self.database) as db:
            payload = json.loads(db.execute(
                "SELECT payload FROM hr_records WHERE resident_id='r3:second'"
            ).fetchone()[0])
            payload["extensions"]["authority_principal"]["value"] = "resident:Grace"
            db.execute(
                "UPDATE hr_records SET payload=? WHERE resident_id='r3:second'",
                (json.dumps(payload),),
            )

        with self.assertRaisesRegex(ValueError, "duplicate authority principal"):
            self.capability.resolve_authority_principal(self.helen, "r3:first")


if __name__ == "__main__":
    unittest.main(verbosity=2)
