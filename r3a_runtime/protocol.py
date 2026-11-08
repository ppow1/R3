"""
R3 CONTROLLED SOURCE
File: r3a_runtime/protocol.py
Component: R3A-LOCAL-PROTOCOL
File Revision: 1.0.1
Created: 2026-11-06T15:12:00Z
Created By: Codex GPT-6
Purpose: Implement the bounded versioned JSON-lines contract over private Unix sockets.
Execution Model: Async Unix stream client/server.
Observability: Correlated protocol requests and structured errors.
Dependencies: Python 3.12 standard library; AP0-M1 module/control contracts.
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; local sockets only.
Changed: 2026-11-06T15:12:00Z | R3A-AP0-M1 | Codex GPT-6 | Add local versioned protocol helpers.
Changed: 2026-11-08T15:02:05Z | R3A-CONTEXT-RECOVERY | Codex GPT-6 | Raise the bounded local resident frame ceiling to carry durable context until Grace can compact its model view.
Supersedes: None.
Contracts: MOD-001–MOD-010; AP0-007; AP0-M1 D5/D8.
Tests: tests/test_r3a_protocol.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable


PROTOCOL_MAJOR = 1
PROTOCOL_MINOR = 0
MAX_MESSAGE_BYTES = 1_048_576


def encode(message: dict[str, Any]) -> bytes:
    raw = json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ValueError("Protocol message exceeds the configured contract frame size")
    return raw


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any]:
    raw = await reader.readline()
    if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
        raise ValueError("Invalid or oversized protocol frame")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Protocol frame must be a JSON object")
    return value


async def request(socket_path: str | Path, module_id: str, module_version: str,
                  operation: str, payload: dict[str, Any] | None = None,
                  timeout: float = 5.0) -> dict[str, Any]:
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(socket_path)), timeout)
    request_id = str(uuid.uuid4())
    try:
        writer.write(encode({"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                             "module_id": module_id, "module_version": module_version,
                             "operation": operation, "request_id": request_id,
                             "correlation_id": request_id, "payload": payload or {}}))
        await writer.drain()
        response = await asyncio.wait_for(read_message(reader), timeout)
        if response.get("request_id") != request_id or response.get("correlation_id") != request_id:
            raise ValueError("Protocol response correlation mismatch")
        if response.get("protocol_version", {}).get("major") != PROTOCOL_MAJOR:
            raise ValueError("Protocol major version mismatch")
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "module protocol operation failed"))
        return response
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


class ModuleProtocolServer:
    def __init__(self, socket_path: str | Path, module_id: str, module_version: str,
                 handler: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]):
        self.socket_path = Path(socket_path)
        self.module_id = module_id
        self.module_version = module_version
        self.handler = handler
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.socket_path.unlink(missing_ok=True)
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.socket_path), limit=MAX_MESSAGE_BYTES)
        self.socket_path.chmod(0o600)

    async def serve_forever(self) -> None:
        if self.server is None:
            await self.start()
        assert self.server is not None
        async with self.server:
            await self.server.serve_forever()

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.socket_path.unlink(missing_ok=True)

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_id = str(uuid.uuid4())
        try:
            message = await read_message(reader)
            request_id = str(message.get("request_id", request_id))
            version = message.get("protocol_version")
            if not isinstance(version, dict) or version.get("major") != PROTOCOL_MAJOR:
                raise ValueError("incompatible protocol major version")
            if message.get("module_id") != self.module_id:
                raise ValueError("module identity mismatch")
            if message.get("module_version") != self.module_version:
                raise ValueError("module version mismatch")
            operation = message.get("operation")
            payload = message.get("payload", {})
            if not isinstance(operation, str) or not isinstance(payload, dict):
                raise ValueError("operation or payload has invalid shape")
            result = await self.handler(operation, payload)
            response = {"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                        "module_id": self.module_id, "module_version": self.module_version,
                        "request_id": request_id, "correlation_id": message.get("correlation_id", request_id),
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "ok": True, "result": result}
        except Exception as exc:
            response = {"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                        "module_id": self.module_id, "module_version": self.module_version,
                        "request_id": request_id, "correlation_id": request_id,
                        "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:1000]}"}
        try:
            writer.write(encode(response))
            await writer.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass
