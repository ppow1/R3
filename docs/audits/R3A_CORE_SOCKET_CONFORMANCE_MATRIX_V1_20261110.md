<!--
R3 CONTROLLED AUDIT RECORD
File: docs/audits/R3A_CORE_SOCKET_CONFORMANCE_MATRIX_V1_20261110.md
Component: R3A-CORE-SOCKET-CERTIFICATION
File Revision: 1.0.0
Created: 2026-11-10
Created By: Independent Auditor V2
Purpose: Independently assess R3A core socket conformance and freeze readiness.
Execution Model: Source review, isolated test execution, read-only runtime observation.
Observability: Exact Git SHAs, test output, process metadata, configuration digest, linked issue evidence.
Dependencies: Steward Issue #56 comment 6774539560; AD-024; approved R3A Modularity Compliance Specification v1.
Authority: Steward P0 core-freeze certification directive; no freeze or production change authorized.
Changed: 2026-11-10 | R3A-CORE-SOCKET-AUDIT-001 | Independent Auditor V2 | Publish first complete core socket conformance matrix.
Supersedes: None.
Contracts: AD-024; AP0-001–AP0-013; MOD-001–MOD-014; STM-001–STM-007; capability, resident binding, durable handler, authorization and diagnostics contracts.
Tests: 483 passed, 10 skipped, 1 known notification-manifest digest failure, 34 subtests passed on c62bb28.
History/Predecessor: New audit artifact. Governing spec was approved at e6a0b736431f4dac41e36274a2bfeb551b529c57 and is present in the Auditor branch, not in candidate c62bb28.
-->
# R3A Core Socket Conformance Matrix v1

**Review date:** 2026-11-10  
**Disposition:** **FAIL — NOT READY TO FREEZE**  
**Published core candidate reviewed:** `c62bb28d026e1c1cad99c90583f0debae067f2a1` (`integration/r3a-coordinator-v2-20261109`)  
**Proposed freeze revision:** None recommended until the finite defects and acceptance gaps below are closed. Steward retains freeze authority.

## Scope and baseline identity

This review applies the approved AD-024 modularity requirements, Charter revision 1.0.1, Roadmap Baseline 1.0 / document revision 1.0.3, AP0 specification 1.0.2, Module Lifecycle and Contract Specification 1.0.2, Capability Contract v1, Resident Execution Profile 1.1.0, Activity Intake Contract 1.1.0, State/Diagnostic Contract 1.0.1, and Bounded Testing/Acceptance Policy. The approved Modularity Compliance Specification is commit `e6a0b736431f4dac41e36274a2bfeb551b529c57`; that controlled file is absent from candidate `c62bb28`, so the candidate does not carry its own governing-spec revision.

`c62bb28` is the published source candidate and is a descendant of the #43/#46 work. It is **not** the exact source observed in the live CME process. Read-only process inspection found Ring 0 PID 1160036 (started Nov 9 23:56 EST) and CME PID 1535593 (started Nov 10 09:18 EST), both with working directory `/home/admin1/r3a-workstreams/coordinator-20261109-v2`. CME started before Coordinator merge `1dd57e1` at 09:22 and before the reviewed candidate's final staging commit at 10:10. The checkout is currently at unpublished `e4982addd034b6457e552f6864af5618653a8e6a` with two source/test files modified after CME start. The in-memory CME revision cannot be established exactly from available diagnostics. The bootstrap file was not read; its SHA-256 is `ddb8de5eb022d8e59982e70e50b5062fa0677e1bb71fb07cc5406dc4a3374f5e` (path `/home/admin1/.config/r3a-ap0-m1/bootstrap.live-modular-e7a6f56.json`). A read-only Comms CME projection at 12:44 EST reported healthy monitor status but did not report the R3A source SHA, applied config revision, module lifecycle set, or durable-ledger evidence.

No running service, database, grant, identity, or Coordinator file was changed during this audit. All automated tests ran from a detached worktree at `c62bb28` using `/tmp/r3a-live-modular-test-venv`.

## Versioned contract manifest for the candidate

