"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_protocol.py
Component: R3A-LOCAL-PROTOCOL-REGRESSION
File Revision: 1.0.0
Created: 2026-11-08T15:02:05Z
Created By: Codex GPT-6
Purpose: Verify bounded resident protocol frames can carry durable reasoning context to Grace.
Execution Model: Python unittest.
Observability: Exact frame boundary assertions.
Dependencies: Python standard library; r3a_runtime.protocol.
Authority: AP1 context recovery, Steward directive, Issue #43.
Changed: 2026-11-08T15:02:05Z | R3A-CONTEXT-RECOVERY | Codex GPT-6 | Cover the 1 MiB bounded module frame contract.
Supersedes: None.
Contracts: AP0 module RPC; R3A-019.
Tests: This test module.
History/Predecessor: New file.
"""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.protocol import MAX_MESSAGE_BYTES, ModuleProtocolServer, encode, request


class ProtocolFrameBudgetTests(unittest.TestCase):
    def test_frames_over_64k_can_reach_resident_compaction_within_bounded_limit(self):
        payload = {"protocol_version": {"major": 1, "minor": 0}, "payload": {"context": "x" * 70000}}
        encoded = encode(payload)
        self.assertGreater(len(encoded), 65536)
        self.assertLessEqual(len(encoded), MAX_MESSAGE_BYTES)

    def test_local_module_rpc_round_trips_context_over_64k(self):
        async def exercise(socket_path):
            async def handler(operation, payload):
                return {"operation": operation, "context_bytes": len(payload["context"].encode())}

            server = ModuleProtocolServer(socket_path, "resident.test", "1.0.0", handler)
            await server.start()
            try:
                return await request(socket_path, "resident.test", "1.0.0", "execute",
                                     {"context": "x" * 70000})
            finally:
                await server.close()

        with tempfile.TemporaryDirectory() as directory:
            response = asyncio.run(exercise(Path(directory) / "module.sock"))
        self.assertEqual(response["result"]["context_bytes"], 70000)

    def test_frames_above_one_mib_remain_rejected(self):
        payload = {"protocol_version": {"major": 1, "minor": 0},
                   "payload": {"context": "x" * MAX_MESSAGE_BYTES}}
        with self.assertRaisesRegex(ValueError, "configured contract frame size"):
            encode(payload)


if __name__ == "__main__":
    unittest.main()
