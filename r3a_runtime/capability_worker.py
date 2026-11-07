"""
R3 CONTROLLED SOURCE
File: r3a_runtime/capability_worker.py
Component: R3A-CAPABILITY-PROVIDER-WORKER
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Load and execute one digest-pinned provider under the generic module protocol.
Execution Model: CME-supervised child process with a private Unix socket binding.
Observability: Versioned hello, readiness, health, checkpoint, execute, and stop calls.
Dependencies: Python standard library; r3a_runtime.protocol; manifest provider package.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Implement a generic provider worker with pinned artifact checks and sanitized execution errors.
Supersedes: None.
Contracts: MOD-001–MOD-010; r3a.capability-provider.v1; AP0-M1 JSON-lines protocol.
Tests: tests/test_r3a_capability_integration_demo.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import signal
from pathlib import Path
from typing import Any

from .protocol import ModuleProtocolServer


class CapabilityWorker:
    def __init__(self, module_id: str, module_version: str, entrypoint: str,
                 artifact: Path, artifact_digest: str):
        self.module_id = module_id
        self.module_version = module_version
        self.entrypoint = entrypoint
        self.artifact = artifact
        self.artifact_digest = artifact_digest
        self.state = "INSTALLED"
        self.provider = None
        self.stopping = asyncio.Event()

    async def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "hello":
            return {"contract_id": "r3a.capability-provider.v1",
                    "supported_protocol": {"major": 1, "min_minor": 0, "max_minor": 0},
                    "module_id": self.module_id, "module_version": self.module_version}
        if operation == "health":
            return {"state": self.state, "health": "healthy" if self.state == "ACTIVE" else "available"}
        if operation == "prepare":
            if self.state not in {"INSTALLED", "STOPPED"}:
                raise RuntimeError(f"cannot prepare provider in {self.state}")
            if hashlib.sha256(self.artifact.read_bytes()).hexdigest() != self.artifact_digest:
                raise RuntimeError("provider artifact digest changed after registration")
            for artifact_path, expected_digest in payload.get("pinned_artifacts", {}).items():
                if hashlib.sha256(Path(artifact_path).read_bytes()).hexdigest() != expected_digest:
                    raise RuntimeError("supporting provider artifact digest changed after registration")
            module_name, object_name = self.entrypoint.split(":", 1)
            module = importlib.import_module(module_name)
            if Path(module.__file__).resolve() != self.artifact.resolve():
                raise RuntimeError("provider entrypoint resolved outside its pinned artifact")
            factory = getattr(module, object_name)
            config = payload.get("configuration")
            if not isinstance(config, dict):
                raise ValueError("provider configuration must be an object")
            try:
                self.provider = factory(config)
            except Exception as exc:
                raise RuntimeError(f"provider initialization failed ({type(exc).__name__})") from None
            if not callable(getattr(self.provider, "invoke", None)):
                raise TypeError("provider entrypoint did not create an invoke-capable provider")
            self.state = "ACTIVATING"
            return {"prepared": True}
        if operation == "activate":
            if self.state != "ACTIVATING" or self.provider is None:
                raise RuntimeError("provider has not been prepared")
            self.state = "ACTIVE"
            return {"active": True}
        if operation == "execute":
            if self.state != "ACTIVE" or self.provider is None:
                raise RuntimeError("provider is not active")
            arguments, context = payload.get("arguments"), payload.get("context")
            if not isinstance(arguments, dict) or not isinstance(context, dict):
                raise ValueError("provider execute envelope is invalid")
            try:
                result = self.provider.invoke(arguments, context=context)
            except Exception as exc:
                raise RuntimeError(f"provider execution failed ({type(exc).__name__})") from None
            try:
                json.dumps(result)
            except (TypeError, ValueError):
                raise TypeError("provider returned a non-JSON result") from None
            return {"provider_result": result}
        if operation == "checkpoint":
            return {"checkpointed": True, "state": self.state}
        if operation == "stop":
            self.state = "STOPPED"
            self.provider = None
            self.stopping.set()
            return {"stopped": True}
        raise ValueError(f"unsupported provider lifecycle operation: {operation}")


async def run(args) -> None:
    worker = CapabilityWorker(args.module_id, args.module_version, args.entrypoint,
                              Path(args.artifact), args.artifact_sha256)
    server = ModuleProtocolServer(args.socket, args.module_id, args.module_version, worker.handle)
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
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
