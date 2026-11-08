"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_institutional_knowledge.py
Component: R3A-KNOWLEDGE-RETRIEVAL-TESTS
File Revision: 1.3.0
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: Verify registered institutional knowledge retrieval, authorization, freshness, and provenance.
Execution Model: unittest; local deterministic provider and CME test doubles.
Observability: Test names and assertion failures.
Dependencies: R3A capability contracts, CME, knowledge provider, configured source files.
Authority: AP1 / R3A-019; read-only capability regression tests.
Changed: 2026-11-07T23:45:06Z | AP1-K2 | Codex GPT-6 | Verify 1.1.0 compatibility, citation and digest integrity, and external configuration reload behavior.
Supersedes: None.
Contracts: institution.knowledge.read@1.1.0; R3A capability-operation v1.
Tests: This module; tests.test_r3a_capability_contracts; tests.test_r3a_ap1.
History/Predecessor: Git blob 91fc5f0f6fd3e14dc802b9be754ca5f903492e68 at commit d0404a5.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.capability_contracts import (CapabilityRegistry, normalize_provider_result,
                                              operation_from_manifest)
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

    def test_provider_revision_1_1_remains_compatible_with_operation_contract_v1(self):
        charter = ROOT / "docs/PROJECT_CHARTER_REVISION_2_REVIEW.md"
        roadmap = ROOT / "docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md"
        config = {"sources": [
            {"source_id": "knowledge.r3.charter.revision-2", "path": str(charter),
             "freshness_max_age_seconds": 86400},
            {"source_id": "knowledge.r3a.master-roadmap.baseline-1", "path": str(roadmap),
             "freshness_max_age_seconds": 86400},
        ], "max_results": 10, "max_document_bytes": 1024 * 1024}
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        registry = CapabilityRegistry()
        registry.register(operation_from_manifest(manifest), config, legacy_manifest=manifest)
        registered = registry.resolve("institution.knowledge.read", "1.0.0")
        descriptor = registered.descriptor
        self.assertEqual("1.1.0", descriptor["operation_revision"])
        self.assertEqual("1.2.0", descriptor["provider"]["provider_version"])
        self.assertEqual("1.0.0", descriptor["contract_version"])
        self.assertEqual("read", descriptor["effect_class"])
        provider = registered.load_provider()
        raw = provider.invoke({"query": "Who owns personnel records, and what does AP1 require for knowledge grounding?"},
                              context={})
        output, evidence = normalize_provider_result(raw, descriptor)
        facts = output["results"]
        citations = {item["source_id"]: item for item in facts}
        self.assertTrue({"knowledge.r3.charter.revision-2",
                         "knowledge.r3a.master-roadmap.baseline-1"}.issubset(citations))
        self.assertEqual({item["source_id"] for item in facts},
                         {item["evidence_id"] for item in evidence})
        for source_id, item in citations.items():
            source_path = Path(item["uri"].removeprefix("file://"))
            raw_source = source_path.read_bytes()
            self.assertEqual(hashlib.sha256(raw_source).hexdigest(), item["document_sha256"])
            self.assertEqual(item["document_sha256"], item["document_revision"])
            self.assertEqual(item["document_sha256"], item["source_sha256"])
            self.assertEqual(item["excerpt_sha256"], item["sha256"])
            self.assertRegex(item["source_path"], r"markdown\..+@L\d+-L\d+$")
            self.assertTrue(item["retrieved_at"])
            self.assertEqual(item["document_sha256"],
                             next(ev["document_sha256"] for ev in evidence
                                  if ev["evidence_id"] == source_id))
            excerpt = item["content"].encode("utf-8")
            self.assertEqual(hashlib.sha256(excerpt).hexdigest(), item["excerpt_sha256"])

    def test_external_configuration_change_replaces_sources_after_registry_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            alpha = root / "alpha.md"
            beta = root / "beta.md"
            alpha.write_text("# Alpha policy\n\nAlpha retention is thirty days.\n", encoding="utf-8")
            beta.write_text("# Beta policy\n\nBeta retention is ninety days.\n", encoding="utf-8")
            config_path = root / "institutional-knowledge.json"

            def write_configuration(source_id: str, path: Path) -> None:
                config_path.write_text(json.dumps({"sources": [
                    {"source_id": source_id, "path": str(path), "freshness_max_age_seconds": 86400}],
                    "max_results": 10, "max_document_bytes": 1024 * 1024}), encoding="utf-8")

            def reload_registry():
                manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
                configuration = json.loads(config_path.read_text(encoding="utf-8"))
                registry = CapabilityRegistry()
                registry.register(operation_from_manifest(manifest), configuration,
                                  legacy_manifest=manifest)
                return registry.resolve("institution.knowledge.read", "1.0.0").load_provider()

            write_configuration("knowledge.test.alpha", alpha)
            first = reload_registry().invoke({"query": "retention"}, context={})
            self.assertEqual({"knowledge.test.alpha"},
                             {source["source_id"] for source in first.output["sources"]})
            first_revision = first.output["results"][0]["document_revision"]
            write_configuration("knowledge.test.beta", beta)
            reloaded = reload_registry().invoke({"query": "retention"}, context={})
            self.assertEqual({"knowledge.test.beta"},
                             {source["source_id"] for source in reloaded.output["sources"]})
            self.assertEqual({"knowledge.test.beta"},
                             {item["source_id"] for item in reloaded.output["results"]})
            self.assertNotEqual(first_revision, reloaded.output["results"][0]["document_revision"])
            self.assertIn("ninety", reloaded.output["results"][0]["content"])

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
            self.assertEqual("1.1.0", registered.descriptor["operation_revision"])
            tool = registered.resident_tool_projection()
            cme = CME.__new__(CME)
            cme.module_id = "resident.grace"
            cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                           capability_registry=registry, source_digest="config-rev-1")
            raw = registered.load_provider().invoke(
                {"query": "What is the retention period?"}, context={})
            output, evidence = normalize_provider_result(raw, registered.descriptor)
            cme.invoke_capability = AsyncMock(return_value={
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": "knowledge-invocation", "operation_id": "institution.knowledge.read",
                "operation_contract_version": "1.0.0", "provider": registered.descriptor["provider"],
                "outcome": "SUCCEEDED", "started_at": "2026-11-08T01:00:00Z",
                "finished_at": "2026-11-08T01:00:01Z", "output": output, "evidence": evidence,
                "authorization": {"provider_id": "capability_grants", "allowed": True,
                                  "decision_id": "decision-read", "audit_event_id": "audit-read",
                                  "policy_revision": None, "config_revision": "config-rev-1"}})
            request = {"contract_id": tool["contract_id"], "contract_version": tool["contract_version"],
                       "capability_id": tool["capability_id"],
                       "arguments": {"query": "What is the retention period?"}}
            result = asyncio.run(cme._invoke_resident_capability(
                {"activity_id": "activity-1", "attempt_id": "attempt-1"}, request))
            cme.invoke_capability.assert_awaited_once()
            invocation = cme.invoke_capability.await_args.args[0]
            self.assertEqual("r3a.capability-invocation.v1", invocation["contract_id"])
            self.assertEqual("institution.knowledge.read", invocation["operation_id"])
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
            cme.module_id = "resident.grace"
            cme.settings = SimpleNamespace(module_capabilities=("institution.knowledge.read",),
                                           capability_registry=registry, source_digest="config-rev-1")
            cme.invoke_capability = AsyncMock(side_effect=PermissionError("grant denied"))
            request = {"contract_id": tool["contract_id"], "contract_version": tool["contract_version"],
                       "capability_id": tool["capability_id"], "arguments": {"query": "secret policy"}}
            with self.assertRaisesRegex(PermissionError, "grant denied"):
                asyncio.run(cme._invoke_resident_capability(
                    {"activity_id": "activity-1", "attempt_id": "attempt-1"}, request))
            cme.invoke_capability.assert_awaited_once()

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

    def test_markdown_retrieval_cites_section_and_exact_source_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "office-policy.md"
            source.write_text(
                "# Institutional roles\n\n"
                "## Responsibilities\n\n"
                "- Grace prioritizes operational work and maintains autonomous operation.\n"
                "- Helen owns personnel records, staffing, and resident development.\n",
                encoding="utf-8")
            result = create_provider(self._configuration(source)).invoke(
                {"query": "Who owns personnel records and staffing?"}, context={})
            fact = result.output["results"][0]
            self.assertEqual("- Helen owns personnel records, staffing, and resident development.",
                             fact["content"])
            self.assertIn("h2.responsibilities@L3", fact["source_path"])
            self.assertTrue(fact["source_path"].endswith("@L6-L6"))
            self.assertEqual(fact["source_id"], result.evidence[0]["evidence_id"])
            self.assertEqual(fact["document_sha256"], result.evidence[0]["document_sha256"])

    def test_multiple_configured_documents_keep_distinct_source_lineage(self):
        with tempfile.TemporaryDirectory() as directory:
            charter = Path(directory) / "charter.md"
            procedures = Path(directory) / "procedures.md"
            charter.write_text("# Charter\n\nRecords must be retained for institutional continuity.\n",
                               encoding="utf-8")
            procedures.write_text("# Procedure\n\nRecords must be retained for operational review.\n",
                                  encoding="utf-8")
            config = {"sources": [
                {"source_id": "knowledge.test.charter", "path": str(charter),
                 "freshness_max_age_seconds": 86400},
                {"source_id": "knowledge.test.procedures", "path": str(procedures),
                 "freshness_max_age_seconds": 86400},
            ], "max_results": 10, "max_document_bytes": 1024 * 1024}
            result = create_provider(config).invoke(
                {"query": "records retained institutional continuity operational review"}, context={})
            facts = result.output["results"]
            self.assertEqual({"knowledge.test.charter", "knowledge.test.procedures"},
                             {item["source_id"] for item in facts})
            self.assertEqual({charter.as_uri(), procedures.as_uri()},
                             {item["uri"] for item in facts})
            self.assertEqual({item["source_id"] for item in facts},
                             {item["evidence_id"] for item in result.evidence})
            self.assertTrue(all(item["document_revision"] == item["document_sha256"]
                                and item["excerpt_sha256"] for item in facts))

    def test_markdown_fenced_examples_do_not_change_document_section_context(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "spec.md"
            source.write_text(
                "# Verified section\n\n"
                "```markdown\n## Example-only heading\nExample retention value.\n```\n\n"
                "The verified retention value is thirty days.\n",
                encoding="utf-8")
            result = create_provider(self._configuration(source)).invoke(
                {"query": "Example retention value"}, context={})
            fact = result.output["results"][0]
            self.assertIn("Example retention value.", fact["content"])
            self.assertIn("h1.verified-section@L1", fact["source_path"])
            self.assertNotIn("example-only-heading", fact["source_path"])

    def test_approved_charter_and_roadmap_are_real_retrievable_sources(self):
        charter = ROOT / "docs/PROJECT_CHARTER_REVISION_2_REVIEW.md"
        roadmap = ROOT / "docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md"
        config = {"sources": [
            {"source_id": "knowledge.r3.charter.revision-2", "path": str(charter),
             "freshness_max_age_seconds": 86400},
            {"source_id": "knowledge.r3a.master-roadmap.baseline-1", "path": str(roadmap),
             "freshness_max_age_seconds": 86400},
        ], "max_results": 10, "max_document_bytes": 1024 * 1024}
        provider = create_provider(config)
        charter_result = provider.invoke({"query": "Grace Director of Operations"}, context={})
        roadmap_result = provider.invoke({"query": "AP1 knowledge grounding retrieval"}, context={})
        combined_result = provider.invoke(
            {"query": "Who owns personnel records, and what does AP1 require for knowledge grounding?"},
            context={})
        self.assertIn("knowledge.r3.charter.revision-2",
                      {item["source_id"] for item in charter_result.output["results"]})
        self.assertIn("knowledge.r3a.master-roadmap.baseline-1",
                      {item["source_id"] for item in roadmap_result.output["results"]})
        roadmap_fact = next(item for item in roadmap_result.output["results"]
                            if item["source_id"] == "knowledge.r3a.master-roadmap.baseline-1")
        self.assertIn("AP1 — Grace autonomy and institutional continuity", roadmap_fact["content"])
        self.assertIn("table-row", roadmap_fact["source_path"])
        self.assertNotIn("AP0 — Institutional foundation", roadmap_fact["content"])
        self.assertTrue({"knowledge.r3.charter.revision-2",
                         "knowledge.r3a.master-roadmap.baseline-1"}.issubset(
                             {item["source_id"] for item in combined_result.output["results"]}))
        for result in (charter_result, roadmap_result):
            fact = result.output["results"][0]
            self.assertRegex(fact["source_path"], r"markdown\..+@L\d+-L\d+$")
            self.assertEqual(fact["document_sha256"], fact["document_revision"])
            self.assertEqual(fact["excerpt_sha256"], fact["sha256"])
            self.assertTrue(result.evidence)

    def test_real_engineering_workflow_and_verification_sources_are_retrievable(self):
        execution = ROOT / "hints/development-execution.md"
        acceptance = ROOT / "docs/architecture/R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md"
        config = {"sources": [
            {"source_id": "knowledge.r3.development-execution", "path": str(execution),
             "freshness_max_age_seconds": 86400},
            {"source_id": "knowledge.r3a.testing-acceptance-policy", "path": str(acceptance),
             "freshness_max_age_seconds": 86400},
        ], "max_results": 10, "max_document_bytes": 1024 * 1024}
        provider = create_provider(config)
        workflow = provider.invoke(
            {"query": "inspect local and already-retrieved evidence before executing commands"},
            context={})
        verification = provider.invoke(
            {"query": "risk-based bounded validation proportional to changed behavior"}, context={})
        self.assertTrue(any(item["source_id"] == "knowledge.r3.development-execution"
                            for item in workflow.output["results"]))
        self.assertTrue(any(item["source_id"] == "knowledge.r3a.testing-acceptance-policy"
                            for item in verification.output["results"]))


if __name__ == "__main__":
    unittest.main()
