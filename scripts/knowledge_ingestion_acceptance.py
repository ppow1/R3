#!/usr/bin/env python3
"""Run a local PostgreSQL/CME acceptance exercise against isolated dev data.

The Steward principal/grant are explicit test credentials created only in the
isolated database. This exercises auth enforcement; it does not impersonate the
AP3 browser session or bind decisions to the real catalog entries.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

from r3a_plugins.institutional_knowledge_v1_2_0.review_store import KnowledgeReviewStore
from r3a_runtime.authorization import CapabilityGrantAuthorizationProvider
from r3a_runtime.capability_contracts import CapabilityRegistry, operation_from_manifest
from r3a_runtime.cme import CME
from r3a_runtime.db import Store


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/knowledge-discovery/knowledge_review_proposals.v1.json"
PRINCIPAL = "steward:pat"


def request_for(operation, input_data, *, key, caller, activity=None):
    act = activity or str(uuid.uuid4())
    return {"contract_id":"r3a.capability-invocation.v1",
            "contract_version":"1.1.0" if operation.descriptor["effect_class"].startswith("steward_") else "1.0.0",
            "invocation_id":str(uuid.uuid5(uuid.NAMESPACE_URL,key)),
            "operation_id":operation.descriptor["operation_id"],
            "operation_contract_version":operation.descriptor["contract_version"],
            "caller":caller,"target":{},"input":input_data,
            "activity_id":None if operation.descriptor["effect_class"].startswith("steward_") else act,
            "attempt_id":None if operation.descriptor["effect_class"].startswith("steward_") else str(uuid.uuid5(uuid.NAMESPACE_URL,act+":attempt")),
            "correlation_id":str(uuid.uuid5(uuid.NAMESPACE_URL,key+":correlation")),
            "work_order":None,"budget_reservation":None,"evidence_purpose":"isolated governed knowledge acceptance",
            "idempotency_key":key,"deadline":None,"config_revision":hashlib.sha256(b"isolated-knowledge-acceptance").hexdigest()}


async def main():
    dsn = os.environ.get("R3A_KNOWLEDGE_DATABASE_DSN")
    if not dsn:
        raise SystemExit("set R3A_KNOWLEDGE_DATABASE_DSN to the isolated PostgreSQL database")
    settings = SimpleNamespace(connection_info={"dbname":"r3a_knowledge","user":"admin1","host":"127.0.0.1","port":55494}, worker_concurrency=1)
    # Permit a DSN other than the documented local acceptance endpoint.
    from psycopg.conninfo import conninfo_to_dict
    settings.connection_info = conninfo_to_dict(dsn)
    settings.source_digest = hashlib.sha256(b"isolated-knowledge-acceptance").hexdigest()
    settings.module_id = "resident.grace"
    settings.data_dir = Path.home()/".local/share/r3a-knowledge-provider"
    settings.heartbeat_stale_after_seconds = 10
    settings.machine_catalog_dir = ROOT/"r3a_runtime/state_machines"
    registry = CapabilityRegistry()
    config = {"sources":[{"source_id":"acceptance.process-state-machine",
                           "path":str(ROOT/"r3a_runtime/state_machines/process.json"),
                           "freshness_max_age_seconds":86400}],
              "max_results":10,"max_document_bytes":1048576,
              "database_dsn_env":"R3A_KNOWLEDGE_DATABASE_DSN"}
    for filename in ("manifest.read.json","manifest.proposals-list.json","manifest.proposals-decide.json"):
        manifest=json.loads((ROOT/"r3a_plugins/institutional_knowledge_v1_2_0"/filename).read_text())
        descriptor=operation_from_manifest(manifest)
        registry.register(descriptor,config,legacy_manifest=manifest)
    settings.capability_registry=registry
    store=Store(settings)
    await store.migrate()
    await store.open()
    runtime=None
    try:
        for item in registry.discover():
            d=item["descriptor"]
            mode={"read":"read_only","steward_read":"steward_read","steward_write":"steward_write"}[d["effect_class"]]
            await store.register_capability(d["operation_id"],d["provider"]["provider_id"],mode,
                contract_version=d["contract_version"],metadata={"allowed_steward_principals":d["caller_constraints"]["allowed_principals"]})
        for cap in ("institution.knowledge.proposals.list","institution.knowledge.proposals.decide"):
            await store.grant_capability(PRINCIPAL,cap,"isolated local auth-path acceptance grant")
        await store.grant_capability("resident.grace","institution.knowledge.read","isolated knowledge retrieval acceptance grant")
        await store.seed_machines()
        from r3a_runtime.provider_runtime import ProviderProcessManager
        runtime=ProviderProcessManager(settings,store,registry)
        activation=await runtime.activate(registry.resolve("institution.knowledge.proposals.list","1.1.0"))
        catalog=json.loads(CATALOG.read_text())
        summary=KnowledgeReviewStore(dsn).import_catalog(catalog)
        # Use durable acceptance copies whose content/provenance are copied from
        # actual reviewed documents. The seven original entries remain pending.
        demo=json.loads(json.dumps(catalog))
        ids={"r3-source-boundary":"acceptance-demo-source-boundary",
             "r3-knowledge-grounding":"acceptance-demo-knowledge-grounding",
             "external-no-silent-promotion":"acceptance-demo-no-silent-promotion"}
        demo["entries"]=[entry for entry in demo["entries"] if entry["entry_id"] in ids]
        for entry in demo["entries"]: entry["entry_id"]=ids[entry["entry_id"]]
        for batch in demo["batches"]:
            batch["entry_ids"]=[ids[x] for x in batch["entry_ids"] if x in ids]
            if batch["entry_ids"]: batch["batch_id"]="acceptance-demo-"+batch["batch_id"]
        demo["batches"]=[b for b in demo["batches"] if b["entry_ids"]]
        KnowledgeReviewStore(dsn).import_catalog(demo)

        cme=CME.__new__(CME)
        cme.settings=settings;cme.store=store;cme.authorization_provider=CapabilityGrantAuthorizationProvider(store,settings.source_digest)
        cme.provider_runtime=runtime
        principal={"principal_id":PRINCIPAL,"resident_id":None,"service_id":None}
        listing=registry.resolve("institution.knowledge.proposals.list","1.1.0")
        listed=await cme.invoke_capability(request_for(listing,{"include_decided":False},key="knowledge-acceptance-list-v1",caller=principal))
        proposals=listed["output"]["proposals"]
        batch_summaries=[{"batch_id":b["batch_id"],"title":b["title"],"entry_count":b["entry_count"],
                           "pending_count":b["pending_count"],"source_digest":b["source_digest"]}
                          for b in listed["output"]["batches"] if not b["batch_id"].startswith("acceptance-demo-")]
        selected={p["proposal_id"]:p for p in proposals}
        decisions=[
          {"proposal_id":ids["r3-source-boundary"],"proposal_revision":selected[ids["r3-source-boundary"]]["proposal_revision"],"source_digest":selected[ids["r3-source-boundary"]]["source_digest"],"decision":"approve"},
          {"proposal_id":ids["r3-knowledge-grounding"],"proposal_revision":selected[ids["r3-knowledge-grounding"]]["proposal_revision"],"source_digest":selected[ids["r3-knowledge-grounding"]]["source_digest"],"decision":"reject","rationale":"Acceptance exercise verifies rejected material is excluded."},
          {"proposal_id":ids["external-no-silent-promotion"],"proposal_revision":selected[ids["external-no-silent-promotion"]]["proposal_revision"],"source_digest":selected[ids["external-no-silent-promotion"]]["source_digest"],"decision":"defer","individual_review":True,"rationale":"Acceptance exercise verifies an individually flagged item can be deferred."},
        ]
        deciding=registry.resolve("institution.knowledge.proposals.decide","1.1.0")
        from r3a_runtime.capability_contracts import CapabilityContractError
        try:
            await cme.invoke_capability(request_for(deciding,{"decisions":decisions},key="knowledge-acceptance-denied-caller-v1",caller={"principal_id":"resident:grace","resident_id":"resident.grace","service_id":None}))
            raise RuntimeError("resident caller unexpectedly passed Steward operation constraints")
        except CapabilityContractError:
            pass
        flagged=dict(decisions[2]);flagged.pop("individual_review");flagged.pop("rationale")
        try:
            KnowledgeReviewStore(dsn).decide({"decisions":[flagged]},
                {"caller":principal,"authorization":{"allowed":True,"decision_id":"test-only","audit_event_id":"test-only"},
                 "effect_class":"steward_write","idempotency_key":"knowledge-acceptance-flagged-bulk-v1",
                 "invocation_id":"test-only","correlation_id":str(uuid.uuid4())})
            raise RuntimeError("flagged proposal unexpectedly passed bulk review requirements")
        except ValueError as exc:
            if "individual review" not in str(exc): raise
        stale=dict(decisions[0]);stale["source_digest"]="0"*64
        try:
            KnowledgeReviewStore(dsn).decide({"decisions":[stale]},
                {"caller":principal,"authorization":{"allowed":True,"decision_id":"test-only","audit_event_id":"test-only"},
                 "effect_class":"steward_write","idempotency_key":"knowledge-acceptance-stale-source-v1",
                 "invocation_id":"test-only","correlation_id":str(uuid.uuid4())})
            raise RuntimeError("stale source digest unexpectedly passed review")
        except ValueError as exc:
            if "changed after review" not in str(exc): raise
        decision_request=request_for(deciding,{"decisions":decisions},key="knowledge-acceptance-decisions-v1",caller=principal)
        committed=await cme.invoke_capability(decision_request)
        replay=await cme.invoke_capability(decision_request)
        if replay != committed: raise RuntimeError("canonical decision replay changed its durable result")
        changed=json.loads(json.dumps(decision_request))
        changed["input"]["decisions"][0]["rationale"]="different input under the same idempotency key"
        try:
            await cme.invoke_capability(changed)
            raise RuntimeError("changed invocation unexpectedly reused an idempotency key")
        except ValueError as exc:
            if "different canonical request" not in str(exc): raise
        read=registry.resolve("institution.knowledge.read")
        grace={"principal_id":"resident:grace","resident_id":"resident.grace","service_id":None}
        approved_query="Riverview 3 engineering operational runbooks ppow1 R3"
        retrieved=await cme.invoke_capability(request_for(read,{"query":approved_query,"limit":10},key="knowledge-acceptance-retrieval-v1",caller=grace))
        approved=[x for x in retrieved["output"]["results"] if x.get("source_id")=="institutional:acceptance-demo-source-boundary:v1"]
        rejected_query="designated Steward decision established authorized promotion operation"
        isolated=await cme.invoke_capability(request_for(read,{"query":rejected_query,"limit":10},key="knowledge-acceptance-isolation-v1",caller=grace))
        non_promoted_ids={"institutional:acceptance-demo-knowledge-grounding:v1","institutional:acceptance-demo-no-silent-promotion:v1"}
        non_promoted_matches=[x["source_id"] for x in isolated["output"]["results"] if x.get("source_id") in non_promoted_ids]
        if not approved or non_promoted_matches:
            raise RuntimeError("approved retrieval or rejected/deferred isolation acceptance failed")
        # Verify originals remain pending and test item/decision lineage is durable after a new DB connection.
        import psycopg
        with psycopg.connect(dsn) as conn:
            original_states=conn.execute("SELECT state,count(*) FROM r3a.knowledge_proposals WHERE proposal_id NOT LIKE 'acceptance-demo-%' GROUP BY state ORDER BY state").fetchall()
            durable=conn.execute("SELECT count(*) FROM r3a.knowledge_review_decisions WHERE proposal_id LIKE 'acceptance-demo-%'").fetchone()[0]
            promoted=conn.execute("SELECT knowledge_item_id,source_digest,content_sha256,source_references,reviewer_principal,approved_at FROM r3a.institutional_knowledge_items WHERE knowledge_item_id='institutional:acceptance-demo-source-boundary:v1'").fetchone()
        print(json.dumps({"provider":"r3a.institutional-knowledge@1.2.0","provider_process":activation,"operations":["institution.knowledge.proposals.list@1.0.0","institution.knowledge.proposals.decide@1.0.0","institution.knowledge.read@1.1.0"],"catalog_import":summary,"catalog_batches":batch_summaries,"acceptance_demo_catalog_ids":ids,"decisions":committed["output"]["decisions"],"decision_replay_identical":replay==committed,"fail_closed_checks":["non-Steward caller","flagged item bulk decision","stale source digest","changed request under reused idempotency key"],"retrieval":{"knowledge_item_id":approved[0]["source_id"],"uri":approved[0]["uri"],"source_digest":approved[0]["source_sha256"],"content_digest":approved[0]["sha256"],"source_references":approved[0]["source_references"],"approval":approved[0]["approval"]},"rejected_deferred_knowledge_matches":non_promoted_matches,"other_configured_source_matches":len(isolated["output"]["results"]),"original_catalog_states":original_states,"durable_test_decision_count":durable,"durable_promoted_record":promoted,"authorization":committed["authorization"]},default=str,indent=2))
    finally:
        if runtime is not None and runtime.processes:
            provider_id,provider_version=next(iter(runtime.processes))
            await runtime.stop(provider_id,provider_version)
        await store.close()


if __name__=="__main__":
    asyncio.run(main())
