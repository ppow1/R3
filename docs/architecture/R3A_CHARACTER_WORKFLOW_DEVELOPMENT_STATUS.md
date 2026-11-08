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

## Not operationally activated

The repository does not expose a deployed HR authenticated transport or a server-side mapping from authenticated principals to `VerifiedPrincipal`/capability grants in this environment. The CharacterWorkflowService is therefore not mounted as an HTTP or CME capability, and no real resident/human principal has executed the workflow. No Vicky/Helen directory correction, HR mutation, credential/grant creation, or Coordinator runtime deployment occurred. A local database migration and callback-driven integration test do not demonstrate production HR identity, authorization, or live inference.

Before mounting or activating the capability, supply the existing authenticated HR read path, institutional actor verifier and capability-grant adapter, and approved database connection configuration. Then run the workflow with authorized principals and verify runtime prompt retrieval through the resident inference route. Production migration requires the normal backup/change record and deployment process.

## Rollback

Migration `009` is additive and does not alter existing HR records. The development database can be discarded independently. For a future production rollback, first disable dossier reads/activation in the runtime, retain audit history, restore the previous application revision, and use a reviewed forward migration if schema rollback is required. Do not delete revision or event history in place.
