# R3 CONTROLLED SOURCE
# File: tests/test_grace_native_capabilities.py
# Component: R3-GRACE-OPERATIONAL-TOOL-REGRESSION
# File Revision: 1.1.1
# Created: 2026-11-04 UTC (date precision only)
# Created By: ChatGPT GPT-6
# Purpose: Permanent live resource observation and canonical journal evidence write tests.
# Execution Model: Temp R3 journal and fake canonical grant verifier; no production data.
# Observability: R3 events rows, exact authorization outcomes and no-replay ledger.
# Dependencies: Python stdlib, runtime/grace_native_capabilities.py, runtime/institution.py
# Authority: R3 unified integration; issues #16, #28 and #29.
# Changed: 2026-11-04 UTC | R3-GRACE-TOOLS-002 | Add permanent host and evidence contracts.
# Changed: 2026-11-04 UTC | R3-GRACE-TOOLS-005 | Permanent bounded GPU probe tests and portable snapshot assertions.
# Changed: 2026-11-04 UTC | R3-GRACE-TOOLS-006 | Correct test fixture line terminators for nvidia-smi CSV.
# Supersedes: None
# Contracts: docs/r3-native-tool-contract.md
# Tests: python -m unittest tests.test_grace_native_capabilities -v
# History/Predecessor: New test.
import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.capabilities import CapabilityDenied
from runtime.grace_native_capabilities import (
    EvidenceJournal, local_host_observations, local_nvidia_gpu_observations,
    register_grace_operational_tools)
from runtime.governed_tools import ExecutionAttemptLedger, GovernedToolGateway
from runtime.institution import Journal
from runtime.tool_server import ToolRouter


class CanonicalVerifier:
    def __init__(self):
        self.allowed = set()

    def authorize(self, **kw):
        requested = (kw["principal"], kw["resource_id"], kw["action"],
                     kw["operation"], kw["scope_ref"])
        if requested not in self.allowed:
            raise CapabilityDenied("Missing shared R3 exact grant")
        return {"grant_id": "test-approval"}


class GraceOperationalToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.journal = Journal(base / "institution.db")
        self.addCleanup(self.journal.db.close)
        self.connection = sqlite3.connect(base / "tool-events.db", check_same_thread=False)
        self.addCleanup(self.connection.close)
        self.verifier = CanonicalVerifier()
        self.audit_events = []
        self.gateway = GovernedToolGateway(
            identity_resolver=lambda token: (
                "resident:grace" if token == "valid-resident-token"
                else (_ for _ in ()).throw(CapabilityDenied("Invalid credential"))),
            verifier=self.verifier, audit=self.audit_events.append,
            write_ledger=ExecutionAttemptLedger(self.connection, threading.Lock()))
        register_grace_operational_tools(
            self.gateway, evidence_journal=EvidenceJournal(base / "institution.db"))
        self.router = ToolRouter(base / "router.db", governed=self.gateway)
        self.addCleanup(self.router.db.close)

    def allow(self, resource, action, operation):
        self.verifier.allowed.add(
            ("resident:grace", resource, action, operation, "institution:r3"))

    def invoke(self, name, params, correlation):
        return self.router.invoke(
            {"tool": name, "params": params, "correlation_id": correlation},
            authorization="Bearer valid-resident-token")

    def test_real_local_probe_returns_provenanced_host_not_remote_claims(self):
        observed = list(local_host_observations())
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].kind, "physical-host")
        self.assertEqual(observed[0].source, "r3:local-os-probe")
        self.assertIsNotNone(datetime.fromisoformat(observed[0].observed_at))

    def test_resource_snapshot_requires_exact_read_grant(self):
        args = {"scope_ref": "institution:r3"}
        name = "r3.resources.local_snapshot"
        self.assertEqual(self.invoke(name, args, "read-denied")[0], 403)
        self.allow("registry:local", "inventory.snapshot", "read")
        code, response = self.invoke(name, args, "read-authorized")
        self.assertEqual(code, 200)
        resources = response["result"]["result"]["resources"]
        hosts = [item for item in resources if item["kind"] == "physical-host"]
        self.assertEqual(len(hosts), 1)
        self.assertEqual(hosts[0]["source"], "r3:local-os-probe")
        self.assertIsNone(hosts[0]["authorized"])

    def test_nvidia_gpu_probe_records_vram_and_source(self):
        result = SimpleNamespace(returncode=0,
            stdout="GPU-0123, NVIDIA Test GPU, 16384, 8192\n", stderr="")
        with patch("runtime.grace_native_capabilities.subprocess.run", return_value=result) as run:
            resources = list(local_nvidia_gpu_observations())
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].resource_id, "gpu:GPU-0123")
        self.assertEqual(resources[0].kind, "nvidia-gpu")
        self.assertEqual(resources[0].capacity["vram_total_bytes"], 16384 * 1048576)
        self.assertEqual(resources[0].capacity["vram_free_bytes"], 8192 * 1048576)
        self.assertEqual(resources[0].source, "r3:local-nvidia-smi")
        self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_nvidia_probe_absent_or_unavailable_does_not_invent_gpu(self):
        for error in (FileNotFoundError("nvidia-smi absent"), TimeoutError("timeout")):
            with self.subTest(error=type(error).__name__):
                with patch("runtime.grace_native_capabilities.subprocess.run", side_effect=error):
                    self.assertEqual(list(local_nvidia_gpu_observations()), [])
        with patch("runtime.grace_native_capabilities.subprocess.run",
                   return_value=SimpleNamespace(returncode=1, stdout="", stderr="failure")):
            self.assertEqual(list(local_nvidia_gpu_observations()), [])

    def test_nvidia_probe_discards_invalid_capacity_rows(self):
        result = SimpleNamespace(returncode=0,
            stdout="GPU-1, GPU, 100, 101\nGPU-2, GPU, invalid, 5\nGPU-3, GPU, 50, 25\n",
            stderr="")
        with patch("runtime.grace_native_capabilities.subprocess.run", return_value=result):
            resources = list(local_nvidia_gpu_observations())
        self.assertEqual([r.resource_id for r in resources], ["gpu:GPU-3"])

    def test_evidence_write_denied_without_grant(self):
        name = "r3.evidence.record"
        args = {"scope_ref": "institution:r3", "objective_id": "OBJ",
                "statement": "A verifiable resident observation"}
        self.assertEqual(self.invoke(name, args, "no-grant")[0], 403)
        rows = self.journal.db.execute(
            "SELECT COUNT(*) FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()[0]
        self.assertEqual(rows, 0)

    def test_evidence_write_is_durable_and_not_self_verified(self):
        self.allow("journal:institution", "evidence.record", "write")
        args = {"scope_ref": "institution:r3", "objective_id": "OBJ",
                "statement": "Local capacity was observed",
                "evidence_refs": ["r3:resource:local"]}
        code, response = self.invoke("r3.evidence.record", args, "evidence-1")
        self.assertEqual(code, 200)
        self.assertEqual(response["result"]["result"]["review_status"],
                         "NOT_INDEPENDENTLY_VERIFIED")
        saved = self.journal.db.execute(
            "SELECT resident,kind,detail FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()
        self.assertEqual(saved[:2], ("resident:grace", "EVIDENCE_SUBMITTED"))
        detail = json.loads(saved[2])
        self.assertEqual(detail["principal_id"], "resident:grace")
        self.assertEqual(detail["grant_id"], "test-approval")
        self.assertEqual(detail["acceptance"], "NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(self.invoke("r3.evidence.record", args, "evidence-1")[0], 409)
        self.assertEqual(self.journal.db.execute(
            "SELECT COUNT(*) FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()[0], 1)

    def test_caller_cannot_claim_independent_acceptance(self):
        self.allow("journal:institution", "evidence.record", "write")
        args = {"scope_ref": "institution:r3", "objective_id": "OBJ",
                "statement": "Claim", "accepted": True}
        self.assertEqual(self.invoke("r3.evidence.record", args, "spoof-acceptance")[0], 403)
        self.assertEqual(self.journal.db.execute(
            "SELECT COUNT(*) FROM events WHERE kind='EVIDENCE_SUBMITTED'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
