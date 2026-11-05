
import os
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
        self.authority = object()

    def issue_resident_credential(self, **kwargs):
        self.issued.append(kwargs)
        return {
            "status": "ISSUED",
            "credential_id": "test-credential-id",
            "credential": "test-secret-never-returned",
        }

    def revoke_resident_credential(self, **kwargs):
        self.revoked.append(kwargs)
        return {"status": "REVOKED"}


class FakeIdentity:
    def __init__(self, authority):
        self.authority = authority

    def authenticate(self, credential):
        if credential != "test-secret-never-returned":
            raise ValueError("Unexpected test credential")
        return "resident:Chloe"


class CredentialProvisionTests(unittest.TestCase):
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
            for resident_id in module.HR_PRINCIPAL_MAP:
                db.execute(
                    "INSERT INTO hr_records VALUES (?, 1, '{}')",
                    (resident_id,),
                )

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

    def test_unknown_resident_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            module._provision_resident_credential(
                self.service, self.request, self.body("resident:Unknown")
            )
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(self.service.issued, [])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
