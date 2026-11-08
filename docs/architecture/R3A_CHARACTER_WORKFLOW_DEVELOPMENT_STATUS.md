# R3A Character Workflow Development Status

**Status date:** 2026-11-08
**Workstream:** Character Architecture
**Branch:** `engineering/r3a-character-architecture-20261107`

## Implemented in this branch

- PostgreSQL-backed immutable dossier revisions, an activated-version pointer, and append-only governance events in migration `009_resident_dossiers.sql`.
- A workflow service for authenticated dossier reads, proposals, review submission, approval/rejection, publication, activation, and rollback. It requires injected server-side actor verification, canonical HR identity resolution, and capability authorization. The adapter to `HRCapability.read` rejects request-supplied identity claims and does not provision residents.
- Durable-canon self-approval is denied even when the author appears in the configured reviewer set. Reviewer identities are policy configuration, not source-code constants.
- Runtime context now requires an active dossier and verified identity binding before it can be applied to inference. Prompt composition remains inspectable for provisional dossiers but marks them provisional; only approved/active components are composed.
- Protected/personnel-sensitive components cannot be submitted to the ordinary character dossier store. Existing runtime context filtering limits prompt classifications to public and institutional.

## Local development deployment evidence

An isolated UTF-8 PostgreSQL cluster was created for this workstream, bound to a local Unix socket only. Its `r3a_character_dev` database is owned by the existing `r3a_runtime` role. All migrations `001_ap0.sql` through `009_resident_dossiers.sql` were applied through `r3a_runtime.db.Store.migrate()` and appear in `r3a.schema_migrations` with checksums. No managed Coordinator database or runtime was changed.

The integration test used generated `r3:test-workflow-*` identities and test-only actor, HR resolver, and capability callbacks. It executed proposal → review → independent approval → publication → activation, current and historical reads, protected component rejection, unauthorized access rejection, immutable revision enforcement, rollback, and history retrieval. These records are test data, not institutional HR registrations.

## Deployed R3 HR authority and integration boundary

Read-only host inspection on 2026-11-08 found `r3-institution.service` active. Its unified R3 release worker has both `R3_HR_DB_PATH` and `R3_HR_DATABASE` set to the same existing SQLite file, and that file is the same filesystem object as `/home/admin1/.local/share/r3/hr/residents.sqlite3`. This corrects the earlier claim that the 13-row store was unbound: the active R3 web worker is configured to use that store. The live `/api/v1/health` endpoint returned `hr_storage: ready` (HTTP 200).

The active release uses `r3_chat_api` and `r3_resident_directory` for a Steward-authenticated HR directory projection. An unauthenticated request to `/api/v1/chat/residents` returned HTTP 401. The route calls the existing `HRCapability` with the session principal and filters confidential fields; it is a read-only directory projection, not a general personnel-record editor. The active R3 source also defines `HRCapability.save` and revision-checked `associate_authority_principal`, and `hr_stdio` can dispatch `hr.save`, but no authenticated `hr.write`/association route or active stdio host was found in the deployed app. `r3_app.get_hr_capability` is an in-process factory requiring a host-injected `VerifiedPrincipal` and server-side grant callback; it is not itself a transport.

The current R3 authority contract has exact resource/action/operation/scope grants and durable grant audit. This branch now includes `R3CapabilityGrantAdapter` for that contract and `resident-identity-association.v1.schema.json`, a privacy-minimized evidence projection joining HR record/revision and confidential principal association, active dossier revision, directory snapshot digest and office binding revision, credential reference, grant references, and runtime profile/route. The projection rejects name-based or equal-looking ID matches. It does not create a resident registry or mutate the R3 directory.

## Not operationally activated

The CharacterWorkflowService remains unmounted as an HTTP or CME capability, and no real authenticated principal has executed it. The existing R3 website read is gated by an authenticated Steward session that is not available to this worktree; the live unauthenticated check correctly returned 401. No live HR association or directory mutation was made. No authenticated HR write endpoint is exposed by the active app, and the exact R3 `hr.write` association operation is not invocable here through its host-injected principal/grant checker. Character-specific R3 grants and server-side session-to-`VerifiedPrincipal` binding have not been verified. Therefore no Vicky/Helen record was changed and no live proposal, approval, activation, or inference was claimed.

For Vicky and Helen, the latest Coordinator snapshot reports no directory occupant or office binding. For Grace, it reports principal `resident:grace`, office `office:grace`, Director of Operations, binding revision 9, snapshot digest `23a2e6124dbdf6f595b65dbc47a1d91cbb20f547b4a1fd56eb0e4a35fb82ae19`. No verified HR `authority_principal` association currently connects `r3:grace` to `resident:grace`; a matching name is insufficient. The existing revision-checked `HRCapability.associate_authority_principal` is the established HR write operation, but invoking it needs an authorized HR principal, exact `hr.write` grant, authoritative match evidence, and durable provenance. Vicky/Helen additionally need their directory principal and office binding established by the directory authority.

Before mounting or activating the character capability, the R3 host must provide the authenticated session resolver, canonical `R3Authority` instance, `HRCapability` factory, and exact character/HR grants. Add an authenticated HR association endpoint through the existing capability (with evidence reference and revision check) or an equivalent trusted in-process route; the Character Architecture branch must not bypass the R3 host boundary. Then run a real authorized dossier workflow and verify prompt retrieval through the resident inference route.

## Rollback

Migration `009` is additive and does not alter existing HR records. The development database can be discarded independently. For a future production rollback, first disable dossier reads/activation in the runtime, retain audit history, restore the previous application revision, and use a reviewed forward migration if schema rollback is required. Do not delete revision or event history in place.
