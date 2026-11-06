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
        from runtime.hr_identity_association import register_hr_identity_association
        register_hr_identity_association(gateway, args.hr_database)
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


class CompositionError(ValueError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose(base_release: Path, destination: Path, *, expected_sha256: str = BASE_TOOL_SERVER_SHA256) -> dict:
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
    if not staged_governed.is_file():
        shutil.rmtree(destination)
        raise CompositionError("native broker governed gateway is missing")
    governed_text = staged_governed.read_text(encoding="utf-8")
    if (text.count(_ARGS_ANCHOR) != 1 or text.count(_REGISTER_ANCHOR) != 1
            or text.count(_HR_PATH_ANCHOR) != 1 or text.count(_DENIAL_ANCHOR) != 1
            or text.count("        def do_GET(self):\n") != 1
            or text.count("from runtime.capabilities import CapabilityDenied\n") != 1
            or governed_text.count(_GOVERNED_IMPORT) != 1
            or governed_text.count(_GOVERNED_DENIAL) != 1):
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
        "staged_tool_server_sha256": _sha256(staged_server),
        "added_capabilities": ["r3.proposal.submit", "r3.proposal.status"],
        "added_hr_operation": "hr.associate_principal",
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
