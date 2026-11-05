import unittest
from unittest.mock import patch

from fastapi import HTTPException

import r3_app


class RecoveryIdentityIntegrationTests(unittest.TestCase):
    def test_recovery_forwards_exact_native_principal_without_deriving_name(self):
        request = object()
        inbox = type("Inbox", (), {})()
        observed = {}

        def resume(event_id, **kwargs):
            observed["event_id"] = event_id
            observed.update(kwargs)
            return 91

        inbox.resume_blocked = resume
        identity = {"principal": "human:steward:account-opaque-73", "role": "steward"}
        with patch("r3_native_auth_api.authenticated_identity", return_value=identity) as auth:
            successor = r3_app.resume_blocked_activity(
                request, inbox, object(), 14, "runtime dependency restored"
            )

        self.assertEqual(successor, 91)
        self.assertEqual(observed["principal"], identity["principal"])
        self.assertEqual(observed["event_id"], 14)
        self.assertEqual(observed["resolution_evidence"], "runtime dependency restored")
        auth.assert_called_once_with(request, mutation=True)

    def test_recovery_rejects_non_steward_native_session(self):
        with patch("r3_native_auth_api.authenticated_identity", return_value={
            "principal": "human:resident:opaque-2", "role": "resident",
        }):
            with self.assertRaises(HTTPException) as raised:
                r3_app.resolve_recovery_caller(object())
        self.assertEqual(raised.exception.status_code, 403)

    def test_recovery_rejects_missing_native_principal(self):
        with patch("r3_native_auth_api.authenticated_identity", return_value={
            "role": "steward",
        }):
            with self.assertRaises(HTTPException) as raised:
                r3_app.resolve_recovery_caller(object())
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
