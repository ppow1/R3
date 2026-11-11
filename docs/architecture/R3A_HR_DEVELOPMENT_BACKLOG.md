# R3A HR Development Backlog and Dependency Register

Updated 2026-11-11 from Issue #58 and Step 61 dispatch #61 comment `6803213372`.

| ID | Work / required evidence | Owner | Status | Next action |
|---|---|---|---|---|
| HRD-01 | Universal packet schema, source-reference validator, resumable lifecycle and durable R3A packet/event repository | HR Development | Reconciled with active Coordinator baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`; canonical authority spoofing and recursive-ref blockers remain corrected. Combined focused tests: 143 passed, 1 separate-DSN checkpoint test skipped in the main invocation then passed separately (1 passed). | Auditor reviews combined exact SHA and package; Coordinator integrates migration/service only after review and deployment approval |
| HRD-02 | Authoritative R3A HR person/appointment read and approved active appointment for Vicky | HR authority / Helen's configured HR manager authority | BLOCKED: Issue #33 verifies a legacy `r3:vicky` row in `onboarding`, revision 1, not an active appointment or R3A identity. Existing HR source branch/commit exposes `hr.directory`, `hr.read`, `hr.save`; no current authenticated appointment decision supplied. | HR authority names accountable source approver, supplies current record revision, approved appointment, assignment, authority and effective dates |
| HRD-03 | Resident occupant, canonical principal and active Engineering Manager office binding | Riverview directory authority with HR approval | BLOCKED: last authenticated snapshot recorded at 2026-11-10T12:49:05Z returned Grace only; read path is `institutional.directory.discover`; no occupant/binding writer or named write owner identified. | Coordinator/directory authority names source owner and authorized write procedure; after HR approval, establish binding and capture fresh authenticated digest/revisions |
| HRD-04 | Provenance-bearing HR-to-directory association writer | HR authority/source owner; R3A consumes the operation | BLOCKED: source owner/approver not identified in available issue evidence; verified host has `hr.directory`, `hr.read`, `hr.save`, but lacks `associate_authority_principal_with_provenance`. | Accountable HR source owner publishes or identifies a governed writer meeting the interface in `R3A_HR_ONBOARDING_DEPLOYMENT_PLAN.md`; keep R3A adapter fail-closed |
| HRD-05 | Character approval, canon revision, memory/continuity and relationship policy | Character Architecture / Jessica's configured approval authority | BLOCKED for Vicky: provisional dossier only; no approved Character Bible/continuity evidence | Obtain source artifact refs and required independent approval through existing Character Architecture workflow |
| HRD-06 | Resident credential issue, ownership, expiry and verification | Security | BLOCKED: no resident credential provisioning interface or approval evidence identified | Security publishes governed credential API/procedure, expiry and rotation/revocation evidence contract |
| HRD-07 | Exact grants and renew/revoke | Security / R3Authority | BLOCKED for Vicky: no grant refs or approvals | Approve exact capability/resource/action/operation/scope and expiry; validate effective CME authorization independently |
| HRD-08 | Runtime module, model route, dependencies, CME registration/config | Coordinator #51 with Autonomy #43 | BLOCKED for Vicky: no Vicky execution profile/route or deployed registration evidence | Coordinator/Autonomy agree canonical module, route, capability interface and live execution acceptance tests |
| HRD-09 | Authenticated Website resident directory and chat/persistence | Coordinator / Website #51 | PARTIAL platform path exists; Vicky not present in latest authenticated roster; chat not verified. Directory-provider test's inactive-provider fixture is corrected; registration alone remains fail-closed | After approved binding/runtime, authenticate through `/api/v1/steward/residents`, then prove resident chat turn and persistence |
| HRD-10 | Independent acceptance review and institutional activation | Independent Auditor #56; Steward | BLOCKED until HRD-02..09 evidence exists | Auditor reviews packet/trace; Steward provides explicit activation approval after all checks pass |
| HRD-11 | Migration, DB role grants, service composition and production deployment | Coordinator #51 | Active baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f` is now an ancestor. Combined migration stack through 019, rollback/re-upgrade and transaction/privacy checks pass in private disposable PostgreSQL 16; shared migration remains unapplied. No authenticated onboarding service composition/API or least-privilege DB grants are present. | Auditor review of combined SHA; Coordinator identifies service integration owner, approves DB grants/route/release procedure and maintenance window before shared migration |
| HRD-12 | Immutable onboarding handoff package and exact digest manifest | HR Development; Coordinator consumes after review | Deterministic package builder and archive/digest regressions implemented. It will label the bundle `SOURCE_CANDIDATE_NOT_DEPLOYABLE` until host composition, authority writers, and review gates exist. | Build from the clean merged source SHA; verify in-band hashes and archive digest; commit sidecars and handoff; obtain exact-SHA Auditor review |
| HRD-13 | Universal process backlog/maintenance | HR Development and each domain owner | OPEN | Keep this register updated; implement source-independent improvements without waiting for Vicky's external approvals |

## Completed source artifacts in the current candidate

- `r3a_runtime/schemas/resident-onboarding-packet.v1.schema.json`
- `r3a_runtime/state_machines/resident_onboarding.v1.json`
- `r3a_runtime/residents/onboarding.py`
- `r3a_runtime/residents/onboarding_repository.py`
- `r3a_runtime/migrations/019_resident_onboarding.sql`
- `r3a_runtime/rollback/019_resident_onboarding.down.sql` (data-preserving refusal if records exist)
- `docs/architecture/R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md`
- `docs/runbooks/R3A_RESIDENT_ONBOARDING.md`
- `docs/runbooks/R3A_HR_ONBOARDING_DEPLOYMENT_PLAN.md`
- `docs/onboarding/packet-template.json`
- `docs/onboarding/vicky.packet.json`
- `tests/fixtures/resident-onboarding-synthetic.json`
- `tests/test_r3a_resident_onboarding.py`
- `tests/test_r3a_resident_onboarding_postgres.py` (explicit disposable database only)
- `scripts/package_r3a_hr_onboarding.py` and `tests/test_r3a_hr_onboarding_package.py` (deterministic immutable handoff bundle)
- `tests/test_r3a_institutional_directory.py` fail-closed inactive-provider fixture regression

Source implementation and operational activation have distinct status. No external record, appointment, identity, binding, credential, grant, module or chat configuration is modified by the source candidate.