| Interface | Candidate revision observed | Source |
|---|---|---|
| Capability operation | `r3a.capability-operation.v1@1.0.0`; 1.1.0 reserved for Steward effects | `r3a_runtime/schemas/capability-operation.v1.schema.json`; `capability_contracts.py:217-239` |
| Capability invocation/result | `r3a.capability-invocation.v1@1.0.0`; 1.1.0 for Steward operations | `r3a_runtime/schemas/capability-invocation.v1.schema.json`; `capability_contracts.py` |
| Module manifest | `r3a.module-manifest.v1@1.0.0` and `@1.1.0` | `capability_contracts.py:242-255`; `module-manifest.v1.1.schema.json` |
| Provider process protocol | `r3a.capability-provider.v1`, major 1 with declared minor range | `module-manifest.v1.schema.json`; module lifecycle spec |
| Resident module binding | `r3a.resident.module-binding.v1@1.0.0` | `schemas/resident-module-binding.v1.schema.json`; `module_extensions.py:54-84` |
| Resident executor declaration | `r3a.resident.executor@1.0.0`; execution contract range major 1 | `module_extensions.py:214-230`; `module-manifest.v1.1.schema.json` |
| Resident execution context | `r3a.resident.execution-profile@1.0.0` | `R3A_RESIDENT_EXECUTION_PROFILE.md`; `cme.py:710-772` |
| Activity intake | `r3a.activity-intake.v1@1.0.0` | `schemas/activity-intake.v1.schema.json`; `Store.submit_activity_intake` |
| Durable activity handler | `r3a.activity-handler@1.0.0`; activity-intake range major 1 | `schemas/activity-handler.v1.schema.json`; `module_extensions.py:110-160,326-358` |
| State machines | `module.lifecycle@2`, `activity.generic@1`, `process.lifecycle@1` | `r3a_runtime/state_machines/` |
| External bootstrap | `schema_version: 1`; resident bindings are validated against v1.1 module declarations | `config.py:343-395,855-906` |

The reviewed provider fixture artifact SHA-256 is `43e8d4e2cfa308a84c103771ec294ee611adcc428ccd7f15dc5115a9bb051e8c`; shared contract fixture SHA-256 is `363943e2fe13953964fa2c10483a8114b7f514535cc87fd34a5f75330ec8f886`. The lifecycle demo's replacement provider SHA-256 is `26ed0d3790295f09533101395e01901f0eacaa27525f0da622d419ddca494665`.

## Conformance matrix

