# R3 CONTROLLED TEST
# File: tests/test_comms5_mcp_transport.py
# Component: R3-COMMS5-MCP-TRANSPORT-TESTS
# File Revision: 1.0.1
# Created: 2026-11-06T01:48:39Z
# Created By: Codex GPT-6, acting on Steward instruction
# Purpose: Verify the Comms5 adapter over authenticated MCP Streamable HTTP without live institutional writes.
# Execution Model: In-process MCP server with a controlled test bearer and disposable proposal records.
# Observability: Captured operation names and IDs only; no production credentials or proposal content.
# Dependencies: MCP Python SDK v1; Uvicorn; runtime.comms5_proposals.
# Authority: Grace Autonomy P1; isolated protocol regression only.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add authenticated MCP transport regression.
# Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Use stateless JSON responses for deterministic transport teardown.
# Supersedes: None
# Contracts: riverview-comms-contract:5.0; Model Context Protocol Streamable HTTP.
# Tests: `python -m unittest tests.test_comms5_mcp_transport -v`
# History/Predecessor: New file; no predecessor.
import socket
import threading
import unittest

from mcp.server.fastmcp import FastMCP
import uvicorn

from runtime.comms5_proposals import Comms5DraftClient


class AuthenticatedASGI:
    def __init__(self, app, bearer):
        self.app = app
        self.bearer = bearer

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            if headers.get(b"authorization") != ("Bearer " + self.bearer).encode():
                await send({"type": "http.response.start", "status": 401, "headers": []})
                await send({"type": "http.response.body", "body": b"unauthorized"})
                return
        await self.app(scope, receive, send)


class MCPStartupSignal:
    def __init__(self, app, started):
        self.app = app
        self.started = started

    async def __call__(self, scope, receive, send):
        async def observed_send(message):
            if message.get("type") == "lifespan.startup.complete":
                self.started.set()
            await send(message)
        await self.app(scope, receive, observed_send)


class Comms5MCPTransportTests(unittest.TestCase):
    def test_authenticated_streamable_http_draft_and_readback(self):
        calls = []
        server = FastMCP(
            "controlled-comms5-test", log_level="CRITICAL",
            json_response=True, stateless_http=True,
        )

        @server.tool()
        def submit_steward_seed(
            authenticated_principal: str,
            client_id: str,
            client_name: str,
            client_type: str,
            client_version: str,
            protocol_version: str,
            correlation_id: str,
            classification: str,
            seed_text: str,
            idempotency_key: str,
        ) -> dict:
            calls.append(("submit_steward_seed", authenticated_principal, idempotency_key))
            return {
                "status": "submitted", "executed": True,
                "seed_id": "seed:mcp-test", "proposal_id": "proposal:mcp-test",
                "revision": 1, "lifecycle_status": "DRAFT",
            }

        @server.tool()
        def seed_status(seed_id: str) -> dict:
            calls.append(("seed_status", seed_id))
            return {
                "status": "available", "executed": True,
                "seed_id": seed_id, "proposal_id": "proposal:mcp-test",
                "revision": 1, "lifecycle_status": "DRAFT",
                "revision_record": {"title": "Clock", "objective": "Date and time"},
            }

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        started = threading.Event()
        app = MCPStartupSignal(AuthenticatedASGI(server.streamable_http_app(), "controlled-test"), started)
        uvicorn_server = uvicorn.Server(uvicorn.Config(app, log_level="critical", lifespan="on"))
        thread = threading.Thread(
            target=uvicorn_server.run,
            kwargs={"sockets": [sock]},
            daemon=True,
        )
        thread.start()
        self.addCleanup(sock.close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(setattr, uvicorn_server, "should_exit", True)
        self.assertTrue(started.wait(10), "controlled MCP test server did not start")

        client = Comms5DraftClient(
            f"http://127.0.0.1:{port}/mcp", "controlled-test",
        )
        result = client.submit(
            "Title: Clock\nObjective: Show date and time.",
            principal="resident:test",
            correlation_id="call-mcp-test",
        )
        self.assertEqual(result["proposal_id"], "proposal:mcp-test")
        self.assertEqual(result["lifecycle_status"], "DRAFT")
        self.assertEqual([x[0] for x in calls], ["submit_steward_seed", "seed_status"])
        self.assertEqual(calls[0][1], "resident:test")


if __name__ == "__main__":
    unittest.main()
