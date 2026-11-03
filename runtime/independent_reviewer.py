# R3 CONTROLLED SOURCE
# File: runtime/independent_reviewer.py
# Component: R3-INDEPENDENT-REVIEWER
# File Revision: 1.0.2
# Created: 2026-11-03T01:37:00.460Z
# Created By: Codex
# Purpose: Evaluate durable assignments using independent read-only tool observations.
# Execution Model: Separate configured inference request with native tool continuation.
# Observability: Returned findings retain actual tool outputs in the verification ledger.
# Dependencies: runtime.resident_inference.InferenceEndpoint; runtime.native_tools.NativeTools.
# Authority: Steward verification policy; only configured read-only tools may be invoked.
# Changed: 2026-11-03T01:37:00.460Z | R3-VERIFY-WIRING-001 | Codex | Add independent evidence gathering evaluator.
# Changed: 2026-11-03T02:00:13.409Z | R3-VERIFY-WIRING-003 | Codex | Read durable source event and turn history using a separate read-only SQLite connection.
# Changed: 2026-11-03 UTC | R3-REVIEW-LINEAGE-001 | Codex | Include linked prior and continuation events in independent journal observations.
# Supersedes: None
# Contracts: runtime/verification.py; hints/verification-and-learning.md
# Tests: Existing permanent verification contracts; no new test added.
# History/Predecessor: Git blob 1ceae4c7d417b5fa7b7ee0e751fdabd207c5969e.
"""Independent criterion evaluator that withholds executor-provided evidence."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path

from runtime.native_tools import NativeTools
from runtime.resident_inference import InferenceEndpoint


class IndependentReviewer:
    def __init__(self, endpoint: InferenceEndpoint, tools: NativeTools, system_prompt: str, *, journal_path: str | Path):
        if not system_prompt.strip():
            raise ValueError("Reviewer system prompt required")
        self.endpoint = endpoint
        self.tools = tools
        self.system_prompt = system_prompt
        self.journal_path = Path(journal_path).resolve()

    def probe(self) -> None:
        self.tools.discover()
        request = urllib.request.Request(self.endpoint.url.rstrip("/") + "/models", method="GET")
        with urllib.request.urlopen(request, timeout=self.endpoint.timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError("Reviewer inference endpoint unavailable")

    @staticmethod
    def _compact_lineage_event(item: dict, *, source_event_id: int) -> dict:
        """Remove repeated continuation envelopes while retaining direct journal evidence."""
        event = item["event"]
        payload = dict(event["payload"])
        result = event["result"]
        decision = result.get("decision") if isinstance(result, dict) else None
        state = decision.get("state") if isinstance(decision, dict) else None
        event_id = event.get("id")
        preserve_detail = (
            event_id == source_event_id
            or payload.get("previous_event_id") is None
            or state in ("complete", "blocked")
        )

        if not preserve_detail:
            # These fields are already present in the assignment root or the original
            # review-feedback event. Continuation payloads copy them forward verbatim.
            for key in ("objective", "acceptance_criteria", "source_payload",
                        "findings", "previous_result"):
                payload.pop(key, None)
            if isinstance(result, dict) and isinstance(decision, dict) and state == "continue":
                result = {
                    **({"continuation_event_id": result["continuation_event_id"]}
                       if "continuation_event_id" in result else {}),
                    "decision": {
                        "state": "continue",
                        **({"next_step": decision["next_step"]}
                           if isinstance(decision.get("next_step"), str) else {}),
                    },
                }

        turns = []
        for turn in item["turns"]:
            content = turn.get("content")
            if turn.get("kind") == "ASSISTANT":
                if isinstance(content, dict) and content.get("tool_calls"):
                    # TOOL_INTENT rows below are the durable, normalized record of calls.
                    continue
                if not preserve_detail and state == "continue":
                    # The continuation decision is retained in event.result above.
                    continue
            turns.append(turn)

        compact_event = {**event, "payload": payload, "result": result}
        return {"event": compact_event, "turns": turns}

    @staticmethod
    def _summarize_lineage(events: dict[int, dict], *, source_event_id: int) -> dict:
        """Summarize repeated journal actions while preserving their durable references."""
        event_ids = sorted(events)
        child_event_ids = set()
        event_type_counts = {}
        status_counts = {}
        terminal_events = []
        tool_actions = {}
        call_tools = {}

        def digest(value) -> str:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":")).encode("utf-8")
            return hashlib.sha256(encoded).hexdigest()

        for event_id in event_ids:
            item = events[event_id]
            event = item["event"]
            payload = event["payload"]
            event_type = event["event_type"]
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            status = event["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

            for key in ("source_event_id", "previous_event_id"):
                linked_id = payload.get(key)
                if isinstance(linked_id, int) and not isinstance(linked_id, bool) and linked_id in events:
                    child_event_ids.add(event_id)

            result = event.get("result")
            decision = result.get("decision") if isinstance(result, dict) else None
            state = decision.get("state") if isinstance(decision, dict) else None
            if state != "continue" and result is not None:
                evidence = decision.get("evidence") if isinstance(decision, dict) else None
                terminal_events.append({
                    "event_id": event_id,
                    "event_type": event_type,
                    "status": status,
                    "decision_state": state,
                    "objective_status": result.get("objective_status") if isinstance(result, dict) else None,
                    "result_sha256": digest(result),
                    "evidence_sha256": digest(evidence) if evidence is not None else None,
                })

            for turn in item["turns"]:
                kind = turn.get("kind")
                content = turn.get("content") or {}
                sequence = turn.get("sequence")
                if kind == "TOOL_INTENT":
                    name = content.get("tool")
                    name = name if isinstance(name, str) and name else "<unknown>"
                    params = content.get("params", {})
                    params_digest = digest(params)
                    action = tool_actions.setdefault(name, {
                        "call_count": 0,
                        "parameter_digests": set(),
                        "first_call": None,
                        "last_call": None,
                        "result_count": 0,
                        "first_result": None,
                        "last_result": None,
                        "result_digests": set(),
                        "result_chain": hashlib.sha256(),
                    })
                    reference = {
                        "event_id": event_id,
                        "sequence": sequence,
                        "tool_call_id": content.get("tool_call_id"),
                        "params_sha256": params_digest,
                    }
                    action["call_count"] += 1
                    action["parameter_digests"].add(params_digest)
                    if action["first_call"] is None:
                        action["first_call"] = reference
                    action["last_call"] = reference
                    call_tools[(event_id, content.get("tool_call_id"))] = (name, params)
                elif kind == "TOOL_RESULT":
                    call_id = content.get("tool_call_id")
                    matched = call_tools.get((event_id, call_id))
                    name = matched[0] if matched else "<unmatched>"
                    action = tool_actions.setdefault(name, {
                        "call_count": 0,
                        "parameter_digests": set(),
                        "first_call": None,
                        "last_call": None,
                        "result_count": 0,
                        "first_result": None,
                        "last_result": None,
                        "result_digests": set(),
                        "result_chain": hashlib.sha256(),
                    })
                    result_content = content.get("content")
                    result_digest = digest(result_content)
                    sample = {
                        "event_id": event_id,
                        "sequence": sequence,
                        "tool_call_id": call_id,
                        "content": result_content,
                    }
                    action["result_count"] += 1
                    action["result_digests"].add(result_digest)
                    encoded_digest = result_digest.encode("ascii")
                    action["result_chain"].update(len(encoded_digest).to_bytes(4, "big"))
                    action["result_chain"].update(encoded_digest)
                    if action["first_result"] is None:
                        action["first_result"] = sample
                    action["last_result"] = sample

        root_event_ids = [event_id for event_id in event_ids if event_id not in child_event_ids]
        root_events = [
            IndependentReviewer._compact_lineage_event(
                events[event_id], source_event_id=source_event_id
            )
            for event_id in root_event_ids
        ]

        summarized_actions = {}
        for name, action in sorted(tool_actions.items()):
            summarized_actions[name] = {
                "call_count": action["call_count"],
                "parameter_variant_count": len(action["parameter_digests"]),
                "first_call": action["first_call"],
                "last_call": action["last_call"],
                "result_count": action["result_count"],
                "distinct_result_count": len(action["result_digests"]),
                "result_sequence_sha256": action["result_chain"].hexdigest(),
                "first_result": action["first_result"],
                "last_result": action["last_result"],
            }

        return {
            "event_count": len(event_ids),
            "event_ids": event_ids,
            "root_event_ids": root_event_ids,
            "event_type_counts": event_type_counts,
            "status_counts": status_counts,
            "terminal_events": terminal_events,
            "root_events": root_events,
            "tool_actions": summarized_actions,
        }

    def _observe_journal(self, request: dict) -> dict:
        source_event_id = request.get("source_event_id")
        if isinstance(source_event_id, bool) or not isinstance(source_event_id, int):
            raise ValueError("Review request has no source event identifier")
        uri = self.journal_path.as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=self.endpoint.timeout)
        try:
            pending = [source_event_id]
            events = {}
            while pending:
                event_id = pending.pop()
                if event_id in events:
                    continue
                row = connection.execute(
                    "SELECT id,resident,event_type,payload,status,result "
                    "FROM resident_inbox WHERE id=?", (event_id,)
                ).fetchone()
                if row is None:
                    raise LookupError("A linked assignment event is unavailable")
                payload = json.loads(row[3])
                if payload.get("assignment_id") != request.get("assignment_id"):
                    raise ValueError("Assignment lineage contains another assignment")
                if payload.get("acceptance_criteria") != request.get("criteria"):
                    raise ValueError("Assignment lineage criteria changed")
                turns = connection.execute(
                    "SELECT seq,kind,content FROM resident_turns WHERE event_id=? ORDER BY seq",
                    (event_id,),
                ).fetchall()
                events[event_id] = {
                    "event": {
                        "id": row[0], "resident": row[1], "event_type": row[2],
                        "payload": payload, "status": row[4],
                        "result": json.loads(row[5]) if row[5] else None,
                    },
                    "turns": [
                        {"sequence": item[0], "kind": item[1], "content": json.loads(item[2])}
                        for item in turns
                    ],
                }

                links = []
                for key in ("source_event_id", "previous_event_id"):
                    if key in payload:
                        linked_id = payload[key]
                        if isinstance(linked_id, bool) or not isinstance(linked_id, int):
                            raise ValueError("Assignment lineage contains an invalid event link")
                        links.append(linked_id)
                result = events[event_id]["event"]["result"]
                if isinstance(result, dict) and "continuation_event_id" in result:
                    linked_id = result["continuation_event_id"]
                    if isinstance(linked_id, bool) or not isinstance(linked_id, int):
                        raise ValueError("Assignment continuation contains an invalid event link")
                    links.append(linked_id)
                pending.extend(link for link in links if link not in events)

            if source_event_id not in events:
                raise LookupError("Review source event is unavailable")
            primary = events[source_event_id]
            lineage_event_ids = sorted(events)
            return {
                "event": primary["event"],
                "turns": primary["turns"],
                "lineage_event_ids": lineage_event_ids,
                "lineage_summary": self._summarize_lineage(
                    events, source_event_id=source_event_id),
            }
        finally:
            connection.close()

    def __call__(self, request: dict) -> dict:
        criteria = request.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError("Review request has no acceptance criteria")
        journal = self._observe_journal(request)
        descriptors = self.tools.discover()
        by_name = {item["tool"]: item for item in descriptors}
        definitions = [item["definition"] for item in descriptors]
        journal_id = "journal-event-" + str(request["source_event_id"])
        observations = {
            journal_id: {
                "source": "read-only-r3-journal",
                "observed_at": time.time(),
                "result": journal,
            }
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps({
                "assignment_id": request["assignment_id"],
                "acceptance_criteria": criteria,
                "journal_observation_id": journal_id,
                "journal_observation": journal,
                "available_tools": [
                    {"tool": item["tool"], "read_only": item["read_only"]}
                    for item in descriptors
                ],
            }, ensure_ascii=False)},
        ]
        next_observation = 1
        while True:
            response = self.endpoint.complete(messages, definitions)
            choices = response.get("choices") or []
            if not choices or not isinstance(choices[0].get("message"), dict):
                raise RuntimeError("Reviewer returned no usable message")
            message = choices[0]["message"]
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                try:
                    assessment = json.loads(message.get("content") or "")
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("Reviewer response is not JSON") from exc
                break
            for call in calls:
                function = call.get("function") or {}
                name = function.get("name")
                call_id = call.get("id")
                if not isinstance(call_id, str) or not call_id or name not in by_name:
                    raise RuntimeError("Reviewer requested an unavailable tool")
                arguments = function.get("arguments", "{}")
                params = json.loads(arguments) if isinstance(arguments, str) else arguments
                if not isinstance(params, dict):
                    raise RuntimeError("Reviewer tool arguments must be an object")
                observation_id = "obs-" + str(next_observation)
                next_observation += 1
                try:
                    raw = self.tools.invoke(by_name[name], params)
                    value = json.loads(raw)
                    observations[observation_id] = {
                        "tool": name, "observed_at": time.time(), "result": value,
                    }
                    content = json.dumps({"observation_id": observation_id, "result": value},
                                         ensure_ascii=False)
                except Exception as exc:
                    content = json.dumps({"tool": name, "error": type(exc).__name__})
                messages.append({
                    "role": "tool", "tool_call_id": call_id, "content": content,
                })
        if not isinstance(assessment, dict) or not isinstance(assessment.get("findings"), list):
            raise RuntimeError("Reviewer response must contain findings")
        expected = [item.get("id") for item in criteria if isinstance(item, dict)]
        received = [item.get("criterion_id") for item in assessment["findings"]
                    if isinstance(item, dict)]
        if len(expected) != len(criteria) or len(received) != len(expected) or set(received) != set(expected):
            raise RuntimeError("Reviewer findings must cover each criterion exactly once")
        findings = []
        for finding in assessment["findings"]:
            result = finding.get("result")
            reason = finding.get("reason")
            if result not in ("PASS", "FAIL", "INSUFFICIENT_EVIDENCE"):
                result = "INSUFFICIENT_EVIDENCE"
            if not isinstance(reason, str) or not reason.strip():
                reason = "Reviewer did not provide an evidence-based reason."
            ids = finding.get("observation_ids")
            if not isinstance(ids, list):
                ids = []
            selected = [observations[item] for item in ids
                        if isinstance(item, str) and item in observations]
            if result in ("PASS", "FAIL") and not selected:
                result = "INSUFFICIENT_EVIDENCE"
                reason = "No successful independent tool observation supports this finding."
            findings.append({
                "criterion_id": finding["criterion_id"],
                "result": result,
                "reason": reason,
                "evidence": {
                    "independent_observation": bool(selected),
                    "observations": selected,
                },
            })
        return {
            "implementation_revision": "source-event:" + str(request["source_event_id"]),
            "findings": findings,
        }