| Requirement | Result | Source/test evidence | Operational evidence and limit |
|---|---|---|---|
| Ring 0 remains a minimal independent supervisor; CME lifecycle is separate (AD-001–003, AP0-001/002) | **NOT VERIFIED** | Source and unit suite include Ring 0/CME lifecycle paths; full suite passes except noted failure. | Ring 0 and CME are running, but the observed CME predates `c62bb28`; no exact in-memory source revision, controlled restart test, or matching durable lifecycle query was available. |
| Provider registry, digest/contract validation, discovery separate from authority (AD-004/007, AP0-007/008, MOD-001–006) | **PASS** (fixture/source) | `ProviderProcessManager`, registry validation and lifecycle implementation. Focused command: 89 passed. Real child-provider process fixture in `test_registered_engineering_provider_process_can_be_replaced_and_stopped` installs, activates, invokes, fails a replacement, preserves prior version, replaces successfully, deactivates, detects process death, and leaves unrelated telemetry registered. | The integration test uses a temporary directory and in-memory lifecycle Store; it does not run Ring 0 or PostgreSQL. It proves provider process behavior, not full live acceptance. |
| Generic resident-to-module binding, canonical identity association, digest/version pin, fail-closed binding and authorization (AD-024, MOD-011–013) | **PASS** (source/fixture); live activation **NOT VERIFIED** | `config.py:867-906` validates role declarations/binding targets; `module_extensions.py:54-84,233-287` verifies authoritative association, unique active module, manifest identity/digest and contract range; `cme.py:774-822` resolves current directory record and configured binding, then authorizes before dispatch. `test_cme_resolves_two_authoritative_resident_bindings_to_one_registered_executor` and `test_cme_rejects_stale_directory_association_before_authorization` passed. | Executor test uses a mocked provider runtime, mocked authoritative directory profiles, and fake module registry rows. It does not start an independently packaged executor worker or use live HR/directory/grants. |
| Generic durable handler registration, compatible handler resolution, capability requirements, request/result/progress/checkpoint validation, authorization denial before execution (AD-024, MOD-014) | **PASS** (source/fixture); live process/recovery **NOT VERIFIED** | `cme.py:553-680,2989-3007`; `module_extensions.py:110-160,326-358`; `db.py:1459-1599` accepts arbitrary namespaced activity types and persists the durable envelope. Shared interop tests exercise allowed/denied paths, digest/version, result and checkpoint validation. | Handler dispatch uses a mocked `provider_runtime` in interop tests. The PostgreSQL process-loss test is skipped without dedicated `R3A_CHECKPOINT_TEST_DSN`; no actual PostgreSQL state or process-loss recovery was verified. |
| Durable checkpoint and progress update/retry recovery (AP0-004/006, MOD-008/009, handler contract) | **NOT VERIFIED** | Code writes a versioned handler binding/checkpoint and verifies binding on retry; regression test `test_handler_checkpoint_survives_progress_and_process_loss_retry` is present. | Test skipped: `requires disposable PostgreSQL R3A_CHECKPOINT_TEST_DSN`. No live durable checkpoint/recovery acceptance. |
| Authorization and identity separation; registration/discovery/binding do not grant; denial fails closed (AP0-008, MOD-006, AD-024) | **PASS** (fixture/source); live grant source **NOT VERIFIED** | `invoke_capability` validates caller/input/target and performs CME authorization/audit; handler and resident tests assert denied requests do not reach execution. `test_r3a_capability_grants.py` included in focused 89-pass run. | No managed authority/grant provider was exercised. Target-scoped operation behavior is separately **NOT VERIFIED**; see below. |
| Normal module install/activation/deactivation/replacement/config reload avoids CME/Ring 0 restart (AD-004/024, MOD-004/013) | **PASS** (provider fixture); live proof **NOT VERIFIED** | `test_r3a_module_extension_lifecycle.py` asserts stable CME/provider PIDs across config reload, safe-boundary refusal and failed reload rollback. Process lifecycle integration demo performs real provider subprocess activation/replacement/stop. | No Ring 0 was run under controlled audit, so AP0-007/AD-024 live no-restart criterion is not independently established. Resident and handler module roles were not separately exercised as child processes. |
| Compatibility/dependency fail-closed; truthful lifecycle/health diagnostics (MOD-003/005/010, STM-001–007) | **PASS** (fixture/source) | Full tests exercise incompatible contract rejection, digest/dependency validation, replacement failure, health loss, lifecycle status and diagnostics. | Persistent status and diagnostics were not compared against live PostgreSQL rows for the reviewed SHA. |
| External configuration validation/revision and module binding reload | **PASS** (fixture/source); live revision **NOT VERIFIED** | `config.py:343-395,855-906`; lifecycle test validates safe boundary and process retention across compatible reload. | No managed config apply/rollback or durable config revision query performed; live bootstrap hash recorded above, contents not read. |
| Notification generic intake/module boundary (AD-024, activity-intake v1.1.0 / handler v1) | **FAIL** | `cme.py:1354-1381` retains hardcoded `notification.ingest`; `db.py:1421-1457` reads institution events, synthesizes a Grace-specific objective, then calls `submit_grace_objective`. `config.py:355-389` only accepts `institution_events.v1`. This bypasses `submit_activity_intake` and registered handler routing. | Core defect FS-01; detailed below. Existing N1 behavior must remain regression-tested during correction. |
| Knowledge responsibility remains module-owned (AD-024, modularity specification §4) | **FAIL** | `cme.py:1956-1963,1987-1990` special-cases `institution.knowledge.read` and directly retrieves configured files when provider resolution returns none. | Core defect FS-02; provider/fallback behavior needs parity and denial/evidence tests before targeted fallback removal. |
| Engineering workflow policy is replaceable through handler contract (AD-024, modularity specification §4) | **FAIL** | `cme.py:2514+` implements Engineering proposal/work-order/execution/verifier continuation in CME; `cme.py:3030-3035` contains an Engineering-specific branch and refuses delegated residents. | Core defect FS-03; target incremental handler extraction/equivalence, not a CME rewrite. |
| Module-specific Website/API journey and generic module controls | **NOT VERIFIED** | This core candidate includes capability discovery/control paths but no complete independent Website acceptance run. | Website #51's authenticated user journey is outside this socket-only fixture set. No live module management, diagnostics or workflow UI acceptance was observed. |
| Truthful process isolation description | **PASS** (documented/source) | Lifecycle contract and provider launch path describe separate child process under CME service UID, filtered environment and private socket; no OS sandbox is claimed. | Same-UID privilege and configured credential exposure remain as documented baseline risk, not a freeze blocker requiring new sandbox design. |
| Five-minute audited-package rollout target | **NOT VERIFIED** | Isolated provider process replacement fixture completed in 5.40 seconds wall-clock (one test command; test body 3.56 seconds). This includes fixture setup, install, activation, invocation, replacement and deactivation. | The test starts from an in-repository test manifest and does not record audited-package queue-entry time or deployment/runtime activation time. It is evidence that the fixture path is fast, not a measured queue-to-operational-activation SLA. |

