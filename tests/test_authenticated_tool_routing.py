import sqlite3
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from runtime.capabilities import Capability
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.resident_identity import PREFIX, digest_secret
from runtime.tool_server import ToolRouter


class AuthenticatedToolRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        authority_db = root / "authority.db"
        initialize_empty_schema(authority_db)
        self.authority = R3Authority(authority_db)
        self.credential_id = uuid.uuid4().hex
        self.token = PREFIX + "." + self.credential_id + "." + "A" * 43
        self.calls = []
        capability = Capability(
            name="r3.test.write",
            action="test.write",
            description="Test write",
            parameters={"type": "object"},
            executor=lambda params: self.calls.append(params) or {"done": True},
            read_only=False,
            resource_ref="resource:test",
        )
        self.router = ToolRouter(
            root / "tools.db",
            authority=self.authority,
            capabilities=(capability,),
        )
        with sqlite3.connect(authority_db) as db:
            db.execute(
                """INSERT INTO resident_credentials
                   (credential_id,principal,secret_hash,created_at,
                    expires_at,revoked_at,issued_by,idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (self.credential_id, "resident:grace",
                 digest_secret(self.credential_id, self.token),
                 time.time(), time.time() + 3600, None,
                 "human:steward:test", "test-credential"),
            )

    def payload(self):
        return {
            "tool": "r3.test.write",
            "params": {"scope_ref": "scope:test"},
            "correlation_id": "call-test-1",
        }

    def grant(self):
        with self.authority._connect() as db:
            db.execute(
                """INSERT INTO capability_grants
                   (grant_id,principal,resource_ref,action,operation,
                    scope_ref,active,approved_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                ("r3-grant:test", "resident:grace", "resource:test",
                 "test.write", "write", "scope:test", 1,
                 "human:steward:test"),
            )

    def test_unauthenticated_write_denied(self):
        code, _ = self.router.invoke(self.payload())
        self.assertEqual(code, 403)
        self.assertFalse(self.calls)

    def test_authenticated_without_grant_denied(self):
        code, _ = self.router.invoke(
            self.payload(), credential=self.token)
        self.assertEqual(code, 403)
        self.assertFalse(self.calls)

    def test_authenticated_with_exact_grant(self):
        self.grant()
        code, response = self.router.invoke(
            self.payload(), credential=self.token)
        self.assertEqual(code, 200)
        self.assertTrue(response["ok"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(
            response["result"]["authorization"]["grant_id"],
            "r3-grant:test",
        )

    def test_revocation_denies_next_call(self):
        self.grant()
        with self.authority._connect() as db:
            db.execute(
                "UPDATE capability_grants SET active=0 WHERE grant_id=?",
                ("r3-grant:test",),
            )
        code, _ = self.router.invoke(
            self.payload(), credential=self.token)
        self.assertEqual(code, 403)
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
