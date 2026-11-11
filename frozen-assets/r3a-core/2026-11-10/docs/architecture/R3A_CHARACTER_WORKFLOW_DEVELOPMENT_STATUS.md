<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_CHARACTER_WORKFLOW_DEVELOPMENT_STATUS.md
Component: R3A-CHARACTER-WORKFLOW-STATUS
File Revision: 1.0.2
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: Report implementation evidence, integration boundaries, and the owned Character Architecture backlog.
Execution Model: N/A; status and handoff record.
Observability: Git revision, isolated test output, managed runtime and Issue #56 evidence.
Dependencies: Character Architecture branch, R3 HR authority, Coordinator integration, Issue #56.
Authority: Steward directives and Jessica's final architectural approval.
Changed: 2026-11-08 UTC | CA-03 | Codex GPT-6 | Refresh Coordinator status, migration evidence, and ordered backlog.
Changed: 2026-11-08 UTC | CA-03 | Codex GPT-6 | Add route and office-binding pin continuity evidence.
Changed: 2026-11-08 UTC | CA-05 | Codex GPT-6 | Add prompt tamper and sink privacy regression evidence.
Changed: 2026-11-08 UTC | CA-10 | Codex GPT-6 | Add digest-verified Coordinator package manifest and privacy-preserving context hook acceptance.
Changed: 2026-11-08 UTC | CA-11 | Codex GPT-6 | Add audited active-character retirement with reversible pointer removal and migration 014.
Supersedes: None
Contracts: approved-character-context@2.0.0; R3A roadmap and punch lists.
Tests: Full repository unittest suite; isolated PostgreSQL migration/workflow.
History/Predecessor: Git parent 6b4e8d1.
-->
# R3A Character Workflow Development Status

**Status date:** 2026-11-08
**Workstream:** Character Architecture
**Branch:** `engineering/r3a-character-architecture-20261107`

## Implemented in this branch

- PostgreSQL-backed immutable dossier revisions, an activated-version pointer, and append-only governance events in migration `011_resident_dossiers.sql`.
- A workflow service for authenticated dossier reads, proposals, review submission, approval/rejection, publication, activation, and rollback. It requires injected server-side actor verification, canonical HR identity resolution, and capability authorization. The adapter to `HRCapability.read` rejects request-supplied identity claims and does not provision residents.
- Durable-canon self-approval is denied even when the author appears in the configured reviewer set. Reviewer identities are policy configuration, not source-code constants.
- Runtime context now requires an active dossier and verified identity binding before it can be applied to inference. Prompt composition remains inspectable for provisional dossiers but marks them provisional; only approved/active components are composed.
- Protected/personnel-sensitive components cannot be submitted to the ordinary character dossier store. Existing runtime context filtering limits prompt classifications to public and institutional.
- Approved context contract `r3a.resident.approved-character-context@2.0.0` resolves only active revisions through an injected authenticated HR/directory resolver and exact context-read grant. Migrations `012_character_context_pins.sql` through `014_context_pin_execution_profile.sql` store the immutable dossier/identity/provider pin, HR source and principal-association references, exact directory snapshot/office-binding evidence, and verified execution-profile/route revision for each inference activity or conversation boundary; they store no prompt text. A boundary cannot silently move to a newer character revision; a new safe boundary can use the new active revision, and prior pins remain retrievable.
- Context sink projections apply classification before use: inference receives approved public/institutional context only; memory and communications receive a versioned context reference without prompt text; diagnostics receive metadata only. Every allow/deny audit projection omits character content.
- `HRPrincipalAssociationAdapter` validates the authoritative directory source, snapshot digest, exact canonical principal, office binding revision, and evidence references, then requires exact scoped `hr.write` and an HR host method that revision-checks and persists provenance. It deliberately fails closed if the host exposes only the current provenance-free association method.
- Coordinator package `r3a.resident.character-architecture@1.0.0` declares the v2 host hook, authenticated-boundary fields, injected HR/repository/grant/sink services, activation gates, and inference-versus-reference-only sink policy. Its artifact digest is checked before use and package data is included in built distributions. The in-process hook avoids generic CME capability output so prompt text cannot enter invocation replay/output evidence; it requires a separate server-side sink authorizer and content-free audit sink.
- Character retirement is an explicit runtime lifecycle action: only the current active revision can be retired by a configured runtime activator with exact `character.retire` capability. Migration `016_character_revision_retirement.sql` appends the retirement event and removes the current pointer while retaining immutable revisions, audit history, and prior execution pins. New execution boundaries fail closed until a revision is activated; authorized rollback can restore a retired revision.

