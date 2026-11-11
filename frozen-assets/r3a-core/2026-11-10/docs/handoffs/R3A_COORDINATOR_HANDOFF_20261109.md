# R3A Coordinator Handoff — 2026-11-09

## Purpose and stopping point

This handoff transfers the R3A integration and resident-chat assignment to a replacement Coordinator session. The Steward directed this session to stop implementation at its next safe stopping point and document verified state. No source changes were made in response to the final resident-chat correction. No service was restarted, stopped, or reconfigured during this handoff.

The current user request is generic chat for every onboarded and authorized resident. The Website must show the authorized dynamic directory roster separately from chat readiness. Grace is the first live acceptance case, not a special-case implementation. Inspect the existing R/3 Grace path and the R3A registry before assuming additional HR operations are needed.

## Current repository state

- Repository: `ppow1/R3`
- Branch: `integration/r3a-unified-20261109`
- HEAD: `3510889c868135b9c83f9919983bec3167ac18dc` — `Make Steward resident chat dispatch generic`
- Parent: `f514d3d` — `Allow grant-checked direct principal reads`
- Working tree: clean; branch tracks `origin/integration/r3a-unified-20261109`.
- Runtime source in the active unit's working directory is this checkout. The Ring0 unit uses the separately provisioned `/home/admin1/r3a-phase0/.venv`; the Website unit uses `/home/admin1/R3/.venv`.
- No handoff commit exists yet. This document is the only intended change in the handoff commit.

## Live services and runtime evidence

Observed locally on 2026-11-09, shortly after 23:08 UTC:

| Service | State | Process / deployment detail |
|---|---|---|
| `r3a-ap0-m1-ring0.service` | active/running | PID 882834; started 17:22 EST; launches Ring0 from `/home/admin1/r3a-phase0/.venv`, with config `/home/admin1/.config/r3a-ap0-m1/bootstrap.live-modular-e7a6f56.json`; working directory is the coordinator checkout. |
| `r3a-ap3-website.service` | active/running | PID 884835; started 17:24 EST; Uvicorn bound to `127.0.0.1:18311`; `/home/admin1/R3/.venv`; working directory is the coordinator checkout. LAN HTTPS terminates through the existing proxy at `https://192.168.1.155:8311`. |
| `r3-institution.service` | active/running | Existing R/3 release `r3-unified-8ab4b2ab1669`; PID reported as 0 by systemd while unit state remains active. This service was not changed. |

The configured R3A module is `resident.grace@1.2.12`; bootstrap source digest is `e103ed089a8d4eaa13d2d3a04bbca915a3e2b1706378755fc91a8db3b41a2c75`. Its configured resident-office route is `Director of Operations` → model role `resident.primary`; that role uses route `octominer1-primary-80b`.

Live HTTP probes: `/` returned 302, `/login` returned 200, anonymous `/api/v1/steward/session` returned 401, and anonymous `/api/v1/steward/residents` returned 401. These probes establish that the Website is serving and protected anonymously; they do not establish an authenticated session or chat acceptance. The Website health endpoint returned a running response but labels its service `r3`.

No service was restarted in this session. The prior managed integration report on #56 records release `3510889`, active CME/Ring0 and Website, PostgreSQL 16.15 ready, and rollback source `f514d3d`. Treat the prior report's authenticated browser result as historical; this handoff did not have the Steward browser session.

## PostgreSQL and durable state

Using the configured R3A database through the existing `Store` read path, the migration ledger contains all migrations `001_ap0.sql` through `018_steward_identity.sql`. The exact later migrations are:

- `009_steward_sessions.sql`
- `010_governed_knowledge.sql`
- `011_resident_dossiers.sql`
- `012_character_context_pins.sql`
- `013_context_pin_identity_provenance.sql`
- `014_context_pin_execution_profile.sql`
- `015_context_pin_authorization_scope.sql`
- `016_character_revision_retirement.sql`
- `017_steward_conversations.sql`
- `018_steward_identity.sql`

The live database currently reports 0 `r3a.steward_conversations` and 0 `r3a.steward_conversation_messages`. Therefore no live R3A Website conversation has been completed or persisted.

