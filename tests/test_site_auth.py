"""Permanent regression tests for R3 website authentication."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import asyncio

from r3_app import app


class SiteAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.client = self

    def get(self, path, headers=None):
        async def run():
            messages = []
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "root_path": "",
                "headers": [
                    (k.lower().encode(), v.encode())
                    for k, v in (headers or {}).items()
                ],
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
            }
            received = False

            async def receive():
                nonlocal received
                if not received:
                    received = True
                    return {
                        "type": "http.request",
                        "body": b"",
                        "more_body": False,
                    }
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

            await app(scope, receive, send)
            return messages

        messages = asyncio.run(run())
        start = next(
            m for m in messages
            if m["type"] == "http.response.start"
        )
        body = b"".join(
            m.get("body", b"")
            for m in messages
            if m["type"] == "http.response.body"
        )

        class Result:
            pass

        result = Result()
        result.status_code = start["status"]
        result.headers = {
            k.decode().lower(): v.decode()
            for k, v in start["headers"]
        }
        result.text = body.decode("utf-8", errors="replace")
        return result

    def test_anonymous_root_redirects_to_login(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login")

    def test_anonymous_infrastructure_is_denied(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get("/api/v1/institution/runtime")
        self.assertEqual(response.status_code, 401)

    def test_anonymous_settings_are_denied(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get("/api/v1/settings/manifest")
        self.assertEqual(response.status_code, 401)

    def test_anonymous_snapshot_is_denied(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get("/api/v1/snapshot")
        self.assertEqual(response.status_code, 401)

    def test_anonymous_assets_are_denied(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get("/web/chat-client.js")
        self.assertEqual(response.status_code, 401)

    def test_forged_identity_header_does_not_bypass_auth(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get(
                "/api/v1/institution/runtime",
                headers={"X-R3-Principal": "w@wjs1.com"}
            )
        self.assertEqual(response.status_code, 401)

    def test_login_page_is_public(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn("R3 Steward Sign In", response.text)

    def test_health_is_public(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)

    def test_r3_prefix_redirect(self):
        with patch("r3_app._principal",
                   side_effect=HTTPException(401, "No session")):
            response = self.client.get(
                "/", headers={"X-Forwarded-Prefix": "/r3"}
            )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/r3/login")


if __name__ == "__main__":
    unittest.main()

# R3-SITE-LOGOUT-003
class AuthenticationCookieRegressionTests(unittest.TestCase):

    def test_both_authentication_cookies_are_preserved(self):
        from r3_chat_api import _browser_cookies

        cookies = _browser_cookies([
            "rv_account_session=abc; Path=/api/v1; Secure; HttpOnly; SameSite=Lax",
            "rv_account_csrf=xyz; Path=/; Secure; SameSite=Strict",
        ])

        self.assertEqual(len(cookies), 2)
        self.assertTrue(cookies[0].startswith("rv_account_session="))
        self.assertTrue(cookies[1].startswith("rv_account_csrf="))

        for cookie in cookies:
            self.assertIn("Path=/", cookie)
            self.assertNotIn("Path=/api/v1", cookie)
            self.assertIn("Secure", cookie)

        self.assertIn("HttpOnly", cookies[0])
        self.assertIn("SameSite=Strict", cookies[1])

    def test_unexpected_authentication_cookie_is_rejected(self):
        from fastapi import HTTPException
        from r3_chat_api import _browser_cookies

        with self.assertRaises(HTTPException):
            _browser_cookies(["unexpected=value; Path=/"])

    def test_logout_request_forwards_cookie_and_csrf(self):
        from unittest.mock import patch
        from starlette.requests import Request
        from r3_chat_api import _portal_request

        captured = {}

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, limit):
                return b'{"status":"logged_out"}'

            class Headers:
                def get_all(self, name, default=None):
                    if name.lower() == "set-cookie":
                        return [
                            "rv_account_session=; Max-Age=0; Path=/api/v1; Secure; HttpOnly",
                            "rv_account_csrf=; Max-Age=0; Path=/; Secure",
                        ]
                    return default

            headers = Headers()

        def fake_urlopen(req, timeout):
            captured["method"] = req.get_method()
            captured["cookie"] = req.get_header("Cookie")
            captured["csrf"] = req.get_header("X-riverview-csrf")
            return FakeResponse()

        scope = {
            "type": "http",
            "method": "DELETE",
            "scheme": "https",
            "path": "/api/v1/chat/session",
            "headers": [
                (b"cookie", b"rv_account_session=abc; rv_account_csrf=xyz"),
                (b"x-riverview-csrf", b"xyz"),
            ],
        }

        request = Request(scope)

        with patch("r3_chat_api.urllib.request.urlopen", side_effect=fake_urlopen):
            status, body, cookies = _portal_request(
                "http://127.0.0.1:8767/api/v1/auth/session",
                request,
                method="DELETE",
            )

        self.assertEqual(status, 200)
        self.assertEqual(captured["method"], "DELETE")
        self.assertIn("rv_account_session=abc", captured["cookie"])
        self.assertEqual(captured["csrf"], "xyz")
        self.assertEqual(len(cookies), 2)

    def test_profile_logout_uses_riverview_csrf_cookie(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] /
                  "web/index.html").read_text(encoding="utf-8")
        logout = source.split("// R3-SITE-LOGOUT-003", 1)[1]
        self.assertIn("value.startsWith('rv_account_csrf=')", logout)
        self.assertNotIn("value.startsWith('r3_steward_csrf=')", logout)
        self.assertIn("X-Riverview-CSRF", logout)
        self.assertIn("method: 'DELETE'", logout)

    def test_profile_menu_has_site_wide_logout(self):
        from pathlib import Path

        page = (Path(__file__).resolve().parents[1]
                / "web/index.html").read_text(encoding="utf-8")

        self.assertIn('id="profile-signout"', page)
        self.assertIn("X-Riverview-CSRF", page)
        self.assertIn("credentials: 'same-origin'", page)
        self.assertIn("method: 'DELETE'", page)
        self.assertIn("location.replace(base + '/login')", page)

    def test_logout_is_not_a_public_unauthenticated_route(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1]
                  / "r3_app.py").read_text(encoding="utf-8")

        self.assertIn('path == "/api/v1/chat/session"', source)
        self.assertIn('request.method == "DELETE"', source)

