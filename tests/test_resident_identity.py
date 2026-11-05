import sqlite3
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.capabilities import CapabilityDenied
from runtime.resident_identity import R3ResidentIdentity, PREFIX, digest_secret


class ResidentIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "authority.db"
        initialize_empty_schema(self.path)
        self.identity = R3ResidentIdentity(R3Authority(self.path))
        self.credential_id = uuid.uuid4().hex
        self.token = PREFIX + "." + self.credential_id + "." + ("A" * 43)
        self.expires_at = time.time() + 3600

        with sqlite3.connect(self.path) as db:
            db.execute(
                """INSERT INTO resident_credentials
                   (credential_id,principal,secret_hash,created_at,
                    expires_at,revoked_at,issued_by,idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    self.credential_id,
                    "resident:grace",
                    digest_secret(self.credential_id, self.token),
                    time.time(),
                    self.expires_at,
                    None,
                    "human:steward:test",
                    "identity-test-1",
                ),
            )

    def test_valid_credential_authenticates(self):
        self.assertEqual(
            self.identity.authenticate(self.token),
            "resident:grace",
        )

    def test_wrong_secret_denied(self):
        wrong = PREFIX + "." + self.credential_id + "." + ("B" * 43)
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(wrong)

    def test_revoked_credential_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE resident_credentials SET revoked_at=? WHERE credential_id=?",
                (time.time(), self.credential_id),
            )
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(self.token)

    def test_expired_credential_denied(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE resident_credentials SET expires_at=? WHERE credential_id=?",
                (time.time() - 1, self.credential_id),
            )
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(self.token)

    def test_missing_credential_denied(self):
        unknown = PREFIX + "." + uuid.uuid4().hex + "." + ("A" * 43)
        with self.assertRaises(CapabilityDenied):
            self.identity.authenticate(unknown)


if __name__ == "__main__":
    unittest.main()
