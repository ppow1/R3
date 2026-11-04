# R3 CONTROLLED SOURCE
# File: runtime/resident_inference.py
# Component: R3-RESIDENT-INFERENCE
# File Revision: 1.3.2
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
# Changed: 2026-11-04 UTC | R3-GRACE-FEEDBACK-LOOP-002 | ChatGPT GPT-6 | Durable lineage repetition detection and blocked outcome.
# Changed: 2026-11-03 UTC | R3-GRACE-RECOVERY-001 | Persist ineffective continuation signal and request alternative method.
# Supersedes: revision 1.3.1
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/engineering-test-policy.md
# Tests: tests/test_inference_http_errors.py (permanent transport diagnostic contract).
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Preserve safe upstream HTTP error codes without leaking request content.
# History/Predecessor: Git blob f890fef537d1463d3ccfca3e660028c03312e732
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

    def finish(self, event_id: int, status: str, result: dict, *, review: dict | None = None) -> None:
        if status not in ("COMPLETED", "FAILED"):
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

    def probe(self) -> None:
        """Confirm the configured model is advertised without retaining response content."""
        request = urllib.request.Request(
            self.url.rstrip("/") + "/models",
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError("Inference endpoint unavailable")
                try:
                    payload = json.load(response)
                except (ValueError, TypeError):
                    raise RuntimeError("Invalid inference model list") from None
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Inference HTTP {exc.code}") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid inference model list")
        advertised = set()
        for key in ("data", "models"):
            entries = payload.get(key)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for field in ("id", "model", "name"):
                    value = entry.get(field)
                    if isinstance(value, str):
                        advertised.add(value)
                aliases = entry.get("aliases")
                if isinstance(aliases, list):
                    advertised.update(value for value in aliases if isinstance(value, str))
        if self.model not in advertised:
            raise RuntimeError("Configured inference model unavailable")

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
                 conversation_store=None):
        self.inbox = inbox
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.tools = tools
        self.continuation_event_types = frozenset(continuation_event_types)
        self.conversation_store = conversation_store

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
        if event_type in self.continuation_event_types and payload.get("recovery_required"):
            continuity_contract += (
                "\nRecovery required: the previous continuation repeated an ineffective "
                "step without new evidence. Reassess the objective, inspect prior "
                "results, and select a materially different authorized method. "
                "Do not claim completion without verified acceptance evidence. "
                "If no authorized alternative exists, report the actual dependency. "
                "A repeated tool observation is not objective progress, even if "
                "other observations such as uptime change. "
                "Do not repeat the same inspection as a substitute for action."
            )
            repeated_tools = payload.get("repeated_tool_observations")
            if isinstance(repeated_tools, list) and repeated_tools:
                continuity_contract += (
                    "\\nPreviously unchanged tool observations: "
                    + json.dumps([name for name in repeated_tools if isinstance(name, str)])
                    + ". Identify the unmet acceptance condition and a different "
                    "authorized action or an explicit external dependency."
                )
            continuity_contract += (""

            )
        if event_type == "CONVERSATION_MESSAGE":
            if self.conversation_store is None:
                raise RuntimeError("Conversation storage is not configured")
            messages = [{"role": "system", "content": self.system_prompt}]
            messages.extend(self.conversation_store.prompt_history(
                payload["conversation_id"], payload["message_id"]))
        else:
            messages = [
                {"role": "system", "content": self.system_prompt + continuity_contract},
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
                if not calls and event_type in self.continuation_event_types:
                    try:
                        decision = json.loads(message.get("content") or "")
                    except (ValueError, TypeError) as exc:
                        raise RuntimeError("Activity requires structured decision") from exc
                    if not isinstance(decision, dict) or decision.get("state") not in ("continue", "complete", "blocked"):
                        raise RuntimeError("Invalid activity state")
                    if decision["state"] == "continue":
                        next_step = decision.get("next_step")
                        if not isinstance(next_step, str) or not next_step.strip():
                            raise RuntimeError("Continuing activity requires next_step")
                        # Durable evidence lineage is independent of the wording
                        # of the proposed next step. This catches alternating or
                        # rephrased plans that recycle the same claimed evidence.
                        import hashlib
                        evidence_key = hashlib.sha256(
                            json.dumps(decision.get("evidence"), sort_keys=True,
                                       default=str).encode()
                        ).hexdigest()
                        previous = payload.get("continuation_evidence", [])
                        if not isinstance(previous, list):
                            previous = []
                        previous = [x for x in previous if isinstance(x, str)]
                        # A model's evidence text is not proof of external progress.
                        # Record whether tool output has repeated across turns.
                        observed = []
                        tool_names = {}
                        for kind, item in self.inbox.history(event_id):
                            if kind == "TOOL_INTENT":
                                tool_names[item.get("tool_call_id")] = item.get("tool")
                            elif kind == "TOOL_RESULT":
                                name = tool_names.get(item.get("tool_call_id"), "unknown")
                                output = item.get("content", "")
                                if not isinstance(output, str):
                                    output = json.dumps(output, sort_keys=True, default=str)
                                observed.append([name, hashlib.sha256(output.encode()).hexdigest()])
                        prior_observations = payload.get("continuation_observations", [])
                        if not isinstance(prior_observations, list):
                            prior_observations = []
                        repeated_tools = sorted({name for name, digest in observed
                                                 if [name, digest] in prior_observations})
                        repeated_without_evidence = evidence_key in previous
                        if repeated_tools:
                            repeated_without_evidence = True
                        recovery_required = repeated_without_evidence
                        # Repeated observations request recovery, but do not
                        # automatically fail an objective: monitoring may be
                        # legitimate and an unchanged result is not a blocker.
                        # The resident must explicitly report state=blocked
                        # when no authorized alternative exists.
                        self.inbox.continue_activity(event_id, resident, event_type, {
                            **payload,
                            "objective": payload.get("objective", payload),
                            "previous_event_id": event_id,
                            "previous_result": decision,
                            "next_step": next_step,
                            "continuation_evidence": [*previous, evidence_key],
                            "continuation_observations": prior_observations + observed,
                            "repeated_tool_observations": repeated_tools,
                            "recovery_required": recovery_required,
                        }, {"decision": decision, "model": result.get("model")})
                        return
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
                    self.inbox.finish(event_id, "COMPLETED" if decision["state"] == "complete" else "FAILED",
                                      {"decision": decision, "model": result.get("model"),
                                       "objective_status": "REPORTED_VERIFIED" if objective_verified else "UNVERIFIED"},
                                      review=review)
                    return
                if not calls:
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
            if event_type == "CONVERSATION_MESSAGE" and self.conversation_store is not None:
                self.conversation_store.fail_event(event_id, type(exc).__name__)
            raise
