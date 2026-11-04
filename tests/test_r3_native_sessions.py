# R3 CONTROLLED SOURCE
# File: tests/test_r3_native_sessions.py
# Component: R3-NATIVE-STEWARD-AUTH-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-04 UTC | ChatGPT GPT-6
# Purpose: Permanent R3 human session security regressions.
# Authority: Steward; Website Development issue #16.
# Supersedes: None

import tempfile
import unittest
from pathlib import Path

from r3_native_sessions import (
    AuthenticationDenied,
    NativeSessions,
    initialize_empty_schema,
)


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "sessions.sqlite"
        initialize_empty_schema(self.db)
        self.auth = NativeSessions(self.db)
        self.auth.bootstrap_steward(
            "steward@example.test",
            "A-long-test-password-123",
        )

    def test_empty_store_has_no_implicit_login(self):
        other = Path(self.temp.name) / "empty.sqlite"
        initialize_empty_schema(other)
        with self.assertRaises(AuthenticationDenied):
            NativeSessions(other).login(
                "steward@example.test", "A-long-test-password-123"
            )

    def test_valid_login(self):
        session = self.auth.login(
            "steward@example.test", "A-long-test-password-123"
        )
        principal = self.auth.authenticate(session["token"])
        self.assertEqual(principal["role"], "steward")
        self.assertTrue(principal["principal"].startswith("human:steward:"))

    def test_wrong_password_denied(self):
        with self.assertRaises(AuthenticationDenied):
            self.auth.login("steward@example.test", "incorrect")

    def test_unknown_account_denied(self):
        with self.assertRaises(AuthenticationDenied):
            self.auth.login("unknown@example.test", "incorrect")

    def test_bootstrap_cannot_repeat(self):
        with self.assertRaises(AuthenticationDenied):
            self.auth.bootstrap_steward(
                "another@example.test", "Another-long-password-123"
            )

    def test_missing_session_denied(self):
        with self.assertRaises(AuthenticationDenied):
            self.auth.authenticate("")

    def test_forged_session_denied(self):
        with self.assertRaises(AuthenticationDenied):
            self.auth.authenticate("forged-session-token")

    def test_csrf_required_for_mutation(self):
        session = self.auth.login(
            "steward@example.test", "A-long-test-password-123"
        )
        with self.assertRaises(AuthenticationDenied):
            self.auth.authenticate(session["token"], mutation=True)

    def test_invalid_csrf_denied(self):
        session = self.auth.login(
            "steward@example.test", "A-long-test-password-123"
        )
        with self.assertRaises(AuthenticationDenied):
            self.auth.authenticate(
                session["token"], csrf="forged", mutation=True
            )

    def test_valid_csrf(self):
        session = self.auth.login(
            "steward@example.test", "A-long-test-password-123"
        )
        result = self.auth.authenticate(
            session["token"], csrf=session["csrf"], mutation=True
        )
        self.assertEqual(result["role"], "steward")

    def test_logout_revokes_session(self):
        session = self.auth.login(
            "steward@example.test", "A-long-test-password-123"
        )
        self.auth.logout(session["token"])
        with self.assertRaises(AuthenticationDenied):
            self.auth.authenticate(session["token"])

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            self.auth.bootstrap_steward("x@example.test", "short")


if __name__ == "__main__":
    unittest.main()
