<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_HR_VICKY_TRANSFER_MATRIX_2026-11-10.md
Component: R3A-HR-VICKY-TRANSFER
File Revision: 1.0.0
Created: 2026-11-10 UTC
Created By: Codex GPT-6
Purpose: Account for every deliverable and finding from quarantined legacy PR #57 and record the R3A-only disposition.
Execution Model: Source inventory, interface review, and R3A transfer record.
Observability: Exact baseline/PR references, target modules, tests, and explicit external blockers.
Dependencies: Issue #58; PR #57 at cff4bba7502ed4ad31ebcad97e4b83d056d198db; R3A Coordinator V2 baseline b1b38130e796adfe02c7343f71764e9ab0513f6b.
Authority: Steward transfer order in R3A Issue #58. Does not authorize personnel decisions, directory writes, credentials, grants, merge, or deployment.
Changed: 2026-11-10 UTC | R3A-HR-VICKY-TRANSFER | Codex GPT-6 | Inventory the quarantined PR and transfer its useful contract/test semantics into R3A-owned code.
Supersedes: None
Contracts: R3A institutional directory; R3A resident identity-association v1; HRPrincipalAssociationAdapter.
Tests: tests.test_r3a_hr_association; tests.test_r3a_resident_dossiers; tests.test_r3a_institutional_directory.
History/Predecessor: New file; evidence source https://github.com/ppow1/R3/pull/57.
-->
# R3A HR / Vicky Transfer Matrix

## Scope and baseline

