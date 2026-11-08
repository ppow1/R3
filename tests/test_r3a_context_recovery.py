from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.config import ModelRoute
from r3a_runtime.grace_module import compact_evidence_for_context, fit_model_request_context
from r3a_runtime.protocol import (
    MAX_MESSAGE_BYTES,
    MAX_RESIDENT_EXECUTION_FRAME_BYTES,
    ModuleProtocolServer,
    encode,
    request,
)


class ContextBudgetTests(unittest.TestCase):
    def test_projection_keeps_exact_relevant_content_and_does_not_mutate_evidence(self):
        original = [{"source_id": "telemetry", "content": {
            "gpu_name": "GPU-A", "status": "running",
            "history": "irrelevant history. " * 900 + "temperature was 72 degrees."}}]
        before = json.loads(json.dumps(original))
        projected, omissions = compact_evidence_for_context(original, "temperature 72 degrees")
        self.assertEqual(original, before)
        self.assertEqual(len(projected), 1)
        self.assertEqual(projected[0]["source_id"], "telemetry")
        self.assertIn("context_projection", projected[0])
        self.assertTrue(projected[0]["context_projection"]["omitted_content_sha256"])
        self.assertTrue(omissions)

    def test_model_request_uses_projection_before_exceeding_route_budget(self):
        evidence = [{"source_id": "telemetry", "content":
                     "temperature is 72 degrees. " + "unrelated historical sample. " * 1400}]
        user = {"objective": "Report the temperature", "evidence": evidence,
                "evidence_inventory": [{"source_id": "telemetry", "sha256": "a" * 64}]}
        request_template = {"messages": [
            {"role": "system", "content": "Use cited evidence."},
            {"role": "user", "content": json.dumps(user, separators=(",", ":"))}],
            "max_tokens": 192}
        route = ModelRoute("test", "openai-compatible", "http://localhost/v1/chat/completions",
                           "model", 5.0, 192, 4096)
        projected, report = fit_model_request_context(
            request_template, evidence, "temperature 72 degrees", route)
        self.assertIsNotNone(projected)
        self.assertEqual(report["durable_evidence_mutated"], False)
        self.assertIn(report["mode"], {"budget_projection", "budget_projection_aggressive"})
        self.assertLessEqual(report["estimated_prompt_tokens"], report["prompt_budget_tokens"])
        encoded_user = json.loads(projected["messages"][-1]["content"])
        self.assertIn("context_projection", encoded_user["evidence"][0])
        self.assertEqual(evidence[0]["content"], user["evidence"][0]["content"])


class ResidentFrameTests(unittest.IsolatedAsyncioTestCase):
    async def test_resident_frame_can_carry_checkpoint_while_default_provider_bound_stays_small(self):
        self.assertEqual(MAX_MESSAGE_BYTES, 65536)
        self.assertEqual(MAX_RESIDENT_EXECUTION_FRAME_BYTES, 1_048_576)
        large = "x" * 70_000
        with self.assertRaises(ValueError):
            encode({"payload": large})
        with tempfile.TemporaryDirectory() as directory:
            socket = Path(directory) / "resident.sock"

            async def handle(operation, payload):
                if operation == "health":
                    return {"state": "ACTIVE"}
                return {"size": len(payload["checkpoint"])}

            server = ModuleProtocolServer(socket, "resident.test", "1.0.0", handle,
                                          max_message_bytes=MAX_RESIDENT_EXECUTION_FRAME_BYTES)
            await server.start()
            try:
                result = await request(socket, "resident.test", "1.0.0", "execute",
                                       {"checkpoint": large}, max_message_bytes=MAX_RESIDENT_EXECUTION_FRAME_BYTES)
                self.assertEqual(result["result"]["size"], len(large))
            finally:
                await server.close()


if __name__ == "__main__":
    unittest.main()
