# R3 CONTROLLED SOURCE
# File: tests/test_resident_host_integration.py
# Component: R3-RESIDENT-HOST-INTEGRATION
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Permanent resident inference to actual local host execution contract.
from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from runtime.host_execution import HostExecutor
from runtime.native_tools import NativeTools
from runtime.resident_inference import Inbox, InferenceEndpoint, ResidentInference
from runtime.tool_server import ToolRouter, handler_for


class ModelHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(size))
        if not any(message.get("role") == "tool" for message in payload["messages"]):
            message = {"role": "assistant", "content": None, "tool_calls": [{
                "id": "call-host", "type": "function",
                "function": {"name": "r3.host.version", "arguments": "{}"}}]}
        else:
            message = {"role": "assistant", "content": "Host result received"}
        body = json.dumps({"model": "regression", "choices": [{"message": message}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ResidentHostIntegrationTests(unittest.TestCase):
    def test_resident_executes_local_host_command_and_audits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog = root / "tools.json"
            catalog.write_text(json.dumps({"tools": [{
                "name": "r3.host.version", "description": "Read Python version",
                "argv": ["/usr/bin/python3", "--version"],
                "timeout_seconds": 10, "read_only": True
            }]}))
            router = ToolRouter(root / "audit.db", HostExecutor(catalog))
            tool_server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(router))
            model_server = ThreadingHTTPServer(("127.0.0.1", 0), ModelHandler)
            threads = []
            db = sqlite3.connect(root / "resident.db")
            try:
                for server in (tool_server, model_server):
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    threads.append(thread)
                inbox = Inbox(db)
                event_id = inbox.enqueue("Grace", "HOST_CHECK", {"request": "Check host"})
                resident = ResidentInference(
                    inbox,
                    InferenceEndpoint(f"http://127.0.0.1:{model_server.server_port}/v1", "regression", 5),
                    system_prompt="Use available tools",
                    tools=NativeTools(f"http://127.0.0.1:{tool_server.server_port}", 5,
                                      ("r3.host.version",)),
                )
                asyncio.run(resident("Grace"))
                self.assertEqual(db.execute(
                    "SELECT status FROM resident_inbox WHERE id=?", (event_id,)
                ).fetchone()[0], "COMPLETED")
                history = inbox.history(event_id)
                self.assertEqual([kind for kind, _ in history],
                                 ["ASSISTANT", "TOOL_INTENT", "TOOL_RESULT", "ASSISTANT"])
                output = json.loads(history[2][1]["content"])
                self.assertEqual(output["returncode"], 0)
                self.assertIn("Python", output["stdout"])
                self.assertEqual(router.db.execute(
                    "SELECT tool,outcome FROM tool_audit").fetchall(),
                    [("r3.host.version", "OK")])
            finally:
                db.close()
                for server in (tool_server, model_server):
                    server.shutdown()
                    server.server_close()
                for thread in threads:
                    thread.join(timeout=3)
                router.db.close()


if __name__ == "__main__":
    unittest.main()
