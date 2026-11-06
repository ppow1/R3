# R3 CONTROLLED SOURCE
# File: runtime/resident_inference.py
# Component: R3-RESIDENT-INFERENCE
# File Revision: 1.4.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Reusable event-driven resident inference against an existing OpenAI-compatible endpoint.
# Execution Model: Async worker invoked by the institutional scheduler; durable SQLite inbox.
# Observability: Inbox status, model response, and failure details persisted in SQLite.
# Dependencies: Python 3.12 standard library; existing model HTTP endpoint.
# Authority: R3 Charter Revision 2; does not alter model or MCP configuration.
# Changed: 2026-11-02 UTC | R3-GRACE-001 | Initial reusable inference/inbox boundary.
# Changed: 2026-11-02 UTC | R3-GRACE-004 | Durable tool-call continuation with fail-closed recovery
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-005 | Atomically queue review on completion with explicit criteria.
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-006 | Preserve assignment metadata across activity continuation.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-002 | Preserve evidence-backed blocked state as durable unresolved outcome.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-003 | Block repeated no-progress continuation, preserving durable evidence.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-004 | Include tool results observed during the active inference turn.
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-005 | Authority-referenced idempotent blocked activity resumption.\n# Supersedes: None
# Changed: 2026-11-05 UTC | R3-GRACE-RECOVERY-006 | Require canonical exact-grant authorization and audit for blocked activity resumption.
# Changed: 2026-11-06T02:31:00Z | GRACE-AUTONOMY-P3 | Codex GPT-6 | Bound durable continuation chains and escalate exhausted work instead of looping.
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/engineering-test-policy.md
# Tests: tests/test_inference_http_errors.py; tests/test_resident_continuity.py
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Preserve safe upstream HTTP error codes without leaking request content.
# History/Predecessor: Git blob 1e433f2ddb10f439ef7599bf48a19c6fb11ea2c0; immediate predecessor blob 82761cbeb022e623295237b3aed3048694fe51cf.
"""Durable resident inbox and inference adapter; tool routing uses existing llama.cpp /tools adapter."""
from __future__ import annotations

import asyncio
import inspect
import json
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from runtime.llama_tools import LlamaTools
from runtime.verification import VerificationLedger


