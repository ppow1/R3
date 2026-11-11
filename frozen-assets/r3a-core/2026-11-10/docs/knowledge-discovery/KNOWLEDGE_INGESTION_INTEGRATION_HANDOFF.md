<!--
R3 CONTROLLED DOCUMENT
File: docs/knowledge-discovery/KNOWLEDGE_INGESTION_INTEGRATION_HANDOFF.md
Component: R3A-KNOWLEDGE-INGESTION-INTEGRATION
File Revision: 1.0.0
Created: 2026-11-08 UTC
Created By: Codex GPT-6
Purpose: Give Coordinator and Website the exact external manifest/config/grant additions for governed Knowledge review.
Execution Model: Shared bootstrap references three Knowledge operation manifests and one shared provider configuration.
Observability: Generic provider lifecycle, capability registry and authorization events.
Dependencies: Issues #43/#46/#47/#51; current integration baseline b835ed4.
Authority: R3A Knowledge ingestion directive.
Changed: 2026-11-08 | AP1-K1 | Publish integration handoff.
Supersedes: None.
Contracts: r3a.knowledge-review-api.v1@1.0.0; capability operation/invocation v1.1.0 Steward effects.
Tests: scripts/knowledge_ingestion_acceptance.py.
History/Predecessor: New document.
-->
# Governed Knowledge ingestion integration handoff

## External runtime configuration

Use one provider configuration file for all three operation manifests. `sources` remains externally selected; point it at the approved Charter and roadmap sources plus any other enabled local institutional sources. Preserve the existing configured source IDs and bounds. Add the database environment variable reference:

```json
{
  "sources": [
    {
      "source_id": "<configured-source-id>",
      "path": "<absolute-approved-document-path>",
      "freshness_max_age_seconds": 86400
    }
  ],
  "max_results": 10,
  "max_document_bytes": 1048576,
  "database_dsn_env": "R3A_KNOWLEDGE_DATABASE_DSN"
}
```

Set `R3A_KNOWLEDGE_DATABASE_DSN` in the provider environment to the existing R3A PostgreSQL connection; credentials remain out of JSON. Each module manifest allowlists this environment name. Do not point the managed runtime at the isolated acceptance database.

Add these operation entries to the existing `capability_operations` bootstrap array, each referencing the same provider config file:

```json
[
  {"manifest":"<knowledge>/manifest.read.json", "configuration":"<external>/knowledge-provider.json"},
  {"manifest":"<knowledge>/manifest.proposals-list.json", "configuration":"<external>/knowledge-provider.json"},
  {"manifest":"<knowledge>/manifest.proposals-decide.json", "configuration":"<external>/knowledge-provider.json"}
]
```

The read descriptor stays `institution.knowledge.read`, operation revision 1.1.0, operation contract 1.0.0, and Grace-only caller constraint. Proposal list and decision manifests are separate operations under the same provider `r3a.institutional-knowledge@1.2.0`; their contract version is 1.1.0 and only `steward:pat` is allowed in the current prototype manifests. Replace that literal only if AP3's authoritative principal differs, then coordinate the manifest update.

## PostgreSQL and grants

Apply migration `010_governed_knowledge.sql` through the existing `Store.migrate()` ladder after the coordinator's migration 009. The migration extends the generic capability access-mode enum with `steward_read`/`steward_write` and adds the three Knowledge review/promotion tables. It does not create any capability grants.

After operation registration, explicitly grant `institution.knowledge.proposals.list` and `institution.knowledge.proposals.decide` to the exact allowed Steward principal using the existing CME capability-grant path. Registration alone authorizes nothing. Existing Grace read grants for `institution.knowledge.read` remain required. Website forwards through authenticated Steward Access; AP3 must supply the principal, and CME applies its ordinary grant-backed authorization and audit.

## Isolated acceptance environment

The automated acceptance runner expects a separate local PostgreSQL 16 cluster/database with canonical prerequisite migrations and an isolated test grant. For a fresh development host, create a private cluster owned by the developer account, create database `r3a_knowledge`, and provision the prerequisite non-login role `r3a_runtime`. Then run:

```sh
R3A_KNOWLEDGE_DATABASE_DSN='host=127.0.0.1 port=<isolated-port> dbname=r3a_knowledge user=<isolated-test-user>' \
  .venv/bin/python scripts/knowledge_ingestion_acceptance.py
```

The runner applies all canonical migrations, loads the actual seven source-grounded proposals as pending, activates the provider child process, and exercises list/decision/retrieval through the generic CME dispatcher. Three `acceptance-demo-*` copies exercise approve, reject, and defer. The test-granted `steward:pat` principal is a local authorization fixture, not a browser-authenticated Steward. All seven real catalog entries remain pending. Do not report the fixture decisions as institutional approval.

## Website behavior

Website can render the published input/output schemas through existing authenticated capability discovery and invoke route. Use returned batch title, description, source set, summary, conflict notes, recommendation, and state counts to summarize each batch; use `batch_id` to group entries and `next_cursor` to paginate. Expand batch actions into explicit item decisions; submit `individual_review: true` plus rationale for every flagged/conflicting proposal. Show item `decision_id`, reviewer, time, source digest, CME authorization/audit references, and `knowledge_item_id` on approval. Verify approval by calling the existing Knowledge read operation and displaying its provenance citation.
