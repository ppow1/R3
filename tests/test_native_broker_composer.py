# R3 CONTROLLED SOURCE
# File: tests/test_native_broker_composer.py
# Component: R3-HR-NATIVE-BROKER-COMPOSER-REGRESSION
# File Revision: 1.0.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Ensure digest-pinned additive broker composition preserves existing registrations and institutional authority routing.
# Execution Model: unittest with temporary source trees.
# Observability: Composer errors, output manifest, and generated module compilation.
# Dependencies: scripts.deployment.compose_native_broker.
# Authority: Staging tests do not activate the broker or alter production resources.
# Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Cover staged authoritative-service decision handling.
# Supersedes: Prior composer tests for grant-gated proposal overlay.
# Contracts: docs/architecture/RESIDENT_AUTHORITY_AND_CAPABILITIES.md.
# Tests: This module.
# History/Predecessor: Git blob f2860927878dbf859b0a90206c43b858199b06d7 at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.deployment.compose_native_broker import (
    CompositionError,
    compose,
)


ARGS_ANCHOR = ('    parser.add_argument("--institution-db", type=Path, '
               'help="Existing R3 institution journal for governed evidence writes")\n')
REGISTER_ANCHOR = '''        register_hr_governed_tools(
            gateway,
            "/home/admin1/.local/share/r3/hr/residents.sqlite3",
        )
'''
REGISTER_OVERLAY_EXPECTATION = '            str(args.hr_database),\n'


class NativeBrokerComposerTests(unittest.TestCase):
    def make_base(self, root: Path) -> tuple[Path, str]:
        base = root / "base"
        (base / "runtime").mkdir(parents=True)
        source = ("import argparse\nfrom pathlib import Path\n"
                  "from runtime.capabilities import CapabilityDenied\n"
                  "def main():\n    parser = argparse.ArgumentParser()\n"
                  "    parser.add_argument(\"--institution-db\", type=Path, "
                  "help=\"Existing R3 institution journal for governed evidence writes\")\n"
                  "    if args.authority_db:\n"
                  "        register_grace_operational_tools(gateway, evidence_journal=evidence)\n"
                  + REGISTER_ANCHOR
                  + "    router = ToolRouter()\n"
                  + "def handler_for(router):\n    class Handler:\n        def do_GET(self):\n            pass\n"
                  + "class ToolRouter:\n    def invoke(self):\n        if True:\n            try:\n                pass\n"
                  + "            except CapabilityDenied:\n"
                  + "                code, outcome, result = 403, \"DENIED\", {\"ok\": False, \"error\": \"Resident authorization denied\"}\n"
                  + "            except Exception:\n                pass\n")
        governed = '''from dataclasses import dataclass
from typing import Callable, Protocol
from runtime.capabilities import AuthorityUnavailable, CapabilityDenied

@dataclass(frozen=True)
class ExecutionContext:
    principal: str
    grant_id: str
    resource_id: str
    action: str
    operation: str
    scope_ref: str
    correlation_id: str

@dataclass(frozen=True)
class GovernedCapability:
    name: str
    resource_id: str
    action: str
    operation: str
    description: str
    parameters: dict
    executor: Callable[[dict, ExecutionContext], object]

class Ledger:
    def outcome(self, **kwargs):
        if state not in ("COMPLETED", "UNCERTAIN"):
            raise ValueError("Invalid write outcome")

class GovernedToolGateway:
    def register(self, capability: GovernedCapability) -> None:
        if capability.name in self._capabilities:
            raise ValueError("Duplicate capability")
        self._capabilities[capability.name] = capability

    def authorize(self):
        try:
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
        except Exception:
            event["outcome"] = "DENIED"
            self.audit(dict(event))
            raise
        try:
            result = capability.executor(params, ExecutionContext(
                principal=principal, grant_id=evidence["grant_id"],
                resource_id=capability.resource_id, action=capability.action,
                operation=capability.operation, scope_ref=scope,
                correlation_id=correlation_id))
            event["outcome"] = "COMPLETED"
            self.audit(dict(event))
        except Exception:
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
        path = base / "runtime" / "tool_server.py"
        path.write_text(source, encoding="utf-8")
        (base / "runtime" / "governed_tools.py").write_text(governed, encoding="utf-8")
        return base, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_composes_additively_and_preserves_existing_registration_calls(self):
        with tempfile.TemporaryDirectory(prefix="r3-broker-composer-") as tmp:
            root = Path(tmp)
            base, digest = self.make_base(root)
            target = root / "staged"
            governed_digest = hashlib.sha256((base / "runtime" / "governed_tools.py").read_bytes()).hexdigest()
            manifest = compose(base, target, expected_sha256=digest,
                               expected_governed_sha256=governed_digest)
            server = (target / "runtime" / "tool_server.py").read_text()
            self.assertIn("register_grace_operational_tools(gateway, evidence_journal=evidence)", server)
            self.assertIn("register_hr_governed_tools(", server)
            self.assertNotIn("register_hr_identity_association", server)
            self.assertIn(REGISTER_OVERLAY_EXPECTATION, server)
            self.assertIn("register_internal_proposal_tools(", server)
            self.assertIn("hr_database=args.hr_database", server)
            self.assertTrue((target / "runtime" / "hr_identity_association.py").is_file())
            self.assertIn("/v1/diagnostics/authorization", server)
            self.assertIn("AUTHORIZATION_EXPIRED", server)
            self.assertIn("--institutional-proposal-credential-file", server)
            self.assertEqual(manifest["added_capabilities"],
                             ["r3.proposal.submit", "r3.proposal.status"])
            self.assertNotIn("added_hr_operation", manifest)
            self.assertFalse(manifest["credential_values_included"])
            compile(server, str(target / "runtime" / "tool_server.py"), "exec")
            compiled = (target / "runtime" / "governed_tools.py").read_text()
            compile(compiled, str(target / "runtime" / "governed_tools.py"), "exec")
            self.assertIn('"authoritative-service"', compiled)
            self.assertIn('state not in ("COMPLETED", "UNCERTAIN", "DENIED")', compiled)
            self.assertIn('authority_source=(', compiled)

    def test_unexpected_base_digest_fails_before_creating_destination(self):
        with tempfile.TemporaryDirectory(prefix="r3-broker-composer-") as tmp:
            root = Path(tmp)
            base, _ = self.make_base(root)
            target = root / "staged"
            with self.assertRaises(CompositionError):
                compose(base, target, expected_sha256="0" * 64)
            self.assertFalse(target.exists())

    def test_ambiguous_registration_anchor_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="r3-broker-composer-") as tmp:
            root = Path(tmp)
            base, _ = self.make_base(root)
            source = base / "runtime" / "tool_server.py"
            source.write_text(source.read_text() + REGISTER_ANCHOR)
            target = root / "staged"
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaises(CompositionError):
                compose(base, target, expected_sha256=digest,
                        expected_governed_sha256=hashlib.sha256(
                            (base / "runtime" / "governed_tools.py").read_bytes()).hexdigest())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
