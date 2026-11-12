"""
R3 CONTROLLED SOURCE
File: r3a_runtime/control.py
Component: R3A-CONTROL-SOCKET
File Revision: 1.0.0
Created: 2026-11-06T15:18:00Z
Created By: Codex GPT-6
Purpose: Provide local-only CME control transport and Unix socket lifecycle helpers.
Execution Model: Async Unix domain socket JSON protocol.
Observability: Correlated request/response IDs and bounded errors.
Dependencies: Python 3.12 standard library; r3a_runtime.protocol.
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; socket only.
Changed: 2026-11-06T15:18:00Z | R3A-AP0-M1 | Codex GPT-6 | Add private CME control socket.
Supersedes: None.
Contracts: AP0-001/002/007/010; AP0-M1 D1/D5/D8.
Tests: tests/test_r3a_protocol.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from .protocol import MAX_MESSAGE_BYTES, PROTOCOL_MAJOR, PROTOCOL_MINOR


def _json_default(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "hex"):
        return str(value)
    raise TypeError(f"Cannot encode {type(value).__name__}")


async def control_request(socket_path: str | Path, operation: str,
                          payload: dict[str, Any] | None = None,
                          idempotency_key: str | None = None,
                          timeout: float = 5.0) -> dict[str, Any]:
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(socket_path)), timeout)
    request_id = str(uuid.uuid4())
    try:
        message = {"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                   "request_id": request_id, "correlation_id": request_id,
                   "idempotency_key": idempotency_key or request_id,
                   "operation": operation, "payload": payload or {}}
        writer.write(json.dumps(message, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout)
        if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
            raise ValueError("Invalid CME control response frame")
        response = json.loads(raw)
        if response.get("request_id") != request_id:
            raise ValueError("CME control response correlation mismatch")
        if not response.get("ok", False):
            raise RuntimeError(response.get("error", "CME control request failed"))
        return response["result"]
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


class ControlServer:
    def __init__(self, socket_path: str | Path,
                 handler: Callable[[str, dict[str, Any], str], Awaitable[dict[str, Any]]],
                 mode: int = 0o600):
        self.path = Path(socket_path)
        self.handler = handler
        self.mode = mode
        self.server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.unlink(missing_ok=True)
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.path), limit=MAX_MESSAGE_BYTES)
        self.path.chmod(self.mode)

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.path.unlink(missing_ok=True)

    async def serve_forever(self) -> None:
        if self.server is None:
            await self.start()
        assert self.server is not None
        async with self.server:
            await self.server.serve_forever()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request_id = str(uuid.uuid4())
        try:
            raw = await reader.readline()
            if not raw or len(raw) > MAX_MESSAGE_BYTES or not raw.endswith(b"\n"):
                raise ValueError("Invalid or oversized CME control request")
            request = json.loads(raw)
            request_id = str(request.get("request_id", request_id))
            version = request.get("protocol_version", {})
            if not isinstance(version, dict) or version.get("major") != PROTOCOL_MAJOR:
                raise ValueError("Incompatible CME control protocol")
            operation = request.get("operation")
            payload = request.get("payload", {})
            key = request.get("idempotency_key")
            if not isinstance(operation, str) or not isinstance(payload, dict) or not isinstance(key, str):
                raise ValueError("Invalid CME control request shape")
            result = await self.handler(operation, payload, key)
            response = {"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                        "request_id": request_id, "correlation_id": request.get("correlation_id", request_id),
                        "ok": True, "result": result}
        except Exception as exc:
            response = {"protocol_version": {"major": PROTOCOL_MAJOR, "minor": PROTOCOL_MINOR},
                        "request_id": request_id, "correlation_id": request_id,
                        "ok": False, "error": f"{type(exc).__name__}: {str(exc)[:1000]}"}
        try:
            writer.write(json.dumps(response, sort_keys=True, separators=(",", ":"),
                                     default=_json_default).encode() + b"\n")
            await writer.drain()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (BrokenPipeError, ConnectionResetError):
                pass


def process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
