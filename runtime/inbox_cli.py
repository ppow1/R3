# R3 CONTROLLED SOURCE
# File: runtime/inbox_cli.py
# Component: R3-DURABLE-EVENT-INTERFACE
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: Persistent, generic event submission and read-only status inspection.
# Tests: tests/test_inbox_cli.py
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
        else:
            row = connection.execute("SELECT id,resident,event_type,status,result FROM resident_inbox WHERE id=?", (args.id,)).fetchone()
            if row is None:
                parser.error("Event not found")
            turns = connection.execute("SELECT seq,kind FROM resident_turns WHERE event_id=? ORDER BY seq", (args.id,)).fetchall()
            print(json.dumps({"event_id": row[0], "resident": row[1], "event_type": row[2], "status": row[3],
                              "result": json.loads(row[4]) if row[4] else None,
                              "turns": [{"seq": seq, "kind": kind} for seq, kind in turns]}))
    finally:
        connection.close()


if __name__ == "__main__":
    run()
