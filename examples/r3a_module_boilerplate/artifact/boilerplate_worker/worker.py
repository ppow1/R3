"""A minimal AP0-M1 JSON-lines worker scaffold with no default authority.

R3 CONTROLLED SOURCE
File: examples/r3a_module_boilerplate/artifact/boilerplate_worker/worker.py
Component: R3A-MODULE-BOILERPLATE-WORKER
File Revision: 1.0.1
Created: 2026-11-11T21:52:37Z
Created By: Codex GPT-6
Purpose: Demonstrate the existing module lifecycle protocol without implementing module-specific work.
Execution Model: Async child process using the host-supplied private Unix-socket JSON-lines protocol.
Observability: Correlated hello, health, prepare, activate, execute, checkpoint, and stop responses.
Dependencies: Python 3.12 standard library; host-supplied r3a_runtime.protocol; external JSON configuration file.
Authority: Steward assignment #68 comment 6807799874; Planned Step 126 comment 6807801282. No capability grants or core/socket changes.
Changed: 2026-11-11T21:52:37Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Add a reusable lifecycle-only process scaffold.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Enforce the declared external configuration shape before opening the socket.
Supersedes: None.
Contracts: AP0-M1 r3a.module.v1; r3a.resident.execution@1.0.0.
Tests: tests/test_module_boilerplate_example.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import signal
from pathlib import Path
from typing import Any

from r3a_runtime.protocol import ModuleProtocolServer


class BoilerplateWorker:
    def __init__(self) -> None:
        self.stopping = asyncio.Event()
        self.state = "READY"

    async def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "hello":
            return {"contract_id": "r3a.resident.execution", "contract_version": "1.0.0"}
        if operation == "health":
            return {"state": self.state, "module": "example.module-boilerplate"}
        if operation == "prepare":
            if self.state == "STOPPED":
                raise RuntimeError("stopped worker cannot be prepared")
            return {"accepted": True, "state": self.state}
        if operation == "activate":
            if self.state == "STOPPED":
                raise RuntimeError("stopped worker cannot be activated")
            self.state = "ACTIVE"
            return {"accepted": True, "state": self.state}
        if operation == "execute":
            raise NotImplementedError("replace with module-owned behavior before accepting work")
        if operation == "checkpoint":
            if self.state == "STOPPED":
                raise RuntimeError("stopped worker has no live checkpoint")
            return {"state": self.state, "checkpoint": None}
        if operation == "stop":
            self.state = "STOPPED"
            self.stopping.set()
            return {"stopped": True}
        raise ValueError(f"unsupported lifecycle operation: {operation}")


def load_configuration(config_path: str) -> dict[str, Any]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    if (not isinstance(config, dict)
            or set(config) != {"schema_id", "schema_version", "settings"}
            or config.get("schema_id") != "example.module-boilerplate.configuration.v1"
            or config.get("schema_version") != 1
            or not isinstance(config.get("settings"), dict)):
        raise ValueError("external module configuration is invalid")
    settings = config["settings"]
    if set(settings) - {"display_label"}:
        raise ValueError("external module configuration contains an undeclared setting")
    label = settings.get("display_label")
    if label is not None and (not isinstance(label, str) or not 1 <= len(label) <= 80):
        raise ValueError("external module display_label is invalid")
    return config


async def run(socket_path: str, module_id: str, module_version: str, config_path: str) -> None:
    load_configuration(config_path)

    worker = BoilerplateWorker()
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
