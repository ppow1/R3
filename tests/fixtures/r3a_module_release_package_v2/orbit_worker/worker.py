"""A generic JSON-lines worker fixture for the resident module package contract.

R3 CONTROLLED SOURCE
File: tests/fixtures/r3a_module_release_package_v2/orbit_worker/worker.py
Component: FIXTURE-R3A-MODULE-JSONL-WORKER
File Revision: 1.0.1
Created: 2026-11-11T18:57:26Z
Created By: Codex GPT-6
Purpose: Exercise a non-Grace versioned resident module artifact through the AP0-M1 JSON-lines protocol.
Execution Model: Async process fixture supervised by a test; not production code.
Observability: Module identity, version, protocol health and stop response.
Dependencies: Python standard library; installed host contract r3a_runtime.protocol.
Authority: AD-024; Step 70/84 shared interoperability fixture; no identity or grant authority.
Changed: 2026-11-11T18:57:26Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Add generic Orbit worker fixture.
Changed: 2026-11-11T19:00:20Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Correct package fixture provenance metadata.
Supersedes: None.
Contracts: r3a.module-process-binding.v1@1.0.0; r3a.module.v1.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New fixture; deliberately uses executor.orbit, not a resident identity.
"""
from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path
from typing import Any

from r3a_runtime.protocol import ModuleProtocolServer


class OrbitWorker:
    def __init__(self) -> None:
        self.stopping = asyncio.Event()
        self.active = False

    async def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "hello":
            return {"contract_id": "r3a.resident.execution", "contract_version": "1.0.0"}
        if operation == "health":
            return {"state": "ACTIVE" if self.active else "READY", "module": "executor.orbit"}
        if operation in {"prepare", "activate"}:
            self.active = operation == "activate"
            return {"accepted": True, "state": "ACTIVE" if self.active else "READY"}
        if operation == "execute":
            return {"accepted": True, "activity_id": payload.get("activity_id")}
        if operation == "checkpoint":
            return {"state": "ACTIVE" if self.active else "READY"}
        if operation == "stop":
            self.active = False
            self.stopping.set()
            return {"stopped": True}
        raise ValueError(f"unsupported fixture operation: {operation}")


async def run(socket_path: str, module_id: str, module_version: str, config_path: str) -> None:
    if not Path(config_path).is_file():
        raise FileNotFoundError("module configuration is unavailable")
    worker = OrbitWorker()
    server = ModuleProtocolServer(socket_path, module_id, module_version, worker.handle)
    await server.start()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, worker.stopping.set)
        except NotImplementedError:
            pass
    await worker.stopping.wait()
    await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--module-version", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.socket, args.module_id, args.module_version, args.config))


if __name__ == "__main__":
    main()
