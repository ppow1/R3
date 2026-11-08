import copy
import json
import unittest
from pathlib import Path
from r3a_plugins.institutional_knowledge.review_store import KnowledgeReviewStore, validate_item_decision

from r3a_runtime.capability_contracts import (CapabilityContractError, operation_from_manifest,
                                               validate_invocation_request, validate_operation)


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "r3a_plugins/institutional_knowledge"


class GovernedKnowledgeContractTests(unittest.TestCase):
    def test_existing_grace_read_and_steward_review_operations_register_separately(self):
        ops = {}
        for filename in ("manifest.read.json", "manifest.proposals-list.json", "manifest.proposals-decide.json"):
            manifest = json.loads((MANIFESTS / filename).read_text())
            operation = operation_from_manifest(manifest)
            ops[operation["operation_id"]] = operation
        read = ops["institution.knowledge.read"]
        self.assertEqual("1.0.0", read["contract_version"])
        self.assertEqual("1.1.0", read["operation_revision"])
        self.assertEqual("1.2.0", read["provider"]["provider_version"])
        self.assertEqual(["resident.grace"], read["caller_constraints"]["allowed_residents"])
        self.assertEqual("1.1.0", ops["institution.knowledge.proposals.list"]["contract_version"])
        self.assertEqual("steward_read", ops["institution.knowledge.proposals.list"]["effect_class"])
        self.assertEqual(["steward:pat"], ops["institution.knowledge.proposals.list"]["caller_constraints"]["allowed_principals"])
        decision = ops["institution.knowledge.proposals.decide"]
        self.assertEqual("1.1.0", decision["contract_version"])
        self.assertEqual("steward_write", decision["effect_class"])
        self.assertEqual(["steward:pat"], decision["caller_constraints"]["allowed_principals"])

    def test_steward_write_requires_explicit_principal_and_new_operation_contract(self):
        descriptor = operation_from_manifest(json.loads((MANIFESTS / "manifest.proposals-decide.json").read_text()))
        invalid = copy.deepcopy(descriptor)
        invalid["caller_constraints"]["allowed_principals"] = []
        with self.assertRaisesRegex(CapabilityContractError, "explicit Steward"):
            validate_operation(invalid)
        invalid = copy.deepcopy(descriptor)
        invalid["contract_version"] = "1.0.0"
        with self.assertRaisesRegex(CapabilityContractError, "capability-operation.v1 contract"):
            validate_operation(invalid)

    def test_steward_invocation_allows_null_activity_only_for_exact_steward_contract(self):
        descriptor = operation_from_manifest(json.loads((MANIFESTS / "manifest.proposals-decide.json").read_text()))
        request = {"contract_id":"r3a.capability-invocation.v1","contract_version":"1.1.0",
                   "invocation_id":"inv-1","operation_id":descriptor["operation_id"],
                   "operation_contract_version":"1.1.0",
                   "caller":{"principal_id":"steward:pat","resident_id":None,"service_id":None},
                   "target":{},"input":{"decisions":[{"proposal_id":"p1","proposal_revision":1,
                     "source_digest":"a"*64,"decision":"defer"}]},
                   "activity_id":None,"attempt_id":None,"correlation_id":"00000000-0000-4000-8000-000000000001",
                   "work_order":None,"budget_reservation":None,"evidence_purpose":"review proposals",
                   "idempotency_key":"review-1","deadline":None,"config_revision":"b"*64}
        self.assertEqual("steward:pat", validate_invocation_request(request, descriptor)["caller"]["principal_id"])
        request["caller"]["principal_id"] = "resident:grace"
        with self.assertRaisesRegex(CapabilityContractError, "allowed_principals"):
            validate_invocation_request(request, descriptor)

    def test_non_steward_operations_still_require_activity_lineage(self):
        descriptor = operation_from_manifest(json.loads((MANIFESTS / "manifest.read.json").read_text()))
        request = {"contract_id":"r3a.capability-invocation.v1","contract_version":"1.0.0",
                   "invocation_id":"inv-1","operation_id":descriptor["operation_id"],
                   "operation_contract_version":"1.0.0",
                   "caller":{"principal_id":"resident:grace","resident_id":"resident.grace","service_id":None},
                   "target":{},"input":{},"activity_id":None,"attempt_id":None,
                   "correlation_id":"00000000-0000-4000-8000-000000000001","work_order":None,
                   "budget_reservation":None,"evidence_purpose":"list proposals","idempotency_key":None,
                   "deadline":None,"config_revision":"b"*64}
        with self.assertRaisesRegex(CapabilityContractError, "activity_id and attempt_id"):
            validate_invocation_request(request, descriptor)

    def test_steward_list_allows_direct_authenticated_session_without_activity(self):
        descriptor = operation_from_manifest(json.loads((MANIFESTS / "manifest.proposals-list.json").read_text()))
        request = {"contract_id":"r3a.capability-invocation.v1","contract_version":"1.1.0",
                   "invocation_id":"inv-1","operation_id":descriptor["operation_id"],
                   "operation_contract_version":"1.1.0",
                   "caller":{"principal_id":"steward:pat","resident_id":None,"service_id":None},
                   "target":{},"input":{"include_decided":False},"activity_id":None,"attempt_id":None,
                   "correlation_id":"00000000-0000-4000-8000-000000000001","work_order":None,
                   "budget_reservation":None,"evidence_purpose":"review proposals","idempotency_key":None,
                   "deadline":None,"config_revision":"b"*64}
        self.assertIsNone(validate_invocation_request(request, descriptor)["activity_id"])

    def test_provider_refuses_binding_decision_without_cme_authorization(self):
        store = KnowledgeReviewStore("host=127.0.0.1 port=1 dbname=unreachable")
        with self.assertRaisesRegex(PermissionError, "authenticated CME Steward authorization"):
            store.decide({"decisions":[{"proposal_id":"p","decision":"approve"}]},
                         {"effect_class":"steward_write","caller":{"principal_id":"steward:pat"},
                          "authorization":{"allowed":False}})

    def test_flagged_items_require_individual_review_and_sensitive_content_cannot_be_promoted(self):
        item={"flags":["uncertain-authority"]}
        with self.assertRaisesRegex(ValueError,"individual review"):
            validate_item_decision(item,{"decision":"approve"})
        validate_item_decision(item,{"decision":"defer","individual_review":True,"rationale":"review later"})
        with self.assertRaisesRegex(PermissionError,"cannot be promoted"):
            validate_item_decision({"flags":["credential"]},
                                   {"decision":"approve","individual_review":True,"rationale":"reviewed"})


if __name__ == "__main__":
    unittest.main()
