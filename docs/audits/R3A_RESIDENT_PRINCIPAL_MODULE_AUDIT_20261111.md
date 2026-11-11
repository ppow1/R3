# Resident Principal and Executable Module ID Audit

**Assignment:** Issue #43, Steward comment `6785046697`  
**Compared sources:** current integration baseline `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`; Autonomy correction `a9da804013e3eb6757c888ac3e7131495c006b89` and its working correction candidate.  
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

`a9da804013e3eb6757c888ac3e7131495c006b89` fixes that Grace-specific missed boundary: the envelope and directory execution profile are checked against the bound canonical resident principal, while `self.module_id` stays the registered executable identity; bound execution requires both the profile and CME envelope. It also recovers conversation event kind from nested activity input. It did not introduce the original issue. The repository-wide scan found repeated fixture/API/association mistakes and one separate frozen CME handler-action mismatch.

## Confirmed corrections in this candidate

| Path and current line | Intended type | Correction | Permanent regression |
|---|---|---|---|
| `r3a_runtime/resident_identity.py:19-43` | Principal and module as distinct nominal values | Added `ResidentPrincipalId` / `ResidentModuleId` and strict namespace parsers; no new identity source | `tests/test_r3a_resident_identity_kinds.py` |
| `r3a_runtime/grace_module.py:810-817,829-833,859-861` | Bound execution principal is canonical; process module stays dotted | Enforces separate types and validates the profile against the envelope's principal | `tests/test_r3a_grace_resident_conversation.py`; `tests/test_r3a_ap1.py` |
| `r3a_runtime/residents/identity_association.py:40-45,61-79` | HR and directory principal use colon; runtime `profile_id` uses dotted module ID | Association now validates both namespaces while preserving the existing HR, dossier, directory and grant references | `tests/test_r3a_resident_dossiers.py` |
| `r3a_runtime/residents/runtime_context.py:31-40,84-90` | Authenticated/directory resident identity is canonical | Rejects module-shaped identities in character-context authority input | `tests/test_r3a_resident_dossiers.py` |
| `r3_app.py:177-179,216-219` | Website conversation `resident_id` is a principal | API rejects executable module IDs at create/list boundaries | `tests/test_r3a_website.py` |
| `tests/test_r3a_steward_conversations.py`, `tests/test_r3a_notification_delivery.py`, `tests/test_r3a_activity_handler_interop.py`, `tests/test_r3a_ap1.py`, `tests/test_r3a_resident_dossiers.py` | Test field follows its named contract | Replaced dotted IDs in principal, directory, binding, target and profile-principal fields; preserved dotted IDs in module fields | Focused tests listed below |
| `tests/fixtures/capabilities/octominer.invocation.request.v1.json:7`, `tests/test_r3a_reasoning_provider.py`, `tests/test_r3a_bitwarden_consumer_integration.py`, `tests/test_r3a_capability_contracts.py`, `tests/test_r3a_capability_integration_demo.py` | `caller.principal_id` is colon; `caller.resident_id` is dotted | Corrected invocation evidence; module ID and grant constraints remain unchanged | Capability contract/provider tests |
| `tests/test_r3a_capability_grants.py` | Grant `module_id` is executable module identity | Corrected a colon-form principal incorrectly stored as a module ID | Capability grant tests |

The changed test fixtures include two separately bound resident principals, `resident:alpha` and `resident:beta`, both associated with the same registered handler module. This demonstrates separate identity bindings without hardcoding identity-specific executor behavior.

## Confirmed integration-only mismatch

At baseline `2cc3fe3`, `r3a_plugins/engineering_workspace/manifest.json:83` set `caller_constraints.allowed_principals` to `resident.grace`, while line 84 correctly set `allowed_residents` to `resident.grace`. The principal has been corrected to `resident:grace`; the module remains dotted. Because the current integration manifest is newer than the one on the older `a9da804` tree, this was corrected on its own branch based directly on `2cc3fe3`, preserving the integrated Engineering handler and lifecycle declarations. Commit `afa220c0c6e37292b8ba1c36484abebff36b68b7` is pushed. Its focused manifest-registration regression passes (**2 passed**); it is a candidate branch and has not been merged into the Coordinator baseline.

## Frozen CME blocker, not changed here

`r3a_runtime/cme.py:1016-1021` constructs a handler-action capability request with both `caller.principal_id` and `caller.resident_id` set to `execution_principal`. For a bound resident, the first must be the canonical `resident:<slug>` and the second the registered executable `resident.<slug>` (the handler's registered module ID). The existing integration regression now asserts that pair and is a strict expected failure because CME is frozen under the current Steward instruction. This is separately assigned to the CME owner through #51; the Autonomy candidate does not edit CME.

Other occurrences where CME itself invokes a provider as its configured primary module, and module IDs in registry/profile execution data, were not changed without evidence that their contract actor is a bound resident principal. They remain explicitly visible in the occurrence inventory rather than being punctuation-rewritten.

## Occurrence inventory and manual disposition

The adjacent TSVs are exhaustive line scans of the named trees for `resident:<slug>` and `resident.<slug>` in tracked source/config/schema/test file types. They include path, line, literal, field context, intended class, disposition prompt and source excerpt:

- `R3A_RESIDENT_ID_OCCURRENCES_2CC3_20261111.tsv` — current integration baseline `2cc3fe3`.
- `R3A_RESIDENT_ID_OCCURRENCES_A9DA_20261111.tsv` — active Grace correction worktree after this audit's edits.

The TSV field classifier is deliberately a candidate locator, not an authority: ambiguous `resident_id` fields are resolved against the owning contract and summarized above. Explicit negative fixtures that contain a deliberately swapped value remain negative tests. Provisional external source identifiers in the Grace dossier are evidence notes, not authoritative principal or module bindings, and remain unchanged pending the HR/directory owner's crosswalk.

## Evidence limits

The scan covers checked-in R3A text, code, manifests, schemas and migrations in both trees. It does not read live database contents or infer authority from display names. No CME source was changed and no live inference, grant, deployment or authenticated Website acceptance is claimed.
