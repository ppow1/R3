import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteAssetAndChatSSOTests(unittest.TestCase):

    def test_background_uses_subpath_safe_url(self):
        html = (ROOT / "web/index.html").read_text()
        self.assertIn(
            "url('api/v1/visual/background')", html
        )
        self.assertIn(
            "background.src='api/v1/visual/background';",
            html
        )

    def test_chat_does_not_render_second_login(self):
        js = (ROOT / "web/chat-client.js").read_text()
        self.assertNotIn(
            "Sign in to R3 Chat", js
        )
        self.assertNotIn(
            "r3-chat-login", js
        )
        self.assertIn(
            "const session = await json('/session');", js
        )
        self.assertIn(
            "credentials: 'same-origin'", js
        )

    def test_chat_get_requests_use_session_without_origin_requirement(self):
        import inspect
        import r3_chat_api

        source = inspect.getsource(r3_chat_api.build_chat_router)

        for route in (
            "/api/v1/chat/capabilities",
            "/api/v1/chat/conversations",
            "/api/v1/chat/conversations/{conversation_id}/messages",
        ):
            self.assertIn(route, source)

        self.assertIn(
            "_origin(request, cfg); principal = _principal(request, cfg)",
            source
        )

    def test_disallowed_origin_still_rejected(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from r3_chat_api import _origin

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"origin", b"https://untrusted.invalid")],
        }
        request = Request(scope)

        with self.assertRaises(HTTPException) as result:
            _origin(
                request,
                {"allowed_origins": ["https://riverview.ionoge.com"]},
            )

        self.assertEqual(result.exception.status_code, 403)

    def test_missing_origin_allowed_for_safe_get(self):
        from starlette.requests import Request
        from r3_chat_api import _origin

        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
        })

        _origin(
            request,
            {"allowed_origins": ["https://riverview.ionoge.com"]},
        )


if __name__ == "__main__":
    unittest.main()
