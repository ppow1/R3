# R3 CONTROLLED SOURCE
# File: runtime/resident_inference.py
# Component: R3-RESIDENT-INFERENCE
# File Revision: 1.0.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Reusable event-driven resident inference against an existing OpenAI-compatible endpoint.
# Execution Model: Async worker invoked by the institutional scheduler; durable SQLite inbox.
# Observability: Inbox status, model response, and failure details persisted in SQLite.
# Dependencies: Python 3.12 standard library; existing model HTTP endpoint.
# Authority: R3 Charter Revision 2; does not alter model or MCP configuration.
# Changed: 2026-11-02 UTC | R3-GRACE-001 | Initial reusable inference/inbox boundary.
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/engineering-test-policy.md
# Tests: Permanent integration contracts pending; no synthetic production work.
# History/Predecessor: New file.
"""Durable resident inbox and inference adapter; external tool routing is not yet connected."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class Inbox:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.execute("""CREATE TABLE IF NOT EXISTS resident_inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resident TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            result TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )""")
        self.db.execute("CREATE INDEX IF NOT EXISTS resident_inbox_pending ON resident_inbox(resident,status,id)")

    def enqueue(self, resident: str, event_type: str, payload: dict) -> int:
        now = time.time()
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO resident_inbox(resident,event_type,payload,created_at,updated_at) VALUES (?,?,?,?,?)",
                (resident, event_type, json.dumps(payload), now, now))
        return int(cursor.lastrowid)

    def next(self, resident: str) -> tuple[int, str, dict] | None:
        row = self.db.execute(
            "SELECT id,event_type,payload FROM resident_inbox WHERE resident=? AND status IN ('PENDING','PROCESSING') ORDER BY id LIMIT 1",
            (resident,)).fetchone()
        if row is None:
            return None
        with self.db:
            self.db.execute("UPDATE resident_inbox SET status='PROCESSING',updated_at=? WHERE id=?",
                            (time.time(), row[0]))
        return int(row[0]), row[1], json.loads(row[2])

    def finish(self, event_id: int, status: str, result: dict) -> None:
        if status not in ("COMPLETED", "FAILED"):
            raise ValueError("Invalid terminal inbox status")
        with self.db:
            self.db.execute(
                "UPDATE resident_inbox SET status=?,result=?,updated_at=? WHERE id=?",
                (status, json.dumps(result), time.time(), event_id))


@dataclass(frozen=True)
class InferenceEndpoint:
    url: str
    model: str
    timeout: float = 120.0

    def __post_init__(self):
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("Inference endpoint must be HTTP(S)")
        if not self.model:
            raise ValueError("Model name is required")

    def complete(self, messages: list[dict]) -> dict:
        request = urllib.request.Request(
            self.url.rstrip("/") + "/chat/completions",
            data=json.dumps({"model": self.model, "messages": messages, "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)


class ResidentInference:
    """Processes genuine durable inbox events, never fabricates periodic resident work."""

    def __init__(self, inbox: Inbox, endpoint: InferenceEndpoint, *, system_prompt: str):
        self.inbox = inbox
        self.endpoint = endpoint
        self.system_prompt = system_prompt

    async def __call__(self, resident: str) -> None:
        event = self.inbox.next(resident)
        if event is None:
            return
        event_id, event_type, payload = event
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps({"event_type": event_type, "payload": payload})},
        ]
        try:
            result = await asyncio.to_thread(self.endpoint.complete, messages)
            choices = result.get("choices") or []
            if not choices or not isinstance(choices[0].get("message"), dict):
                raise RuntimeError("Model returned no usable message")
            message = choices[0]["message"]
            if message.get("tool_calls"):
                # Never report tool requests as executed actions.
                raise RuntimeError("Model requested tools but resident tool dispatcher is not connected")
            self.inbox.finish(event_id, "COMPLETED", {
                "message": message, "usage": result.get("usage"),
                "model": result.get("model"),
            })
        except Exception as exc:
            self.inbox.finish(event_id, "FAILED", {"error": repr(exc)})
            raise