class Inbox:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        VerificationLedger(db)
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

    def continue_activity(self, event_id, resident, event_type, payload, result):
        """Atomically close one activity turn and queue the next."""
        now = time.time()
        with self.db:
            row = self.db.execute("SELECT status FROM resident_inbox WHERE id=?", (event_id,)).fetchone()
            if row is None or row[0] != "PROCESSING":
                raise RuntimeError("Activity continuation requires PROCESSING event")
            cursor = self.db.execute(
                "INSERT INTO resident_inbox(resident,event_type,payload,created_at,updated_at) VALUES (?,?,?,?,?)",
                (resident, event_type, json.dumps(payload), now, now))
            self.db.execute(
                "UPDATE resident_inbox SET status='COMPLETED',result=?,updated_at=? WHERE id=?",
                (json.dumps({**result, "continuation_event_id": cursor.lastrowid}), now, event_id))
        return int(cursor.lastrowid)

    def resume_blocked(self, event_id: int, *, authority, principal: str,
                       resolution_evidence: str) -> int:
        """Resume only under an effective exact R3 grant, preserving the blocked record."""
        if not isinstance(principal, str) or not principal.strip():
            raise ValueError("Resumption requires an authenticated authority principal")
        if not isinstance(resolution_evidence, str) or not resolution_evidence.strip():
            raise ValueError("Resumption requires dependency resolution evidence")
        if (authority is None
                or not callable(getattr(authority, "authorize", None))
                or not callable(getattr(authority, "audit", None))):
            raise ValueError("Audited canonical R3 authority is required for resumption")
        row = self.db.execute(
            "SELECT resident,event_type,payload,status,result FROM resident_inbox WHERE id=?",
            (event_id,),
        ).fetchone()
        if row is None or row[3] != "BLOCKED" or row[1] != "RESIDENT_ACTIVITY":
            raise ValueError("Resumption requires a BLOCKED resident activity")
        payload = json.loads(row[2])
        assignment_id = payload.get("assignment_id")
        scope_ref = ("assignment:" + assignment_id
                     if isinstance(assignment_id, str) and assignment_id.strip()
                     else "resident-inbox-event:" + str(event_id))
        grant = authority.authorize(
            principal=principal,
            action="resident.activity.resume",
            scope_ref=scope_ref,
            resource_id=scope_ref,
            operation="write",
        )
        if not isinstance(grant, dict) or not isinstance(grant.get("grant_id"), str):
            raise PermissionError("Canonical authority returned no grant identity")
        grant_id = grant["grant_id"]
        authority.audit({
            "principal": principal,
            "capability": "resident-inbox",
            "action": "resident.activity.resume",
            "scope_ref": scope_ref,
            "correlation_id": "resident-inbox-resume:" + str(event_id),
            "grant_id": grant_id,
            "outcome": "AUTHORIZED",
            "resource_ref": scope_ref,
            "operation": "write",
        })
        with self.db:
            row = self.db.execute(
                "SELECT resident,event_type,payload,status,result FROM resident_inbox WHERE id=?",
                (event_id,),
            ).fetchone()
            if row is None or row[3] != "BLOCKED" or row[1] != "RESIDENT_ACTIVITY":
                raise ValueError("Resumption requires a BLOCKED resident activity")
            resident, event_type, raw_payload, _, raw_result = row
            for successor_id, raw in self.db.execute(
                "SELECT id,payload FROM resident_inbox WHERE resident=? AND event_type=?",
                (resident, event_type),
            ):
                existing = json.loads(raw)
                if existing.get("resumed_from_blocked_event_id") == event_id:
                    if (existing.get("resumption_grant_id") != grant_id
                            or existing.get("resumption_principal") != principal
                            or existing.get("resumption_evidence") != resolution_evidence):
                        raise ValueError("Blocked activity already resumed with different evidence")
                    return int(successor_id)
            payload = {
                **json.loads(raw_payload),
                "previous_event_id": event_id,
                "previous_result": json.loads(raw_result or "{}"),
                "resumed_from_blocked_event_id": event_id,
                "resumption_grant_id": grant_id,
                "resumption_principal": principal,
                "resumption_scope_ref": scope_ref,
                "resumption_evidence": resolution_evidence,
            }
            now = time.time()
            cursor = self.db.execute(
                "INSERT INTO resident_inbox(resident,event_type,payload,created_at,updated_at) VALUES (?,?,?,?,?)",
                (resident, event_type, json.dumps(payload), now, now),
            )
            blocked_result = json.loads(raw_result or "{}")
            blocked_result["resumed_event_id"] = int(cursor.lastrowid)
            self.db.execute(
                "UPDATE resident_inbox SET result=?,updated_at=? WHERE id=?",
                (json.dumps(blocked_result), now, event_id),
            )
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

    def continuation_depth(self, payload: dict) -> int:
        """Count durable continuation links, stopping at an authorized resume root."""
        if not isinstance(payload, dict):
            return 0
        resume_root = payload.get("resumed_from_blocked_event_id")
        cursor = payload.get("previous_event_id")
        visited = set()
        depth = 0
        while isinstance(cursor, int) and not isinstance(cursor, bool):
            if cursor in visited or (isinstance(resume_root, int) and cursor == resume_root):
                break
            visited.add(cursor)
            depth += 1
            row = self.db.execute(
                "SELECT payload FROM resident_inbox WHERE id=?", (cursor,)
            ).fetchone()
            if row is None:
                break
            previous = json.loads(row[0]).get("previous_event_id")
            cursor = previous if isinstance(previous, int) else None
        return depth

    def record(self, event_id: int, kind: str, content: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO resident_turns(event_id,seq,kind,content) "
                "VALUES (?,COALESCE((SELECT MAX(seq)+1 FROM resident_turns WHERE event_id=?),0),?,?)",
                (event_id, event_id, kind, json.dumps(content)),
            )

    def finish(self, event_id: int, status: str, result: dict, *, review: dict | None = None) -> None:
        if status not in ("COMPLETED", "FAILED", "BLOCKED"):
            raise ValueError("Invalid terminal inbox status")
        with self.db:
            if review is not None:
                if status != "COMPLETED":
                    raise ValueError("Only completed activities may request review")
                VerificationLedger(self.db).submit_review(
                    event_id, review["assignment_id"], review["criteria"], review["evidence"])
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
                 system_prompt: str, tools: LlamaTools | None = None,
                 continuation_event_types: tuple[str, ...] = (),
                 conversation_store=None, max_continuations: int = 8):
        if isinstance(max_continuations, bool) or not isinstance(max_continuations, int) or max_continuations < 1:
            raise ValueError("max_continuations must be a positive integer")
        self.inbox = inbox
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.tools = tools
        self.continuation_event_types = frozenset(continuation_event_types)
        self.conversation_store = conversation_store
        self.max_continuations = max_continuations

    async def __call__(self, resident: str) -> None:
        event = self.inbox.next(resident)
        if event is None:
            return
        event_id, event_type, payload = event
        continuity_contract = (
            "\n\nResident activity continuity: an activity turn is not the objective itself. "
            "Carry forward the original objective and prior evidence. "
            "Use state=continue with a specific next_step when an authorized, meaningful "
            "action remains; use state=blocked when an external dependency prevents progress; "
            "use state=complete only when the assigned objective is satisfied, "
            "not merely because a tool call or investigation ended. "
            "Set objective_verified=true only when the objective's acceptance conditions "
            "are supported by observed evidence; otherwise omit it or set false. "
            "Never invent a next action or repeat an ineffective step."
        ) if event_type in self.continuation_event_types else ""
        continuation_depth = 0
        continuation_limit_reached = False
        if event_type == "CONVERSATION_MESSAGE":
            if self.conversation_store is None:
                raise RuntimeError("Conversation storage is not configured")
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_store.prompt_history(
                payload["conversation_id"], payload["message_id"]))
        else:
            continuation_depth = self.inbox.continuation_depth(payload)
            continuation_limit_reached = (
                event_type in self.continuation_event_types
                and continuation_depth >= self.max_continuations
            )
            messages = [
                {"role": "system", "content": self.system_prompt + continuity_contract + (
                    " Continuation budget is exhausted; use existing evidence to report complete or blocked, "
                    "and request escalation if criteria are unmet." if continuation_limit_reached else ""
                )},
                {"role": "user", "content": json.dumps({"event_type": event_type, "payload": payload})},
            ]
        try:
            history = self.inbox.history(event_id)
            pending = set()
            observed_tool_result = False
            for kind, item in history:
                if kind == "ASSISTANT":
                    messages.append(item)
                elif kind == "TOOL_INTENT":
                    pending.add(item["tool_call_id"])
                elif kind == "TOOL_RESULT":
                    observed_tool_result = True
                    pending.discard(item["tool_call_id"])
                    messages.append(item)
            if pending:
                raise RuntimeError("Uncertain tool outcome requires reconciliation; no replay")
            descriptors = await asyncio.to_thread(self.tools.discover) if self.tools else []
            if continuation_limit_reached:
                descriptors = []
            definitions = [d["definition"] for d in descriptors]
            by_name = {d["tool"]: d for d in descriptors}
            while True:
                complete = self.endpoint.complete
                result = (await complete(messages, definitions)
                          if inspect.iscoroutinefunction(complete)
                          else await asyncio.to_thread(complete, messages, definitions))
                choices = result.get("choices") or []
                if not choices or not isinstance(choices[0].get("message"), dict):
                    raise RuntimeError("Model returned no usable message")
                message = choices[0]["message"]
                calls = message.get("tool_calls") or []
                self.inbox.record(event_id, "ASSISTANT", message)
                messages.append(message)
                if continuation_limit_reached and calls:
                    self.inbox.finish(event_id, "BLOCKED", {
                        "decision": {"state": "blocked", "reason": "Continuation budget exhausted"},
                        "objective_status": "BLOCKED",
                        "dependency": "Bounded continuation limit reached; Steward review required",
                        "continuation_depth": continuation_depth,
                        "continuation_limit": self.max_continuations,
                        "escalation_required": True,
                    })
                    return
                if not calls and event_type in self.continuation_event_types:
                    try:
                        decision = json.loads(message.get("content") or "")
                    except (ValueError, TypeError) as exc:
                        raise RuntimeError("Activity requires structured decision") from exc
                    if not isinstance(decision, dict) or decision.get("state") not in ("continue", "complete", "blocked"):
                        raise RuntimeError("Invalid activity state")
                    if decision["state"] == "continue":
                        if continuation_limit_reached:
                            self.inbox.finish(event_id, "BLOCKED", {
                                "decision": decision,
                                "objective_status": "BLOCKED",
                                "dependency": "Bounded continuation limit reached; Steward review required",
                                "continuation_depth": continuation_depth,
                                "continuation_limit": self.max_continuations,
                                "escalation_required": True,
                            })
                            return
                        next_step = decision.get("next_step")
                        if not isinstance(next_step, str) or not next_step.strip():
                            raise RuntimeError("Continuing activity requires next_step")
                        prior = payload.get("previous_result")
                        # An identical proposed action with identical evidence and no
                        # newly observed tool result is not a meaningful continuation.
                        # Do not invent progress or enqueue an infinite feedback loop.
                        if (isinstance(prior, dict)
                                and prior.get("state") == "continue"
                                and prior.get("next_step") == next_step
                                and prior.get("evidence") == decision.get("evidence")
                                and not observed_tool_result):
                            self.inbox.finish(event_id, "BLOCKED", {
                                "decision": decision,
                                "model": result.get("model"),
                                "objective_status": "BLOCKED",
                                "dependency": "Repeated continuation without new evidence",
                                "previous_event_id": payload.get("previous_event_id"),
                                "previous_result": prior,
                            })
                            return
                        self.inbox.continue_activity(event_id, resident, event_type, {
                            **payload,
                            "objective": payload.get("objective", payload),
                            "previous_event_id": event_id,
                            "previous_result": decision,
                            "next_step": next_step,
                        }, {"decision": decision, "model": result.get("model")})
                        return
                    if decision["state"] == "blocked":
                        # Keep reported external dependencies distinct from tool/runtime errors.
                        # A blocked activity has not met objective acceptance criteria.
                        explanations = (
                            decision.get("dependency"), decision.get("reason"),
                            decision.get("evidence"),
                        )
                        if not any(
                            (isinstance(item, str) and bool(item.strip()))
                            or (isinstance(item, (dict, list)) and bool(item))
                            for item in explanations
                        ):
                            raise RuntimeError("Blocked activity requires dependency evidence")
                    # An inbox turn is not the same thing as a verified objective.
                    # Keep objective status explicit in durable results so downstream
                    # observers cannot mistake a model's 'complete' for acceptance.
                    objective_verified = (
                        decision["state"] == "complete"
                        and decision.get("objective_verified") is True
                        and isinstance(decision.get("evidence"), (dict, list, str))
                        and bool(decision.get("evidence"))
                    )
                    criteria = payload.get("acceptance_criteria")
                    assignment_id = payload.get("assignment_id")
                    review = None
                    if (decision["state"] == "complete" and isinstance(assignment_id, str)
                            and assignment_id.strip() and isinstance(criteria, list) and criteria):
                        review = {
                            "assignment_id": assignment_id,
                            "criteria": criteria,
                            "evidence": decision.get("evidence", {}),
                        }
                    terminal = "BLOCKED" if decision["state"] == "blocked" else "COMPLETED"
                    objective_status = (
                        "BLOCKED" if terminal == "BLOCKED"
                        else "REPORTED_VERIFIED" if objective_verified else "UNVERIFIED"
                    )
                    self.inbox.finish(event_id, terminal,
                                      {"decision": decision, "model": result.get("model"),
                                       "objective_status": objective_status},
                                      review=review)
                    return
                if not calls:
                    if event_type == "CONVERSATION_MESSAGE":
                        content = message.get("content")
                        if not isinstance(content, str) or not content.strip():
                            raise RuntimeError("Model returned an empty conversation reply")
                    self.inbox.finish(event_id, "COMPLETED", {
                        "message": message, "usage": result.get("usage"),
                        "model": result.get("model"),
                    })
                    if event_type == "CONVERSATION_MESSAGE":
                        self.conversation_store.complete_event(
                            event_id, resident, str(message.get("content") or ""))
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
                            correlation_id=call_id,
                        )
                    except Exception as exc:
                        output = json.dumps({"error": str(exc)})
                    tool_message = {
                        "role": "tool", "tool_call_id": call_id, "content": output,
                    }
                    self.inbox.record(event_id, "TOOL_RESULT", tool_message)
                    observed_tool_result = True
                    messages.append(tool_message)
        except Exception as exc:
            self.inbox.finish(event_id, "FAILED", {"error": repr(exc)})
            if event_type == "CONVERSATION_MESSAGE" and self.conversation_store is not None:
                self.conversation_store.fail_event(event_id, type(exc).__name__)
            raise
