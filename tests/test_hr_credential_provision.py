# R3 CONTROLLED SOURCE
# File: tests/test_hr_credential_provision.py
# Component: STEWARD-AUTHORITY-REGRESSION-TESTS
# File Revision: 1.1.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Verify HR-linked resident credential provisioning and safety boundaries
# Execution Model: Python unittest against temporary HR and credential stores
# Observability: Deterministic assertions; no real credentials or grants
# Dependencies: r3_steward_authority_api; FastAPI; SQLite
# Authority: Test-only fixtures; no production state access
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-001 | Codex | Cover dynamic HR principal resolution
# Supersedes: Git predecessor at d49a4bb35ae9bbfc75f79a3bad7adb8ee9abcac2
# Contracts: confidential HR extensions.authority_principal
# Tests: python3 -m unittest discover -s tests -p test_hr_credential_provision.py
# History/Predecessor: Git commit d49a4bb35ae9bbfc75f79a3bad7adb8ee9abcac2

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
import r3_steward_authority_api as module


class FakeService:
    def __init__(self):
        self.issued = []
        self.revoked = []
        self.grants = []
        self.authority = SimpleNamespace()

    def issue_resident_credential(self, **kwargs):
        self.issued.append(kwargs)
        self.authority.principal = kwargs["resident_principal"]
        return {
            "status": "ISSUED",
            "credential_id": "test-credential-id",
            "credential": "test-secret-never-returned",
        }

    def revoke_resident_credential(self, **kwargs):
        self.revoked.append(kwargs)
        return {"status": "REVOKED"}

    def request(self, **kwargs):
        self.grants.append(("request", kwargs))

    def decide(self, **kwargs):
        self.grants.append(("decide", kwargs))

    def delegate(self, **kwargs):
        self.grants.append(("delegate", kwargs))


class FakeIdentity:
    def __init__(self, authority):
        self.authority = authority

    def authenticate(self, credential):
        if credential != "test-secret-never-returned":
            raise ValueError("Unexpected test credential")
        return self.authority.principal


