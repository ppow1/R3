<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_INSTITUTIONAL_KNOWLEDGE_CAPABILITY.md
Component: R3A-INSTITUTIONAL-KNOWLEDGE
File Revision: 1.2.0
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: Describe the authorized institutional knowledge provider, sources, evidence, and operating boundaries.
Execution Model: Deterministic in-process retrieval through CME's resident capability path.
Observability: Registry operation/provider revision, per-source availability/freshness, document and excerpt SHA-256, and retrieval timestamps.
Dependencies: R3A capability-operation v1; CME activity-scoped grants; externally configured local source files.
Authority: AP1 / R3A-019; Grace owns reasoning and decisions, CME owns authorization and dispatch.
Changed: 2026-11-07T22:00:34Z | AP1-K2 | Codex GPT-6 | Document source inventory, Markdown citations, freshness, and current managed-config boundary.
Changed: 2026-11-07T22:08:20Z | AP1-K2 | Codex GPT-6 | Classify engineering guidance and existing directory/runbook authorities.
Supersedes: None.
Contracts: institution.knowledge.read@1.1.0; r3a.capability-operation.v1.
Tests: tests/test_r3a_institutional_knowledge.py; tests.test_r3a_capability_contracts; tests.test_r3a_ap1.
History/Predecessor: Git blob fd57ca51b98f1ef8135bcc70a431ca5fb4d49772 at commit 0be4c92986bb2db54b07840d80742a63e84a207a.
-->
# R3A institutional knowledge retrieval capability

## Capability and retrieval behavior

Grace selects the existing `institution.knowledge.read` operation through the
resident capability interface. Its provider is dynamically registered from
`r3a_plugins/institutional_knowledge/manifest.json` using the canonical
`r3a.capability-operation.v1` contract. AP1-K2 advances the implementation
revision from `1.0.1` to `1.1.0` for section/line citation semantics while
keeping the operation ID, input/output schemas, activity-scoped grant, and CME
dispatch unchanged.

The provider reuses `r3a_runtime.knowledge.retrieve_bytes`. JSON sources are
extracted into deterministic keyed facts. Markdown sources are divided into
paragraphs, list items, and table rows, with heading hierarchy and physical
line ranges in `source_path`. Each result carries its configured source ID,
file URI, source path, document revision/SHA-256, excerpt SHA-256, file
modification time, retrieval time, freshness, and matched terms.

Every invocation rereads the bounded bytes and recomputes the document hash;
there is no in-memory index cache to invalidate. Freshness is assessed against
the configured age threshold, while the digest detects content changes even
when the file timestamp is unreliable. Missing, oversized, or unreadable
sources stay visible as unavailable observations; stale sources are still
identified as stale. No matching facts produces no evidence.

## Source selection and authority

Source selection is external configuration: the provider searches every source
listed in the configured `sources` array and has no hardcoded document roster
or model-controlled source selector. Adding a source therefore requires an
explicit configuration change, with an institutionally appropriate source ID,
absolute path, and freshness threshold. A configured path is a retrieval
allowlist, not a new authority decision or capability grant.

The inspected repository contains the Steward-approved R3 Charter Revision 2
at `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md`, the Steward-approved R3A
Master Roadmap Baseline 1.0 at
`docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md`, and controlled R3A
architecture, capability, lifecycle, state-machine, and verification
documents. Steward-directed R3 engineering guidance is available in
`hints/development-governance.md`, `hints/development-execution.md`,
`hints/development-bootstrap.md`, `hints/engineering.md`, and
`hints/file-provenance.md`. The R3A
architecture charter supplements rather than supersedes the institutional
charter. Historical project notes, punch lists, generic deployment runbooks,
and unverified personnel or resident records are not presumed authoritative.
The AP0-M1 plan is planning-only, and no dedicated R3A operational runbook was
found. The Steward-authorized command-grant runbook contains an imported
historical commissioning appendix, so it is classified as a separate security
authority source and is not in the proposed general Grace corpus. Current
office/occupant data has an existing `institutional.directory.discover`
adapter and is not copied into a static document index.
The charter explicitly keeps Evelyn's private continuity/communications out
of general operational search and requires separate protected boundaries for
Gray Man; neither is part of the proposed general Grace corpus.

The managed AP1-K1 external configuration inspected for this work still
contains the process lifecycle JSON source only and remains on operation
revision `1.0.1`. The K2 multi-document
configuration was exercised against the actual checked-in charter, roadmap,
capability contract, lifecycle specification, verification policy, engineering
guidance, and process state machine, but has not been installed into the shared
runtime. Runtime
configuration/restart and a Grace 80B objective using multiple institutional
sources are pending a coordinator-scheduled shared-runtime window.

## Authority and continuity

CME continues to check the activity-scoped `institution.knowledge.read`
grant, invoke the registered provider, and persist its result through Grace's
existing continuation. Grace decides whether to retrieve, reasons over the
returned evidence, and interprets or cites it. Registry presence does not
grant access; retrieval supplies evidence and makes no institutional
decision. No separate registry, scheduler, or decision engine is introduced.