The active authorization records include:

- `steward:camrui` → `institutional.directory.discover`, grant `13882556-bc77-4424-b0d3-fd525825e4c4` (the prior #56 report records this grant and a successful fresh directory read).
- `resident.grace` → existing read grants for `host.process.read`, `infrastructure.octominer.telemetry.read`, `institution.diagnostics.read`, `institution.knowledge.read`, `institutional.directory.discover`, and `postgres.readiness`.
- No active `resident.delegate` grant for `resident.grace` was present in the live grants query.
- No active `resident.objective.execute` grant for `resident:grace` was present.

The grants table supports activity-scoped grants. Current chat discovery checks for global `resident.delegate` and `resident.objective.execute` grants. Do not issue wider grants merely to make the selector show a resident; establish the intended minimal chat authorization scope through the existing grant authority.

## Resident chat: current implementation

### Website → CME → resident path

The Website frontend in `web/steward-workspace-api.mjs` loads `/api/v1/steward/residents`, lets the Steward select a resident, creates a durable conversation through `/api/v1/steward/conversations`, and sends turns with a client-generated idempotency key. `r3_app.py` authenticates the Website session and forwards these operations to the CME control path. The CME stores conversation ownership, selected resident, messages, activity link, and turn idempotency in PostgreSQL. Sending a turn submits generic `resident.objective.submit`; the activity then goes through CME scheduling, authorization, resident module IPC, configured inference, and durable results.

The current generic conversation code is in commit `3510889` and its parent `f514d3d`. Focused implementation files include:

- `r3a_runtime/cme.py` — directory discovery, conversation create/list/read/send, generic objective intake, directory-backed profile resolution and module activation.
- `r3a_runtime/db.py` and migrations `017_steward_conversations.sql`, `018_steward_identity.sql` — durable conversation and Steward identity state.
- `web/steward-workspace-api.mjs` — roster selection and conversation UI behavior.
- `r3_app.py` — authenticated Website API boundary.
- `tests/test_r3a_steward_conversations.py`, `tests/test_r3a_website.py`, `tests/test_steward_workspace_api.mjs` — focused behavior checks.

Prior reported test evidence for `3510889`: runtime conversation/autonomy/capability suites 47/47, Website backend 20/20, browser workspace API 14/14. These are test results, not live conversation evidence.

### Observed roster behavior and failure

`steward.residents.discover` obtains a measured/fresh directory snapshot through the canonical directory capability. It then returns only rows considered authorized/executable. Its current code checks direct equality between the directory `resident_id` and CME `module_id`, or tries configured office routing plus the CME's `resident.delegate` grant and the target's `resident.objective.execute` grant. The Website then drops rows with `authorized === false` and has no separate onboarding/readiness presentation.

This conflates the institutional roster with execution eligibility. It causes rostered but not-yet-onboarded residents to disappear instead of showing them with chat unavailable. The directory contract returns principal, display name, office, office role/status, binding revision, and directory availability metadata; it does not define an onboarding field. Directory `availability_state` describes the provider's measurement availability, not resident onboarding or chat authorization. Do not translate that field into “onboarded.”

Prior managed fresh directory evidence recorded on #56:

- Source `riverview_authority.directory`; one office, one binding, one resident.
- Directory principal `resident:grace`, office `office:grace`, binding revision 9.
- Snapshot SHA-256: `23a2e6124dbdf6f595b65dbc47a1d91cbb20f547b4a1fd56eb0e4a35fb82ae19`.
- Active registered resident module: `resident.grace@1.2.12`.
- CME's current eligible-resident projection was empty. Conversation-create failed closed at the missing `resident.delegate` check; no conversation or inference was created.

The current Website therefore protects the route correctly but does not satisfy the roster or chat acceptance requirements.

### R/3 Grace mechanism inspected

The active R/3 service uses release `r3-unified-8ab4b2ab1669` and source under `/home/admin1/.local/share/r3/releases/r3-unified-8ab4b2ab1669/source`.

- `config/runtime.json` has a configured dynamic roster map with key `grace` → `residents/grace.json`.
- The Grace config says runtime name `Grace`, role `Director of Operations`, enabled `true`, model `/root/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf`, and tool provider `r3-native` with configured allowed tool IDs `r3.status` and `r3.host.uptime`.
- `runtime/serve.py` loads the configured resident entries, registers each enabled resident with the existing `Institution` scheduler and `ResidentInference`, and starts the conversation API with the registered names and per-resident tool projection.
- `runtime/conversations.py` persists conversations/messages in the runtime journal database, pins each conversation to the server-authenticated Steward principal, validates the resident against the registered runtime roster, and sends messages into the resident inbox. The scheduler/inference loop produces and reconciles the actual response into the durable transcript.
- R/3 resident tool credentials are independently read from the resident credential store. `runtime/resident_identity.py` verifies a credential against the R/3 authority and returns its canonical `resident:<slug>` principal. No credential values were read or copied for this handoff.
- The R/3 website proxy in `/home/admin1/R3/r3_chat_api.py` validates the authenticated portal session and derives a principal server-side, then calls the loopback conversation API. It currently uses an externally configured `resident_id` for its chat routes; it is not a generic dynamic roster UI.

What this proves: R/3's runtime has a dynamic configured resident roster and its conversation API routes by the same registered runtime name. It is a useful execution/conversation precedent. It does **not** by itself prove the relationship between R3A directory principal `resident:grace` and R3A module principal `resident.grace`, nor authorize reusing R/3 runtime/auth in R3A.

### R3A registry and identity evidence

The live R3A registry query showed:

- `r3a.module_registry` has `resident.grace@1.2.12` active/healthy, entrypoint `r3a_runtime.grace_module`, owner `R3A-CME`; its manifest has no resident execution profile or directory-principal binding.
- The same registry stores provider modules such as directory `1.1.1`, knowledge `1.2.1`, OctoMiner telemetry `2.0.0`, and resource-monitor providers; these are independent of the resident module registry identity.
- `r3a.capability_grants` has no resident binding relation and no table name containing a resident identity registry. The resident-related tables found are dossier revisions/current/events and character-context pins.
- Configured resident execution routing maps office role `Director of Operations` to model role `resident.primary`; the role maps to route `octominer1-primary-80b`. This supplies an office-based model route, not a durable binding from a directory principal to a registered module ID.
- The versioned `r3a.resident.execution-profile@1.0.0` built by `_resolve_resident_execution_profile` carries the directory principal, office, route, configuration revision, and directory evidence. It does not name the registered source module ID or an authoritative binding reference.
- `r3a.resident.identity-association.v1` is a validated source-grounded evidence projection, not a canonical registry. Its current schema records HR, dossier, directory, credential/grant references and runtime profile/revision/route, but does not resolve to a registered module ID. Character-context code refuses use without a verified HR principal association and a pinned profile.
- The dossier index under `data/residents/index.json` labels its legacy resident IDs provisional and the roster crosswalk unreconciled. It is not evidence of a live directory-to-module association.

Conclusion: R3A already has the authoritative dynamic roster, an active resident executable, a model route for Grace's office, durable conversations, and generic CME routing machinery. No second directory or scheduler is indicated. The live R3A records inspected do not currently establish that the directory principal and active module are the same authorized resident. A new HR API is not proven to be the only solution: first inspect existing R/3 resident identity/credential records and approved R3A identity/profile records for an authoritative existing binding or procedure. Do not infer the binding from spelling, display name, or role alone. If none exists, identify precisely the missing existing-authority evidence and let its owner supply it.

## Integration workstreams

The repository has local/remote branches for the following workstreams. SHAs below are the observed `origin` branch heads at handoff time where the remote ref existed. Branch head does not by itself prove a PR merge, deployment, or acceptance.

| Workstream | Branch / observed pushed SHA | Integration and operational state at handoff |
|---|---|---|
| Coordinator | `integration/r3a-unified-20261109` — `3510889c868135b9c83f9919983bec3167ac18dc` | Current integration/deployment owner. Generic conversation submission integrated and deployed. Chat still fails before real conversation because no verified directory-to-runtime binding/grants. |
| Modular Plugins | `engineering/r3a-modular-plugins-20261106` — `220c09e93c5f15bccdffdcacc88a873a011f3e0b` | Generic provider lifecycle and registry work incorporated in the unified runtime. Live active providers include directory 1.1.1, Knowledge 1.2.1, telemetry 2.0.0 and resource monitoring. |
| AP3 Bitwarden | `engineering/r3a-ap3-bitwarden-20261107` — `ce05b7307f203e0b37e5857228149c56e9353ae4` | Source integration is partial/uncertain at current unified HEAD; original handoff reported versioned contracts, provider configuration and in-process secret lease with focused tests. Live Bitwarden auth/retrieval was not verified because `bws` and machine-account credentials were unavailable. Do not expose secret values. |
| Live Modular Integration | `integration/r3a-live-modular-candidate-20261108` — `f7ec1161846be67365bc9f60cecd94d3d79d794f` | Integration/managed-runtime work supplied modular lifecycle and earlier releases. Current Ring0/CME is active; no new deployment was done in this handoff. |
| AP3 Website | `engineering/r3a-ap3-website-20261107` — `68b4b07c880d55c1fa961ebad2999044e3c8be53` | Website/auth source is in unified code. Website and login are live; anonymous protected calls return 401. Actual authenticated chat/browser acceptance was not verified in this handoff. |
| AP1 Notifications | `engineering/r3a-ap1-notifications-20261107` — `471c2cf836a0ac3ff5f73f46a1aeae5290b9d7bf` | Source has isolated durable notification work. Managed generic notification intake/read grants and real delivery/acknowledgment remain separate acceptance requirements; do not imply live delivery. |
| Character Architecture | `engineering/r3a-character-architecture-20261107` — `da26e98d26ea2ef9bcb6f6755e4f8419e849b69d` | Dossier schemas, governed revisions, identity/provenance validators and context pins integrated. Live approved dossier/HR binding for Grace and other residents not established by current R3A records. PR #54 and #56 remain the coordination trail. |
| Engineering Integration | `integration/r3a-grace-engineering-20261107` — `0a33cc6bd5c1fd367ea021738bbe9fb1f4ae8d4e` | Engineering work-order, evidence and independent-verification code integrated with autonomy path. Prior isolated/live engineering demonstrations exist in #43; this handoff did not execute a new operation. |
| AP3 Remote Access | `engineering/r3a-ap3-remote-20261107` — `16b6230d5b48bb9bd1872f687f43678faeb296d7` | Native independent R3A identity/session source integrated/deployed in prior work; migration ledger is through 018 and Website login serves. A live authenticated browser chat was not verified now. |
| AP1 Knowledge | `engineering/r3a-knowledge-governed-ingestion-20261108` — `5b84e756cd18eb4110f3c3479620d25840e202bd`; earlier `engineering/r3a-ap1-knowledge-20261107` — `4fe86ba4158e0f1f4b134114af276c942456c77` | Knowledge provider versions 1.1.0 and 1.2.1 show active/healthy in PostgreSQL. Managed authorized retrieval/chat acceptance was not exercised in this handoff. |
| Autonomy | `integration/r3a-autonomy-escalation-20261107` — `27d3d56a5f7420cbc71b22fe2dda02c48f04d28d`; multi-resident branch `integration/r3a-multi-resident-20261108` — `c02c882c4b8459a58df8ead4b8e41fd8f1065395` | Generic durable resident dispatch and activity work are present; Grace real objective execution was separately demonstrated. Multi-resident chat/delegation cannot be claimed until profile/binding, route and grants are established. |

The relevant current source branches exist, but no branch inventory was refreshed beyond the branches above. The branch heads are not guaranteed to be the latest releases from their owners. Check each issue/PR before taking more source.

## Shared contracts and deviations to review

- Canonical invocation: `r3a.capability-invocation.v1`.
- Directory output: `r3a.institutional-directory.v1` from `institutional.directory.discover`.
- Generic resident activity intake: `resident.objective.submit`; chat events use `event_kind="conversation"`.
- Resident profile: `r3a.resident.execution-profile@1.0.0`.
- Steward conversation: `r3a.steward-conversation.v1` with durable PostgreSQL message/activity lineage.
- Character context: `r3a.resident.approved-character-context@2.0.0` with revision/profile pinning and no authority transfer.
- Core deviations relevant to chat: the roster API currently fuses roster listing and chat eligibility, the UI hides ineligible rows, and the execution profile does not identify a registered runtime module. The directory does not publish an onboarding-status field. These are observed implementation gaps; do not rewrite the architecture to resolve them.
- Safety boundary: CME must continue to authorize and execute; Website must not call a model directly. Do not manufacture resident grants or identity associations.

## Outstanding issues and responsible owners

1. **Roster view semantics / Coordinator integration (#56, #51):** return the dynamic, authorized directory roster without dropping rows just because execution is unavailable; expose onboarding/readiness/chat availability separately. Do not label directory measurement state as onboarding state. Website should render unavailable residents disabled with the evidence-backed status.
2. **Existing resident binding source (Character Architecture / HR authority, #33, #43, #56):** inspect existing authoritative R/3 identity mapping, R3A resident profiles and module manifests. The missing relationship to establish is specifically: which authoritative directory resident principal is permitted to execute through which registered module/provider identity and version resolution, with auditable provenance. If existing authority contains this, use it. If not, ask the existing authority owner for the record/contract. Do not presume a new HR operation is mandatory.
3. **Grant state (institutional authorization / CME owner, #43, #56):** absent `resident.delegate` on `resident.grace` and `resident.objective.execute` on `resident:grace` were observed. Determine the exact intended authority principals and minimal scopes only after resolving the binding; then provision via existing audited grant management. No resident execution grant was added.
4. **Live chat acceptance (Coordinator / Website #51 / Autonomy #43):** authenticated browser call, roster display, conversation ID, real Grace 80B inference request/result, PostgreSQL history after refresh/restart, authorization/audit evidence. No conversation or message exists yet.
5. **Other residents:** the current live directory snapshot held one binding. Residents present in an HR roster but not in that directory snapshot cannot be claimed available. Judy and other incomplete residents must remain visible when they are in the authorized directory roster, with chat disabled until onboarding/execution/authorization evidence passes.

## Recommended first investigation for the replacement Coordinator

1. Read latest #56, #43, #51, #33 and PR #54 reports; refresh remote branch/PR heads.
2. Inspect the existing authoritative R/3 resident identity/credential-to-runtime association metadata using sanitized, read-only queries. Inspect R3A's active resident profile, module manifest, `r3a.resident.identity-association.v1` evidence, and character-context pin source together. Do not print credential material or protected dossier content.
3. Compare source-backed identity/principal, configured execution profile and active module ID/version. If an explicit existing binding is found, carry its provenance and revision into the generic runtime resolution. If none is found, report the exact absent relation and ask the responsible authority owner for that information rather than assuming a new HR API.
4. In parallel, correct roster projection so every current directory resident is returned with independent `onboarding_status`, `execution_status`, `authorization_status`, and `chat_available` fields where each status is evidence-backed. Preserve fail-closed create/send validation.
5. Run focused tests, deploy via existing process, then perform authenticated browser acceptance only with the Steward's real session. Record actual conversation/activity/model request IDs and verify message history persists.

## GitHub coordination links

- [Issue #43 — Autonomy](https://github.com/ppow1/R3/issues/43)
- [Issue #51 — Website](https://github.com/ppow1/R3/issues/51)
- [Issue #56 — Coordinator integration](https://github.com/ppow1/R3/issues/56)
- [Issue #33 — HR authority](https://github.com/ppow1/R3/issues/33)
- [PR #54 — Character Architecture](https://github.com/ppow1/R3/pull/54)

Prior relevant integration report: [#56 comment 6753112537](https://github.com/ppow1/R3/issues/56#issuecomment-6753112537). The most recent prior binding/grant report: [#56 comment 6753364162](https://github.com/ppow1/R3/issues/56#issuecomment-6753364162). This handoff supersedes its assumption that the missing HR association operation is the only possible resolution; it does not change the observed absence of a durable R3A principal-to-module binding in the inspected deployed records.
