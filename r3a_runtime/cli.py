"""
R3 CONTROLLED SOURCE
File: r3a_runtime/cli.py
Component: R3A-OPERATOR-CLI
File Revision: 1.0.0
Created: 2026-11-06 UTC (exact time not independently captured)
Created By: Codex GPT-6
Purpose: Expose operator-invoked AP0 diagnostics, CME controls and isolated backup actions.
Execution Model: Local command line using Unix sockets and PostgreSQL client utilities.
Observability: JSON responses with explicit operation results and source revisions.
Dependencies: r3a_runtime.config/control/diagnostics/backup.
Authority: AP0-M1 implementation authorized in GitHub Issue #42; isolated R3A only.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Finalize local diagnostics, lifecycle and backup CLI.
Supersedes: None.
Contracts: AP0-007/010/013; AP0-M1 D8/D9.
Tests: Targeted command-line and live isolated runtime verification.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from .backup import create_backup, restore_backup
from .config import load_settings
from .control import control_request
from .diagnostics import status


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


async def _run(args: argparse.Namespace) -> Any:
    settings = load_settings(args.config)
    if args.command == "status":
        return await status(settings)
    if args.command in {"events", "definitions"}:
        return await control_request(settings.diagnostics_socket, args.command)
    if args.command == "backup":
        return await create_backup(settings, Path(args.output) if args.output else None)
    if args.command == "restore":
        return await restore_backup(settings, Path(args.backup), args.target_database)

    payload = {}
    operation = args.command.replace("-", ".")
    if args.command in {"module-install", "module-activate", "module-replace"}:
        if args.version is not None:
            payload["version"] = args.version
    if args.command == "module-activate":
        payload["module_id"] = args.module_id
    elif args.command == "capability-check":
        payload = {"module_id": args.module_id, "capability_id": args.capability_id}
    elif args.command == "capability-grant":
        payload = {"module_id": args.module_id, "capability_id": args.capability_id,
                   "reason": args.reason}
    elif args.command == "config-reload":
        operation = "config.reload"
    return await control_request(settings.control_socket, operation, payload,
                                 idempotency_key=args.idempotency_key)


def main() -> None:
    parser = argparse.ArgumentParser(prog="r3a", description="R3A AP0 local operator interface")
    parser.add_argument("--config", required=True, help="external R3A bootstrap JSON")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "events", "definitions", "module-stop", "config-reload"):
        commands.add_parser(name)
    for name in ("module-install", "module-activate", "module-replace"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--version", required=name != "module-install", default=None)
        if name == "module-activate":
            cmd.add_argument("--module-id", required=True)
    for name in ("capability-check", "capability-grant"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--module-id", required=True)
        cmd.add_argument("--capability-id", required=True)
        if name == "capability-grant":
            cmd.add_argument("--reason", required=True)
    for name in ("module-install", "module-activate", "module-stop", "module-replace",
                 "capability-check", "capability-grant", "config-reload"):
        commands.choices[name].add_argument("--idempotency-key")
    backup = commands.add_parser("backup")
    backup.add_argument("--output")
    restore = commands.add_parser("restore")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--target-database", required=True)
    args = parser.parse_args()
    try:
        _emit(asyncio.run(_run(args)))
    except Exception as exc:
        print(f"r3a: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
