"""Safe, detail-rich ntfy payload tests; never targets the configured phone topic."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from r3a_plugins.notification_service.ntfy import NtfyPublisher, render_notification_presentation


DELIVERY = {
    "delivery_id": "c98b8b58-9fae-5b69-af8b-b72f908d4448",
    "source_id": "r3a.institution-events",
    "source_event_id": "e062185a-a7d9-4bb9-a593-a72df24ae253",
    "event_type": "process.failed",
    "correlation_id": "e062185a-a7d9-4bb9-a593-a72df24ae253",
    "severity": "error", "urgency": "critical", "requires_action": True,
    "evidence_refs": ["r3a.institution_events/e062185a-a7d9-4bb9-a593-a72df24ae253"],
    "notification": {
        "occurred_at": "2026-11-08T14:09:44.977487Z",
        "evidence": {"subject_type": "process", "subject_id": "ring0", "prior_state": "RUNNING",
                     "next_state": "FAILED", "reason": "The scheduler heartbeat exceeded its deadline."},
    },
}


class NtfyPresentationTests(unittest.TestCase):
    def test_message_has_reason_source_severity_utc_local_and_safe_view_actions(self):
        message=render_notification_presentation(DELIVERY,website_base_url="https://steward.example",
                                                 presentation_timezone="America/New_York")
        self.assertEqual("ERROR · Service unavailable",message["title"])
        self.assertIn("The scheduler heartbeat exceeded its deadline",message["details"])
        self.assertIn("r3a.institution-events · process.failed",message["details"])
        self.assertIn("UTC 2026-11-08T14:09:44.977487Z",message["occurred_at_local"])
        self.assertEqual(3,len(message["actions"]))
        self.assertTrue(all(item["method"]=="view" and item["mutates"] is False
                            and item["requires_authenticated_website"] for item in message["actions"]))
        self.assertTrue(all("notification_id=c98b8b58-9fae-5b69-af8b-b72f908d4448" in item["destination"]
                            for item in message["actions"]))

    def test_website_action_intent_does_not_call_a_mutation_endpoint(self):
        message=render_notification_presentation(DELIVERY,website_base_url="https://steward.example",
                                                 presentation_timezone="America/New_York")
        ack=next(item for item in message["actions"] if item["action_id"]=="acknowledgment")
        self.assertIn("notification_intent=acknowledgment",ack["destination"])
        self.assertEqual("view",ack["method"])
        self.assertNotIn("/acknowledgment",ack["destination"])

    def test_without_configured_website_destination_no_actions_are_fabricated(self):
        message=render_notification_presentation(DELIVERY,website_base_url=None,
                                                 presentation_timezone="America/New_York")
        self.assertIsNone(message["detail_url"])
        self.assertEqual([],message["actions"])

    def test_detail_text_is_bounded_and_header_injection_is_removed(self):
        event={**DELIVERY,"notification":{**DELIVERY["notification"],"evidence":{
            **DELIVERY["notification"]["evidence"],"reason":"bad\r\nX-Authorization: token"+"x"*2000}}}
        message=render_notification_presentation(event,website_base_url="https://steward.example",
                                                 presentation_timezone="America/New_York")
        self.assertLessEqual(len(message["details"]),3500)
        self.assertNotIn("\r",message["details"])
        self.assertNotIn("\nX-Authorization",message["details"])


class NtfyHttpPublisherTests(unittest.TestCase):
    def test_authenticated_payload_is_detailed_and_contains_view_only_actions(self):
        captured={}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["path"]=self.path
                captured["auth"]=self.headers.get("Authorization")
                captured["payload"]=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                body=json.dumps({"id":"ntfy-message-test-001"}).encode()
                self.send_response(200);self.send_header("Content-Length",str(len(body)))
                self.end_headers();self.wfile.write(body)
            def log_message(self,*_): return
        server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            publisher=NtfyPublisher(f"http://127.0.0.1:{server.server_port}",topic="isolated-test",
                token="unit-test-token",website_base_url="https://steward.example")
            message_id=publisher.publish(DELIVERY,presentation_timezone="America/New_York")
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
        self.assertEqual("ntfy-message-test-001",message_id)
        self.assertEqual("Bearer unit-test-token",captured["auth"])
        payload=captured["payload"]
        self.assertEqual("isolated-test",payload["topic"])
        self.assertIn("RUNNING → FAILED",payload["message"])
        self.assertIn("UTC 2026-11-08",payload["message"])
        self.assertEqual(3,len(payload["actions"]))
        self.assertTrue(all(action["action"]=="view" for action in payload["actions"]))
        self.assertNotIn("attach",payload)

    def test_untrusted_non_loopback_http_transport_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"HTTPS or loopback HTTP"):
            NtfyPublisher("http://192.0.2.1:2586",topic="test",token="token",
                          website_base_url="https://steward.example")


if __name__=="__main__": unittest.main()
