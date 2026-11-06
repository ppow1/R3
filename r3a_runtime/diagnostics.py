"""
R3 CONTROLLED SOURCE
File: r3a_runtime/diagnostics.py
Component: R3A-TRUTHFUL-DIAGNOSTICS
File Revision: 1.0.2
Created: 2026-11-06T15:18:00Z
Created By: Codex GPT-6
Purpose: Serve read-only process, activity, registry, event and machine diagnostics from PostgreSQL.
Execution Model: Async local Unix socket projection.
Observability: Durable snapshot with source timestamps and explicit freshness.
Dependencies: r3a_runtime.db; r3a_runtime.control.
Authority: AP1 / R3A-019 authorized by Steward; local read-only diagnostics only.
Changed: 2026-11-06T15:18:00Z | R3A-AP0-M1 | Codex GPT-6 | Add truthful diagnostic projection.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Bound status payload and report module/process freshness from live observations.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Expose objective progress, model references, completed decisions and failure diagnostics.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Expose event input kind and route in activity diagnostics.
Supersedes: None.
Contracts: AP0-010; R3A-019; AP0-M1 D8; STM-006.
Tests: tests/test_r3a_ap1.py; live AP1 diagnostics evidence pending this revision.
History/Predecessor: Git blob 546ac5d442cedca0fb3d7ab919b0929233b39b01 at commit cdcb63ce1fa33975ce4468d5121e4bfef5429f92.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .control import ControlServer
from .db import Store


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if hasattr(value, "hex"):
        return str(value)
    raise TypeError(f"Cannot encode {type(value).__name__}")


class DiagnosticProjection:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store

    async def handle(self, operation: str, payload: dict[str, Any], _key: str) -> dict[str, Any]:
        if operation not in {"status", "events", "definitions"}:
            raise ValueError("Diagnostic API is read-only and does not support this operation")
        snapshot = await self.store.snapshot()
        now = datetime.now(timezone.utc)
        if operation == "events":
            return {"observed_at": now.isoformat(), "events": snapshot["events"][:20]}
        if operation == "definitions":
            return {"observed_at": now.isoformat(), "definitions": snapshot["state_machines"]}
        processes = []
        for row in snapshot["processes"]:
            heartbeat = row["heartbeat_at"]
            age = (now - heartbeat).total_seconds()
            freshness = "fresh" if age <= self.settings.diagnostic_stale_after_seconds else "stale"
            health = row["health"] if freshness == "fresh" else "stale"
            processes.append({**row, "heartbeat_age_seconds": age, "freshness": freshness, "health": health})
        known = {row["component_id"] for row in snapshot["processes"]}
        for component in ("ring0", "cme"):
            if component not in known:
                processes.append({"component_id": component, "state": "unknown", "health": "unknown",
                                  "freshness": "unknown", "heartbeat_at": None})
        module_health = []
        for row in snapshot["modules"]:
            observed = row["observed_at"]
            age = (now - observed).total_seconds() if observed else None
            freshness = "unknown" if age is None else (
                "fresh" if age <= self.settings.diagnostic_stale_after_seconds else "stale")
            module_health.append({"module_id": row["module_id"], "module_version": row["module_version"],
                                  "contract_id": row["contract_id"], "protocol_major": row["protocol_major"],
                                  "protocol_minor": row["protocol_minor"],
                                  "artifact_digest": row["artifact_digest"],
                                  "lifecycle_state": row["lifecycle_state"], "observed_at": observed,
                                  "diagnostic": row["diagnostic"], "observation_age_seconds": age,
                                  "freshness": freshness,
                                  "health": row["health"] if freshness == "fresh" else freshness})
        event_summary = await self.store.rows(
            "SELECT count(*) AS retained_events, max(persisted_at) AS latest_event_at "
            "FROM r3a.institution_events"
        )
        activities = [{key: row[key] for key in (
            "activity_id", "activity_type", "state", "attempt_count", "attempt_id",
            "available_at", "lease_owner", "lease_until", "updated_at", "exception", "input",
            "progress", "result")}
            for row in snapshot["activities"][:10]]
        machines = [{key: row[key] for key in ("machine_id", "machine_version", "digest")}
                    for row in snapshot["state_machines"]]
        return {"observed_at": now.isoformat(), "instance_id": self.settings.instance_id,
                "source": "postgresql", "source_freshness": "fresh",
                "configuration": snapshot["configuration"], "processes": processes,
                "modules": module_health, "resources": snapshot["resources"],
                "activities": activities, "event_summary": event_summary[0],
                "state_machines": machines}


def make_server(settings: Settings, store: Store) -> ControlServer:
    async def handler(operation: str, payload: dict[str, Any], key: str) -> dict[str, Any]:
        return await DiagnosticProjection(settings, store).handle(operation, payload, key)
    return ControlServer(settings.diagnostics_socket, handler, mode=0o640)


async def status(settings: Settings) -> dict[str, Any]:
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(settings.diagnostics_socket)), 4.0)
    request_id = __import__("uuid").uuid4().hex
    try:
        writer.write(json.dumps({"protocol_version": {"major": 1, "minor": 0},
                                 "request_id": request_id, "correlation_id": request_id,
                                 "idempotency_key": request_id, "operation": "status", "payload": {}},
                                separators=(",", ":")).encode() + b"\n")
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), 4.0)
        if not raw:
            raise RuntimeError("diagnostic socket returned no response")
        response = json.loads(raw)
        if response.get("request_id") != request_id:
            raise RuntimeError("diagnostic response correlation mismatch")
        if not response.get("ok"):
            raise RuntimeError(response.get("error", "diagnostic request unavailable"))
        return response["result"]
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass
