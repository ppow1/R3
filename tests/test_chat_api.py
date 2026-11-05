import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from r3_chat_api import _origin, _principal, _runtime, load_config


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key.lower(), default)


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = Headers({k.lower(): v for k, v in (headers or {}).items()})


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.token = self.root / "conversation.token"
        self.token.write_text("server-secret\n", encoding="utf-8")
        self.config = {
            "conversation_api_base_url": "http://127.0.0.1:8770",
            "conversation_api_credential_file": str(self.token),
            "website_auth_session_url": "http://127.0.0.1:8767/api/v1/auth/session",
            "website_auth_login_url": "http://127.0.0.1:8767/api/v1/auth/session",
            "website_auth_reset_url": "http://127.0.0.1:8767/api/v1/auth/password-reset",
            "resident_id": "Grace", "required_role": "steward",
            "request_timeout_seconds": 5, "allowed_origins": ["https://192.168.1.155"],
        }
        self.config_file = self.root / "chat.json"
        self.config_file.write_text(json.dumps(self.config), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_config_rejects_non_loopback_runtime(self):
        bad = dict(self.config, conversation_api_base_url="http://0.0.0.0:8770")
        self.config_file.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(HTTPException):
            load_config(self.config_file)

    def test_principal_uses_native_session_not_browser_header(self):
        from r3_native_sessions import NativeSessions, initialize_empty_schema

        db = self.root / "native-auth.sqlite"
        initialize_empty_schema(db)
        store = NativeSessions(db)
        store.bootstrap_steward(
            "steward@example.test",
            "Strong-test-password-123",
        )
        session = store.login(
            "steward@example.test",
            "Strong-test-password-123",
        )

        request = FakeRequest({
            "x-r3-principal": "attacker@example.com",
        })
        request.cookies = {
            "r3_steward_session": session["token"],
        }

        with patch("r3_chat_api.native_store", return_value=store):
            principal = _principal(request, self.config)

        self.assertEqual(principal.principal_id, "steward@example.test")
        self.assertEqual(principal.role, "steward")

    def test_spoofed_browser_header_without_native_session_denied(self):
        request = FakeRequest({
            "x-r3-principal": "human:steward:spoofed",
        })
        request.cookies = {}

        with self.assertRaises(HTTPException) as context:
            _principal(request, self.config)

        self.assertEqual(context.exception.status_code, 401)

    def test_runtime_uses_server_credential_and_trusted_principal(self):
        class Reply:
            status = 202
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, _limit): return b'{"status":"QUEUED"}'
        seen = {}
        def open_request(req, timeout):
            seen.update(url=req.full_url, headers={k.lower(): v for k, v in req.header_items()},
                        body=req.data, timeout=timeout)
            return Reply()
        with patch("r3_chat_api.urllib.request.urlopen", side_effect=open_request):
            result = _runtime(self.config, "steward@example.com", "/v1/conversations/123/messages", "POST",
                              {"content": "Hi", "client_message_id": "stable-key"})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(seen["headers"]["authorization"], "Bearer server-secret")
        self.assertEqual(seen["headers"]["x-r3-principal"], "steward@example.com")
        self.assertEqual(json.loads(seen["body"])["client_message_id"], "stable-key")

    def test_mutation_origin_must_match_configured_website(self):
        with self.assertRaises(HTTPException):
            _origin(FakeRequest({"origin": "https://evil.example"}), self.config, required=True)
        with self.assertRaises(HTTPException):
            _origin(FakeRequest(), self.config, required=True)


if __name__ == "__main__":
    unittest.main()
