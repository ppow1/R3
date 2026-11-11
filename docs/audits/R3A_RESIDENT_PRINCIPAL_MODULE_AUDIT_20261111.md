<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_RESIDENT_PRINCIPAL_MODULE_AUDIT_20261111.md
Component: R3A-RESIDENT-IDENTITY-AUDIT
File Revision: 1.0.3
Created: 2026-11-11 UTC (audit creation date established by prior candidate commit)
Created By: Codex GPT-6
Purpose: Record the principal/module identity audit, contract dispositions, corrections, evidence and open ownership gates.
Execution Model: Source, contract and test audit.
Observability: Versioned report and occurrence inventories.
Dependencies: R3A resident execution, invocation, HR/directory, Website and module contracts.
Authority: Steward Issue #43 assignment comment 6785046697; AD-024.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Reconcile findings to integration baseline and include all current CME owner blockers.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Record binding contract validation, final regression results and refreshed occurrence inventory.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Add confirmed frozen Engineering and verifier-result identity mismatches with strict expected-failure regressions.
Supersedes: None.
Contracts: r3a.resident.execution-profile@1.0.0; r3a.capability-invocation.v1; r3a.resident.module-binding.v1.
Tests: Referenced permanent regression suite; this report is not operational acceptance evidence.
History/Predecessor: Prior candidate blob 39b3022dfc4b61fd0f918ff142ffe0174f969198.
-->
# Resident Principal and Executable Module ID Audit

