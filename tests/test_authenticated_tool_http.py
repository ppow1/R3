import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError

from runtime.native_tools import NativeTools
from runtime.tool_server import handler_for
from tests.test_authenticated_tool_routing import AuthenticatedToolRoutingTests


class AuthenticatedToolHTTPTests(AuthenticatedToolRoutingTests):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_for(self.router)
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def client(self, credential):
        return NativeTools(
            "http://127.0.0.1:" + str(self.server.server_port),
            timeout=5,
            allowed_tools=("r3.test.write",),
            credential=credential,
        )

    def descriptor(self, client):
        matches = [
            d for d in client.discover()
            if d["tool"] == "r3.test.write"
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_http_exact_grant_executes_and_audits(self):
        self.grant()
        client = self.client(self.token)
        descriptor = self.descriptor(client)
        result = json.loads(client.invoke(
            descriptor,
            {"scope_ref": "scope:test"},
            correlation_id="http-test-1",
        ))
        self.assertEqual(result["authorization"]["grant_id"], "r3-grant:test")
        self.assertEqual(result["correlation_id"], "http-test-1")
        self.assertEqual(len(self.calls), 1)

        with self.authority._connect() as db:
            audit = db.execute(
                """SELECT outcome FROM capability_audit
                   WHERE correlation_id=? ORDER BY id""",
                ("http-test-1",),
            ).fetchall()
        self.assertIn(("AUTHORIZED",), audit)
        self.assertIn(("COMPLETED",), audit)

    def test_http_missing_credential_denied(self):
        client = self.client(None)
        descriptor = self.descriptor(client)
        with self.assertRaises(PermissionError):
            client.invoke(
                descriptor,
                {"scope_ref": "scope:test"},
                correlation_id="http-test-2",
            )
        self.assertFalse(self.calls)

    def test_http_missing_grant_denied(self):
        client = self.client(self.token)
        descriptor = self.descriptor(client)
        with self.assertRaises(HTTPError) as caught:
            client.invoke(
                descriptor,
                {"scope_ref": "scope:test"},
                correlation_id="http-test-3",
            )
        self.assertEqual(caught.exception.code, 403)
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