## Test evidence

All commands ran against the detached worktree at `c62bb28d026e1c1cad99c90583f0debae067f2a1`.

| Command | Result |
|---|---|
| Focused: `pytest -q tests/test_r3a_activity_handler_interop.py tests/test_r3a_activity_intake_contract.py tests/test_r3a_activity_intake_consumer.py tests/test_r3a_module_contracts.py tests/test_r3a_module_extensions.py tests/test_r3a_module_extension_lifecycle.py tests/test_r3a_capability_grants.py tests/test_r3a_capability_integration_demo.py` | **89 passed in 7.95s** |
| Provider package/process lifecycle and resident/handler dispatch focused tests | **5 passed in 3.69s**, 5.84s total command wall-clock |
| Provider package/process lifecycle test alone, `/usr/bin/time` | **1 passed in 3.56s**, **5.40s total command wall-clock** |
| Full suite: `pytest -q` | **483 passed, 10 skipped, 1 failed, 34 subtests passed in 28.42s** |
| PostgreSQL checkpoint test: `pytest -q -rs tests/test_r3a_activity_checkpoint_persistence.py` | **1 skipped**: dedicated `R3A_CHECKPOINT_TEST_DSN` absent |

The one full-suite failure is the known Notification Service manifest pin mismatch: `tests/test_r3a_notification_service.py::NotificationServicePresentationTests::test_versioned_service_manifest_pins_runtime_artifacts_and_categories` expected SHA-256 `107ea3b45871477ab24038114d4f00b1bf92d4b78b2ca4882c859635800780c3`, actual `8f6584602d6b6a9c2e8e3f01694c75da721b40a0f1b8f64b91ec9bf587da5480`. This is attributed to the previously tracked #48 notification artifact correction, not silently waived. The #48 owner must publish a corrected digest-bearing commit and rerun the regression before freeze.

## Finite core-side correction list