This transfer is R3A-only. The legacy draft [PR #57](https://github.com/ppow1/R3/pull/57), head `cff4bba7502ed4ad31ebcad97e4b83d056d198db`, was inspected file by file and closed unmerged as directed by [Issue #58](https://github.com/ppow1/R3/issues/58#issuecomment-6768560524). No PR #57 code was merged, cherry-picked, or copied into R3A. It remains historical evidence only.

The designated worktree `/home/admin1/r3a-workstreams/hr-development` was clean on branch `engineering/r3a-hr-development-20261110` at stale phase-zero `65d33c4a22e05393fce6ec985c947e2ec5fceef0`. Fetch confirmed the Coordinator V2 integration head at `b1b38130e796adfe02c7343f71764e9ab0513f6b` (`integration/r3a-coordinator-v2-20261109`). The old branch was 14 commits unique to itself and 101 commits behind that base; a merge-tree preview found conflicts in 14 R3A runtime, test, and dossier files. To avoid dropping or overwriting either line, the original worktree was left untouched and a successor worktree was created from the exact Coordinator V2 head:

- Worktree: `/home/admin1/r3a-workstreams/hr-development-coordinator-v2`
- Branch: `engineering/r3a-hr-vicky-20261110`
- Starting SHA: `b1b38130e796adfe02c7343f71764e9ab0513f6b`

The newer `integration/r3a-live-modular-integration-20261110` head `990f90449d460178febed8105f431af24d50a300` is a staged source candidate, not the Coordinator V2 integration baseline, and was not used as the base.

## PR #57 deliverable inventory

| PR #57 item | Original behavior / useful finding | R3A target and disposition | Evidence |
|---|---|---|---|
| `docs/runbooks/HR_PERSONNEL_SYSTEM.md` (32 added lines) | Described exact write scope, revision, resolver, active-state, provenance, idempotency, audit, and the fact that the legacy host had not wired a resolver. | **Not copied.** Legacy service instructions and SQLite paths are out of R3A scope. Contract lessons are expressed in `r3a_runtime/residents/hr_association.py` and this matrix. R3A directory discovery remains read-only. | R3A focused association tests verify exact scope, revision, active HR state, fresh evidence, idempotency/correlation forwarding, and fail-closed missing host operation. |
| `runtime/hr_governed_capabilities.py` (140 added lines) | Proposed a legacy HR-host tool that resolves an opaque evidence reference, checks exact `r3:hr`/`hr.save`/`write` scope, expected revision, active HR status, and returns persisted provenance/audit references. | **Reimplemented at the R3A client boundary**, not at the legacy host: `r3a_runtime/residents/hr_association.py` now reads the exact revision/status, requires a trusted resolver to bind the HR ID/revision to a fresh R3A directory snapshot, derives the canonical principal only from that result, and forwards stable idempotency/correlation values. The external host operation remains absent and is not implemented here. | `tests/test_r3a_hr_association.py`; existing `test_hr_association_adapter_fails_closed_without_hr_provenance_operation`. |
| `runtime/hr_store.py` (122 added lines) | Proposed SQLite association, provenance, idempotency, and audit tables with revision increment in one legacy HR transaction. | **Not transferred.** An R3A dossier or local table must not become a second HR/identity/binding authority. R3A PostgreSQL stores character revisions and context pins; it does not own `resident_occupants` or `office_bindings`. Persistence must occur through the existing authoritative source operation once that owner publishes it. | Source inspection found the R3A directory plugin is read-only; no R3A directory/occupant write API or authenticated onboarding writer is present in the Coordinator V2 baseline. |
| `tests/test_hr_association.py` (250 added lines; 9 tests) | Covered absent resolver, exact HR write contract, wrong scope/action/resource, stale revision/evidence, active status, Vicky onboarding rejection, idempotency/conflicting reuse, duplicate principal, and audit/provenance references. Its fake gateway and synthetic data were test-only. | **R3A boundary semantics rewritten; source-host invariants explicitly deferred.** `tests/test_r3a_hr_association.py` tests authorization denial before reads/resolution, exact resource/action/operation/scope on the allowed path, fresh snapshot and HR revision binding, active office and appointment gates, missing host operation, stable key forwarding, required persisted audit/provenance response, and Vicky’s `onboarding` row failing before resolver invocation. Generic positive fixtures use `fixture` IDs only; no Vicky principal or binding is invented. Conflict replay, duplicate-principal rejection, and atomic persistence cannot be meaningfully tested against an absent external writer; they remain mandatory writer contract tests when that authority owner supplies the operation. | Focused suite result is recorded below. The legacy fake-gateway implementation and SQLite table assertions were not copied. |

## R3A authority and findings

- The R3A `institutional.directory.discover` provider reads `riverview_authority.institutional_offices`, `office_bindings`, and `resident_occupants` in a read-only repeatable-read transaction. It does not read legacy HR SQLite and contains no write path.
- The directory projection provides canonical directory principal, office ID/role/status, binding revision, and snapshot provenance. It does **not** provide an HR ID crosswalk. An approved server-side resolver must join an authorized revisioned HR identity source to this fresh R3A projection without accepting caller-supplied identity claims.
- R3A already has `HRPrincipalAssociationAdapter` and `validate_identity_association`; the adapter fails closed because the authoritative HR host operation `associate_authority_principal_with_provenance` is absent. This source candidate strengthens that R3A consumer contract. It does not create a parallel authority or claim that the external operation is deployed.
- Existing evidence from the last authenticated managed R3A roster snapshot recorded in Issue #33 lists `resident:grace` / `office:grace` only. This operator has no approved authenticated R3A roster session or directory write interface; no fresh Vicky identity/binding query or write was performed.
- The prior governed legacy read found HR row `r3:vicky`, Engineering Manager, `onboarding`, revision 1. It is legacy-source evidence only. It establishes no R3A principal, active binding, appointment approval, credential, or grant.
- No HR record, R3A directory row, office binding, credential, grant, service, or external database was changed.

## Exact external interface still required

An authorized R3A onboarding/authority owner must provide or identify the existing operation for establishing an occupant and active office binding. Until that exists, R3A can only discover and validate bindings; it cannot create one.

The HR-to-directory association host interface must be server-authenticated and revision checked. Its trusted resolver must accept an opaque evidence reference and return a privacy-minimized record containing the exact HR resident ID and revision/source reference, canonical directory principal, active office ID/role/status, binding revision, fresh snapshot digest/time, and source references that include the requested evidence reference. The writer must enforce the exact `r3:hr` / `hr.write` (or `hr.save`) / `write` / `r3:vicky` scope, reject stale/conflicting revision and duplicate principal, and atomically persist the association, provenance, idempotency result, and audit event in its existing authority. The R3A adapter passes stable idempotency/correlation values and requires auditable success references; it does not implement or deploy this external writer.

Vicky’s HR row is still `onboarding`. HR authority must record an approved active appointment and Engineering Manager assignment through its authorized procedure before association. Credential issuance and chat execution grants require separate exact approval. Directory visibility, model/execution readiness, and live chat are separate gates.

## Tests

Focused command:

```text
python3 -m unittest tests.test_r3a_hr_association tests.test_r3a_resident_dossiers -v
Ran 38 tests — OK
```

An additional attempt to include `tests.test_r3a_institutional_directory` and `tests.test_r3a_capability_grants` ran the 38 available tests successfully but could not import either neighboring suite because `psycopg_pool` is not installed in this shell environment. The project declares `psycopg[binary,pool]>=3.2,<4` in `pyproject.toml`; no dependency installation or environment change was made.

These are source-level fixture results only. They are not a live directory query, R3A authority write, HR host integration, credential/grant verification, deployment, or chat acceptance.
