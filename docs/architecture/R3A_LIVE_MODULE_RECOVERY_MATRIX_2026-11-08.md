<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_LIVE_MODULE_RECOVERY_MATRIX_2026-11-08.md
Component: R3A-LIVE-MODULAR-ACCEPTANCE
File Revision: 1.0.1
Created: 2026-11-08
Created By: Unknown (legacy document; original author not recorded)
Purpose: Record isolated real-process recovery acceptance against fetched Modular Plugins and Coordinator candidates.
Execution Model: Independent PostgreSQL, Ring 0/CME, and provider child processes; Unix-domain control interfaces.
Observability: Exact candidate revisions, activity records, process identities, and regression evidence.
Dependencies: R3A lifecycle and recovery contracts; isolated PostgreSQL and module provider interfaces.
Authority: Steward directive R3A Live Module Recovery Acceptance, 2026-11-08.
Changed: 2026-11-08 | R3A-LIVE-MODULAR | Record live candidate matrix and exact residual defects.
Changed: 2026-11-11T18:04:20Z | R3A-WEBSITE-INTEGRATION-STEP46 | Codex GPT-6 | Reconcile the deployed Website recovery-matrix edit into the Coordinator candidate.
Tests: Live acceptance plus focused fixture tests; full candidate unit-suite result below.
Supersedes: Extends R3A_LIVE_MODULAR_INTEGRATION_ACCEPTANCE_2026-11-08.md.
Contracts: R3A module lifecycle and recovery contracts; hints/file-provenance.md.
History/Predecessor: Immediate predecessor blob db65c13ea43db2a6ad117ec331cafeaf105fa13d at frozen baseline 89eda1331b96fe40918e4aa67de09c5ae3f45227.
-->
# R3A live module recovery acceptance matrix — 2026-11-08

## Acceptance summary

**Independent module replacement with core and unrelated-module continuity: PASS on Coordinator candidate `c1818d5dbbc2b05fad0468322c32c227a5da5a49`.** The isolated CME replaced Engineering Workspace 1.0.0 with 1.0.3, attempted and contained a failed 1.0.2 activation, rolled back to 1.0.0, and reinstalled 1.0.3. During deactivation, replacement, rollback, and provider crash recovery, the separate telemetry provider remained active and callable; Ring 0 and CME remained healthy. After a CME-only crash, Ring 0 restarted CME and restored the exact configured module versions, including Engineering Workspace 1.0.3 and telemetry 2.0.0.

