
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
    """Native R3 authentication lifecycle, independent of retired R2."""

    def test_full_login_access_refresh_logout_revocation(self):
        import tempfile
        from pathlib import Path
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from r3_native_sessions import (
            NativeSessions,
            initialize_empty_schema,
        )
        from r3_native_auth_api import build_native_auth_router

        origin = "https://riverview.ionoge.com"

        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "native.sqlite"
            initialize_empty_schema(db)
            store = NativeSessions(db)
            store.bootstrap_steward(
                "steward@example.test",
                "Strong-test-password-123",
            )

            app = FastAPI()
            app.include_router(
                build_native_auth_router(
                    store_factory=lambda: store,
                    allowed_origins=(origin,),
                )
            )

            with TestClient(app, base_url=origin) as client:
                anonymous = client.get(
                    "/api/v1/native-auth/session"
                )
                self.assertEqual(anonymous.status_code, 401)

                login = client.post(
                    "/api/v1/native-auth/login",
                    headers={"Origin": origin},
                    json={
                        "email": "steward@example.test",
                        "password": "Strong-test-password-123",
                    },
                )
                self.assertEqual(login.status_code, 200, login.text)

                session = client.get(
                    "/api/v1/native-auth/session"
                )
                self.assertEqual(session.status_code, 200)
                self.assertEqual(
                    session.json()["identity"]["roles"],
                    ["steward"],
                )

                csrf = client.cookies.get("r3_steward_csrf")
                self.assertTrue(csrf)

                no_csrf = client.delete(
                    "/api/v1/native-auth/session",
                    headers={"Origin": origin},
                )
                self.assertEqual(no_csrf.status_code, 401)

                logout = client.delete(
                    "/api/v1/native-auth/session",
                    headers={
                        "Origin": origin,
                        "X-Riverview-CSRF": csrf,
                    },
                )
                self.assertEqual(logout.status_code, 200)

                revoked = client.get(
                    "/api/v1/native-auth/session"
                )
                self.assertEqual(revoked.status_code, 401)


if __name__ == "__main__":
    unittest.main()
