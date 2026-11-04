import unittest
from pathlib import Path
from fastapi import HTTPException
from r3_steward_authority_api import build_steward_authority_router

ROOT = Path(__file__).resolve().parents[1]

class StewardAuthorityRegressionTests(unittest.TestCase):

    def setUp(self):
        router = build_steward_authority_router(ROOT)
        self.routes = {
            route.path: route.endpoint
            for route in router.routes
        }

    def test_capabilities_are_discoverable(self):
        result = self.routes[
            "/api/v1/steward-authority/capabilities"
        ]()
        self.assertEqual(
            result["contract"], "r3.steward-authority.v1"
        )

    def test_mutations_are_not_implicitly_authorized(self):
        result = self.routes[
            "/api/v1/steward-authority/capabilities"
        ]()
        self.assertFalse(result["mutations_enabled"])
        for operation in (
            "request", "approve", "deny", "renew", "revoke"
        ):
            self.assertEqual(
                result["operations"][operation], "not enabled"
            )

    def test_unbound_inventory_fails_closed(self):
        for name in ("inventory", "pending", "active", "history"):
            with self.subTest(name=name):
                with self.assertRaises(HTTPException) as context:
                    self.routes[
                        "/api/v1/steward-authority/" + name
                    ]()
                self.assertEqual(
                    context.exception.status_code, 503
                )

    def test_no_grant_mutation_routes_exposed(self):
        for path in self.routes:
            self.assertNotIn(
                path.rsplit("/", 1)[-1],
                ("approve", "deny", "renew", "revoke", "request")
            )









    def test_application_routes_registered(self):
        import asyncio
        from r3_app import app

        async def request(path):
            messages = []
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
                await asyncio.sleep(0)
                return {"type": "http.disconnect"}

            async def send(message):
                messages.append(message)

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
                "headers": [(b"host", b"localhost")],
                "server": ("localhost", 80),
                "client": ("127.0.0.1", 12345),
            }

            await app(scope, receive, send)

            status = next(
                m["status"] for m in messages
                if m["type"] == "http.response.start"
            )
            return status

        for path in (
            "/api/v1/steward-authority/capabilities",
            "/api/v1/steward-authority/inventory",
            "/api/v1/steward-authority/pending",
            "/api/v1/steward-authority/active",
            "/api/v1/steward-authority/history",
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    asyncio.run(request(path)),
                    401,
                    "Unauthenticated authority access must be denied"
                )


    def test_authority_assets_registered(self):
        from r3_app import app
        paths = {
            getattr(route, "path", None)
            for route in app.routes
        }
        self.assertIn(
            "/web/steward-authority.js", paths
        )
        self.assertIn(
            "/web/steward-authority.css", paths
        )

    def test_authority_ui_is_linked(self):
        page = (ROOT / "web/index.html").read_text()
        self.assertIn("steward-authority.js", page)
        self.assertIn("steward-authority.css", page)

    def test_assets_exist(self):
        self.assertTrue(
            (ROOT / "web/steward-authority.js").is_file()
        )
        self.assertTrue(
            (ROOT / "web/steward-authority.css").is_file()
        )

if __name__ == "__main__":
    unittest.main()
