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
        governed = ("from runtime.capabilities import AuthorityUnavailable, CapabilityDenied\n"
                    "class Gateway:\n    def auth(self):\n        try:\n            pass\n"
                    "        except Exception:\n            event[\"outcome\"] = \"DENIED\"\n"
                    "            self.audit(dict(event))\n            raise\n")
        path = base / "runtime" / "tool_server.py"
        path.write_text(source, encoding="utf-8")
        (base / "runtime" / "governed_tools.py").write_text(governed, encoding="utf-8")
        return base, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_composes_additively_and_preserves_existing_registration_calls(self):
        with tempfile.TemporaryDirectory(prefix="r3-broker-composer-") as tmp:
            root = Path(tmp)
            base, digest = self.make_base(root)
            target = root / "staged"
            manifest = compose(base, target, expected_sha256=digest)
            server = (target / "runtime" / "tool_server.py").read_text()
            self.assertIn("register_grace_operational_tools(gateway, evidence_journal=evidence)", server)
            self.assertIn("register_hr_governed_tools(", server)
            self.assertIn("register_hr_identity_association(gateway, args.hr_database)", server)
            self.assertIn(REGISTER_OVERLAY_EXPECTATION, server)
            self.assertIn("register_internal_proposal_tools(", server)
            self.assertIn("hr_database=args.hr_database", server)
            self.assertTrue((target / "runtime" / "hr_identity_association.py").is_file())
            self.assertIn("/v1/diagnostics/authorization", server)
            self.assertIn("AUTHORIZATION_EXPIRED", server)
            self.assertIn("--institutional-proposal-credential-file", server)
            self.assertEqual(manifest["added_capabilities"],
                             ["r3.proposal.submit", "r3.proposal.status"])
            self.assertFalse(manifest["credential_values_included"])
            compile(server, str(target / "runtime" / "tool_server.py"), "exec")
            compile((target / "runtime" / "governed_tools.py").read_text(),
                    str(target / "runtime" / "governed_tools.py"), "exec")

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
                compose(base, target, expected_sha256=digest)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
