import tempfile
import unittest
from pathlib import Path

from runtime.capabilities import AuthorityUnavailable
from runtime.capability_authority import initialize_empty_schema
from runtime.tool_server import build_router


class ToolServerAuthorityStartupTests(unittest.TestCase):
    def test_valid_authority_database_is_connected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authority_db = root / "authority.db"
            initialize_empty_schema(authority_db)
            router = build_router(
                audit_db=root / "tools.db",
                authority_db=authority_db,
            )
            try:
                self.assertIsNotNone(router.authority)
                self.assertIsNotNone(router.identity)
            finally:
                router.db.close()

    def test_missing_authority_database_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(AuthorityUnavailable):
                build_router(
                    audit_db=root / "tools.db",
                    authority_db=root / "missing.db",
                )

    def test_legacy_read_only_startup_remains_available(self):
        with tempfile.TemporaryDirectory() as directory:
            router = build_router(
                audit_db=Path(directory) / "tools.db",
            )
            try:
                self.assertIsNone(router.authority)
                self.assertEqual(
                    [item["tool"] for item in router.discover()],
                    ["r3.status"],
                )
            finally:
                router.db.close()


if __name__ == "__main__":
    unittest.main()