## Local development deployment evidence

An isolated UTF-8 PostgreSQL cluster was previously created for this workstream, bound to a local Unix socket only. Its `r3a_character_dev` database has migrations `001_ap0.sql` through `014_context_pin_execution_profile.sql` applied through `r3a_runtime.db.Store.migrate()`. During this continuation, a separate disposable local PostgreSQL 16 cluster/database applied migrations `001`–`013` through the same `Store.migrate()` path; neither was a managed Coordinator database or runtime.

The integration test uses generated `r3:test-workflow-*` identities and test-only actor, HR resolver, and capability callbacks. It executes proposal → review → independent approval → publication → activation, current and historical reads, protected component rejection, unauthorized access rejection, immutable revision enforcement, rollback, history retrieval, and revision-pinned conversation boundaries that remain stable after later activation. These records are test data, not institutional HR registrations.

## Approved character-context interface and activation boundary

`ApprovedCharacterContextProvider.retrieve()` is the versioned interface for a verified resident identity and runtime binding. It requires an authoritative HR identity revision, current directory resident principal plus office binding revision, a server-authenticated actor, an exact `character.context.read` grant, an actually active dossier revision, and sourced prompt components. It returns contract v2 with the selected dossier/context digests, approval state, source/component references, provider, execution boundary, and durable pin reference. It does not accept drafts or provisional dossiers.

The activation boundary is the start of one `inference_activity` or `conversation_boundary`. The current active revision is pinned transactionally at first use. Repeated lookup for that same boundary must match the original identity, provider, revision, and digest; a changed identity/binding/provider or a new revision within the same boundary fails. A subsequent new boundary may use a newly activated revision. Historical activated revisions remain usable only for boundaries already pinned to them, preserving continuity and rollback lineage. The inference host must attach the `pin_ref` and both digests to durable activity evidence; this workstream does not alter CME's running inference path.

The managed Grace module now consumes contract v2 (Coordinator commit `d399886`; deployed under integration `c02c882`, Grace `1.2.11`). Coordinator reports a live authorized objective but explicitly says it carried no character context. `project_for_grace_context_v1()` remains only for older integrations: it requires the server-verified execution profile to exactly match the context's profile ID, revision, resident ID, route, and source reference, and it rejects an unverified identity mismatch. The current managed path is v2; no character-bearing inference has been reported.

Before downstream use, `project_context_for_sink()` filters by authorized classification. It sends prompt text only to inference, sends a reference-only record to memory and communications, and returns metadata-only diagnostics. Audit callbacks receive safe IDs, sink, pin, context digest, and decision—not prompt text or protected facts. Resident chat/message transport and memory persistence still need to consume this contract through their existing shared modules.

The association adapter accepts only an opaque evidence reference from its caller and resolves the authoritative directory snapshot/binding through an injected server-side resolver; client-supplied mapping fields are not trusted. It requires the HR authority to expose `associate_authority_principal_with_provenance`, including server-verified principal, expected HR revision, and the resolved source evidence in its atomic audit/history update. The deployed host currently exposes only a provenance-free method and no authenticated association route. Thus the adapter validates and routes the governed operation but cannot complete it against the existing deployment until the HR host adds that exact operation.

