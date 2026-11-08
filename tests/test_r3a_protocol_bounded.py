from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from r3a_runtime.protocol import (MAX_MESSAGE_BYTES, ModuleProtocolServer,
                                  ProtocolFrameTooLarge, encode, request)


class BoundedProviderProtocolTests(unittest.TestCase):
    def test_encode_rejects_oversized_frames_with_specific_error(self):
        with self.assertRaises(ProtocolFrameTooLarge):
            encode({"history": "x" * MAX_MESSAGE_BYTES})

    def test_oversized_provider_result_returns_bounded_controlled_error(self):
        async def scenario(socket: Path):
            async def handler(_operation, _payload):
                return {"telemetry_history": ["record-" + "x" * 7000 for _ in range(12)]}

            server = ModuleProtocolServer(socket, "r3a.telemetry.fixture", "1.0.0", handler)
            await server.start()
            try:
                with self.assertRaisesRegex(RuntimeError, "response_too_large"):
                    await request(socket, "r3a.telemetry.fixture", "1.0.0", "execute")
            finally:
                await server.close()

        with tempfile.TemporaryDirectory(prefix="r3a-protocol-bounds-") as temporary:
            asyncio.run(scenario(Path(temporary) / "provider.sock"))


if __name__ == "__main__":
    unittest.main()
