<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_RESIDENT_CHARACTER_INTEGRATION_HANDOFF.md
Component: R3A-RESIDENT-CHARACTER-INTEGRATION
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact creation time not captured)
Created By: Codex GPT-6
Purpose: Prepare Coordinator and Autonomy integration of resident dossier architecture.
Execution Model: Integration handoff; Character Architecture branch includes an optional Grace inference context hook; sibling worktrees and running services remain unchanged.
Observability: Branch and contract references plus explicit prerequisites and rollback.
Dependencies: R3A resident directory, execution profile, capability grants, AP0 schema migration.
Authority: Steward directive; user authorized implementation, integration, migration, deployment, and live verification. Deployment was not technically ready in this environment.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Record cross-workstream integration requirements.
Changed: 2026-11-08 UTC | CHARACTER-ARCHITECTURE | Codex GPT-6 | Update HR reconciliation, runtime adapter, privacy, and operational blockers.
Supersedes: None
Contracts: R3A_RESIDENT_CHARACTER_ARCHITECTURE.md; resident dossier and runtime binding v1.
Tests: 182 repository unittests pass in the R3A virtualenv; 13 dossier records validate through repository validation. JSON files parse and Python compilation and `git diff --check` pass. No database migration or character-context live acceptance was run.
History/Predecessor: New file.
-->
# Character Architecture Integration Handoff

## Current worktree boundaries

Character Architecture source branch: `engineering/r3a-character-architecture-20261107`, starting at `0e2af25`. Sibling worktrees `../coordinator` (`integration/r3a-multi-resident-20261108`) and `../live-modular` (`integration/r3a-live-modular-candidate-20261108` at `8ec1259`) were inspected read-only. This branch now includes an optional `resident_character_context` input in the Grace inference module. The sibling worktrees, CME dispatcher, active providers, grants, live databases, and services were not modified.

The current related R3A coordination issues inspected were [#43 (AP1 Grace autonomy)](https://github.com/ppow1/R3/issues/43), [#47 (AP1 knowledge retrieval)](https://github.com/ppow1/R3/issues/47), and [#46 (modular capability plugins)](https://github.com/ppow1/R3/issues/46). These AP1 scopes do not authorize or track this AP4 Character Architecture assignment, so none was repurposed. No Character Architecture AP4 milestone issue was present in the inspected results. The contracts below are implementation handoff requirements, not evidence that Coordinator or Autonomy has integrated them.

## Required interfaces

1. Obtain the canonical person identity from governed HR. Obtain a fresh, bounded R3A office-binding projection from `institutional.directory.discover`, then resolve the HR ID to a runtime ID through an explicit, verified crosswalk before context activation. Do not equate HR `r3:*` IDs and directory/runtime `resident.*` IDs from matching names.
2. Load the dossier version and call `compose_prompt`. Persist the component refs, source refs and digest with the request/provenance record. Include only approved `public` and `institutional` modules. Never pass `personnel_sensitive` or `protected` source material through a generic prompt.
3. Merge settings through `resolve_personality`; persist the resolved values and winning scopes for reproducibility. Durable traits, memory, mood, relationships and provider settings stay distinct.
4. Bind execution through `runtime_binding` or an adapter implementing `r3a.resident.runtime-binding@1.0.0`. HR supplies canonical identity; the directory supplies the current office/runtime projection and must crosswalk to HR. CME still supplies/authorizes operations and grants. Do not copy capabilities into the dossier.
5. Pass claim-level epistemic spans and source references independently of visible rendering. Keep resident annotations, audit findings, corrections and message-level status as separate durable facts. Existing ordinary chat responses must not wait on a mandatory extra inference pass.
6. Before passing an approved bundle to Grace, use `load_runtime_context` with a server-attested principal, fresh HR identity/crosswalk, approved dossier revision, and HR authorization reference. The inference module validates exact directory-resident binding, approval, digest, and public/institutional classification scope, then applies the context and personality settings. The adapter cannot establish HR authority or verify a caller by itself; the upstream governed HR adapter must do so.

## Database and compatibility

`r3a_runtime/migrations/009_resident_dossiers.sql` adds immutable revision records, a current pointer, and governance/rollback events. It is additive and unexecuted. No migration was applied. Protected relationships and Steward identity remain governed HR data; do not introduce a parallel identity registry in R3A PostgreSQL. Extend the existing HR record/capability contract and store relationship facts only behind its authenticated access service.

Grace compatibility: current primary runtime uses `resident.grace`; the legacy HR snapshot uses `r3:grace`. The directory provider returned `directory_source_not_configured`, so no crosswalk is available; no live Grace turn received this branch's dossier context. `r3a.resident.execution-profile@1.0.0` remains unchanged. The additive input rejects unapproved, mismatched, digest-invalid, or protected-scope bundles. Live status through the Coordinator checkout confirmed Ring 0/CME healthy, Grace 1.2.8 active, and primary/autonomic/vision model roles fresh. The installed `r3a` CLI in the phase0 venv rejects the current `module_manifest` config, while `python -m r3a_runtime.cli` from the active Coordinator checkout reads it correctly. No character context was supplied by that running revision.

Vicky integration: `r3:vicky` has the Engineering Manager / Foundry minimum context and configurable dimensions but no verified active HR snapshot link, approved Character Bible, qualification claims, provider route, memory, or relationships. Obtain the HR identity and current office/runtime projection plus Helen/Jessica source approvals before activating a Vicky runtime binding. Her dossier alone is not onboarding completion.

Chloe is a charter-listed Chief Architect and a legacy HR row, but authoritative identity/office confirmation remains open. The `chatgpt_mediated_candidate_unverified` implementation marker is a requested candidate mode, not an available or authorized provider route.

## Known interface risks

- Directory output currently lacks a responsibilities field. Responsibilities in dossiers are linked to charter/HR evidence, not to a current directory binding.
- The directory source contract is PostgreSQL `riverview_authority`; the recorded live invocation says `directory_source_not_configured`. Its empty/unavailable response is not an HR roster or a reason to provision an identity.
- HR docs describe a distinct SQLite service and governed capabilities. No HR-to-directory import/synchronization contract is documented.
- System Python lacks `psycopg_pool`; repository tests pass with `/home/admin1/r3a-phase0/.venv/bin/python` and the Character Architecture worktree on `PYTHONPATH`.
- The approved roadmap places Jessica/character development in AP4. This Steward directive specifically authorizes the Character Architecture workstream implementation and explicitly requests integration preparation with Coordinator/Autonomy. Keep this work as an isolated interface/data-layer change; do not unilaterally reprioritize or amend milestone acceptance beyond that explicit directive.

## Deployment prerequisites and rollback

Deployment and live testing were explicitly authorized, but character-architecture activation is blocked by unavailable authoritative directory data, no verified HR-to-directory crosswalk, no live HR read/write capability in Comms5, and no authenticated HR/Character Architecture workflow endpoint. The available Grace operator interface submits objective tasks with state-transition acceptance criteria; it has no casual-chat interaction for the coffee acceptance scenario. The running revision does not load this branch's dossier or context adapter. Tests A–E therefore remain unrun against the character-enabled operational runtime. These are concrete integration blockers, not a change to the Steward's authorization.

Rollback leaves immutable dossier/event history intact and points the current revision to a retained predecessor, recording the actor, reason and event. For an adapter rollout, disable the adapter through validated configuration and resume the existing resident profile/system prompt path. Do not remove migration data or reset identity/authority state as a rollback shortcut.