| ID | Finding and evidence | Owner | Minimum correction | Required acceptance/regression |
|---|---|---|---|---|
| FS-01 | Notification intake remains a CME/Store special case (`cme.py:1354-1381`; `db.py:1421-1457`) and turns source events directly into Grace objectives rather than generic authorized `r3a.activity-intake.v1` work. | Coordinator/CME #43; Notification #48 supplies adapter behavior. | Route the configured notification adapter through the existing authorized source capability and generic durable intake; preserve N1 semantics and let the registered handler own notification policy. No second scheduler/store. | Generic intake fixture plus isolated DB test proves grant denial before adapter, replay/conflict, lifecycle projection and event/provenance parity with current N1; non-Grace handler dispatches without a new CME type branch; Grace objective and notification regressions pass. |
| FS-02 | CME directly reads Knowledge files when registered provider lookup is absent (`cme.py:1956-1963,1987-1990`). | Coordinator/CME #43 and Knowledge #47. | Keep CME invocation/grant/audit/evidence-reference coordination; remove the local domain retrieval fallback after the Knowledge provider contract has parity coverage. | Provider allow/deny/unavailable tests, evidence/provenance parity, no fallback on provider failure, and existing Grace knowledge regression. |
| FS-03 | CME owns the Engineering proposal, work-order, correction and verifier workflow (`cme.py:2514+`, dispatch branch `3030-3035`) and rejects secondary resident execution for this domain. | Coordinator/CME #43 with the assigned AP2 Engineering module workstream. | Migrate incrementally to a registered handler for Engineering policy/workflow; retain CME generic scheduler, durable work identity/state, authorization, invocation audit and recovery. No wholesale extraction. | Equivalence tests for work-order creation/authorization, idempotent execution, continuation/checkpoint, verifier PASS/FAIL and Grace compatibility; new handler and existing Grace/provider paths coexist without a domain branch. |
| Target-scoped capability through resident compatibility projection | **NOT VERIFIED; not counted as a demonstrated core defect.** `cme.py:1993-2002` supplies `{}` for `target`; the canonical invocation validator (`capability_contracts.py:289-327`) validates target against the operation schema. The current candidate's OctoMiner operation permits empty target and config-selects its host. #59's requested host-scope behavior is a module/integration acceptance issue until a concrete operation requires resident-selected target data. | Live Modular Integration #59 / Coordinator to prove target-scope semantics for the approved module. | Do not change the socket on speculation. Verify whether an approved target is configuration-fixed or caller-selected; if caller-selected, file a separate evidence-backed interface finding. | #59 acceptance must show intended host scope matches invocation target, provider configuration, and authorization audit; existing read providers remain compatible. |

Items not listed as core defects: the #48 digest mismatch belongs to the Notification module/package and must be corrected by that owner; the target-scope behavior is unverified pending #59's concrete invocation semantics; missing HR directory rows, grants, provider configuration and Website activation are operational dependencies, not authority the core may invent. Stronger sandboxing remains deferred to a threat model under AD-024.

## Freeze recommendation and remaining gates

**Recommendation: FAIL — NOT READY TO FREEZE.** The provider, generic resident-binding and handler sockets are present and pass substantial fixture coverage, but a freeze would make three demonstrated domain-specific core paths (FS-01 through FS-03) part of the immutable baseline. In addition, the mandatory same-SHA end-to-end proof is incomplete: only the provider role has exercised an actual child process; resident executor and durable handler execution use mocked process dispatch; the PostgreSQL recovery test is skipped; the target runtime source/config revision is not correlated to the published SHA. The target-scope behavior for #59 remains NOT VERIFIED and is not treated as a demonstrated core defect.

Before a new freeze review, require:

1. A corrected published core commit closing FS-01–FS-03 with permanent parity tests.
2. One disposable, independently packaged provider/resident/handler module acceptance sequence on one unchanged core SHA covering install, register, discover, activate, authorized invocation, denial, deactivate, replace/rollback, recovery, diagnostics, and no CME/Ring 0 restart.
3. The PostgreSQL checkpoint/process-loss regression run against a dedicated disposable database; do not count the skipped test as recovery acceptance.
4. A queue-entry and activation timestamp for the audited package and an observed <=5 minute duration; separately report the managed-runtime result.
5. An exact managed runtime source/config release identifier and matching diagnostics evidence. The current live CME health projection is not release evidence for `c62bb28`.
6. Corrected #48 notification manifest digest; full regression suite green for the candidate SHA.
7. The approved modularity specification revision and contract manifest included or immutably referenced in the proposed freeze record.

The #59 target-scope integration result must also be included in the next freeze review, with a clear PASS or an exact module/interface finding.

No source code, production process, shared database, identity, authorization grant, or service configuration was changed by this audit. This is a recommendation only; the Steward owns any freeze decision.