## Deployed R3 HR authority and integration boundary

Read-only host inspection on 2026-11-08 found `r3-institution.service` active. Its unified R3 release worker has both `R3_HR_DB_PATH` and `R3_HR_DATABASE` set to the same existing SQLite file, and that file is the same filesystem object as `/home/admin1/.local/share/r3/hr/residents.sqlite3`. This corrects the earlier claim that the 13-row store was unbound: the active R3 web worker is configured to use that store. The live `/api/v1/health` endpoint returned `hr_storage: ready` (HTTP 200).

The active release uses `r3_chat_api` and `r3_resident_directory` for a Steward-authenticated HR directory projection. An unauthenticated request to `/api/v1/chat/residents` returned HTTP 401. The route calls the existing `HRCapability` with the session principal and filters confidential fields; it is a read-only directory projection, not a general personnel-record editor. The active R3 source also defines `HRCapability.save` and revision-checked `associate_authority_principal`, and `hr_stdio` can dispatch `hr.save`, but no authenticated `hr.write`/association route or active stdio host was found in the deployed app. `r3_app.get_hr_capability` is an in-process factory requiring a host-injected `VerifiedPrincipal` and server-side grant callback; it is not itself a transport.

The current R3 authority contract has exact resource/action/operation/scope grants and durable grant audit. This branch now includes `R3CapabilityGrantAdapter` for that contract and `resident-identity-association.v1.schema.json`, a privacy-minimized evidence projection joining HR record/revision and confidential principal association, active dossier revision, directory snapshot digest and office binding revision, credential reference, grant references, and runtime profile/route. The projection rejects name-based or equal-looking ID matches. It does not create a resident registry or mutate the R3 directory.

## Not operationally activated

The CharacterWorkflowService and approved context provider remain unmounted as HTTP or CME capabilities, and no real authenticated principal has executed them. The existing R3 website read is gated by an authenticated Steward session that is not available to this worktree; the live unauthenticated check correctly returned 401. No live HR association or directory mutation was made. No authenticated HR write endpoint is exposed by the active app, and the exact R3 `hr.write` association operation with provenance is not invocable here through its host-injected principal/grant checker. Character-specific R3 grants and server-side session-to-`VerifiedPrincipal` binding have not been verified. Therefore no Vicky/Helen record was changed and no live proposal, approval, activation, context retrieval, or inference was claimed.

For Vicky and Helen, the latest Coordinator snapshot reports no directory occupant or office binding. For Grace, it reports principal `resident:grace`, office `office:grace`, Director of Operations, binding revision 9, snapshot digest `23a2e6124dbdf6f595b65dbc47a1d91cbb20f547b4a1fd56eb0e4a35fb82ae19`. No verified HR `authority_principal` association currently connects `r3:grace` to `resident:grace`; a matching name is insufficient. The existing revision-checked `HRCapability.associate_authority_principal` is the established HR write operation, but invoking it needs an authorized HR principal, exact `hr.write` grant, authoritative match evidence, and durable provenance. Vicky/Helen additionally need their directory principal and office binding established by the directory authority.

Before mounting or activating the character capability, the R3 host must provide the authenticated session resolver, canonical `R3Authority` instance, `HRCapability` factory, a provenance-bearing revision-checked HR association operation, and exact character/HR grants. The Coordinator must provide the current directory-to-execution binding projection and consume context v2 through its established module/inference path, attaching pin references to durable activity evidence. Then run a real authorized dossier workflow and verify prompt retrieval through resident inference. Grace has an approved dossier only if HR/Character governance records evidence of approval and activation; no dossier shell or test identity can satisfy this gate. Vicky requires authoritative directory principal/office binding and execution profile before activation.

## Rollback

Migration `009` is additive and does not alter existing HR records. The development database can be discarded independently. For a future production rollback, first disable dossier reads/activation in the runtime, retain audit history, restore the previous application revision, and use a reviewed forward migration if schema rollback is required. Do not delete revision or event history in place.

