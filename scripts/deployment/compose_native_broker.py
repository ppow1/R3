# R3 CONTROLLED SOURCE
# File: scripts/deployment/compose_native_broker.py
# Component: R3-HR-NATIVE-BROKER-COMPOSER
# File Revision: 1.1.0
# Created: Unknown (legacy; exact creation time not independently established)
# Created By: Unknown (legacy)
# Purpose: Stage the additive proposal adapter over a digest-pinned HR-enabled broker release.
# Execution Model: Copy-on-stage source composition; never edits the active release in place.
# Observability: Digest-pinned input, manifest, compile and integration checks.
# Dependencies: Immutable HR broker release; R3 proposal adapter and HR identity contract.
# Authority: Institutional registry owns proposal authorization; deployment requires existing release policy.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Patch staged broker to consume the named institutional authority decision without a duplicate local grant.
# Changed: 2026-11-06T23:58:00Z | GRACE-AUTHORITY-ARCH-002 | Codex GPT-6 | Keep HR identity writes on the HR-owned path; compose a read-only HR crosswalk resolver only.
# Supersedes: Prior overlay that required exact R3 grants for institutional proposal calls.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md; docs/r3-native-tool-contract.md.
# Tests: tests/test_native_broker_composer.py; actual-base isolated composition and module compilation.
# History/Predecessor: Git blob e61f1773248bab63978f3cd5cd712163140884fc at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
"""Compose an additive proposal adapter over the deployed HR-enabled broker.

The composer intentionally accepts one audited broker base and adds only the
proposal client and two capability registrations. The active release is never
edited in place. Staging to a release path is validated against the R/3
allowlist; tests may supply a temporary destination directly to ``compose``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from scripts.deployment.r3_resource_policy import validate_release_path


BASE_RELEASE = Path("/home/admin1/.local/share/r3/releases/hr-native-010c2d971828")
BASE_TOOL_SERVER_SHA256 = "dd0a8758be94e4c8bd04c83e1b206e5a8e3faf2b9bfd4b5816378f55949f181c"
BASE_GOVERNED_TOOLS_SHA256 = "abcef5dbb3cc17379ec19f966eaca9ef72d8dec54013de71781d2985abcd3159"

_ARGS_ANCHOR = '    parser.add_argument("--institution-db", type=Path, help="Existing R3 institution journal for governed evidence writes")\n'
_HR_PATH_ANCHOR = '            "/home/admin1/.local/share/r3/hr/residents.sqlite3",\n'
_REGISTER_ANCHOR = '''        register_hr_governed_tools(
            gateway,
            "/home/admin1/.local/share/r3/hr/residents.sqlite3",
        )
'''
_ARGS_OVERLAY = '''    parser.add_argument("--institutional-proposal-url")
    parser.add_argument("--hr-database", type=Path,
                        default=Path("/home/admin1/.local/share/r3/hr/residents.sqlite3"))
    parser.add_argument("--institutional-proposal-credential-file", type=Path)
'''
_REGISTER_OVERLAY = '''
        if (args.institutional_proposal_url is None) != (args.institutional_proposal_credential_file is None):
            parser.error("internal proposal integration requires both endpoint and credential file")
        if args.institutional_proposal_url is not None:
            if args.authority_db is None:
                parser.error("internal proposal integration requires --authority-db")
            from runtime.institutional_proposals import (
                InstitutionalProposalClient, read_resident_credential,
            )
            from runtime.proposal_gateway_adapter import register_internal_proposal_tools
            proposal_client = InstitutionalProposalClient(
                args.institutional_proposal_url,
                read_resident_credential(args.institutional_proposal_credential_file),
            )
            register_internal_proposal_tools(
                gateway, proposal_client, hr_database=args.hr_database)
'''
_EXPIRY_OVERLAY = '''
        from runtime.grant_expiry_monitor import start_monitor
        start_monitor(authority)
'''
_DENIAL_ANCHOR = '''            except CapabilityDenied:
                code, outcome, result = 403, "DENIED", {"ok": False, "error": "Resident authorization denied"}
'''
_DENIAL_OVERLAY = '''            except GrantExpiryMissing as exc:
                code, outcome, result = 403, "GRANT_EXPIRY_MISSING", {
                    "ok": False, "error": "GRANT_EXPIRY_MISSING",
                    "grant": exc.grant,
                    "renewal_action": "Ask the Steward to replace this with an exact seven-day grant.",
                }
            except AuthorizationExpired as exc:
                code, outcome, result = 403, "AUTHORIZATION_EXPIRED", {
                    "ok": False, "error": "AUTHORIZATION_EXPIRED",
                    "grant": exc.grant,
                    "renewal_action": exc.grant["renewal_action"],
                }
            except CapabilityDenied:
                code, outcome, result = 403, "DENIED", {"ok": False, "error": "Resident authorization denied"}
'''
_DIAGNOSTIC_ROUTE = '''
            if self.path == "/v1/diagnostics/authorization":
                if router.governed is None:
                    return self.respond(503, {"error": "Authorization diagnostics unavailable"})
                header = self.headers.get("Authorization")
                if not isinstance(header, str) or not header.startswith("Bearer "):
                    return self.respond(401, {"error": "Resident authentication required"})
                token = header[len("Bearer "):]
                try:
                    principal = router.governed.identity_resolver(token)
                    if not isinstance(principal, str) or not principal.startswith("resident:"):
                        return self.respond(401, {"error": "Resident authentication required"})
                    from runtime.grant_expiry_monitor import scan_once
                    scan_once(router.governed.verifier)
                    return self.respond(200, router.governed.verifier.authorization_diagnostics(
                        principal=principal))
                except Exception:
                    return self.respond(503, {"error": "Authorization diagnostics unavailable"})
'''
_GOVERNED_IMPORT = "from runtime.capabilities import AuthorityUnavailable, CapabilityDenied\n"
_GOVERNED_DENIAL = '''        except Exception:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise
'''
_GOVERNED_EXPIRY = '''        except GrantExpiryMissing as exc:
            event["grant_id"] = exc.grant.get("grant_id")
            event["outcome"] = "GRANT_EXPIRY_MISSING"
            self.audit(dict(event))
            raise
        except AuthorizationExpired as exc:
            event["grant_id"] = exc.grant.get("grant_id")
            event["outcome"] = "AUTHORIZATION_EXPIRED"
            self.audit(dict(event))
            raise
        except Exception:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise
'''
_CONTEXT_GRANT_FIELD = "    grant_id: str\n"
_CAPABILITY_EXECUTOR_FIELD = "    executor: Callable[[dict, ExecutionContext], object]\n"
_REGISTER_BODY = '''    def register(self, capability: GovernedCapability) -> None:
        if capability.name in self._capabilities:
            raise ValueError("Duplicate capability")
        self._capabilities[capability.name] = capability
'''
_AUTHORIZATION_BODY = '''        try:
            evidence = self.verifier.authorize(
                principal=principal, resource_id=capability.resource_id,
                action=capability.action, operation=capability.operation,
                scope_ref=scope)
            if not isinstance(evidence, dict) or not (
                    isinstance(evidence.get("grant_id"), str) and evidence["grant_id"]):
                raise AuthorityUnavailable("Canonical grant evidence required")
            event["grant_id"] = evidence["grant_id"]
            event["outcome"] = "AUTHORIZED"
            # Denial by audit storage must prevent executing any operation.
            self.audit(dict(event))
'''
_EXECUTION_CONTEXT = '''            result = capability.executor(params, ExecutionContext(
                principal=principal, grant_id=evidence["grant_id"],
                resource_id=capability.resource_id, action=capability.action,
                operation=capability.operation, scope_ref=scope,
                correlation_id=correlation_id))
'''
_EXECUTION_COMPLETE = '''            event["outcome"] = "COMPLETED"
            self.audit(dict(event))
'''
_EXECUTION_FAILURE = '''        except Exception:
            event["outcome"] = "UNCERTAIN" if capability.operation == "write" else "FAILED"
            try:
                self.audit(dict(event))
            finally:
                if capability.operation == "write":
                    self.write_ledger.outcome(
                        principal=principal, correlation_id=correlation_id,
                        state="UNCERTAIN")
            raise
'''
_EXECUTION_DENIED = '''        except CapabilityDenied:
            event["outcome"] = "DENIED"
            try:
                self.audit(dict(event))
            finally:
                if capability.operation == "write":
                    self.write_ledger.outcome(
                        principal=principal, correlation_id=correlation_id,
                        state="DENIED")
            raise
'''


class CompositionError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose(base_release: Path, destination: Path, *, expected_sha256: str = BASE_TOOL_SERVER_SHA256,
            expected_governed_sha256: str = BASE_GOVERNED_TOOLS_SHA256) -> dict:
    """Copy the broker runtime to a new destination and apply one exact overlay."""
    base_release = base_release.resolve(strict=True)
    source = base_release / "runtime" / "tool_server.py"
    if not source.is_file() or _sha256(source) != expected_sha256:
        raise CompositionError("native broker base does not match the audited release digest")
    runtime_dir = base_release / "runtime"
    if any(path.is_symlink() for path in runtime_dir.rglob("*")):
        raise CompositionError("native broker runtime contains a symlink; refusing ambiguous copy")
    destination = destination.absolute()
    if destination.exists():
        raise CompositionError("staging destination already exists")
    destination.mkdir(parents=True)
    shutil.copytree(runtime_dir, destination / "runtime", symlinks=False)
    staged_server = destination / "runtime" / "tool_server.py"
    text = staged_server.read_text(encoding="utf-8")
    staged_governed = destination / "runtime" / "governed_tools.py"
    if (not staged_governed.is_file() or
            _sha256(staged_governed) != expected_governed_sha256):
        shutil.rmtree(destination)
        raise CompositionError("native broker governed gateway does not match the audited release digest")
    governed_text = staged_governed.read_text(encoding="utf-8")
    if (text.count(_ARGS_ANCHOR) != 1 or text.count(_REGISTER_ANCHOR) != 1
            or text.count(_HR_PATH_ANCHOR) != 1 or text.count(_DENIAL_ANCHOR) != 1
            or text.count("        def do_GET(self):\n") != 1
            or text.count("from runtime.capabilities import CapabilityDenied\n") != 1
            or governed_text.count(_GOVERNED_IMPORT) != 1
            or governed_text.count(_GOVERNED_DENIAL) != 1
            or governed_text.count(_CONTEXT_GRANT_FIELD) != 1
            or governed_text.count(_CAPABILITY_EXECUTOR_FIELD) != 1
            or governed_text.count(_REGISTER_BODY) != 1
            or governed_text.count(_AUTHORIZATION_BODY) != 1
            or governed_text.count(_EXECUTION_CONTEXT) != 1
            or governed_text.count(_EXECUTION_COMPLETE) != 1
            or governed_text.count(_EXECUTION_FAILURE) != 1
            or governed_text.count('if state not in ("COMPLETED", "UNCERTAIN")') != 1):
        shutil.rmtree(destination)
        raise CompositionError("native broker overlay anchors are absent or ambiguous")
    text = text.replace(_ARGS_ANCHOR, _ARGS_ANCHOR + _ARGS_OVERLAY, 1)
    text = text.replace(_REGISTER_ANCHOR, _REGISTER_ANCHOR + _REGISTER_OVERLAY, 1)
    text = text.replace(_REGISTER_ANCHOR + _REGISTER_OVERLAY,
                        _REGISTER_ANCHOR + _REGISTER_OVERLAY + _EXPIRY_OVERLAY, 1)
    text = text.replace(_HR_PATH_ANCHOR, "            str(args.hr_database),\n", 1)
    text = text.replace(_DENIAL_ANCHOR, _DENIAL_OVERLAY, 1)
    text = text.replace("from runtime.capabilities import CapabilityDenied\n",
                        "from runtime.capabilities import AuthorizationExpired, CapabilityDenied, GrantExpiryMissing\n", 1)
    text = text.replace("        def do_GET(self):\n",
                        "        def do_GET(self):\n" + _DIAGNOSTIC_ROUTE, 1)
    staged_server.write_text(text, encoding="utf-8")
    governed_text = governed_text.replace(_GOVERNED_IMPORT,
        "from runtime.capabilities import AuthorizationExpired, AuthorityUnavailable, CapabilityDenied, GrantExpiryMissing\n", 1)
    governed_text = governed_text.replace(_GOVERNED_DENIAL, _GOVERNED_EXPIRY, 1)
    governed_text = governed_text.replace(_CONTEXT_GRANT_FIELD,
        "    grant_id: str | None\n    authority_source: str = \"r3-capability-authority\"\n", 1)
    governed_text = governed_text.replace(_CAPABILITY_EXECUTOR_FIELD,
        _CAPABILITY_EXECUTOR_FIELD +
        "    authorization_mode: str = \"r3-grant\"\n"
        "    authority_source: str | None = None\n", 1)
    governed_text = governed_text.replace(_REGISTER_BODY, '''    def register(self, capability: GovernedCapability) -> None:
        if capability.authorization_mode not in {"r3-grant", "authoritative-service"}:
            raise ValueError("Unsupported capability authorization mode")
        if capability.authorization_mode == "authoritative-service" and (
                capability.authority_source != "riverview.institutional-proposal-registry"):
            raise ValueError("Authoritative-service capability requires a registered decision service")
        if capability.authorization_mode == "r3-grant" and capability.authority_source is not None:
            raise ValueError("R3 grant capability cannot declare alternate authority")
        if capability.name in self._capabilities:
            raise ValueError("Duplicate capability")
        self._capabilities[capability.name] = capability
'''.replace("\n+", "\n"), 1)
    governed_text = governed_text.replace(_AUTHORIZATION_BODY, '''        evidence = None
        try:
            if capability.authorization_mode == "r3-grant":
                evidence = self.verifier.authorize(
                    principal=principal, resource_id=capability.resource_id,
                    action=capability.action, operation=capability.operation,
                    scope_ref=scope)
                if not isinstance(evidence, dict) or not (
                        isinstance(evidence.get("grant_id"), str) and evidence["grant_id"]):
                    raise AuthorityUnavailable("Canonical grant evidence required")
                event["grant_id"] = evidence["grant_id"]
                event["outcome"] = "AUTHORIZED"
                self.audit(dict(event))
            elif (capability.authorization_mode != "authoritative-service"
                    or capability.authority_source != "riverview.institutional-proposal-registry"):
                raise CapabilityDenied("No valid authority decision path is registered")
'''.replace("\n+", "\n"), 1)
    governed_text = governed_text.replace(_EXECUTION_CONTEXT, '''            result = capability.executor(params, ExecutionContext(
                principal=principal,
                grant_id=evidence["grant_id"] if evidence else None,
                resource_id=capability.resource_id, action=capability.action,
                operation=capability.operation, scope_ref=scope,
                correlation_id=correlation_id,
                authority_source=(capability.authority_source if evidence is None
                                  else "r3-capability-authority")))
'''.replace("\n+", "\n"), 1)
    governed_text = governed_text.replace(
        'if state not in ("COMPLETED", "UNCERTAIN")',
        'if state not in ("COMPLETED", "UNCERTAIN", "DENIED")', 1)
    governed_text = governed_text.replace(_EXECUTION_COMPLETE, '''            if evidence is None:
                event["outcome"] = "AUTHORIZED"
                self.audit(dict(event))
            event["outcome"] = "COMPLETED"
            self.audit(dict(event))
'''.replace("\n+", "\n"), 1)
    governed_text = governed_text.replace(_EXECUTION_FAILURE,
        _EXECUTION_DENIED + _EXECUTION_FAILURE, 1)
    staged_governed.write_text(governed_text, encoding="utf-8")
    repository_root = Path(__file__).resolve().parents[2]
    for module in ("capabilities.py", "capability_authority.py", "grant_expiry_monitor.py"):
        shutil.copy2(repository_root / "runtime" / module, destination / "runtime" / module)
    shutil.copy2(repository_root / "runtime" / "institutional_proposals.py",
                 destination / "runtime" / "institutional_proposals.py")
    shutil.copy2(repository_root / "runtime" / "proposal_gateway_adapter.py",
                 destination / "runtime" / "proposal_gateway_adapter.py")
    shutil.copy2(repository_root / "runtime" / "hr_identity_association.py",
                 destination / "runtime" / "hr_identity_association.py")
    manifest = {
        "format": "r3-native-broker-additive-overlay/v1",
        "base_release": str(base_release),
        "base_tool_server_sha256": expected_sha256,
        "base_governed_tools_sha256": expected_governed_sha256,
        "staged_tool_server_sha256": _sha256(staged_server),
        "added_capabilities": ["r3.proposal.submit", "r3.proposal.status"],
        "proposal_authority_source": "riverview.institutional-proposal-registry",
        "proposal_specific_r3_grants_required": False,
        "preserved_registrations": ["register_grace_operational_tools", "register_hr_governed_tools"],
        "authorization_expiry_diagnostics": "/v1/diagnostics/authorization",
        "authorization_expiry_warning_seconds": 180000,
        "credential_values_included": False,
    }
    (destination / "GRACE_PROPOSAL_OVERLAY.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_RELEASE)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--expected-sha256", default=BASE_TOOL_SERVER_SHA256)
    args = parser.parse_args()
    destination = validate_release_path(args.destination)
    try:
        manifest = compose(args.base, destination, expected_sha256=args.expected_sha256)
    except (OSError, CompositionError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
