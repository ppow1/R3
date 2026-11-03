"""Permanent contracts for durable resident conversations."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from runtime.conversations import ConversationError, ConversationStore, create_server
from runtime.resident_inference import Inbox, ResidentInference


class ConversationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "institution.db"
        self.db = sqlite3.connect(str(self.path), timeout=10)
        self.store = ConversationStore(self.db)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_owner_scoping_and_message_order(self):
        conversation = self.store.create_conversation("steward-1", "Grace", "Operations")
        self.assertEqual(1, len(self.store.list_conversations("steward-1", "Grace")))
        self.assertEqual([], self.store.list_conversations("steward-2", "Grace"))
        with self.assertRaises(ConversationError):
            self.store.messages("steward-2", conversation["conversation_id"], after=0, limit=20)

        first = self.store.send_message(
            "steward-1", conversation["conversation_id"], "First", "client-1")
        self.store.complete_event(first["event_id"], "Grace", "Acknowledged")
        result = self.store.messages(
            "steward-1", conversation["conversation_id"], after=0, limit=20)
        self.assertEqual([1, 2], [item["sequence"] for item in result["messages"]])
        self.assertEqual(["STEWARD", "RESIDENT"], [item["sender_type"] for item in result["messages"]])
        self.assertEqual(["DELIVERED", "DELIVERED"], [item["delivery_status"] for item in result["messages"]])
        self.assertTrue(all(isinstance(item["created_at"], float) for item in result["messages"]))

    def test_send_is_atomic_idempotent_and_persistent_after_reopen(self):
        conversation = self.store.create_conversation("steward-1", "Grace", "")
        conversation_id = conversation["conversation_id"]
        sent = self.store.send_message("steward-1", conversation_id, "Status?", "retry-1")
        duplicate = self.store.send_message("steward-1", conversation_id, "Status?", "retry-1")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(sent["event_id"], duplicate["event_id"])
        with self.assertRaises(ConversationError):
            self.store.send_message("steward-1", conversation_id, "Different", "retry-1")
        self.store.complete_event(sent["event_id"], "Grace", "Healthy")
        self.db.close()

        reopened = sqlite3.connect(str(self.path), timeout=10)
        try:
            store = ConversationStore(reopened)
            result = store.messages("steward-1", conversation_id, after=0, limit=20)
            self.assertEqual(["Status?", "Healthy"], [m["content"] for m in result["messages"]])
        finally:
            reopened.close()

    def test_failed_delivery_is_durable_and_has_no_false_reply(self):
        conversation = self.store.create_conversation("steward-1", "Grace", "")
        sent = self.store.send_message("steward-1", conversation["conversation_id"], "Hello", "retry-2")
        self.store.fail_event(sent["event_id"], "InferenceUnavailable")
        result = self.store.messages("steward-1", conversation["conversation_id"], after=0, limit=20)
        self.assertEqual(1, len(result["messages"]))
        self.assertEqual("FAILED", result["messages"][0]["delivery_status"])
        self.assertEqual("InferenceUnavailable", result["messages"][0]["error_code"])


class ConversationInferenceIntegrationTests(unittest.TestCase):
    def test_scheduler_inference_persists_resident_reply_for_reload(self):
        import asyncio

        class FakeEndpoint:
            def __init__(self):
                self.calls = []

            def complete(self, messages, tools=None):
                self.calls.append(list(messages))
                return {
                    "model": "mock-resident",
                    "choices": [{"message": {"role": "assistant", "content": f"Reply {len(self.calls)}"}}],
                }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "institution.db"
            db = sqlite3.connect(str(path), timeout=10)
            try:
                inbox = Inbox(db)
                store = ConversationStore(db)
                conversation = store.create_conversation("steward-1", "Grace", "")
                sent = store.send_message(
                    "steward-1", conversation["conversation_id"], "Hello Grace", "chat-1")
                endpoint = FakeEndpoint()
                handler = ResidentInference(
                    inbox, endpoint, system_prompt="Grace system prompt",
                    conversation_store=store)
                asyncio.run(handler("Grace"))
                self.assertEqual(
                    ["system", "user"], [m["role"] for m in endpoint.calls[0]])
                result = store.messages(
                    "steward-1", conversation["conversation_id"], after=0, limit=20)
                self.assertEqual(
                    ["Hello Grace", "Reply 1"],
                    [message["content"] for message in result["messages"]])
                self.assertEqual("DELIVERED", result["messages"][0]["delivery_status"])
                self.assertEqual("RESIDENT", result["messages"][1]["sender_type"])

                store.send_message(
                    "steward-1", conversation["conversation_id"], "Follow up", "chat-2")
                asyncio.run(handler("Grace"))
                self.assertEqual(
                    ["system", "user", "assistant", "user"],
                    [m["role"] for m in endpoint.calls[1]])
                self.assertEqual("Reply 1", endpoint.calls[1][2]["content"])
                db.close()

                reopened = sqlite3.connect(str(path), timeout=10)
                try:
                    reloaded = ConversationStore(reopened).messages(
                        "steward-1", conversation["conversation_id"], after=0, limit=20)
                    self.assertEqual([1, 2, 3, 4], [m["sequence"] for m in reloaded["messages"]])
                    self.assertEqual(
                        ["Hello Grace", "Reply 1", "Follow up", "Reply 2"],
                        [m["content"] for m in reloaded["messages"]])
                finally:
                    reopened.close()
            finally:
                try:
                    db.close()
                except sqlite3.Error:
                    pass


class ConversationHttpTests(unittest.TestCase):
    def test_authenticated_create_send_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "institution.db"
            token_file = root / "conversation.token"
            token_file.write_text("test-secret-with-at-least-thirty-two-characters", encoding="utf-8")
            os.chmod(token_file, 0o600)
            probe = socket.socket()
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
            probe.close()
            server = create_server(database, token_file, {"Grace"}, {"Grace": ["r3.status"]}, port=port)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{port}"
            headers = {
                "Authorization": "Bearer test-secret-with-at-least-thirty-two-characters",
                "X-R3-Principal": "steward-1",
                "Content-Type": "application/json",
            }

            def request(method, path, value=None, use_auth=True):
                body = json.dumps(value).encode("utf-8") if value is not None else None
                request_headers = headers if use_auth else {"Content-Type": "application/json"}
                req = urllib.request.Request(base + path, data=body, headers=request_headers, method=method)
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.status, json.load(response)

            try:
                status, created = request("POST", "/v1/residents/Grace/conversations", {"title": "Test"})
                self.assertEqual(201, status)
                conversation_id = created["conversation"]["conversation_id"]
                status, sent = request(
                    "POST", f"/v1/conversations/{conversation_id}/messages",
                    {"content": "Hello Grace", "client_message_id": "browser-1"})
                self.assertEqual(202, status)
                self.assertEqual("QUEUED", sent["delivery_status"])

                maximum_content = "😀" * 100_000
                status, maximum_sent = request(
                    "POST", f"/v1/conversations/{conversation_id}/messages",
                    {"content": maximum_content, "client_message_id": "browser-max"})
                self.assertEqual(202, status)
                self.assertEqual(2, maximum_sent["sequence"])
                over_limit_content = "😀" * 100_001
                with self.assertRaises(urllib.error.HTTPError) as over_limit:
                    request(
                        "POST", f"/v1/conversations/{conversation_id}/messages",
                        {"content": over_limit_content, "client_message_id": "browser-over"})
                self.assertEqual(400, over_limit.exception.code)
                status, loaded = request("GET", f"/v1/conversations/{conversation_id}/messages?after=0&limit=20")
                self.assertEqual(200, status)
                message_id = loaded["messages"][0]["message_id"]
                self.assertEqual("Hello Grace", loaded["messages"][0]["content"])
                self.assertEqual("STEWARD", loaded["messages"][0]["sender_type"])

                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
                server = create_server(database, token_file, {"Grace"}, {"Grace": ["r3.status"]}, port=port)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                status, reloaded = request("GET", f"/v1/conversations/{conversation_id}/messages?after=0&limit=20")
                self.assertEqual(200, status)
                self.assertEqual(message_id, reloaded["messages"][0]["message_id"])
                self.assertEqual("Hello Grace", reloaded["messages"][0]["content"])
                self.assertEqual(2, len(reloaded["messages"]))
                self.assertEqual(maximum_sent["message_id"], reloaded["messages"][1]["message_id"])
                self.assertEqual(100_000, len(reloaded["messages"][1]["content"]))
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    request("GET", f"/v1/conversations/{conversation_id}/messages?after=0", use_auth=False)
                self.assertEqual(401, denied.exception.code)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