## Current owned milestone and ordered backlog

**Evidence date:** 2026-11-08 UTC. **Owner:** Character Architecture. **Approved interface:** `r3a.resident.approved-character-context@2.0.0`. **Previous verification:** 188 passed with isolated PostgreSQL 16 migrations `001`–`013`. This increment's full repository suite: **189 passed, no skips**, with `R3A_CHARACTER_TEST_DSN` pointing to an isolated PostgreSQL 16 database with migrations `001`–`014` applied. The focused dossier suite has 30 passing tests. Status labels distinguish source implementation, isolated verification, and managed activation.

| Order | Work item | State | Evidence / exact dependency | Next action |
|---|---|---|---|---|
| CA-01 | Provenance-bearing HR identity association | Adapter implemented; source integration BLOCKED | Coordinator's latest #54/#56 handoff identifies the deployed authority as R3 native HR (`r3-institution.service`, SQLite `hr_records`) and reports no authenticated provenance-bearing association route or trusted evidence resolver. The actual implementation owner has not responded/been evidenced. No identity was mutated. | Obtain the R3 HR source owner's acknowledgement and operation contract; add the exact authenticated, exact-grant, revision-checked atomic association-plus-provenance operation through that authority. |
| CA-02 | Active Grace canon readiness | Context interface READY; real canon activation BLOCKED | No evidence of a genuinely approved and active Grace revision. Coordinator live objective at #6724942098 used no character context. | Prepare a source-indexed Grace canon review packet; do not approve or activate it here. |
| CA-03 | Approved context v2, pin and privacy hardening | Implemented; isolated tests PASS | Migration `015_context_pin_authorization_scope.sql` stores the exact classification grant scope in each boundary pin. Reused boundaries reject changed authorization scope, execution route, or directory binding; PostgreSQL lifecycle verifies scope/revision conflict and rollback. | Continue with stale profile/digest mismatch matrix, then hand v2 contract evidence to Coordinator/Autonomy. |
| CA-04 | Migration and rollback verification | Implemented; isolated PostgreSQL verification PASS | Fresh disposable PostgreSQL 16 cluster applied migrations `001`–`014` through `Store.migrate()`; rerun returned no pending migrations. Workflow integration verifies retirement, absent current pointer, historical retrieval, retained pin, and rollback restoration. | Preserve the managed DB untouched; repeat under integration owner's authorized migration process after merge. |
| CA-05 | Canon/state separation and confidentiality | Implemented; isolated tests PASS | Regression checks reject prompt tampering and protected classifications; memory and communications receive context references without prompt text, diagnostics remain metadata-only, and deny audit contains metadata only. Durable canon remains separate from memory, relationships, and expiring emotion. | Continue checking trait-promotion governance and per-sink authorization adapters without adding a new memory/chat service. |
| CA-06 | Shared context interfaces | v2 provider implemented; managed consumer deployed, integration incomplete | Grace 1.2.11 consumes v2 and is healthy, but the live activity had no context. No managed HR association or active Grace dossier. | Hand exact v2 contract and activation assertions to Coordinator/Autonomy; do not claim fixture or live context acceptance. |
| CA-07 | Protected `STEWARD` classification | Schema/policy contracts implemented; institutional record unverified | `validate_steward_record` prohibits resident/employee lifecycle fields and requires Steward-governed identity writes. No real identity or preference content is committed. | Expand policy regression tests and await a source-authoritative record projection before real access tests. |
| CA-08 | Vicky/Helen onboarding readiness | Dossier foundations implemented; live binding BLOCKED | Coordinator directory snapshot has Grace only; Vicky/Helen principals, office bindings, grants, credentials, and execution profiles are not evidenced. | Maintain preflight validation and reconcile only from authoritative HR and directory evidence. |
| CA-09 | Managed acceptance handoff | BLOCKED externally | Managed runtime is Coordinator-owned; v2 consumer is live, but the Character Architecture provider is not mounted and HR association write is missing. | Resume after source association and identity crosswalk, then prove authorized character-bearing inference with activity pin evidence. |
| CA-10 | Coordinator package and context-hook handoff | Package implemented; isolated acceptance PASS; host activation BLOCKED | `r3a_runtime/residents/coordinator-character-package.v1.json` is schema- and artifact-digest-validated. Acceptance exercises v2 retrieval through an injected authenticated execution boundary, separate sink authorization, reference-only memory/communications, metadata-only diagnostics, and denied inference without a sink grant. No Coordinator host injection or managed prompt delivery is claimed. | Coordinator wires the package into its in-memory inference path, supplies authenticated HR/grant/repository and sink-authorizer services, captures pin refs in durable activity evidence, then runs managed character-bearing inference after HR association and approved-active canon exist. |
| CA-11 | Character revision retirement and recovery | Implemented; isolated PostgreSQL verification PASS | Exact `character.retire` is restricted to configured runtime activators and the current active revision. The immutable retirement event removes the active pointer; new boundaries are denied context, while a previously pinned boundary continues on its original revision. Historical revision and pin remain, and governed rollback restores the revision. | Coordinator adopts the retirement event/pointer contract as part of context activation, then exercises retirement/recovery in its non-production host. |

