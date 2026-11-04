# R3 CONTROLLED SOURCE
# File: runtime/inbox_cli.py
# Component: R3-DURABLE-EVENT-INTERFACE
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: Persistent, generic event submission and read-only status inspection.
# Tests: tests/test_inbox_cli.py
# Changed: 2026-11-04 UTC | R3-GRACE-OBJECTIVES-006 | Inspect actual assignment review status/findings read-only.
"""Operator CLI for the institutional scheduler's durable resident inbox."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from runtime.resident_inference import Inbox


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("--resident", required=True)
    submit.add_argument("--event-type", required=True)
    submit.add_argument("--payload", required=True, help="JSON object")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--id", type=int, required=True)
    review = sub.add_parser("review")
    review.add_argument("--assignment-id", required=True)
    args = parser.parse_args(argv)
    if args.command == "submit":
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid payload JSON: {exc}")
        if not isinstance(payload, dict):
            parser.error("Payload must be a JSON object")
        if not args.resident.strip() or not args.event_type.strip():
            parser.error("Resident and event type must be nonempty")
        if not args.db.is_file():
            parser.error("Database must already exist; refusing implicit creation")
    elif not args.db.is_file():
        parser.error("Database does not exist")
    connection = sqlite3.connect(f"file:{args.db}?mode={'rw' if args.command == 'submit' else 'ro'}", uri=True, timeout=10)
    try:
        if args.command == "submit":
            resident = connection.execute("SELECT name FROM residents WHERE name=?", (args.resident,)).fetchone()
            if resident is None:
                parser.error("Resident not registered in institution database")
            inbox = Inbox(connection)
            event_id = inbox.enqueue(args.resident, args.event_type, payload)
            print(json.dumps({"event_id": event_id, "status": "PENDING", "resident": args.resident}))
        elif args.command == "inspect":
            row = connection.execute("SELECT id,resident,event_type,status,result FROM resident_inbox WHERE id=?", (args.id,)).fetchone()
            if row is None:
                parser.error("Event not found")
            turns = connection.execute("SELECT seq,kind FROM resident_turns WHERE event_id=? ORDER BY seq", (args.id,)).fetchall()
            print(json.dumps({"event_id": row[0], "resident": row[1], "event_type": row[2], "status": row[3],
                              "result": json.loads(row[4]) if row[4] else None,
                              "turns": [{"seq": seq, "kind": kind} for seq, kind in turns]}))
        else:
            if not args.assignment_id.strip():
                parser.error("Assignment ID must be nonempty")
            # Read the existing ledger only. A status query must never create
            # verification tables, confer acceptance, or change assignments.
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='verification_requests'"
            ).fetchone()
            if row is None:
                parser.error("Verification ledger unavailable")
            status = connection.execute(
                "SELECT id,source_event_id,status,created_at FROM verification_requests "
                "WHERE assignment_id=? ORDER BY id", (args.assignment_id,)
            ).fetchall()
            latest = status[-1] if status else None
            findings = connection.execute(
                "SELECT review_id,criterion_id,result,reason,evidence,reviewer,at "
                "FROM verification_findings WHERE assignment_id=? ORDER BY id",
                (args.assignment_id,)
            ).fetchall()
            print(json.dumps({
                "assignment_id": args.assignment_id,
                "verification_status": latest[2] if latest else "NOT_REQUESTED",
                "latest_request_id": latest[0] if latest else None,
                "latest_source_event_id": latest[1] if latest else None,
                "review_count": len(status),
                "pending_review_count": sum(row[2] == "PENDING" for row in status),
                "findings": [dict(zip(
                    ("review_id","criterion_id","result","reason","evidence","reviewer","at"),
                    (r[0],r[1],r[2],r[3],json.loads(r[4]),r[5],r[6])))
                    for r in findings],
            }))
    finally:
        connection.close()


if __name__ == "__main__":
    run()
