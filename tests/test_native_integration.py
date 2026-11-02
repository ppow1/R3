# R3 CONTROLLED SOURCE
# File: tests/test_native_integration.py
# Component: R3-NATIVE-INTEGRATION-REGRESSION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent real HTTP resident/tool/audit integration regression.
# Contracts: docs/r3-native-tool-contract.md
from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from runtime.native_tools import NativeTools
from runtime.resident_inference import Inbox, InferenceEndpoint, ResidentInference
from runtime.tool_server import ToolRouter, handler_for


class ModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(size))
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        tool_results = [m for m in request["messages"] if m.get("role") == "tool"]
        if not tool_results:
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-1", "type": "function",
                "function": {"name": "r3.status", "arguments": "{}"}}]}
        else:
            message = {"role": "assistant", "content": "R3 status received"}
        body = json.dumps({"model": "test-model", "choices": [{"message": message}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class NativeIntegrationTests(unittest.TestCase):
    def test_resident_tool_call_continues_and_audits_over_http(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            audit = root / "tool-audit.db"
            tool_server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(ToolRouter(audit)))
            model_server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
            threads = []
            try:
                for server in (tool_server, model_server):
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    threads.append(thread)
                db = sqlite3.connect(root / "institution.db")
                inbox = Inbox(db)
                event_id = inbox.enqueue("Grace", "REQUEST", {"question": "Check R3 status"})
                handler = ResidentInference(
                    inbox,
                    InferenceEndpoint(f"http://127.0.0.1:{model_server.server_port}/v1", "test-model", timeout=5),
                    system_prompt="You are Grace",
                    tools=NativeTools(f"http://127.0.0.1:{tool_server.server_port}", 5, ("r3.status",)),
                )
                asyncio.run(handler("Grace"))
                status = db.execute("SELECT status FROM resident_inbox WHERE id=?", (event_id,)).fetchone()[0]
                self.assertEqual(status, "COMPLETED")
                kinds = [kind for kind, _ in inbox.history(event_id)]
                self.assertEqual(kinds, ["ASSISTANT", "TOOL_INTENT", "TOOL_RESULT", "ASSISTANT"])
                with sqlite3.connect(audit) as audit_db:
                    records = audit_db.execute("SELECT tool,outcome FROM tool_audit").fetchall()
                self.assertEqual(records, [("r3.status", "OK")])
                db.close()
            finally:
                for server in (tool_server, model_server):
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
