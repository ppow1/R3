<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_CHARACTER_INTEGRATION_HANDOFF.md
Component: R3A-RESIDENT-CHARACTER-INTEGRATION
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact creation time not captured)
Created By: Codex GPT-6
Purpose: Prepare Coordinator and Autonomy integration of resident dossier architecture.
Execution Model: Integration handoff; no changes to sibling worktrees or managed runtime.
Observability: Branch and contract references plus explicit prerequisites and rollback.
Dependencies: R3A resident directory, execution profile, capability grants, AP0 schema migration.
Authority: Steward directive; user authorized branch implementation, commit, and push; no deployment.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Record cross-workstream integration requirements.
Supersedes: None
Contracts: R3A_RESIDENT_CHARACTER_ARCHITECTURE.md; resident dossier and runtime binding v1.
Tests: 171 repository unittests pass in an isolated virtualenv; 11 dossier instances validate against JSON Schema; no database migration or live directory query was run.
History/Predecessor: New file.
-->
# Character Architecture Integration Handoff

## Current worktree boundaries

Character Architecture source branch: `engineering/r3a-character-architecture-20261107`, starting at `388dd6515f37a6ac52e681fc713a7be99d3f6076`. At discovery, sibling worktrees were `../coordinator` on `engineering/r3a-coordinator-20261107` at `7202d5c` and `../live-modular` on `integration/r3a-live-modular-candidate-20261108` at `8ec1259`. They were inspected read-only. This workstream did not modify their live worktrees, CME dispatch, Grace runtime prompt, provider configuration, grants, live databases, or services.

The current related R3A coordination issues inspected were [#43 (AP1 Grace autonomy)](https://github.com/ppow1/R3/issues/43), [#47 (AP1 knowledge retrieval)](https://github.com/ppow1/R3/issues/47), and [#46 (modular capability plugins)](https://github.com/ppow1/R3/issues/46). These AP1 scopes do not authorize or track this AP4 Character Architecture assignment, so none was repurposed. No Character Architecture AP4 milestone issue was present in the inspected results. The contracts below are implementation handoff requirements, not evidence that Coordinator or Autonomy has integrated them.

## Required interfaces

1. Obtain a fresh, bounded authoritative directory snapshot from `institutional.directory.discover`. Resolve the dossier ID through an explicit, verified crosswalk before calling `DossierRepository.get`. Do not equate HR `r3:*` IDs and directory/runtime `resident.*` IDs from matching names.
2. Load the dossier version and call `compose_prompt`. Persist the component refs, source refs and digest with the request/provenance record. Include only approved `public` and `institutional` modules. Never pass `personnel_sensitive` or `protected` source material through a generic prompt.
3. Merge settings through `resolve_personality`; persist the resolved values and winning scopes for reproducibility. Durable traits, memory, mood, relationships and provider settings stay distinct.
4. Bind execution through `runtime_binding` or an adapter implementing `r3a.resident.runtime-binding@1.0.0`. The authoritative directory still supplies identity and office evidence. CME still supplies/authorizes operations and grants. Do not copy capabilities into the dossier.
5. Pass claim-level epistemic spans and source references independently of visible rendering. Keep resident annotations, audit findings, corrections and message-level status as separate durable facts. Existing ordinary chat responses must not wait on a mandatory extra inference pass.

## Database and compatibility

`r3a_runtime/migrations/009_resident_dossiers.sql` adds immutable revision records, a current pointer, and governance/rollback events. It is additive and unexecuted. Apply only in an isolated candidate DB after review of migration order, role grants, constraints, and transaction behavior. Runtime service roles must not receive direct UPDATE/DELETE on revision/event rows. A narrowly scoped service may create successor revisions and atomically update the pointer. Protected HR and private character records require a separate governed source and authorized projection; do not bulk import.

Grace compatibility: current primary runtime uses `resident.grace`; the legacy HR snapshot uses `r3:grace`. The directory crosswalk is unavailable in this environment, so do not attach the dossier prompt to a live Grace turn yet. Preserve the current `r3a.resident.execution-profile@1.0.0` and current Grace system prompt. After crosswalk confirmation, compose dossier modules as an additive context adapter and verify route/profile lineage. Existing Grace behavior and its CME authority path remain owned by the current runtime.

Vicky integration: `r3:vicky` has the Engineering Manager / Foundry minimum context and configurable dimensions but no canonical ID, approved character bible, qualification claims, provider route, memory, or relationships. Obtain the authoritative directory ID/office/lifecycle and Helen/Jessica source approvals before activating a Vicky runtime binding. Her dossier alone is not onboarding completion.

Chloe is a charter-listed Chief Architect and a legacy HR row, but authoritative identity/office confirmation remains open. The `chatgpt_mediated_candidate_unverified` implementation marker is a requested candidate mode, not an available or authorized provider route.

## Known interface risks

- Directory output currently lacks a responsibilities field. Responsibilities in dossiers are linked to charter/HR evidence, not to a current directory binding.
- The directory source contract is PostgreSQL `riverview_authority`; no configured read credential or API returned here. The directory provider's empty/unavailable response is not a roster.
- HR docs describe a distinct SQLite service and governed capabilities. No HR-to-directory import/synchronization contract is documented.
- Dossier data and tests are new packages. Existing Grace/CME tests may require the R3A virtual environment dependencies (`psycopg`, `psycopg_pool`) not installed in the system Python used for the initial test attempt.
- The approved roadmap places Jessica/character development in AP4. This Steward directive specifically authorizes the Character Architecture workstream implementation and explicitly requests integration preparation with Coordinator/Autonomy. Keep this work as an isolated interface/data-layer change; do not unilaterally reprioritize or amend milestone acceptance beyond that explicit directive.

## Deployment prerequisites and rollback

No deployment is requested or performed. Before future runtime integration: confirm authoritative resident roster/crosswalk; agree stable Coordinator/Autonomy adapter contract; approve and apply the migration only to isolated R3A candidate DB; provision least-privilege roles; configure per-resident providers outside code; obtain Helen/Jessica authenticated review workflows; validate privacy filtering and prompt lineage; run existing AP1/AP2 regression and target integration checks.

Rollback leaves immutable dossier/event history intact and points the current revision to a retained predecessor, recording the actor, reason and event. For an adapter rollout, disable the adapter through validated configuration and resume the existing resident profile/system prompt path. Do not remove migration data or reset identity/authority state as a rollback shortcut.