class CredentialProvisionTests(unittest.TestCase):
    EXISTING_IDENTITIES = {
        "r3:gm": "resident:GM",
        "r3:grace": "resident:Grace",
        "r3:chloe": "resident:Chloe",
        "r3:marie": "resident:Marie",
    }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        root = Path(self.temp.name)
        self.credentials = root / "credentials"
        self.credentials.mkdir(mode=0o700)

        self.hr = root / "residents.sqlite3"
        with sqlite3.connect(self.hr) as db:
            db.execute(
                "CREATE TABLE hr_records "
                "(resident_id TEXT PRIMARY KEY, revision INTEGER, payload TEXT)"
            )
            for resident_id, principal in self.EXISTING_IDENTITIES.items():
                self.insert_record(db, resident_id, principal)

        self.service = FakeService()
        self.request = object()

        self.patches = [
            patch.object(module, "HR_RESIDENT_DATABASE", self.hr),
            patch.object(module, "RESIDENT_CREDENTIAL_DIRECTORY", self.credentials),
            patch.object(module, "R3ResidentIdentity", FakeIdentity),
        ]

        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def body(self, principal):
        return SimpleNamespace(
            resident_principal=principal,
            reason="R3 HR controlled test",
            idempotency_key="test-" + principal,
        )

    @staticmethod
    def payload(resident_id, principal=None, *, classification="confidential",
                in_fields=False):
        container = "fields" if in_fields else "extensions"
        data = {
            "resident_id": resident_id,
            "display_name": (
                "Protected test name" if resident_id == "r3:gm" else "Test resident"
            ),
            "office": "Test office",
            "status": "onboarding",
            "schema_version": 1,
            "fields": {},
            "extensions": {},
            "history_refs": [],
        }
        if principal is not None:
            data[container][module.HR_PRINCIPAL_FIELD] = {
                "value": principal,
                "classification": classification,
            }
        return json.dumps(data)

    def insert_record(self, db, resident_id, principal=None, **kwargs):
        db.execute(
            "INSERT INTO hr_records VALUES (?, 1, ?)",
            (resident_id, self.payload(resident_id, principal, **kwargs)),
        )

    def update_record(self, resident_id, payload):
        with sqlite3.connect(self.hr) as db:
            db.execute("UPDATE hr_records SET payload=? WHERE resident_id=?",
                       (payload, resident_id))

    def test_missing_association_is_rejected(self):
        with sqlite3.connect(self.hr) as db:
            self.insert_record(db, "r3:unlinked")
        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Unlinked")
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.service.issued, [])

    def test_unmatched_principal_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Unknown")
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.service.issued, [])

    def test_existing_principals_are_resolved_from_hr_associations(self):
        for resident_id, principal in self.EXISTING_IDENTITIES.items():
            self.assertEqual(
                module._validate_hr_resident_principal(principal), resident_id
            )

    def test_dynamic_onboarding_association_is_resolved(self):
        with sqlite3.connect(self.hr) as db:
            self.insert_record(db, "r3:new-resident", "resident:independent-reviewer")

        result = module._provision_resident_credential(
            self.service, self.request, self.body("resident:independent-reviewer")
        )

        self.assertEqual(result["hr_resident_id"], "r3:new-resident")
        self.assertEqual(result["principal"], "resident:independent-reviewer")
        self.assertTrue(
            (self.credentials / "independent-reviewer.credential").is_file()
        )

    def test_invalid_association_is_rejected(self):
        self.update_record(
            "r3:chloe",
            self.payload("r3:chloe", "not-a-resident-principal"),
        )
        with self.assertRaises(HTTPException) as caught:
            module._validate_hr_resident_principal("resident:Chloe")
        self.assertEqual(caught.exception.status_code, 409)

    def test_public_association_is_rejected_to_protect_identity(self):
        self.update_record(
            "r3:chloe",
            self.payload("r3:chloe", "resident:Chloe", classification="public"),
        )
        with self.assertRaises(HTTPException) as caught:
            module._validate_hr_resident_principal("resident:Chloe")
        self.assertEqual(caught.exception.status_code, 409)

    def test_duplicate_association_is_rejected(self):
        with sqlite3.connect(self.hr) as db:
            self.insert_record(db, "r3:duplicate", "resident:Chloe")
        with self.assertRaises(HTTPException) as caught:
            module._validate_hr_resident_principal("resident:Chloe")
        self.assertEqual(caught.exception.status_code, 409)

    def test_conflicting_associations_on_one_record_are_rejected(self):
        payload = json.loads(self.payload("r3:chloe", "resident:Chloe"))
        payload["fields"][module.HR_PRINCIPAL_FIELD] = {
            "value": "resident:other",
            "classification": "confidential",
        }
        self.update_record("r3:chloe", json.dumps(payload))
        with self.assertRaises(HTTPException) as caught:
            module._validate_hr_resident_principal("resident:Chloe")
        self.assertEqual(caught.exception.status_code, 409)

    def test_invalid_requested_principal_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            module._validate_hr_resident_principal("resident: bad")
        self.assertEqual(caught.exception.status_code, 422)

    def test_grace_is_preserved(self):
        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Grace")
            )
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.service.issued, [])

    def test_missing_hr_record_is_rejected(self):
        with sqlite3.connect(self.hr) as db:
            db.execute(
                "DELETE FROM hr_records WHERE resident_id='r3:chloe'"
            )

        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Chloe")
            )

        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.service.issued, [])

    def test_successful_provisioning_protects_secret(self):
        result = module._provision_resident_credential(
            self.service, self.request, self.body("resident:Chloe")
        )

        credential_file = self.credentials / "Chloe.credential"

        self.assertTrue(credential_file.is_file())
        self.assertEqual(credential_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            credential_file.read_text().strip(),
            "test-secret-never-returned",
        )

        self.assertEqual(result["principal"], "resident:Chloe")
        self.assertEqual(result["hr_resident_id"], "r3:chloe")
        self.assertEqual(result["expires_at"], 2556143999.0)
        self.assertFalse(result["secret_returned"])
        self.assertNotIn("credential", result)
        self.assertEqual(len(self.service.issued), 1)
        self.assertEqual(self.service.revoked, [])
        self.assertEqual(self.service.grants, [])

    def test_duplicate_file_does_not_issue(self):
        path = self.credentials / "Chloe.credential"
        path.write_text("existing-credential")

        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Chloe")
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.service.issued, [])
        self.assertEqual(path.read_text(), "existing-credential")

    def test_storage_failure_revokes_issued_credential(self):
        with patch.object(module.os, "open", side_effect=OSError("test storage failure")):
            with self.assertRaises(HTTPException) as caught:
                module._provision_resident_credential(
                    self.service, self.request, self.body("resident:Chloe")
                )

        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(len(self.service.issued), 1)
        self.assertEqual(len(self.service.revoked), 1)

    def test_repeat_provisioning_does_not_overwrite_secret(self):
        module._provision_resident_credential(
            self.service, self.request, self.body("resident:Chloe")
        )

        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Chloe")
            )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(len(self.service.issued), 1)

    def test_endpoint_requires_steward_authorization_before_provisioning(self):
        router = module.build_steward_authority_router(Path(self.temp.name))
        endpoint = next(
            route.endpoint for route in router.routes
            if route.path.endswith("/resident-credentials/provision")
        )
        request = SimpleNamespace(
            headers={"origin": "https://r3.test", "host": "r3.test"}
        )
        with patch.object(module, "authenticated_identity", return_value={
            "role": "resident", "principal": "resident:Chloe"
        }):
            with self.assertRaises(HTTPException) as caught:
                endpoint(request, module.ResidentCredentialProvision(
                    resident_principal="resident:Chloe", reason="test",
                    idempotency_key="authorization-test",
                ))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.service.issued, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
