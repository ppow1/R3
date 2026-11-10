# R3A Resident Onboarding and Recovery Runbook

## Before creating a packet

1. Confirm the R3A Coordinator baseline, branch, and deployment release selected for the work. Never operate on the legacy R/3 HR service or a local SQLite copy.
2. Confirm the authenticated actor through the server session. The request body cannot provide an actor, role, canonical principal, appointment approval, or grant.
3. Copy `docs/onboarding/packet-template.json` or create the same empty request through `new_onboarding_packet`; replace the placeholder UUID, request idempotency key, request label, source ref and timestamps. Do not prefill authoritative domain evidence or a canonical `resident_id`.
4. Call `ResidentOnboardingService.create` through an authenticated host composition. The service requires the host authorization callback, authoritative domain-evidence verifier, activation verifier, and durable R3A packet repository. Do not invoke repository writes directly.

## Advance a packet

1. Read the current packet and revision from the repository. Compare source records using each owning authority's read API; capture references, source revision, approvals, and validation results, never raw HR/credential payloads.
2. The domain owner records that domain's evidence refs using `record_domain`. Each verified field needs its own source ref, evidence refs, revision pin, owner and required approval ref. The server-side domain verifier must resolve refs against the authoritative owner. Use `not_applicable` only for conditional/optional requirements and attach the authority decision.
3. Request the next state with the current expected packet revision, exact transition approval, stable idempotency/correlation UUIDs, reason ref, evidence refs, and an event UUID. Persist and reuse the same event UUID on retry. The service checks actor/capability; the repository does row-locked compare-and-swap and stores packet plus immutable event in one transaction.
4. On interruption, reread the current revision. Replay the same idempotency and event keys only for the same request. A conflicting payload requires a new key. A stale revision requires rereading and owner re-review; never auto-rebase an approval.
5. If evidence is missing, the current stage owner moves the packet to BLOCKED with a reason/evidence reference. Resume only to the recorded checkpoint after updating the missing domain. Do not progress based on a successful software write alone.

## Activation, suspension, revocation, and offboarding

- `ACTIVE` requires verified identity and office binding, approved active appointment, character decision, credentials, exact grants, registered runtime route, authenticated directory/chat evidence, all acceptance checks, independent Auditor review, and Steward approval.
- A role assignment never grants credentials, model execution, or capability permissions. Security approves those separately.
- Suspend through Security, HR, or Steward with an approval and preserve the resume checkpoint. Revalidate expired/revoked credentials, grants, appointment, route, and directory before reactivation.
- Revoke only with owner approval. Before `OFFBOARDED`, record credential/grant revocation, module and chat disablement, HR appointment closure, and rollback/recovery evidence. Keep event history append-only.

## Vicky current operator status

Vicky's packet is at `docs/onboarding/vicky.packet.json`. It is a source-controlled evidence example, not an HR record and not a persisted onboarding request. Current evidence is insufficient to assign a canonical R3A resident ID: the latest authenticated directory snapshot in Issue #58 comment 6768796862 (2026-11-10T12:49:05Z) returned Grace only. HR must supply a current authoritative identity and approved active appointment, then the existing directory owner must establish any authorized occupant/office binding. Do not use the provisional dossier key `r3:vicky` as a current R3A identity.

## Recovery and rollback

- If a repository transaction fails, confirm whether packet and audit event both committed; the operation is atomic. Reread before retry.
- If source revisions conflict, stop at the current checkpoint and request revalidation from that source owner. Do not copy the newer source payload into the packet.
- For a wrong packet/domain update, create a successor revision restoring the last valid references with owner approval and a rollback reason. Never delete or mutate prior onboarding events.
- Migration 019 is additive and is applied by the Coordinator-owned `Store.migrate()` checksummed migration runner. Its disposable PostgreSQL integration test uses `R3A_TEST_ONBOARDING_DSN`, requires a database named `r3a_onboarding_test_*` on loopback or a private `/tmp` socket, and drops only the `r3a` schema in that explicitly named test database.
- Run that integration test with `/tmp/r3a-hr-development-venv/bin/python -m unittest tests.test_r3a_resident_onboarding_postgres -v` after exporting the guarded DSN. It applies the complete checked-in migration stack, confirms a second migration pass is a no-op, rolls back/reapplies 019, and checks two concurrent same-revision writes yield one commit and one revision conflict. It also exercises event-write failure atomicity, duplicate-identity uniqueness, post-association create idempotency, packet-reference privacy, immutable event triggers, and refusal to roll back populated evidence.
- Rollback SQL is `r3a_runtime/rollback/019_resident_onboarding.down.sql`, outside the migration glob. In a Coordinator-approved maintenance window, first verify a recoverable database backup and migration identity. The down migration refuses to run if any onboarding packet or event exists; export and retain evidence, obtain the approved retention disposition, and only then use the governed database procedure. It removes only migration 019 and its ledger row; it does not reverse migrations 001–018.
- The real PostgreSQL regression applies the migration stack through 019, verifies repeat migration is a no-op, exercises guarded empty-schema rollback and re-upgrade, then verifies the populated-data rollback is refused. Do not use this test fixture or down migration on a shared database.
- Database grants, HTTP/CME host wiring, production migration and rollout/rollback belong to the Coordinator release procedure. Source tests do not authorize those actions, and this branch has not changed a shared database or enabled a live onboarding API.