Overall recovery acceptance is **PARTIAL** because oversized provider output becomes a generic invocation error instead of a bounded typed protocol result, rejected manifests leave no durable module-lifecycle failure record, and a full engineering capability invocation after restart could not be authorized without the normal durable work-order workflow. No authorization check was bypassed. These are recorded as explicit residuals below and in [Issue #46](https://github.com/ppow1/R3/issues/46).

## Revisions and environment ownership

Fetched candidates tested:

| Component | Exact revision | Result |
|---|---|---|
| Modular Plugins | `d58e004765ee4a6cfa0e6fabd18a0507ce2f1e30` (`engineering/r3a-modular-plugins-20261106`) | Live replacement passed; explicit recovery after a killed provider failed in that implementation. Automatic restore passed when Ring 0 startup grace was raised to 60 seconds / heartbeat stale threshold 30 seconds. |
| Coordinator integration | `c1818d5dbbc2b05fad0468322c32c227a5da5a49` (`integration/r3a-multi-resident-20261108`) | Current matrix target; replacement, rollback, explicit provider recovery, and exact-version restart restore passed. |

The direct merge of these heads is not clean. `git merge-tree --write-tree` reports conflicts in `docs/R3A_MODULAR_FOUNDATION_IMPLEMENTATION.md`, `r3a_runtime/capability_worker.py`, `cme.py`, `config.py`, `db.py`, `provider_runtime.py`, `module-manifest.v1.schema.json`, and capability tests. This workstream did not resolve those conflicts or edit lifecycle implementation. Coordinator candidate `c1818d5` was tested independently in a detached scratch worktree.

The pre-existing isolated live-modular service and database were preserved. Coordinator-managed AP0/CME and R3/V2 services were not targeted. A second isolated candidate environment used:

| Resource | Coordinator candidate environment |
|---|---|
| Source worktree | `/tmp/r3a-live-modular-coordinator-candidate` at `c1818d5dbbc2b05fad0468322c32c227a5da5a49` |
| External bootstrap | `/tmp/r3a-live-modular-coordinator-20261108/config/bootstrap.json` |
| Isolated state root | `/tmp/r3a-live-modular-coordinator-20261108` |
| PostgreSQL | Database `r3a_coord_recovery_20261108`, user `r3a_runtime`, Unix socket `/tmp/r3a-live-modular-coordinator-20261108/data/pgsocket`, port 55513 bound to Unix socket only; current PostgreSQL PID 1800706 |
| Ring 0 | PID 1801125, actual `r3a_runtime.ring0` process |
| CME | PID 1804364 after tested CME restart, actual `r3a_runtime.cme` process |
| CME control / diagnostics | `/tmp/r3a-live-modular-coordinator-20261108/data/run/cme-control.sock`; `/tmp/r3a-live-modular-coordinator-20261108/data/run/cme-diagnostics.sock` |
| Active bootstrap digest after restored valid config | `2f7766b8efa0cf0389e045a9f4e5c9d0d732e7cf771a8fd34b8e48063730898c` |

The separately fetched Modular Plugins scratch cluster remains available at `/tmp/r3a-mod-lifecycle-20261108`; PostgreSQL port 55542 is Unix-socket-only. Its Ring 0/CME processes are PIDs 1795956 / 1796677. The original live-modular database, Ring 0, and CME are separately preserved under `/home/admin1/.local/state/r3a-live-modular-20261108`.

All providers below ran as separate provider child processes from the c1818 candidate. Test manifests and provider artifacts were only staged in the detached scratch worktree and external bootstrap; no lifecycle manager or core code was changed by the integration branch.

## Modules and live capability evidence

| Module | Version | Artifact SHA-256 | Live evidence |
|---|---:|---|---|
| `r3a.octominer-telemetry` | 2.0.0 | `af8aae26cad6f603f69658fea6dde2b868eadf1f4bdce6106b46f4c561587a86` | Provider PID 1801441 before crash recovery; PID 1804008 after recovery; PID 1804402 after CME restart. `infrastructure.octominer.telemetry.read` was discovered and invoked through canonical CME invocation; successful calls returned 13 data outputs and 13 evidence records (7,965 result bytes). In the fresh isolated cluster `available_count=0` because source endpoint credentials/configuration were not present; process and capability invocation were real. |
| `r3a.isolated_workspace` | 1.0.0 → 1.0.3 | fixture artifact `26ed0d3790295f09533101395e01901f0eacaa27525f0da622d419ddca494665` | Provider PIDs observed: 1801756 (1.0.0), 1802132 / 1803594 / 1803805 (1.0.3 across replacement/reactivation/restart). Discoverable capability `engineering.workspace.apply_patch`. Provider activation, stop, replacement, rollback, and restart restoration all verified. A post-restart effectful invocation was not performed: CME requires activity-scoped grant plus durable executing Engineering work order, and this run did not synthesize that authorization. |
| `r3a.acceptance-oversized-result` | 1.0.0 | `03d73a050d4040967a3244097cc7dcf04d2b6a56bec3f102dc05170d91c7dffa` | Real provider PID 1805689 returned a 70,000-byte payload. Invocation recorded durable `FAILED` state with a 1,230-byte error result; caller received `RuntimeError: ValueError: Invalid or oversized protocol frame`. Provider, CME, and Ring 0 stayed healthy. |

## Acceptance matrix

| Check | Result | Exact candidate / evidence |
|---|---|---|
| Ring 0 and CME start from isolated config | **PASS** | c1818; Ring 0 PID 1801125 and CME PID 1801160 initially healthy. |
| Two modules activate and capabilities are discoverable | **PASS** | c1818; telemetry 2.0.0 and workspace 1.0.0 active; discovery listed both canonical operations. |
| Real capability request succeeds | **PASS** | c1818; canonical telemetry invocation returned 13 outputs / 13 evidence records, 7,965 bytes. Source availability was zero due absent endpoint credentials. |
| Deactivate one while unrelated module continues | **PASS** | c1818; workspace 1.0.3 deactivated; telemetry PID 1801441 remained ACTIVE/healthy and canonical invocation succeeded; workspace reactivated. |
| Replace one module while core and unrelated module continue | **PASS** | c1818; workspace 1.0.0 → 1.0.3, telemetry 2.0.0 remained active; Ring 0/CME healthy. No CME restart or other-module restart occurred. |
| Failed activation / failed upgrade is contained | **PASS** | c1818; workspace 1.0.2 configured against absent workspace path failed initialization (`FileNotFoundError`); prior 1.0.3 remained active and telemetry remained available. |
| Roll back to prior working version | **PASS** | c1818; workspace 1.0.3 → 1.0.0 succeeded, then 1.0.0 → 1.0.3 succeeded. |
| Provider child crash isolation and recovery | **PASS** | c1818; telemetry PID 1801441 killed with SIGKILL; lifecycle recorded FAILED / exit code -9; explicit activation recovered provider as ACTIVE PID 1804008. CME and workspace remained available. d58e004 had failed explicit reactivation (`FAILED -> ACTIVE`), defect corrected by c1818. |
| CME restart restores exact desired module versions | **PASS** | c1818; CME PID 1801160 killed; Ring 0 started CME PID 1804364. Telemetry 2.0.0 restored ACTIVE at PID 1804402; workspace 1.0.3 restored ACTIVE at PID 1804395. |
| Desired configuration restoration | **PASS** | c1818; restored providers used active isolated bootstrap digest `2f7766b8efa0cf0389e045a9f4e5c9d0d732e7cf771a8fd34b8e48063730898c`; failed candidate config was reverted before restart. |
| Invalid manifest rejected safely | **PASS / PARTIAL** | c1818; malformed manifest caused bounded `ConfigurationError` on `config.reload`; valid configuration reload restored service. No bad module registered. No durable module lifecycle failure row was created. |
| Missing dependency rejected safely | **PASS / PARTIAL** | c1818; dependency on absent `r3a.missing.acceptance-dependency@^1.0.0` caused `ConfigurationError`; no module row/provider registration. Core healthy; rejection not durably recorded as module lifecycle evidence. |
| Incompatible dependency rejected safely | **PASS / PARTIAL** | c1818; workspace depending on telemetry `^3.0.0` while only 2.0.0 configured caused `ConfigurationError`; no bad module row/provider registration. Core healthy; rejection not durably recorded as module lifecycle evidence. |
| Oversized provider result | **FAIL** | c1818; durable invocation marked FAILED, but caller sees generic invalid-frame runtime error, not bounded typed result/error. Issue #46 defect. |
| Full suite on tested candidate | **BLOCKED by test environment** | c1818; `/usr/bin/python3 -m unittest discover -s tests -v` ran 149 tests, 148 passed, with `test_r3a_ap1` import error because host Python lacks `psycopg_pool`. `/home/admin1/r3a-phase0/.venv/bin/python -m unittest discover -s tests -v` discovered 189 tests, 186 passed, with three import errors because phase0 venv lacks `pytest` (`test_r3a_activity_intake_contract`, `test_r3a_capability_integration_demo`, `test_r3a_module_contracts`). Earlier d58 candidate suite passed 140/140 in phase0 venv. |
| Full candidate merge | **BLOCKED** | d58e004 and c1818d5 directly conflict in eight lifecycle/config/schema/test paths listed above; owned by Modular Plugins / Coordinator integration. |

Replacement interruption was limited to the target workspace provider's stop/start window. The unrelated telemetry provider remained ACTIVE and served a canonical request during target deactivation; no unrelated-service unavailability was observed. A sub-second exact interruption duration was not captured in this run, so no more precise duration is claimed.

## Failures, durability, and recovery details

* **Failed upgrade:** missing workspace path is a provider initialization failure; the prior 1.0.3 provider stayed active. This is a durable module lifecycle transition on the active provider state, unlike invalid dependency candidates rejected during bootstrap reload.
* **Crash:** killed telemetry provider state and exit code were persisted; explicit activation under c1818 recovered it. The earlier d58e004 `FAILED -> ACTIVE` refusal is documented as a version-specific defect, not current-candidate behavior.
* **Restart:** killing CME left Ring 0 in place. Ring 0 restarted CME and CME reconciled configured desired modules to their exact versions. Provider PIDs changed, proving process recovery rather than stale registry state.
* **Rejected config candidates:** manifest/dependency validation failed before provider registration. Database queries found no registry rows for workspace 1.0.4 / 1.0.5 / 1.0.6, the missing dependency, or telemetry 3.0.0. The config-reload failure was returned to its caller but did not yield a durable module-scoped failure record.
* **Oversized IPC result:** result frame overflow remained contained to that invocation; CME/provider process and unrelated telemetry/workspace stayed healthy. The durable invocation failure row exists, but the result contract is not caller-friendly or typed.

## Test and release notes

The integration branch intentionally contains acceptance manifests, the oversize-result probe, fixture checks, and this evidence only. It does not contain lifecycle-source modifications. The current test-worktree HEAD before these additions was `bbc61cf750217919102a80c97ac34348f7dc7968`; the final integration commit is recorded in Git after this report is committed.

Focused local fixture tests cover artifact digest pinning and the distinct missing/incompatible dependency manifests. Both full-suite attempts are blocked by missing test/runtime packages in the available interpreters; rerun in a dependency-complete environment to clear this blocker.

This acceptance report does not designate a production module release. Workspace replacement providers and the oversized output provider are acceptance fixtures. Telemetry 2.0.0 is the existing provider artifact, not a new release. No managed-runtime installation procedure is issued until the merge compatibility and oversized-result defects are resolved.

## Actionable defects and remaining dependencies

1. **IPC frame overflow:** `provider_runtime` rejects the 70,000-byte reply, but canonical invocation leaks a generic runtime error. Expected: bounded typed `FAILED` response with preserved durable evidence and no protocol exception escaping the capability API. Reproduction is the acceptance provider in `r3a_plugins/live_acceptance`; tested against c1818. Owner: Modular Plugins lifecycle/provider protocol. Reported on Issue #46.
2. **Manifest rejection evidence:** invalid/missing/incompatible manifests are rejected before module registration and leave no durable module-scoped rejection evidence. Expected: safe rejection plus durable audit evidence identifying candidate ID/version and dependency/schema cause. Tested against c1818. Owner: Modular Plugins + Coordinator config integration. Reported on Issue #46.
3. **Engineering invocation workflow:** a provider replacement and restart are verified, but post-restart effectful capability execution depends on the configured durable Engineering authorization/work-order workflow. This acceptance run did not create such a work order and did not bypass the gate. To close this evidence item, run the canonical Engineering operation through the normal AP2 adapter.
4. **Candidate compatibility:** d58e004 and c1818d5 are not directly mergeable. Modular Plugins and Coordinator need to publish a compatible integrated revision, after which this isolated matrix can be rerun.
5. **Suite environment:** provide both `pytest` and declared `psycopg_pool` in the isolated test environment and rerun the candidate suite.
