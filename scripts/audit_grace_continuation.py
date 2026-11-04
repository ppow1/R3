#!/usr/bin/env python3
# R3 CONTROLLED SOURCE
# File: scripts/audit_grace_continuation.py
# Component: R3-GRACE-LINEAGE-AUDIT
# File Revision: 1.0.0
# Created: 2026-11-04 UTC
# Created By: ChatGPT GPT-6
# Purpose: Read-only, reusable production continuation lineage and tool-evidence audit.
# Execution Model: Explicit CLI; read-only SQLite connection.
# Observability: Aggregate event lineage, tool call counts, terminal disposition.
# Dependencies: Python 3 standard library.
# Authority: Steward-directed Grace autonomy qualification; no runtime writes.
# Changed: 2026-11-04 UTC | R3-GRACE-LINEAGE-AUDIT-001 | Initial general-purpose diagnostic.
# Supersedes: None
# Contracts: AI_HINTS.md; hints/engineering-test-policy.md
# Tests: No synthetic production events; query is read-only.
"""Summarize durable continuation chains without disclosing objective or tool payloads."""
import argparse
import collections
import json
import sqlite3

def read_json(value):
    try:
        return json.loads(value) if value else {}
    except (TypeError, ValueError):
        return {}

def audit(path, event_type):
    db = sqlite3.connect("file:" + path + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT id, resident, payload, result, status FROM resident_inbox "
        "WHERE event_type=? ORDER BY id", (event_type,)
    ).fetchall()
    by_id = {row["id"]: row for row in rows}
    parent = {}
    for row in rows:
        previous = read_json(row["payload"]).get("previous_event_id")
        if isinstance(previous, int) and previous in by_id:
            parent[row["id"]] = previous
    children = collections.defaultdict(list)
    for child, previous in parent.items():
        children[previous].append(child)
    roots = [row for row in rows if row["id"] not in parent]
    print("event_type=", event_type, "events=", len(rows), "roots=", len(roots))
    for root in roots:
        visited = set()
        queue = [root["id"]]
        lineage = []
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            lineage.append(current)
            queue.extend(children[current])
        if not lineage:
            continue
        final = by_id[max(lineage)]
        states = collections.Counter()
        recovery = 0
        for event_id in lineage:
            row = by_id[event_id]
            payload = read_json(row["payload"])
            result = read_json(row["result"])
            decision = result.get("decision")
            states[decision.get("state", "unknown") if isinstance(decision, dict)
                   else "unknown"] += 1
            recovery += bool(payload.get("recovery_required"))
        placeholders = ",".join("?" for _ in lineage)
        kinds = collections.Counter(
            row["kind"] for row in db.execute(
                "SELECT kind FROM resident_turns WHERE event_id IN (" + placeholders + ")",
                lineage,
            )
        )
        last_result = read_json(final["result"])
        print(json.dumps({
            "root_event_id": root["id"],
            "resident": root["resident"],
            "chain_length": len(lineage),
            "first_event_id": min(lineage),
            "last_event_id": max(lineage),
            "terminal_status": final["status"],
            "terminal_objective_status": last_result.get("objective_status"),
            "decision_states": dict(states),
            "recovery_prompted": recovery,
            "tool_intents": kinds["TOOL_INTENT"],
            "tool_results": kinds["TOOL_RESULT"],
            "assistant_turns": kinds["ASSISTANT"],
        }, sort_keys=True))
    db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="/home/admin1/.local/state/r3-runtime/institution.db")
    parser.add_argument("--event-type", default="REVIEW_FEEDBACK")
    args = parser.parse_args()
    audit(args.db, args.event_type)