## Legacy requirement disposition for this workstream

The required source review covered `R3A_ARCHITECTURE_CHARTER.md`, `R3A_MASTER_ROADMAP_AP0_AP6.md`, `R3A_PUNCH_LIST_AND_PARKING_LOT.md`, `docs/PUNCH_LIST.md`, and `docs/PARKING_LOT.md` at branch `6b4e8d1`; the adjacent exception register was also inspected. Those source documents remain authoritative. This table maps relevant intent only.

| Source items | Disposition | Character Architecture handling |
|---|---|---|
| R3A-015 / R3A-021; R3-P015 | Adopted | Jessica's character capability uses canonical HR identity and existing authorization; Helen retains personnel and confidentiality ownership. |
| R3-P016 | Adopted | Seed minimum usable, explicitly provisional dossiers and expand only through sourced proposals and governed approvals. |
| R3-P017; R3-L010 | Adapted | Personality settings and approved override precedence are versioned components; scalar controls do not substitute for character canon. |
| R3-P018–019; R3-L011 | Adapted | Preserve six epistemic classes and provenance spans without mandatory multipass inference for ordinary conversation. |
| R3-P020; R3-L012 | Deferred to conversation/HMI owners | Character Architecture provides safe classifications and provenance; late-alert navigation and visualization do not create a second chat service. |
| R3-L004 | Deferred | Honcho evaluation waits for approved memory-isolation and retention integration; the current contract is provider-neutral. |
| R3-L009 | Deferred | Mobile client work is outside this lane; future clients can consume the same character-context boundary. |
| R3A-016 / R3-L006–008 | Deferred | Spatial/avatar/Quest and alternative gateway work remain AP5/parking-lot items. |
| R3-P001, P003–004, P022–024 | Adapted as dependencies | Roster, CME participation, capability registry, onboarding, configuration inventory, and release registry remain with HR/Coordinator/platform owners. Character code resolves identities dynamically and never provisions or grants capabilities. |

## HR source-owner handoff

The deployed authority lacks a server-authenticated operation that accepts the authenticated actor, exact `hr.write` grant, canonical resident ID, expected HR revision, source-resolved directory snapshot/office-binding evidence reference, and idempotency key, then atomically writes the principal association with provenance and a durable audit/history successor. Writing `extensions.authority_principal` without its evidence lineage is insufficient. The source-owner request is being posted to shared Issue #56, linked to HR onboarding #33 and the HR Development ownership record in #41. No Grace approval, Vicky/Helen binding, credential, grant, or HR mutation is asserted.
