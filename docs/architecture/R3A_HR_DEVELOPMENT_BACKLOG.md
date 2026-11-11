<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_HR_DEVELOPMENT_BACKLOG.md
Component: R3A-HR-DEVELOPMENT-BACKLOG
File Revision: 1.0.3
Created: Unknown (legacy; predecessor committed before 2026-11-10)
Created By: Unknown (legacy)
Purpose: Track reusable HR onboarding deliverables, authority dependencies, and operational blockers.
Execution Model: Durable workstream backlog; no authority writes or activation.
Observability: Owner, state, next action, test result, and commit evidence.
Dependencies: R3A HR contracts, Issue #58, Coordinator baseline and authority interfaces.
Authority: Steward Steps 66/74/81; R3A architecture and roadmap governance.
Changed: 2026-11-11T18:43:21Z | HRD-STEP-74/81 | Codex GPT-6 | Track host composition, installable package, roster policy, and end-to-end activation register.
Changed: 2026-11-11T18:54:31Z | HRD-STEP-74 | Codex GPT-6 | Record verified wheel and exact install evidence.
Changed: 2026-11-11T21:55:53Z | HRD-STEP-135 | Codex GPT-6 | Record malformed authoritative HR revision guard and exact test evidence.
Supersedes: None; increments legacy document revision after provenance metadata was absent.
Contracts: Universal Resident Onboarding v1; host-composition v1.
Tests: Documentation cross-checked against R3A contracts and issue evidence.
History/Predecessor: Existing register predecessor in branch history; legacy file provenance not recorded.
-->

# R3A HR Development Backlog and Dependency Register

Updated 2026-11-11 from Issue #58 and Steps 61/74/81/135 dispatches #61 comments `6803213372`, `6804154755`, `6804261392`, and `6807891597`.

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
| HRD-11 | Migration, DB role grants, service composition and production deployment | Coordinator #51 | Active baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f` is an ancestor. Combined migration stack through 019, rollback/re-upgrade and transaction/privacy checks passed in private disposable PostgreSQL 16; shared migration remains unapplied. Step 74 implements the `r3a.resident.onboarding.host-composition.v1` façade; authenticated production API route and least-privilege DB grants remain absent. | Auditor reviews exact new SHA; Coordinator names host/service owner and authorizes DB role, route/release procedure and maintenance window before shared migration |
| HRD-12 | Immutable installable onboarding runtime package and exact digest manifest | HR Development; Coordinator installs after approval | Step 74 built `r3a_ap0_runtime-0.1.0-py3-none-any.whl` from source `e247f3fba9c9affdbeac3293b77b91f904cbb27c`; SHA-256 `0886db886f360c44bceeec5cf1760e41c3357020cf100291b81bb6fa9b5d0860`. Isolated target install/import and required migration/rollback/schema/state-machine resource checks passed. The current exact-SHA source archive will be generated from the final committed handoff source. No managed installation/deployment authorized. | Publish wheel/archive checksums and request exact-SHA Auditor review; Coordinator installs only after release gates |
| HRD-13 | Universal HR roster, privacy, crosswalk and resident lifecycle policy | HR authority / Steward; HR Development supplies adapter/schema after policy approval | **BLOCKED.** Current R3A dossier contract requires HR-sensitive fields to stay governed and authorized projections only; no approved universal roster policy/source owner/projection contract is evidenced. | HR authority names owner and approves source-of-truth, lifecycle, data classification, disclosure, retention, correction, provenance and revision rules; then HRD implements generic adapter/tests |
| HRD-14 | Universal Vicky activation and all-resident operational dependency register | HR Development plus each authoritative owner | Step 81 register created at `docs/architecture/R3A_HR_VICKY_ACTIVATION_BACKLOG.md`; records 19 ordered gates, current proof, owner, and next action, including the missing HR-owned universal roster/privacy policy. Vicky activation remains blocked. | Keep status evidence-linked; execute next source-owned work and do not infer missing decisions |
| HRD-15 | Universal process backlog/maintenance | HR Development and each domain owner | Step 135 completed a fail-closed contract correction: the HR association adapter rejects missing, non-integer, boolean, and nonpositive authoritative HR revisions before directory resolution or write. Targeted tests: 9 passed, 8 subtests passed. Source commit `c094f7c`; backlog update follows. The existing wheel/archive predate this change and are not exact artifacts for the new source SHA. | Auditor reviews the exact final source SHA; Coordinator must use a rebuilt exact-SHA artifact only after existing release gates. Continue source-independent HR contract gaps while authority integrations remain unavailable. |

## Completed source artifacts in the current candidate

- `r3a_runtime/schemas/resident-onboarding-packet.v1.schema.json`
- `r3a_runtime/state_machines/resident_onboarding.v1.json`
- `r3a_runtime/residents/onboarding.py`
- `r3a_runtime/residents/onboarding_repository.py`
- `r3a_runtime/residents/onboarding_host.py` — Step 74 versioned authenticated host composition boundary
- `r3a_runtime/migrations/019_resident_onboarding.sql`
- `r3a_runtime/rollback/019_resident_onboarding.down.sql` (data-preserving refusal if records exist)
- `docs/architecture/R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md`
- `docs/runbooks/R3A_RESIDENT_ONBOARDING.md`
- `docs/runbooks/R3A_HR_ONBOARDING_DEPLOYMENT_PLAN.md`
- `docs/onboarding/packet-template.json`
- `docs/onboarding/vicky.packet.json`
- `tests/fixtures/resident-onboarding-synthetic.json`
- `tests/test_r3a_resident_onboarding.py`
- `tests/test_r3a_resident_onboarding_host.py`
- `tests/test_r3a_resident_onboarding_postgres.py` (explicit disposable database only)
- `scripts/package_r3a_hr_onboarding.py` and `tests/test_r3a_hr_onboarding_package.py` (deterministic immutable handoff bundle)
- `tests/test_r3a_institutional_directory.py` fail-closed inactive-provider fixture regression
- `docs/architecture/R3A_HR_VICKY_ACTIVATION_BACKLOG.md` — proof-linked all-resident policy dependencies and Vicky activation path

Source implementation and operational activation have distinct status. No external record, appointment, identity, binding, credential, grant, module or chat configuration is modified by the source candidate.
