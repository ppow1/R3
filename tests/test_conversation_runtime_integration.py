import asyncio
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from runtime.conversations import ConversationStore, create_server
from runtime.resident_inference import Inbox, ResidentInference


class Endpoint:
    def __init__(self, content="Grace response", failure=False):
        self.content = content
        self.failure = failure
        self.calls = []

    def complete(self, messages, definitions):
        self.calls.append(messages)
        if self.failure:
            raise RuntimeError("Inference unavailable")
        return {"choices": [{"message": {
            "role": "assistant", "content": self.content
        }}]}


class ConversationRuntimeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.database = root / "conversation.sqlite"
        self.token = "integration-test-token-" + "x" * 40
        token_file = root / "token"
        token_file.write_text(self.token)
        token_file.chmod(0o600)
        self.db = sqlite3.connect(self.database)
        self.store = ConversationStore(self.db)
        self.inbox = Inbox(self.db)
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        import socket
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            test_port = sock.getsockname()[1]
        self.server = create_server(
            self.database, token_file, {"Grace"}, {"Grace": []},
            port=test_port
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.db.close)

    def request(self, method, path, body=None, authorized=True, principal="steward:test"):
        conn = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        headers = {}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
            headers["X-R3-Principal"] = principal
        if body is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(body)
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        status = response.status
        data = json.loads(response.read())
        conn.close()
        return status, data

    def create(self):
        status, result = self.request(
            "POST", "/v1/residents/Grace/conversations",
            {"title": "Integration"}
        )
        self.assertEqual(status, 201)
        return result["conversation"]["conversation_id"]

    def send(self, conversation_id, content="Hello Grace"):
        return self.request(
            "POST", f"/v1/conversations/{conversation_id}/messages",
            {"content": content, "client_message_id": "message-1"}
        )

    def test_01_authenticated_creation_and_persistent_retrieval(self):
        cid = self.create()
        status, result = self.request(
            "GET", "/v1/residents/Grace/conversations"
        )
        self.assertEqual(status, 200)
        self.assertIn(cid, [
            c["conversation_id"] for c in result["conversations"]
        ])
        self.db.close()
        self.db = sqlite3.connect(self.database)
        self.store = ConversationStore(self.db)
        self.inbox = Inbox(self.db)
        status, result = self.request(
            "GET", "/v1/residents/Grace/conversations"
        )
        self.assertEqual(status, 200)
        self.assertEqual(result["conversations"][0]["conversation_id"], cid)

    def test_02_submission_routes_to_grace_and_persists_reply(self):
        cid = self.create()
        status, submitted = self.send(cid)
        self.assertEqual(status, 202)
        self.assertEqual(submitted["delivery_status"], "QUEUED")
        endpoint = Endpoint("Grace integration verified")
        worker = ResidentInference(
            self.inbox, endpoint, system_prompt="You are Grace",
            conversation_store=self.store
        )
        asyncio.run(worker("Grace"))
        self.assertEqual(len(endpoint.calls), 1)
        self.assertEqual(endpoint.calls[0][1]["content"], "Hello Grace")
        status, result = self.request(
            "GET", f"/v1/conversations/{cid}/messages"
        )
        self.assertEqual(status, 200)
        messages = result["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["delivery_status"], "DELIVERED")
        self.assertEqual(messages[1]["sender_type"], "RESIDENT")
        self.assertEqual(messages[1]["content"], "Grace integration verified")
        status, reopened = self.request(
            "GET", f"/v1/conversations/{cid}/messages"
        )
        self.assertEqual(status, 200)
        self.assertEqual(reopened["messages"], messages)

    def test_03_unauthorized_and_cross_principal_access_rejected(self):
        status, result = self.request(
            "GET", "/v1/residents/Grace/conversations", authorized=False
        )
        self.assertEqual(status, 401)
        cid = self.create()
        status, result = self.request(
            "GET", f"/v1/conversations/{cid}/messages",
            principal="steward:other"
        )
        self.assertEqual(status, 404)
        status, result = self.request(
            "POST", f"/v1/conversations/{cid}/messages",
            {"content": "Unauthorized", "client_message_id": "other"},
            principal="steward:other"
        )
        self.assertEqual(status, 404)

    def test_04_inference_failure_and_empty_reply_never_succeed(self):
        for endpoint in (Endpoint(failure=True), Endpoint(content="")):
            with self.subTest(endpoint=endpoint.__dict__):
                cid = self.create()
                status, submitted = self.send(cid)
                self.assertEqual(status, 202)
                worker = ResidentInference(
                    self.inbox, endpoint, system_prompt="You are Grace",
                    conversation_store=self.store
                )
                with self.assertRaises(RuntimeError):
                    asyncio.run(worker("Grace"))
                status, result = self.request(
                    "GET", f"/v1/conversations/{cid}/messages"
                )
                self.assertEqual(status, 200)
                self.assertEqual(len(result["messages"]), 1)
                self.assertEqual(
                    result["messages"][0]["delivery_status"], "FAILED"
                )
                self.assertTrue(result["messages"][0]["error_code"])


if __name__ == "__main__":
    unittest.main()