**Assignment:** Issue #43, Steward comment `6785046697`  
**Compared sources:** current integration baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`; Autonomy correction `a9da804013e3eb6757c888ac3e7131495c006b89`; reconciled candidate `engineering/r3a-resident-id-audit-integration-20261111`.
**Scope:** R3A runtime, CME, Grace, HR/directory association, module and capability manifests, API/Website source, SQL migrations, scripts, fixtures, and tests.

## Identity rules

| Value | Contract meaning | Keep in |
|---|---|---|
| `resident:<slug>` | Canonical institutional resident principal, obtained from the existing HR/directory association | Principal, directory, binding, resident execution profile, conversation target, authorization actor, activity target |
| `resident.<slug>` | Executable resident module ID | Module registry, module manifest, IPC/module process, `caller.resident_id` on a capability call, executable profile ID in the HR association, module-scoped grants |
| `r3:<slug>` | HR institutional record ID | HR dossier and HR-to-directory crosswalk |

A resident module binding joins the first and second values. It does not authorize the resident. CME must still enforce the existing grants.

## Comparison of the two corrections

`e0b872e079640e8930cb792ee4df13540a5a6037` is a merge commit, not a standalone code correction. Its Coordinator parent (`59e829f`) began separating caller principal from module identity in CME capability dispatch, but the Grace adapter at that baseline still required `ContractEnvelope.resident_id == self.module_id` and validated the directory profile against `self.module_id`. Thus the original correction was incomplete at the resident adapter boundary.

`a9da804013e3eb6757c888ac3e7131495c006b89` fixes that Grace-specific missed boundary: the envelope and directory execution profile are checked against the bound canonical resident principal, while `self.module_id` stays the registered executable identity; bound execution requires both the profile and CME envelope. It also recovers conversation event kind from nested activity input. It did not introduce the original issue. The repository-wide scan found repeated fixture/API/association mistakes and several CME caller-construction paths that require the frozen-core owner's review.

## Confirmed corrections in this candidate

| Path and current line | Intended type | Correction | Permanent regression |
|---|---|---|---|
| `r3a_runtime/resident_identity.py:19-43` | Principal and module as distinct nominal values | Added `ResidentPrincipalId` / `ResidentModuleId` and strict namespace parsers; no new identity source | `tests/test_r3a_resident_identity_kinds.py` |
| `r3a_runtime/grace_module.py` | Bound execution principal is canonical; process module stays dotted | Enforces namespace separation, profile/envelope agreement, and nested durable event-kind recovery; legacy same-module calls remain supported | `tests/test_r3a_ap1.py`; `tests/test_r3a_resident_identity_kinds.py` |
| `r3a_runtime/residents/identity_association.py:40-45,61-79` | HR and directory principal use colon; runtime `profile_id` uses dotted module ID | Association now validates both namespaces while preserving the existing HR, dossier, directory and grant references | `tests/test_r3a_resident_dossiers.py` |
| `r3a_runtime/residents/runtime_context.py:31-40,84-90` | Authenticated/directory resident identity is canonical | Rejects module-shaped identities in character-context authority input | `tests/test_r3a_resident_dossiers.py` |
| `r3a_runtime/module_extensions.py` and `r3a_runtime/schemas/resident-module-binding.v1.schema.json` | Binding `resident_id` is canonical; `module_id` remains a registry-defined executable ID | Rejects module-shaped binding principals and principal-shaped module IDs without imposing a resident-specific prefix on generic module IDs | `tests/test_r3a_module_extensions.py` |
| Shared binding schema sidecar and test declarations | Contract version and module version remain independent from identity type | Schema change is recorded as a versioned controlled artifact; regression covers generic executor ID `executor.orbit` paired with canonical resident principal | `tests/test_r3a_module_extensions.py` |
| `r3_app.py:177-179,216-219` | Website conversation `resident_id` is a principal | API rejects executable module IDs at create/list boundaries | `tests/test_r3a_website.py` |
| `tests/test_r3a_steward_conversations.py`, `tests/test_r3a_notification_delivery.py`, `tests/test_r3a_activity_handler_interop.py`, `tests/test_r3a_ap1.py`, `tests/test_r3a_activity_intake_consumer.py`, `tests/test_r3a_resident_dossiers.py`, `tests/test_r3a_capability_integration_demo.py` | Test field follows its named contract | Replaced dotted IDs in principal, directory, binding, target and profile-principal fields; preserved dotted IDs in module fields. The activity-intake CME fixture now uses generic module identity `r3a.cme`, not Grace's module ID. Grace tests execute with separate principal and module identities. | Focused tests listed below |
| `tests/fixtures/capabilities/octominer.invocation.request.v1.json:7`, `tests/test_r3a_reasoning_provider.py`, `tests/test_r3a_bitwarden_consumer_integration.py`, `tests/test_r3a_capability_contracts.py`, `tests/test_r3a_capability_integration_demo.py` | `caller.principal_id` is colon; `caller.resident_id` is dotted | Corrected invocation evidence; module ID and grant constraints remain unchanged | Capability contract/provider tests |
| `tests/test_r3a_capability_grants.py` | Grant `module_id` is executable module identity | Corrected a colon-form principal incorrectly stored as a module ID | Capability grant tests |
| `docs/architecture/R3A_RESIDENT_EXECUTION_PROFILE.md` | Profile `resident_id` is a canonical principal, not a process/module ID | Clarifies identity types and the binding relationship | `tests/test_r3a_ap1.py`; `tests/test_r3a_resident_identity_kinds.py` |

The changed test fixtures include two separately bound resident principals, `resident:alpha` and `resident:beta`, both associated with the same registered handler module. This demonstrates separate identity bindings without hardcoding identity-specific executor behavior.

## Confirmed integration-only mismatch

At baseline `2cc3fe3`, `r3a_plugins/engineering_workspace/manifest.json:83` set `caller_constraints.allowed_principals` to `resident.grace`, while line 84 correctly set `allowed_residents` to `resident.grace`. The principal has been corrected to `resident:grace`; the module remains dotted. Because the current integration manifest is newer than the one on the older `a9da804` tree, this was corrected on its own branch based directly on `2cc3fe3`, preserving the integrated Engineering handler and lifecycle declarations. The original correction was pushed as `afa220c0c6e37292b8ba1c36484abebff36b68b7`; this reconciled candidate carries the equivalent tree change in commit `6ab0d9103ff1f58f6bd057aff94c993a56e441d2`. Its focused manifest-registration regression passes (**2 passed**); it has not been merged into the Coordinator baseline.

## CME boundary disposition; frozen source not changed

The current integration baseline's generic resident capability action path at `r3a_runtime/cme.py:1999` constructs the correct pair: `caller.principal_id` comes from the durable activity's canonical resident principal, and `caller.resident_id` is the registered executor module ID. `tests/test_r3a_activity_handler_interop.py` exercises this path and asserts the pair. The older #51 handoff at comment `6785629677` described a pre-baseline version of that path; it is not an accurate description of the current integration source.

Three CME-originated calls use CME's own module ID in both caller fields: directory-profile resolution at `cme.py:724`, activity-intake source invocation at `cme.py:1322`, and bounded reasoning escalation at `cme.py:3397`. These calls do not identify a resident principal; they represent CME acting as an institutional module. The existing caller contract does not make the system-actor representation clear enough to reclassify them as resident identity defects. They are preserved and referred to the #51 owner for confirmation of whether CME should identify itself through `service_id` or the existing module principal representation. The authenticated Steward directory call at `cme.py:972` uses the Steward canonical principal and leaves `caller.resident_id` null, as expected.

Two additional confirmed frozen-core mismatches remain:

- `r3a_runtime/cme.py:2455` (`_resident_result_from_verification`) writes `self.module_id` into `r3a.resident.result.resident_id`, even when the durable activity contains a canonical resident principal. A strict expected-failure regression in `tests/test_r3a_ap1.py::ResidentVerificationFeedbackIntegrationTests::test_cme_verifier_result_uses_canonical_resident_principal` records the required behavior until the #51-owned source correction is reviewed.
- The Engineering flow stores `self.module_id` in proposal and work-order `resident_id` (`cme.py:2597,2634`), then passes it as `EngineeringAction.caller_id` (`cme.py:2665`). `EngineeringAction.to_invocation_request` at `r3a_runtime/engineering.py:434` duplicates `caller_id` into both invocation fields. A strict expected-failure regression in `tests/test_r3a_engineering.py::EngineeringContractTests::test_engineering_action_separates_resident_principal_from_executor_module_id` records the required pair pending the reviewed #51/Engineering owner change.

This candidate does not modify CME or its invocation validator. That preserves current service/provider behavior while keeping the remaining system-actor contract question explicit for #51. The candidate corrects independently owned binding, Grace/runtime, directory/HR, Website, manifest, and fixture boundaries; it does not silently reinterpret CME's authority.

## Occurrence inventory and manual disposition

The TSVs are exhaustive line scans of the named trees for `resident:<slug>` and `resident.<slug>` in tracked source/config/schema/test/documentation file types. The generated scan excludes the audit report and occurrence inventories themselves to avoid self-reference. They include path, line, literal, intended type, action/disposition and test/evidence pointer:

- `R3A_RESIDENT_ID_OCCURRENCES_2CC3_20261111.tsv` — current integration baseline `2cc3fe3`.
- `R3A_RESIDENT_ID_OCCURRENCES_A9DA_20261111.tsv` — active Grace correction worktree after this audit's edits.
- `R3A_RESIDENT_ID_OCCURRENCES_INTEGRATION_CANDIDATE_20261111.tsv` — this candidate after reconciliation and corrections (**752 rows including header; SHA-256 `62e686bcad36e651c3baa5e0b1e37680b65fe5b7ca7d7c6a678ca7bac05bf164`**).

The TSV field classifier is deliberately a candidate locator, not an authority: ambiguous `resident_id` fields are resolved against the owning contract and summarized above. Explicit negative fixtures that contain a deliberately swapped value remain negative tests. Provisional external source identifiers in the Grace dossier are evidence notes, not authoritative principal or module bindings, and remain unchanged pending the HR/directory owner's crosswalk.

## Verification on the reconciled integration candidate

- Focused identity/provider/Grace/Website/HR, activity-intake and Engineering suite: **232 passed, 2 xfailed, 11 subtests passed**, one existing Starlette deprecation warning. The xfails are the two frozen-core regressions described above.
- Full suite: **495 passed, 10 skipped, 2 xfailed, 1 failed, 34 subtests passed**, two warnings. The sole failure is `tests/test_r3a_notification_service.py::NotificationServicePresentationTests::test_versioned_service_manifest_pins_runtime_artifacts_and_categories`: an unchanged notification artifact hash mismatch (`manifest.json` expects `107ea3…`; the baseline checked-in `capability_contracts.py` hashes to `8f6584…`). No notification-service files differ from the integration baseline in this candidate. The two xfails are the frozen-core regressions described above.
- CME and Ring 0 source, live inference, database state, grants, deployment, and authenticated Website runtime were not modified or exercised. CME unit/interoperability code paths in the listed test suites were exercised.

## Evidence limits

The scans cover checked-in R3A text, code, manifests, schemas, migrations and tests in the baseline, prior Grace correction, and reconciled current-integration candidate. The automated field classifier is a locator; the owning contract and manual disposition govern ambiguous values. The scan does not read live database contents or infer authority from display names. No CME source was changed and no live inference, grant, deployment or authenticated Website acceptance is claimed.
