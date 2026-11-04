# R3 CONTROLLED SOURCE
# File: runtime/grace_native_capabilities.py
# Component: R3-GRACE-OPERATIONAL-TOOLS
# File Revision: 1.0.0
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Reusable live local-resource observation and governed durable evidence submission.
# Execution Model: Explicit registration into authenticated R3 capability gateway only.
# Observability: Fresh OS probe metadata; evidence event in canonical R3 institution journal.
# Dependencies: Python stdlib; runtime/resource_registry.py; runtime/governed_tools.py.
# Authority: Steward R3 integration directive; no implicit grants, no R2 application services.
# Changed: 2026-11-04 UTC | R3-GRACE-TOOLS-001 | Add useful general-purpose read and durable write capabilities.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md; issues #16, #28 and #29.
# Tests: tests/test_grace_native_capabilities.py
# History/Predecessor: New module; opt-in only until shared authority integration.
"""R3 resident tools. Neither registration nor discovery confers authority."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import time

from runtime.capabilities import AuthorityUnavailable, CapabilityDenied
from runtime.governed_tools import (
    ExecutionContext, GovernedCapability, GovernedToolGateway)
from runtime.resource_registry import Resource, ResourceRegistry


def local_host_observations():
    """Probe ONLY the local host; do not claim remote hosts or GPUs are online."""
    host = platform.node() or "local"
    capacity = {"cpu_logical_count": os.cpu_count()}
    state = "online"
    try:
        disk = shutil.disk_usage("/")
        capacity["root_disk_total_bytes"] = disk.total
        capacity["root_disk_free_bytes"] = disk.free
    except OSError:
        state = "degraded"
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        capacity["ram_total_bytes"] = int(page_size) * int(page_count)
    except (AttributeError, OSError, ValueError):
        capacity["ram_total_bytes"] = None
    yield Resource(
        resource_id="host:" + host,
        kind="physical-host",
        host=host,
        capabilities=("os.cpu_capacity", "os.memory_capacity", "os.disk_capacity"),
        capacity=capacity,
        observed_at=datetime.now(timezone.utc).isoformat(),
        state=state,
        source="r3:local-os-probe",
    )


class EvidenceJournal:
    """Append resident evidence to the EXISTING R3 institution event journal.

    This does not implement another queue, status authority or approval system.
    The event is a resident claim, never independent acceptance or completion.
    """

    def __init__(self, database: str | Path):
        self.database = Path(database)
        if not self.database.is_file():
            raise AuthorityUnavailable("R3 institution journal unavailable")
        try:
            with self._connect() as db:
                db.execute("SELECT id,at,resident,kind,detail FROM events LIMIT 0")
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("R3 institution events table unavailable") from exc

    def _connect(self):
        return sqlite3.connect(
            "file:" + str(self.database.resolve()) + "?mode=rw",
            uri=True, timeout=5)

    def record(self, params: dict, context: ExecutionContext) -> dict:
        if (context.operation != "write" or context.action != "evidence.record"
                or context.resource_id != "journal:institution"):
            raise CapabilityDenied("Incorrect authority for evidence submission")
        if params.get("scope_ref") != context.scope_ref:
            raise CapabilityDenied("Scope mismatch")
        if any(k in params for k in ("principal", "principal_id", "grant_id", "approved", "accepted")):
            raise CapabilityDenied("Executor does not accept claims of identity or approval")
        objective = params.get("objective_id")
        statement = params.get("statement")
        refs = params.get("evidence_refs", [])
        if (not isinstance(objective, str) or not objective
                or not isinstance(statement, str) or not statement
                or not isinstance(refs, list)
                or any(not isinstance(r, str) or not r for r in refs)):
            raise CapabilityDenied("Objective, statement and evidence references required")
        detail = json.dumps({
            "objective_id": objective,
            "statement": statement,
            "evidence_refs": refs,
            "correlation_id": context.correlation_id,
            "grant_id": context.grant_id,
            "principal_id": context.principal,
            "scope_ref": context.scope_ref,
            "acceptance": "NOT_INDEPENDENTLY_VERIFIED",
        }, sort_keys=True)
        try:
            with self._connect() as db:
                cursor = db.execute(
                    "INSERT INTO events(at,resident,kind,detail) VALUES (?,?,?,?)",
                    (time.time(), context.principal, "EVIDENCE_SUBMITTED", detail))
                return {"event_id": cursor.lastrowid,
                        "review_status": "NOT_INDEPENDENTLY_VERIFIED"}
        except sqlite3.Error as exc:
            raise AuthorityUnavailable("Could not append R3 evidence event") from exc


def register_grace_operational_tools(
        gateway: GovernedToolGateway,
        *, resources: ResourceRegistry | None = None,
        evidence_journal: EvidenceJournal | None = None) -> None:
    """Register durable general-purpose tools; canonical grants are external."""
    resources = resources if resources is not None else ResourceRegistry((local_host_observations,))
    gateway.register(GovernedCapability(
        name="r3.resources.local_snapshot",
        resource_id="registry:local",
        action="inventory.snapshot",
        operation="read",
        description="Observe fresh local R3 host CPU, memory and storage capacity",
        parameters={"type": "object", "properties": {
            "scope_ref": {"type": "string"}}, "required": ["scope_ref"],
            "additionalProperties": False},
        executor=lambda _params, _context: {"resources": resources.snapshot()},
    ))
    if evidence_journal is not None:
        gateway.register(GovernedCapability(
            name="r3.evidence.record",
            resource_id="journal:institution",
            action="evidence.record",
            operation="write",
            description="Append a durable, unverified resident evidence claim for independent review",
            parameters={"type": "object", "properties": {
                "scope_ref": {"type": "string"}, "objective_id": {"type": "string"},
                "statement": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}}},
                "required": ["scope_ref", "objective_id", "statement"],
                "additionalProperties": False},
            executor=evidence_journal.record,
        ))
