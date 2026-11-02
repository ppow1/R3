# R3 CONTROLLED SOURCE
# File: runtime/resident_inference.py
# Component: R3-RESIDENT-INFERENCE
# File Revision: 1.1.1
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Reusable event-driven resident inference against an existing OpenAI-compatible endpoint.
# Execution Model: Async worker invoked by the institutional scheduler; durable SQLite inbox.
# Observability: Inbox status, model response, and failure details persisted in SQLite.
# Dependencies: Python 3.12 standard library; existing model HTTP endpoint.
# Authority: R3 Charter Revision 2; does not alter model or MCP configuration.
# Changed: 2026-11-02 UTC | R3-GRACE-001 | Initial reusable inference/inbox boundary.
# Changed: 2026-11-02 UTC | R3-GRACE-004 | Durable tool-call continuation with fail-closed recovery
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/engineering-test-policy.md
# Tests: tests/test_inference_http_errors.py (permanent transport diagnostic contract).
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Preserve safe upstream HTTP error codes without leaking request content.
# History/Predecessor: Git blob b522510df9655189de7e8bcf52503535e3cc2995
"""Durable resident inbox and inference adapter; tool routing uses existing llama.cpp /tools adapter."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from runtime.llama_tools import LlamaTools


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
        self.db.execute("""CREATE TABLE IF NOT EXISTS resident_turns (
            event_id INTEGER NOT NULL, seq INTEGER NOT NULL,
            kind TEXT NOT NULL, content TEXT NOT NULL,
            PRIMARY KEY(event_id, seq)
        )""")

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

    def history(self, event_id: int) -> list[tuple[str, dict]]:
        rows = self.db.execute(
            "SELECT kind,content FROM resident_turns WHERE event_id=? ORDER BY seq",
            (event_id,),
        ).fetchall()
        return [(kind, json.loads(content)) for kind, content in rows]

    def record(self, event_id: int, kind: str, content: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO resident_turns(event_id,seq,kind,content) "
                "VALUES (?,COALESCE((SELECT MAX(seq)+1 FROM resident_turns WHERE event_id=?),0),?,?)",
                (event_id, event_id, kind, json.dumps(content)),
            )

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

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        request = urllib.request.Request(
            self.url.rstrip("/") + "/chat/completions",
            data=json.dumps({"model": self.model, "messages": messages, "stream": False, **({"tools": tools} if tools else {})}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Error messages may echo sensitive prompts or tool results.
            # Retain upstream error classification without persisting its body.
            detail = ""
            try:
                data = json.loads(exc.read(65536))
                error = data.get("error") if isinstance(data, dict) else None
                if isinstance(error, dict):
                    values = (error.get("type"), error.get("code"))
                    safe = [str(v)[:80] for v in values
                            if isinstance(v, (str, int)) and not isinstance(v, bool)]
                    detail = " (" + ", ".join(safe) + ")" if safe else ""
            except (ValueError, OSError, TypeError):
                pass
            raise RuntimeError(f"Inference HTTP {exc.code}{detail}") from None


class ResidentInference:
    """Continue genuine events, preserving tool results and refusing uncertain replay."""

    def __init__(self, inbox: Inbox, endpoint: InferenceEndpoint, *,
                 system_prompt: str, tools: LlamaTools | None = None):
        self.inbox = inbox
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.tools = tools

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
            history = self.inbox.history(event_id)
            pending = set()
            for kind, item in history:
                if kind == "ASSISTANT":
                    messages.append(item)
                elif kind == "TOOL_INTENT":
                    pending.add(item["tool_call_id"])
                elif kind == "TOOL_RESULT":
                    pending.discard(item["tool_call_id"])
                    messages.append(item)
            if pending:
                raise RuntimeError("Uncertain tool outcome requires reconciliation; no replay")
            descriptors = await asyncio.to_thread(self.tools.discover) if self.tools else []
            definitions = [d["definition"] for d in descriptors]
            by_name = {d["tool"]: d for d in descriptors}
            while True:
                result = await asyncio.to_thread(self.endpoint.complete, messages, definitions)
                choices = result.get("choices") or []
                if not choices or not isinstance(choices[0].get("message"), dict):
                    raise RuntimeError("Model returned no usable message")
                message = choices[0]["message"]
                calls = message.get("tool_calls") or []
                self.inbox.record(event_id, "ASSISTANT", message)
                messages.append(message)
                if not calls:
                    self.inbox.finish(event_id, "COMPLETED", {
                        "message": message, "usage": result.get("usage"),
                        "model": result.get("model"),
                    })
                    return
                if not self.tools:
                    raise RuntimeError("Tool execution not configured")
                for call in calls:
                    function = call.get("function") or {}
                    name = function.get("name")
                    call_id = call.get("id")
                    if not isinstance(call_id, str) or not call_id or name not in by_name:
                        raise RuntimeError("Invalid or unknown tool call")
                    arguments = function.get("arguments", "{}")
                    params = json.loads(arguments) if isinstance(arguments, str) else arguments
                    if not isinstance(params, dict):
                        raise RuntimeError("Tool arguments must be an object")
                    self.inbox.record(event_id, "TOOL_INTENT", {
                        "tool_call_id": call_id, "tool": name, "params": params,
                    })
                    try:
                        output = await asyncio.to_thread(
                            self.tools.invoke, by_name[name], params,
                        )
                    except Exception as exc:
                        output = json.dumps({"error": str(exc)})
                    tool_message = {
                        "role": "tool", "tool_call_id": call_id, "content": output,
                    }
                    self.inbox.record(event_id, "TOOL_RESULT", tool_message)
                    messages.append(tool_message)
        except Exception as exc:
            self.inbox.finish(event_id, "FAILED", {"error": repr(exc)})
            raise
