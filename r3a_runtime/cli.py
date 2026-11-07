"""
R3 CONTROLLED SOURCE
File: r3a_runtime/cli.py
Component: R3A-OPERATOR-CLI
File Revision: 1.4.0
Created: 2026-11-06 UTC (exact time not independently captured)
Created By: Codex GPT-6
Purpose: Expose operator-invoked AP0 diagnostics, CME controls and isolated backup actions.
Execution Model: Local command line using Unix sockets and PostgreSQL client utilities.
Observability: JSON responses with explicit operation results and source revisions.
Dependencies: r3a_runtime.config/control/diagnostics/backup.
Authority: AP1 / R3A-019 and AP1 Slices 1–2 authorized by Steward; isolated R3A only.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Finalize local diagnostics, lifecycle and backup CLI.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Add durable idempotent Grace objective submission.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Expose durable notification intake and configured model route selection.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Allow role- and capability/modality-qualified durable Grace objective submissions.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add provider-readiness reporting through the existing local CME control interface.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Replace caller-authored readiness reports with provider-triggered checks.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Accept structured objective criteria through normal durable intake.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Support explicit activity-scoped grants and caller-assigned activity IDs for bounded authorization setup.
Changed: 2026-11-07 | R3A-AP1-MODEL-ROUTING | Codex GPT-6 | Permit configured objective-reasoning or vision task class on durable objective intake.
Changed: 2026-11-07 | R3A-AP1-N1 | Codex GPT-6 | Add idempotent, source-bound institution-event notification intake.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Codex GPT-6 | Expose generic registered provider install, activation, deactivation, replacement and status operations through CME control.
Supersedes: None.
Contracts: AP0-007/008/010/013; R3A-019; AP0-M1 D8/D9; r3a.model-route-decision.v1; r3a.model-readiness.v1.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; no model inference in this slice.
History/Predecessor: Git blob 6e2450c1329b7c1efec6b35f63c534468c4c4571 at commit 0d5f950efc2318774bb95a8dad3b5a498d3f8ce3.
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
    if args.command.startswith("capability-module-"):
        payload = {"operation_id": args.operation_id,
                   "contract_version": args.contract_version}
        if args.provider_version:
            payload["provider_version"] = args.provider_version
        if args.command == "capability-module-replace":
            payload.update({"old_module_id": args.old_module_id,
                            "old_version": args.old_version,
                            "new_provider_version": args.new_provider_version})
    if args.command == "module-activate":
        payload["module_id"] = args.module_id
    elif args.command == "capability-check":
        payload = {"module_id": args.module_id, "capability_id": args.capability_id}
    elif args.command == "capability-grant":
        payload = {"module_id": args.module_id, "capability_id": args.capability_id,
                   "reason": args.reason}
    elif args.command == "grace-objective-submit":
        payload = {"objective": args.objective, "event_kind": args.event_kind,
                   "required_capabilities": args.required_capability,
                   "required_modalities": args.required_modality,
                   "acceptance_criteria": json.loads(args.acceptance_criteria_json)}
        if args.route_id:
            payload["route_id"] = args.route_id
        if args.role_id:
            payload["role_id"] = args.role_id
    elif args.command == "model-readiness-refresh":
        payload = {"role_id": args.role_id}
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
    objective = commands.add_parser("grace-objective-submit",
                                    help="Durably submit a read-only objective to the configured Grace resident")
    objective.add_argument("--objective", required=True)
    objective.add_argument("--event-kind", choices=("objective", "notification"), default="objective",
                           help="Durably classify this incoming event for Grace")
    objective.add_argument("--route-id", help="Configured Grace model route; defaults to bootstrap policy")
    objective.add_argument("--role-id", help="Configured Grace model role; readiness is checked before dispatch")
    objective.add_argument("--required-capability", action="append", default=[],
                           help="Required model capability for role selection; may be repeated")
    objective.add_argument("--required-modality", action="append", default=[],
                           help="Required input modality for role selection; may be repeated")
    objective.add_argument("--acceptance-criteria-json", default="[]",
                           help="Versioned, machine-checkable completion criteria as a JSON array")
    objective.add_argument("--idempotency-key", required=True)
    readiness = commands.add_parser("model-readiness-refresh",
                                    help="Ask CME to perform a configured model-provider readiness check")
    readiness.add_argument("--role-id", required=True)
    readiness.add_argument("--idempotency-key", required=True)
    for name in ("module-install", "module-activate", "module-replace"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--version", required=name != "module-install", default=None)
        if name == "module-activate":
            cmd.add_argument("--module-id", required=True)
    for name in ("capability-module-install", "capability-module-activate",
                 "capability-module-deactivate", "capability-module-status",
                 "capability-module-replace"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--operation-id", required=True)
        cmd.add_argument("--contract-version", default="1.0.0")
        cmd.add_argument("--provider-version")
        if name == "capability-module-replace":
            cmd.add_argument("--old-module-id", required=True)
            cmd.add_argument("--old-version", required=True)
            cmd.add_argument("--new-provider-version", required=True)
    for name in ("capability-check", "capability-grant"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--module-id", required=True)
        cmd.add_argument("--capability-id", required=True)
        if name == "capability-grant":
            cmd.add_argument("--reason", required=True)
    for name in ("module-install", "module-activate", "module-stop", "module-replace",
                 "capability-check", "capability-grant", "capability-module-install",
                 "capability-module-activate", "capability-module-deactivate",
                 "capability-module-status", "capability-module-replace", "config-reload"):
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
