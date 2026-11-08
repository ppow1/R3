<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_LIVE_MODULAR_INTEGRATION_ACCEPTANCE_2026-11-08.md
Component: R3A-LIVE-MODULAR-ACCEPTANCE
File Revision: 1.0.0
Created: 2026-11-08
Purpose: Record actual isolated R3A module lifecycle integration evidence.
Execution Model: Dedicated user services, PostgreSQL cluster, CME control/diagnostics sockets, and child provider processes.
Observability: PostgreSQL event and invocation rows, provider PIDs, protocol responses, and concurrent health probes.
Dependencies: R3A modular foundation candidate; Modular Plugins Issue #46 / PR #53; AP0-M1 runtime.
Authority: Steward directive "R3A Live Modular Integration Acceptance" dated 2026-11-08.
Changed: 2026-11-08 | R3A-LIVE-MODULAR | Codex GPT-6 | Record isolated live baseline, replacement, failure, restart, and continuity results.
Tests: 34 focused unittest cases; live provider invocations and lifecycle operations as recorded below.
Supersedes: None.
-->
# R3A live modular integration acceptance — 2026-11-08

## Result

**Live replacement demonstrated; full two-provider acceptance remains partial.** The isolated CME replaced real OctoMiner telemetry provider 2.0.0 with a distinct, digest-pinned 2.0.1 test artifact, rolled back to 2.0.0, and recovered a killed provider process. During those operations, Ring 0, CME, and the separate `resident.grace` process remained healthy. A concurrent monitor recorded 127/127 healthy CME probes and 127/127 Grace protocol health probes, with no failures and a maximum probe gap of 0.322 seconds.

