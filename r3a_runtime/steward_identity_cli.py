"""
R3 CONTROLLED SOURCE
File: r3a_runtime/steward_identity_cli.py
Component: R3A-AP3-IDENTITY-OPERATOR
File Revision: 1.0.2
Created: 2026-11-09T17:31:32Z
Created By: R3 Integration
Purpose: Provide local audited resident association and initial Steward bootstrap, challenge, disable, and revocation actions.
Execution Model: Explicit operator invocation against the least-privilege AP0 identity-operator role.
Observability: Bounded JSON result codes; one-time challenge is printed only for approved out-of-band delivery.
Authority: Approved R3A Authentication Independence Plan; AP3/R3A-010; Issue #49.
Changed: 2026-11-09T17:54:09Z | R3A-NATIVE-AUTH-INTEGRATION | Codex GPT-6 | Integrate the owner-reviewed native identity operator CLI.
Supersedes: None.
Dependencies: R3A_STEWARD_ADMIN_DSN; r3a-steward-identity CLI contract.
Contracts: R3A native Steward identity lifecycle v1.
Tests: tests/test_r3a_native_identity.py.
Changed: 2026-11-09T21:00:00Z | R3A-STEWARD-BOOTSTRAP | R3A Coordinator | Add owner-only bootstrap evidence file handling for the initial human Steward.
History/Predecessor: Initial implementation in Remote Access commit 16b6230d5b48bb9bd1872f687f43678faeb296d7.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .steward_identity import PostgresStewardIdentityRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="r3a-steward-identity")
    commands = parser.add_subparsers(dest="command", required=True)
    associate = commands.add_parser("associate", help="record an approved non-secret identity association")
    associate.add_argument("--record", required=True, help="0600 JSON association evidence file")
    bootstrap = commands.add_parser("bootstrap-steward", help="associate the initial Steward from verified non-secret R3 metadata")
    bootstrap.add_argument("--record", required=True, help="owner-only JSON bootstrap evidence file")
    challenge = commands.add_parser("challenge", help="issue one single-use enrollment or recovery challenge")
    challenge.add_argument("--principal-id", required=True)
    challenge.add_argument("--actor", required=True)
    challenge.add_argument("--purpose", choices=("initial_enrollment", "credential_recovery"), default="initial_enrollment")
    challenge.add_argument("--lifetime-minutes", type=int, default=30)
    state = commands.add_parser("disable", help="disable or revoke the account and its live AP3 sessions")
    state.add_argument("--principal-id", required=True)
    state.add_argument("--actor", required=True)
    state.add_argument("--reason", choices=("steward_request", "suspected_compromise", "identity_correction"), required=True)
    state.add_argument("--revoke", action="store_true", help="permanently revoke instead of disable")
    args = parser.parse_args(argv)
    dsn = os.environ.get("R3A_STEWARD_ADMIN_DSN", "")
    if not dsn:
        parser.error("R3A_STEWARD_ADMIN_DSN is not configured")
    repository = PostgresStewardIdentityRepository(dsn)
    try:
        if args.command == "associate":
            path = Path(args.record)
            if path.stat().st_mode & 0o077:
                parser.error("association record permissions must be 0600 or stricter")
            record = json.loads(path.read_text(encoding="utf-8"))
            result = repository.associate(record)
            print(json.dumps({"state": result["state"], "principal_id": result["principal_id"],
                              "idempotent": result["idempotent"]}, sort_keys=True))
        elif args.command == "bootstrap-steward":
            path = Path(args.record)
            stat = path.stat()
            if stat.st_mode & 0o077 or stat.st_uid != os.getuid():
                parser.error("bootstrap record must be owned by the operator and mode 0600 or stricter")
            record = json.loads(path.read_text(encoding="utf-8"))
            result = repository.bootstrap_steward(record)
            print(json.dumps({"state": result["state"], "principal_id": result["principal_id"],
                              "idempotent": result["idempotent"]}, sort_keys=True))
        elif args.command == "challenge":
            token = repository.issue_challenge(args.principal_id, args.actor, args.purpose,
                                               args.lifetime_minutes)
            # Displayed once; deliver through the approved out-of-band Steward-controlled channel.
            print(token)
        else:
            repository.set_account_state(args.principal_id, "revoked" if args.revoke else "disabled",
                                         args.actor, args.reason)
            print(json.dumps({"state": "revoked" if args.revoke else "disabled",
                              "principal_id": args.principal_id, "sessions_revoked": True}, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"state": "failed", "reason": getattr(exc, "code", type(exc).__name__)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
