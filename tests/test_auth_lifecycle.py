
import asyncio
import json
import unittest
from http.cookies import SimpleCookie
from unittest.mock import patch

import r3_app


CONFIG = {
    "allowed_origins": ["https://riverview.ionoge.com"],
    "website_auth_login_url": "http://127.0.0.1:8767/api/v1/auth/login",
    "website_auth_session_url": "http://127.0.0.1:8767/api/v1/auth/session",
    "request_timeout_seconds": 5,
    "required_role": "steward",
}


async def asgi_request(method, path, cookies="", body=b"", headers=None):
    incoming = [
        (b"host", b"riverview.ionoge.com"),
        (b"origin", b"https://riverview.ionoge.com"),
    ]

    if cookies:
        incoming.append((b"cookie", cookies.encode()))

    if headers:
        incoming.extend(
            (k.lower().encode(), v.encode())
            for k, v in headers.items()
        )

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "server": ("riverview.ionoge.com", 443),
        "client": ("127.0.0.1", 12345),
        "root_path": "",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": incoming,
    }

    sent = []
    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }
        await asyncio.Event().wait()

    async def send(message):
        sent.append(message)

    await r3_app.app(scope, receive, send)

    starts = [
        message for message in sent
        if message["type"] == "http.response.start"
    ]

    assert len(starts) == 1, (
        f"Expected one response start, got {len(starts)}"
    )

    start = starts[0]

    response_headers = [
        (key.decode("latin-1").lower(), value.decode("latin-1"))
        for key, value in start["headers"]
    ]

    response_body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )

    return start["status"], response_headers, response_body


def header_values(headers, name):
    return [
        value for key, value in headers
        if key == name.lower()
    ]


class FakeR2:
    def __init__(self):
        self.active = False
        self.revoked = False
        self.logout_calls = 0

    def request(
        self, url, request, method="GET",
        body=None, content_type=None, timeout=15
    ):
        cookie = request.headers.get("cookie", "")
        has_session = (
            "rv_account_session=valid-session" in cookie
        )

        if url.endswith("/login") and method == "POST":
            credentials = json.loads(body)

            if credentials != {
                "email": "steward@example.test",
                "password": "test-only-password",
            }:
                return 401, b'{"error":"invalid_credentials"}', []

            self.active = True
            self.revoked = False

            return 200, b'{"status":"authenticated"}', [
                "rv_account_session=valid-session; "
                "Path=/api/v1; Secure; HttpOnly; SameSite=Lax",
                "rv_account_csrf=valid-csrf; "
                "Path=/; Secure; SameSite=Strict",
            ]

        if url.endswith("/session") and method == "GET":
            if self.active and has_session and not self.revoked:
                payload = {
                    "status": "authenticated",
                    "identity": {
                        "email": "steward@example.test",
                        "roles": ["steward"],
                    },
                }
                return 200, json.dumps(payload).encode(), []

            return 401, b'{"status":"unauthenticated"}', []

        if url.endswith("/session") and method == "DELETE":
            csrf = request.headers.get("x-riverview-csrf")

            if (
                self.active
                and has_session
                and not self.revoked
                and csrf == "valid-csrf"
            ):
                self.active = False
                self.revoked = True
                self.logout_calls += 1

                return 200, b'{"status":"logged_out"}', [
                    "rv_account_session=; Max-Age=0; "
                    "Path=/api/v1; Secure; HttpOnly; SameSite=Lax",
                    "rv_account_csrf=; Max-Age=0; "
                    "Path=/; Secure; SameSite=Strict",
                ]

            return 403, b'{"error":"csrf_or_session_invalid"}', []

        raise AssertionError(
            f"Unexpected R2 request: {method} {url}"
        )


class AuthenticationLifecycleTests(unittest.TestCase):

    def test_full_login_access_refresh_logout_revocation(self):
        fake = FakeR2()

        with (
            patch(
                "r3_chat_api._portal_request",
                side_effect=fake.request
            ),
            patch(
                "r3_chat_api.load_config",
                return_value=CONFIG
            ),
            patch.object(
                r3_app,
                "_auth_config",
                return_value=CONFIG
            ),
        ):

            def call(
                method, path, cookies="",
                body=b"", headers=None
            ):
                return asyncio.run(
                    asgi_request(
                        method, path, cookies, body, headers
                    )
                )

            # Anonymous access must be denied.
            status, headers, _ = call("GET", "/")
            self.assertEqual(status, 303)
            self.assertIn(
                "/login",
                header_values(headers, "location")
            )

            status, _, _ = call(
                "GET", "/api/v1/institution/runtime"
            )
            self.assertEqual(status, 401)

            # Sign in through R3.
            payload = json.dumps({
                "email": "steward@example.test",
                "password": "test-only-password",
            }).encode()

            status, headers, _ = call(
                "POST",
                "/api/v1/chat/login",
                body=payload,
                headers={
                    "content-type": "application/json"
                },
            )

            self.assertEqual(status, 200)

            set_cookies = header_values(
                headers, "set-cookie"
            )
            self.assertEqual(len(set_cookies), 2)

            jar = SimpleCookie()

            for value in set_cookies:
                jar.load(value)

            self.assertIn(
                "rv_account_session", jar
            )
            self.assertIn(
                "rv_account_csrf", jar
            )

            self.assertEqual(
                jar["rv_account_session"]["path"], "/"
            )
            self.assertEqual(
                jar["rv_account_csrf"]["path"], "/"
            )

            self.assertTrue(
                jar["rv_account_session"]["httponly"]
            )
            self.assertTrue(
                jar["rv_account_session"]["secure"]
            )

            browser_cookies = (
                "rv_account_session=valid-session; "
                "rv_account_csrf=valid-csrf"
            )

            # Authenticated access persists.
            for _ in range(2):
                status, _, _ = call(
                    "GET", "/", browser_cookies
                )
                self.assertEqual(status, 200)

            status, _, body = call(
                "GET",
                "/api/v1/chat/session",
                browser_cookies
            )

            self.assertEqual(status, 200)
            self.assertEqual(
                json.loads(body)["identity"]["email"],
                "steward@example.test",
            )

            # CSRF protection must reject missing token.
            status, _, _ = call(
                "DELETE",
                "/api/v1/chat/session",
                browser_cookies
            )

            self.assertEqual(status, 403)
            self.assertFalse(fake.revoked)

            # Valid logout must revoke the session.
            status, headers, _ = call(
                "DELETE",
                "/api/v1/chat/session",
                browser_cookies,
                headers={
                    "x-riverview-csrf": "valid-csrf"
                },
            )

            self.assertEqual(status, 200)
            self.assertEqual(fake.logout_calls, 1)

            cleared = header_values(
                headers, "set-cookie"
            )

            self.assertEqual(len(cleared), 2)
            self.assertTrue(
                all("Max-Age=0" in value for value in cleared)
            )
            self.assertTrue(
                all("Path=/" in value for value in cleared)
            )

            # Replaying a revoked cookie must fail.
            status, _, _ = call(
                "GET", "/", browser_cookies
            )
            self.assertEqual(status, 303)

            status, _, _ = call(
                "GET",
                "/api/v1/institution/runtime",
                browser_cookies
            )
            self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
