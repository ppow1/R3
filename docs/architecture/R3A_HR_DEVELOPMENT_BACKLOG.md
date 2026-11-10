# R3A HR Development Backlog and Dependency Register

Updated 2026-11-10 from Issue #58 and Coordinator baseline `d592d1d9e09e05dafb52fac4c598bcf92445fef6`.

| ID | Work / required evidence | Owner | Status | Next action |
|---|---|---|---|---|
| HRD-01 | Universal packet schema, source-reference validator, resumable lifecycle and durable R3A packet/event repository | HR Development | Source implemented; 59 focused HR/onboarding/directory/grant/dossier tests pass; isolated PostgreSQL integration applies migration stack through 019 and passes rollback/re-upgrade, repository transaction, idempotency, revision, privacy, immutable-audit and multi-resident checks | Auditor reviews source and PostgreSQL evidence; Coordinator integrates migration/service only after review and deployment approval |
| HRD-02 | Authoritative R3A HR person/appointment read and approved active appointment for Vicky | HR authority / Helen's configured HR manager authority | BLOCKED: no current authenticated HR source record/API evidence; legacy onboarding row is not accepted | HR supplies read interface, current record revision, appointment approval, assignment, authority and effective dates |
| HRD-03 | Resident occupant, canonical principal and active Engineering Manager office binding | Riverview directory authority with HR approval | BLOCKED: fresh authenticated snapshot at 2026-11-10T12:49:05Z returned Grace only; no R3A writer identified | Directory owner identifies governed occupant/binding write procedure; then repeat authenticated read and capture digest/revisions |
| HRD-04 | Provenance-bearing HR-to-directory association writer | R3/HR authority owner; integration contract consumed by R3A | BLOCKED: host operation `associate_authority_principal_with_provenance` absent | Publish server-authenticated operation with exact scope, expected revision, trusted resolver, atomic provenance/audit and idempotency; retain fail-closed R3A adapter |
| HRD-05 | Character approval, canon revision, memory/continuity and relationship policy | Character Architecture / Jessica's configured approval authority | BLOCKED for Vicky: provisional dossier only; no approved Character Bible/continuity evidence | Obtain source artifact refs and required independent approval through existing Character Architecture workflow |
| HRD-06 | Resident credential issue, ownership, expiry and verification | Security | BLOCKED: no resident credential provisioning interface or approval evidence identified | Security publishes governed credential API/procedure, expiry and rotation/revocation evidence contract |
| HRD-07 | Exact grants and renew/revoke | Security / R3Authority | BLOCKED for Vicky: no grant refs or approvals | Approve exact capability/resource/action/operation/scope and expiry; validate effective CME authorization independently |
| HRD-08 | Runtime module, model route, dependencies, CME registration/config | Coordinator #51 with Autonomy #43 | BLOCKED for Vicky: no Vicky execution profile/route or deployed registration evidence | Coordinator/Autonomy agree canonical module, route, capability interface and live execution acceptance tests |
| HRD-09 | Authenticated Website resident directory and chat/persistence | Coordinator / Website #51 | PARTIAL platform path exists; Vicky not present in latest authenticated roster; chat not verified. Directory-provider test's inactive-provider fixture is corrected; registration alone remains fail-closed | After approved binding/runtime, authenticate through `/api/v1/steward/residents`, then prove resident chat turn and persistence |
| HRD-10 | Independent acceptance review and institutional activation | Independent Auditor #56; Steward | BLOCKED until HRD-02..09 evidence exists | Auditor reviews packet/trace; Steward provides explicit activation approval after all checks pass |
| HRD-11 | Migration, DB role grants, service composition and production deployment | Coordinator #51 | Migration 019 and complete current migration stack validated against isolated PostgreSQL 16.15; guarded empty rollback/re-upgrade passes; shared migration remains unapplied and service API unmounted | Review migration/rollback and test evidence; provision least-privilege packet-store access; integrate only after independent review and release authorization |
| HRD-12 | Universal process backlog/maintenance | HR Development and each domain owner | OPEN | Keep this register updated; implement source-independent improvements without waiting for Vicky's external approvals |

## Completed source artifacts in the current candidate

- `r3a_runtime/schemas/resident-onboarding-packet.v1.schema.json`
- `r3a_runtime/state_machines/resident_onboarding.v1.json`
- `r3a_runtime/residents/onboarding.py`
- `r3a_runtime/residents/onboarding_repository.py`
- `r3a_runtime/migrations/019_resident_onboarding.sql`
- `r3a_runtime/rollback/019_resident_onboarding.down.sql` (data-preserving refusal if records exist)
- `docs/architecture/R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md`
- `docs/runbooks/R3A_RESIDENT_ONBOARDING.md`
- `docs/onboarding/packet-template.json`
- `docs/onboarding/vicky.packet.json`
- `tests/fixtures/resident-onboarding-synthetic.json`
- `tests/test_r3a_resident_onboarding.py`
- `tests/test_r3a_resident_onboarding_postgres.py` (explicit disposable database only)
- `tests/test_r3a_institutional_directory.py` fail-closed inactive-provider fixture regression

Source implementation and operational activation have distinct status. No external record, appointment, identity, binding, credential, grant, module or chat configuration is modified by the source candidate.
