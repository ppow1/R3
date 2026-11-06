"""
R3 CONTROLLED SOURCE
File: r3a_runtime/observer_module.py
Component: R3A-FOUNDATION-OBSERVER
File Revision: 1.0.0
Created: 2026-11-06T15:12:00Z
Created By: Codex GPT-6
Purpose: Run the AP0-M1 real read-only observer as an independently supervised module process.
Execution Model: Versioned JSON-lines Unix socket module process.
Observability: Health handshake and timestamped observation activity response.
Dependencies: r3a_runtime.protocol.
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; only registered read-only capabilities.
Changed: 2026-11-06T15:12:00Z | R3A-AP0-M1 | Codex GPT-6 | Add foundation observer module.
Supersedes: None.
Contracts: AP0-003/007/008/010; MOD-001–MOD-010; AP0-M1 D5/D6.
Tests: tests/test_r3a_protocol.py; live AP0-M1 observer evidence.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
from typing import Any

from .protocol import ModuleProtocolServer


class FoundationObserver:
    def __init__(self, module_id: str, module_version: str):
        self.module_id = module_id
        self.module_version = module_version
        self.state = "INSTALLED"
        self.last_activity: dict[str, Any] | None = None
        self.stopping = asyncio.Event()

    async def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "hello":
            return {"contract_id": "r3a.module.v1", "supported_protocol": {"major": 1, "min_minor": 0, "max_minor": 0},
                    "capabilities": ["host.process.read", "postgres.readiness"], "pid": os.getpid()}
        if operation == "health":
            return {"state": self.state, "health": "healthy", "pid": os.getpid(),
                    "last_activity": self.last_activity}
        if operation == "prepare":
            self.state = "ACTIVATING"
            return {"prepared": True, "module_id": self.module_id}
        if operation == "activate":
            self.state = "ACTIVE"
            return {"active": True}
        if operation == "execute":
            if self.state != "ACTIVE":
                raise RuntimeError("module is not active")
            required = {"activity_id", "attempt_id", "processes", "postgres"}
            if not required.issubset(payload):
                raise ValueError(f"observer input missing {sorted(required - payload.keys())}")
            self.last_activity = {
                "activity_id": payload["activity_id"],
                "attempt_id": payload["attempt_id"],
                "observed_processes": payload["processes"],
                "postgres_readiness": payload["postgres"],
                "observation_source": "registered read-only CME capabilities",
            }
            return self.last_activity
        if operation == "checkpoint":
            return {"state": self.state, "last_activity": self.last_activity}
        if operation == "stop":
            self.state = "STOPPED"
            self.stopping.set()
            return {"stopped": True}
        raise ValueError(f"Unsupported module operation: {operation}")


async def run(socket_path: str, module_id: str, module_version: str) -> None:
    module = FoundationObserver(module_id, module_version)
    server = ModuleProtocolServer(socket_path, module_id, module_version, module.handle)
    await server.start()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, module.stopping.set)
        except NotImplementedError:
            pass
    await module.stopping.wait()
    await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--module-version", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.socket, args.module_id, args.module_version))


if __name__ == "__main__":
    main()
