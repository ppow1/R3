from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.capability_contracts import CapabilityRegistry, operation_from_manifest
from r3a_runtime.cme import CME
from r3a_runtime.acceptance import validate_acceptance
from r3a_plugins.institutional_knowledge.plugin import create_provider


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "r3a_plugins/institutional_knowledge/manifest.json"


class InstitutionalKnowledgeProviderTests(unittest.TestCase):
    def _configuration(self, path: Path, *, freshness: int = 86400) -> dict:
        return {"sources": [{"source_id": "knowledge.test.policy", "path": str(path),
                             "freshness_max_age_seconds": freshness}],
                "max_results": 5, "max_document_bytes": 1024 * 1024}

    def test_registered_operation_is_the_existing_grace_capability_and_carries_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "policy.json"
            source.write_text('{"retention":{"days":30}}', encoding="utf-8")
            config = self._configuration(source)
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            registry = CapabilityRegistry()
            registered = registry.register(operation_from_manifest(manifest), config,
                                           legacy_manifest=manifest)
            self.assertEqual("institution.knowledge.read", registered.descriptor["operation_id"])
            self.assertEqual("1.0.1", registered.descriptor["operation_revision"])
            tool = registered.resident_tool_projection()
            cme = CME.__new__(CME)
            cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                           capability_registry=registry, source_digest="config-rev-1")
            cme._authorize_capability = AsyncMock(return_value={"audit_event_id": "audit-read"})
            request = {"contract_id": tool["contract_id"], "contract_version": tool["contract_version"],
                       "capability_id": tool["capability_id"],
                       "arguments": {"query": "What is the retention period?"}}
            result = asyncio.run(cme._invoke_resident_capability(
                {"activity_id": "activity-1", "attempt_id": "attempt-1"}, request))
            cme._authorize_capability.assert_awaited_once()
            fact = result["output"]["results"][0]
            self.assertEqual("knowledge.test.policy", fact["source_id"])
            self.assertEqual(fact["source_id"], result["evidence"][0]["evidence_id"])
            self.assertEqual(source.as_uri(), fact["uri"])
            self.assertEqual("retention.days", fact["source_path"])
            self.assertEqual("retention.days: 30", fact["content"])
            self.assertEqual(fact["document_sha256"], fact["document_revision"])
            self.assertEqual(fact["document_sha256"], fact["source_sha256"])
            self.assertEqual(fact["excerpt_sha256"], fact["sha256"])
            self.assertEqual(fact["document_sha256"], result["evidence"][0]["document_sha256"])
            self.assertTrue(fact["retrieved_at"])
            self.assertTrue(fact["excerpt_sha256"])
            invalid_request = dict(request)
            invalid_request["arguments"] = {"query": "retention policy", "source_id": "invented.source"}
            with self.assertRaisesRegex(ValueError, "unknown fields"):
                asyncio.run(cme._invoke_resident_capability(
                    {"activity_id": "activity-1", "attempt_id": "attempt-1"}, invalid_request))

    def test_real_source_id_and_digest_satisfy_existing_cited_transition_acceptance(self):
        source = ROOT / "r3a_runtime/state_machines/process.json"
        result = create_provider(self._configuration(source)).invoke(
            {"query": "What are all destinations from STOPPING?"}, context={})
        evidence = result.evidence
        decision = {"assessment": "STOPPING -> STOPPED", "evidence_refs": [
            "knowledge.test.policy"]}
        gaps = validate_acceptance(
            [{"criterion_id": "stop-path", "type": "transition_path",
              "from_state": "STOPPING", "to_state": "STOPPED"}],
            evidence, decision, {"process.json": {evidence[0]["source_sha256"]}})
        self.assertEqual([], gaps)

    def test_denied_retrieval_never_loads_or_returns_source_content(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "policy.json"
            source.write_text('{"secret_policy":"configured fact"}', encoding="utf-8")
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            registry = CapabilityRegistry()
            registered = registry.register(operation_from_manifest(manifest),
                                           self._configuration(source), legacy_manifest=manifest)
            tool = registered.resident_tool_projection()
            cme = CME.__new__(CME)
            cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                           capability_registry=registry, source_digest="config-rev-1")
            cme._authorize_capability = AsyncMock(side_effect=PermissionError("grant denied"))
            request = {"contract_id": tool["contract_id"], "contract_version": tool["contract_version"],
                       "capability_id": tool["capability_id"], "arguments": {"query": "secret policy"}}
            with self.assertRaisesRegex(PermissionError, "grant denied"):
                asyncio.run(cme._invoke_resident_capability(
                    {"activity_id": "activity-1", "attempt_id": "attempt-1"}, request))
            cme._authorize_capability.assert_awaited_once()

    def test_stale_missing_and_changed_documents_are_visible_and_retrieval_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "policy.json"
            source.write_text('{"policy":"alpha retention"}', encoding="utf-8")
            provider = create_provider(self._configuration(source, freshness=0))
            args = {"query": "alpha retention"}
            first = provider.invoke(args, context={})
            second = provider.invoke(args, context={})
            self.assertEqual(first.output["results"][0]["document_sha256"],
                             second.output["results"][0]["document_sha256"])
            self.assertEqual(first.output["results"][0]["content"],
                             second.output["results"][0]["content"])
            self.assertEqual("stale", first.output["sources"][0]["freshness"])
            old_digest = first.output["results"][0]["document_sha256"]
            source.write_text('{"policy":"beta retention"}', encoding="utf-8")
            changed = provider.invoke({"query": "beta retention"}, context={})
            self.assertNotEqual(old_digest, changed.output["results"][0]["document_sha256"])
            source.unlink()
            missing = provider.invoke(args, context={})
            self.assertEqual("unavailable", missing.output["sources"][0]["availability"])
            self.assertEqual([], missing.output["results"])

    def test_unmatched_query_produces_no_claim_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "policy.json"
            source.write_text('{"policy":"alpha retention"}', encoding="utf-8")
            result = create_provider(self._configuration(source)).invoke(
                {"query": "quest avatars"}, context={})
            self.assertEqual([], result.output["results"])
            self.assertEqual([], result.evidence)


if __name__ == "__main__":
    unittest.main()