Institutional Knowledge 1.0.1 was discovered and activated as a real process, but its canonical invocation failed at the provider IPC boundary. The failure is recorded on [Issue #46](https://github.com/ppow1/R3/issues/46#issuecomment-6722474063). Therefore this run does **not** claim that both capability providers returned successful requests. The required replacement-with-continuity behavior did pass for telemetry while the unrelated Grace module continued its scheduled observer work.

The replacement 2.0.1 artifact is an acceptance-only wrapper around the production telemetry collector. It is not a production module release. The lifecycle implementation was not changed in this workstream.

## Ownership and baseline

The starting worktree was clean at commit `8ec12598293e669e22dc827c2f85240dcb2f7794`, branch `integration/r3a-live-modular-candidate-20261108`. The runtime implementation and manifests came from that candidate. No edits, restart commands, capability calls, or database writes were directed at the existing AP0 service during this run.

Initial inspection found an already-running `r3a-ap0-m1` PostgreSQL/Ring 0 environment whose active bootstrap, machine catalog, and provider artifacts pointed into `/home/admin1/r3a-workstreams/coordinator`. It already had Knowledge 1.1.0 and telemetry 2.0.0 child processes. That environment was treated as Coordinator-owned and left out of lifecycle testing. The current AP0 Ring 0 PID was 1701439 at the first inventory and 1752546 at the later check (systemd reports its current start at 09:09:34 EST); no command in this run targeted that unit. Since its PID changed during the observation window, this document makes no AP0 PID-continuity claim.

The candidate manifests at baseline were:

| Provider | Version | Operation | Artifact SHA-256 | Result |
|---|---:|---|---|---|
| `r3a.institutional-knowledge` | 1.0.1 | `institution.knowledge.read` | `1af091cd41ace4cc9fa94d4a8d8d378163a08ea794611975b36849b6f2394054` | Activated; invocation failed at IPC serialization |
| `r3a.octominer-telemetry` | 2.0.0 | `infrastructure.octominer.telemetry.read` | `af8aae26cad6f603f69658fea6dde2b868eadf1f4bdce6106b46f4c561587a86` | Activated; real telemetry invocation succeeded |
| `resident.grace` | 1.2.8 | AP0-M1 resident module | `710281bb9f3a5d656076378af8145c84a89b0e9825016433287589be0a6e37f0` | Active; scheduled `foundation.observe` activities completed |

The provider protocol was `r3a.capability-provider.v1`, protocol 1.0. The canonical operation contract was `r3a.capability-operation.v1` 1.0.0; invocation used `r3a.capability-invocation.v1` 1.0.0 through CME. Explicit grants were stored only in the isolated database.

## Isolated integration environment

The running acceptance instance uses actual Ring 0/CME code from the candidate checkout, real provider child processes, actual capability manifests, and durable PostgreSQL state.

| Resource | Value |
|---|---|
| Data root | `/home/admin1/.local/state/r3a-live-modular-20261108` (mode 0700) |
| External config root | `/home/admin1/.config/r3a-live-modular-20261108` (files mode 0600) |
| PostgreSQL | Dedicated PostgreSQL 16.15 data directory; database `r3a_live_modular_20261108`; port 55512; Unix socket only |
| PostgreSQL socket | `/home/admin1/.local/state/r3a-live-modular-20261108/data/run/.s.PGSQL.55512` |
| CME control socket | `/home/admin1/.local/state/r3a-live-modular-20261108/data/run/cme-control.sock` |
| Diagnostics socket | `/home/admin1/.local/state/r3a-live-modular-20261108/data/run/diagnostics.sock` |
| Grace module socket | `/home/admin1/.local/state/r3a-live-modular-20261108/data/run/module.sock` |
| PostgreSQL unit | `r3a-live-modular-postgres.service` |
| Ring 0 unit | `r3a-live-modular-ring0.service` |
| Bootstrap | [`bootstrap.json`](</home/admin1/.config/r3a-live-modular-20261108/bootstrap.json>) |
| Knowledge config | [`institutional-knowledge.json`](</home/admin1/.config/r3a-live-modular-20261108/institutional-knowledge.json>) |
| Telemetry config | [`octominer-telemetry.json`](</home/admin1/.config/r3a-live-modular-20261108/octominer-telemetry.json>) |

PostgreSQL reports `inet_server_addr() IS NULL`, confirming the database accepts only local Unix-socket connections. Current service snapshot: PostgreSQL PID 1745772, Ring 0 PID 1757336, CME PID 1757376, and Grace module PID 1757418; Ring 0 and CME reported `RUNNING`/`healthy`, with zero Ring 0 service restarts. The isolated services remain running.

Telemetry used the already-configured read-only OctoMiner SSH target and pinned host key through a protected environment file. Credential values were neither copied into Git nor printed. The integration config directed the telemetry sample history to the isolated data root and bounded each response to one history sample per source to stay within the JSON-lines frame size.

## Live capability evidence

Both operation IDs were registered and discoverable from the bootstrap manifest roster. Knowledge 1.0.1 started as a separate provider PID (1747993 in the first run) and passed its module protocol activation handshake. A valid, granted CME invocation then failed with:

```text
RuntimeError: TypeError: provider returned a non-JSON result
```

`InstitutionalKnowledgeProvider.invoke()` returns the documented `CapabilityProviderResult(output, evidence)`, while `CapabilityWorker.handle("execute")` calls `json.dumps(result)` directly. This prevents the distinct output/evidence object from crossing the module socket. CME remained healthy. The exact reproduction and expected owner are recorded on [Issue #46](https://github.com/ppow1/R3/issues/46#issuecomment-6722474063).

Telemetry 2.0.0 was explicitly activated as PID 1755618 after the isolated core restart. The canonical `capability.invoke` request returned `SUCCEEDED`, provider version 2.0.0 and 13 freshness-aware samples. Four samples were fresh: GPU, storage/filesystem, compute-process mapping, and the isolated telemetry history record. The GPU, filesystem, and compute-process samples came from real read-only OctoMiner queries; the configured local model-server, ComfyUI, and R3A request-history sources were unavailable in this environment and were reported as such.

After replacement, the same operation returned provider version 2.0.1 and 13 samples. All 13 contained the fixture's `provider_revision: 2.0.1-live-acceptance-fixture` marker, and four samples were fresh. After rollback, the same operation again returned version 2.0.0 with 13 samples and four fresh sources.

## Lifecycle, continuity, persistence, and restart

Evidence is preserved outside the repository at [`live_lifecycle.json`](</home/admin1/.local/state/r3a-live-modular-20261108/evidence/live_lifecycle.json>) and [`failure_isolation.json`](</home/admin1/.local/state/r3a-live-modular-20261108/evidence/failure_isolation.json>). The timeline below is UTC.

| Operation | Observed result |
|---|---|
| Kill telemetry 2.0.0 child | PID 1755618 was killed with SIGKILL in the isolated service. The next actual telemetry request succeeded using a restarted provider process; recovery request took 5.404 seconds, including real telemetry collection. |
| Deactivate telemetry 2.0.0 | Durable state reached `STOPPED` in 0.353 seconds. CME PID 1754548, Ring 0 PID 1754506, and Grace PID 1754661 were still present; Grace stayed `ACTIVE` and continued scheduled observer work. |
| Replace 2.0.0 with 2.0.1 | CME returned `replaced: true`, `prior_version: 2.0.0`, `version: 2.0.1`, and new provider PID 1755804 in 2.557 seconds. The old provider was stopped after new readiness. |
| Roll back 2.0.1 to 2.0.0 | CME returned `replaced: true`, `prior_version: 2.0.1`, `version: 2.0.0`, and provider PID 1755877 in 1.210 seconds. The restored provider answered a new canonical invocation. |
| Core and unrelated-module continuity | During replacement, 127 CME health calls and 127 Grace protocol health calls succeeded; no probe errors; maximum observed interval 0.322 seconds. The R3A observer continued completing `foundation.observe` activities. |
| Failed activation | Test manifest version 2.0.2 used the pinned fixture artifact but named a nonexistent factory. Activation failed with `AttributeError`; durable lifecycle became `FAILED`; no candidate process remained active. |
| Failed upgrade and recovery | Replacing 2.0.0 with 2.0.2 failed. The old provider returned to `ACTIVE`; a subsequent telemetry invocation succeeded on 2.0.0. |
| Missing dependency | Test manifest 2.0.3 declared `r3a.missing.acceptance-dependency@^1.0.0`, which was not installed. Activation nevertheless returned `ACTIVE`; the test provider was immediately deactivated. Dependency enforcement is a lifecycle defect or unsupported contract and is reported on [Issue #46](https://github.com/ppow1/R3/issues/46#issuecomment-6722580281). |

Two isolated Ring 0 restarts recovered CME and Grace without touching the existing AP0 service or its database. After the second restart, CME recovered to PID 1757376 and Ring 0 to PID 1757336. PostgreSQL remained PID 1745772. Durable module rows, grants, invocation outcomes, migrations, and event history survived; a read-only query found 2,215 events, the eight migrations through `008_activity_scoped_capability_grants.sql`, two active isolated grants, nine successful telemetry invocations, and one failed Knowledge invocation. On CME restart, provider processes do not survive: the last telemetry row was marked stale/failed until explicit activation. Activation on demand then recovered telemetry. Automatic restoration of a previously active provider version was not demonstrated. Provider health observations are not periodically refreshed; after the diagnostic freshness window passes, status can show an active, running provider as stale. The live process and a subsequent invocation are stronger availability evidence than that stale status projection.

The telemetry history configuration initially used the provider defaults (`history_capacity_per_source=128`, `history_limit=8`). After repeated 13-source invocations, a later response exceeded the line-reading limit and the client raised `ValueError: Separator is found, but chunk is longer than limit`. Reducing the isolated response count to one restored successful invocations. This finding is also reported on [Issue #46](https://github.com/ppow1/R3/issues/46#issuecomment-6722580281).

## Failure-isolation matrix

| Failure exercised | Result | Status |
|---|---|---|
| Invalid manifest fields | `load_settings` rejected the manifest before runtime activation | Passed |
| Missing dependency | Declared dependency was absent, but provider activated | Failed; owner follow-up required |
| Failed activation | Nonexistent provider factory was recorded `FAILED`; core remained healthy | Passed |
| Provider process crash | Telemetry process restarted on the next request; CME/Grace stayed healthy | Passed |
| Failed upgrade | Old provider remained/reactivated and invoked successfully | Passed |
| Rollback | 2.0.1 replaced by prior 2.0.0 and invoked successfully | Passed |
| Provider result crosses process protocol | Knowledge's typed output/evidence result was rejected as non-JSON | Failed; owner follow-up required |
| Bounded history response | Default projection exceeded frame limit after repeated collection | Failed at defaults; isolated config workaround used |
| Recovery after CME/Ring 0 restart | Database and event lineage survived; provider required explicit/on-demand activation | Partial; no automatic provider reactivation claim |

## Tests and reproducibility

Focused test command:

```bash
PYTHONPATH=/home/admin1/r3a-workstreams/live-modular \
  /usr/bin/python3 -m unittest -v \
  tests.test_r3a_capability_contracts \
  tests.test_r3a_capability_integration_demo \
  tests.test_r3a_octominer_plugin \
  tests.test_r3a_telemetry_providers \
  tests.test_r3a_live_modular_replacement_fixture
```

**34 tests passed.** `systemd-analyze --user verify` passed for the two isolated units; `git diff --check` passed. The live database invocation ledger and process probe evidence above are separate from these fixture/unit tests.

Operator commands use the isolated config, for example:

```bash
R3A_CONFIG=/home/admin1/.config/r3a-live-modular-20261108/bootstrap.json
/home/admin1/r3a-phase0/.venv/bin/python -m r3a_runtime.cli --config "$R3A_CONFIG" status
/home/admin1/r3a-phase0/.venv/bin/python -m r3a_runtime.cli --config "$R3A_CONFIG" capability-module-status \
  --operation-id infrastructure.octominer.telemetry.read --provider-version 2.0.0
/home/admin1/r3a-phase0/.venv/bin/python -m r3a_runtime.cli --config "$R3A_CONFIG" capability-module-replace \
  --operation-id infrastructure.octominer.telemetry.read \
  --old-module-id r3a.octominer-telemetry --old-version 2.0.0 --new-provider-version 2.0.1
```

The control and diagnostics endpoints are private Unix sockets; PostgreSQL has no TCP listener. No Coordinator service, R3/V2 service, production database, listener, or managed capability grant was intentionally changed.

## Handoff and remaining dependencies

The live replacement proves that the candidate's generic provider lifecycle can replace the telemetry implementation while the core and a separate module process continue operating. It does not qualify the test wrapper for managed installation. PR #53 remains the Modular Plugins implementation handoff; this integration branch provides fixture code, digested manifests, tests, and live evidence.

Before claiming complete two-provider acceptance or asking the Coordinator to consume a production release, Modular Plugins must resolve or disposition the `CapabilityProviderResult` process encoding, missing-dependency activation behavior, telemetry result/frame bound, and desired active-version restoration after restart. Knowledge 1.0.1's manifest/digest is compatible with the candidate registry, but its real invocation does not pass until the IPC result contract is fixed. No managed-runtime installation was performed.
