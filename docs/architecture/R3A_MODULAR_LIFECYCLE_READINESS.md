<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULAR_LIFECYCLE_READINESS.md
Component: R3A-MODULAR-LIFECYCLE-READINESS
File Revision: 1.1.0
Created: 2026-11-08 (original date verified from Git; exact time unavailable)
Created By: Codex GPT-6
Purpose: Record isolated module lifecycle evidence, recovery limits, and integration compatibility.
Execution Model: N/A; acceptance and integration record.
Observability: Source commits, isolated runtime evidence and provider contract tests.
Dependencies: Unified capability registry, CME, module.lifecycle v2.
Authority: Issue #46; no managed service modification.
Changed: 2026-11-08T18:43:38Z | R3A-MODULAR-LIFECYCLE-001 | Codex GPT-6 | Add typed-result and branch compatibility findings plus resource provider boundary.
Supersedes: None; extends the existing readiness record.
Contracts: r3a.capability-operation.v1; r3a.capability-invocation.v1; r3a.capability-provider.v1.
Tests: Referenced isolated lifecycle and provider contract tests.
History/Predecessor: Git blob d28db710d71df0dfb32999508cd0c91ce8a18ee2 at d78f0188d39cb02b9f184b8cfc1d9b43c0960b59.
-->
# R3A Modular Lifecycle Readiness

Status: isolated prototype integration exercised on 2026-11-08.

## Reused architecture

- CME's single capability registry and canonical operation/invocation contracts remain authoritative.
- `capability_operations` loads versioned manifests and configuration. `config.reload` validates a new registry and installs newly declared provider versions without CME source edits.
- CME remains the only authorization and canonical invocation dispatcher. Discovery is informational and grants are checked for each invocation.
- `r3a.module_registry`, the `module.lifecycle` v2 state machine, and the existing event ledger hold durable module identity, version, health, and transitions.
- Provider workers use the established local module protocol, pinned artifact digests, private Unix sockets, and separate child processes.

## Lifecycle controls

The existing CME control interface exposes `capability.module.install`, `capability.module.activate`, `capability.module.deactivate`, `capability.module.status`, and `capability.module.replace`.
An operation must already be registered from external configuration before a control can resolve it. A new version can be added by publishing its versioned manifest/configuration and requesting `config.reload`.
Reload rejects removal or disablement of any live provider until it has been explicitly deactivated.

Activation checks the module manifest protocol range, provider artifact digest, worker handshake, prepare/activate result, and health response. Failed activation is confined to that module. Replacement activates the candidate before switching the registry and stopping the prior version; a failed candidate returns the prior module to `ACTIVE`.
Deactivation closes admission, waits for in-flight provider calls, requests a checkpoint, and then stops the worker. Drain timeout leaves the module visibly in `STOPPING` and blocks new calls so no active work is discarded.

On CME restart, an `ACTIVE` module is reconciled against its recorded worker PID. The runtime terminates only a same-user process whose `/proc` command line matches the registered worker, module ID, and version, then verifies the artifact and performs the normal activation handshake. Explicitly stopped modules remain stopped.
Provider health is refreshed by CME's existing heartbeat loop; a provider diagnostic failure does not stop CME.

Module manifest v1 metadata is validated against the canonical provider identity, artifact digest, entrypoint, capability list, and configuration schema reference. Configured dependencies are version-range checked, dependency cycles are rejected, and activation starts configured dependencies first. Capability references must already be declared by the resident module. Resource references remain identifiers in the shared resource contract; this work adds no competing resource registry.

## Isolated transition evidence

The actual CME process ran against a private PostgreSQL cluster and worktree code at `/tmp/r3a-mod-lifecycle-20261108`; the Coordinator's managed CME was not touched.

- Module A: `r3a.isolated-workspace` v1.0.0 was active. An external manifest/config update added v1.0.2 and v1.0.3 via `config.reload`; CME's PID did not change.
- Module B: `r3a.octominer-telemetry` v2.0.0 remained active through Module A's failed and successful replacement.
- Failed replacement to v1.0.2 failed during provider initialization because its isolated workspace path did not exist. CME returned the prior v1.0.0 module to `ACTIVE` and kept its worker alive.
- Replacement to v1.0.3 succeeded; v1.0.0 reached `STOPPED`, v1.0.3 reached `ACTIVE`, and Module B stayed `ACTIVE`.
- After a graceful runtime stop, Module A v1.0.3 and Module B were activated, then the CME PID was terminated without cleanup. A fresh CME restored both providers through the durable module records and normal worker handshakes with new PIDs. CME reported `RUNNING` and `healthy`.
- A canonical read invocation through CME for telemetry returned `SUCCEEDED` with authorization evidence and contract-validated output. Each OctoMiner, model server, ComfyUI, request-metrics, and history source explicitly returned `unavailable`; telemetry credentials/endpoints were not present, so no measurements are claimed.

The isolated runtime was stopped after evidence capture. No production or shared managed runtime was changed.

## Lifecycle hardening follow-up — 2026-11-08

- Missing and disabled required dependencies are checked before provider readiness; unresolved dependencies fail closed. Restart reconciliation restores durably active or interrupted configured versions, recursively bringing their version-matched dependencies up before dependents. Explicitly stopped versions remain stopped.
- Provider IPC retains the managed `r3a.capability-provider.v1` protocol 1.0 envelope and 65,536-byte frame ceiling. A response too large for the frame now becomes a bounded `ok: false`, `error_code: response_too_large` message. This keeps oversized telemetry history from escaping as an unhandled stream-reader exception.
- The installable `r3a-ap0-runtime` wheel now includes provider manifests and plug-in JSON assets. It was installed into a separate venv and used for a second live CME/PostgreSQL lifecycle run. Module A v1.0.0 depended on telemetry B v2.0.0; version 1.0.2 replaced it; failed 1.0.3 left 1.0.2 active; 1.0.4 then replaced 1.0.2. Killing A's process produced durable `FAILED`, then activation restarted only A while B's PID stayed unchanged. A hard CME kill restored A 1.0.4 and B 2.0.0 with new PIDs, both healthy. Detailed process IDs and PostgreSQL event records are in the [lifecycle hardening evidence](../evidence/R3A_MODULE_LIFECYCLE_HARDENING_20261108.json).
- Stronger filesystem isolation was investigated with Bubblewrap. A standalone probe demonstrated a read-only root with a selected writable workspace. The provider manager does not launch workers inside that sandbox yet; a versioned manifest/config policy for writable/readable paths and network needs must be agreed with the Coordinator first.
- The current isolated acceptance runtime and its private database were stopped after evidence capture. No managed CME or shared runtime was activated.

## Limits and coordinator integration

- Child workers currently run under the CME OS identity. Process separation and private sockets isolate faults, but this is not a separate-user or syscall sandbox.
- Module config values are immutable for a running worker version; a changed configuration should be released as a new provider version.
- The prototype does not migrate module-owned durable state between versions. Modules declaring a migration contract still need a generic migration runner before stateful upgrades are accepted.
- Resource-reference resolution continues through the existing shared registry contract. The coordinator should integrate these lifecycle controls and manifests into the managed CME after its normal branch integration review.

## Contract compatibility and resource modules — 2026-11-08

The lifecycle provider boundary returns either plain JSON output or the existing typed `r3a.capability-provider-result.v1@1.0.0` envelope with separate `output` and `evidence`. The worker validates JSON serializability; the registered operation validates the typed output/evidence schemas after provider resolution. Replacement is versioned, dependency ranges are resolved before activation, dependency cycles fail closed, and only the affected module is stopped/restarted. The isolated tests cover missing-dependency denial, typed result transport, rollback to the previous active version, provider child death and activation recovery, plus CME desired-state restoration with a matching dependency version.

The 65,536-byte provider frame remains a provider-protocol limit. A larger resident-execution envelope in the Coordinator branch is a separate outer contract and must not make oversized provider replies valid. Preserve `ProtocolFrameTooLarge` / `error_code=response_too_large` at the inner boundary and translate it to a bounded typed invocation failure before the resident sees it. The Live Modular acceptance at `f7ec1161846be67365bc9f60cecd94d3d79d794f` and the Coordinator head `c02c882c4b8459a58df8ead4b8e41fd8f1065395` are separate worktrees; their current contract diffs have not been merged or tested from this branch. In particular, durable module-scoped evidence for manifest/dependency rejection before provider registration remains a cross-owner integration item.

The first independently configured resource-monitor package adds `infrastructure.resources.disk-health.read` and `infrastructure.software-environments.discover`, each under the existing CME capability registry and `infrastructure.resource-inventory.read` grant. They do not register physical devices as callable capabilities. Existing OctoMiner telemetry remains the provider for GPU/VRAM/load/fan, GPU process mapping, inference-server and ComfyUI status, mounted filesystem capacity, request metrics and bounded history. The two inventories join by configured host/resource ID without assuming deployment endpoints.

Local read-only evidence is deliberately limited: `lsblk` observed one SATA disk on the development host with 256,060,514,304 bytes; `smartctl` was absent, so health was unavailable. No SAS or remote OctoMiner live measurement is claimed. Fixture tests cover SCSI/SAS smartctl JSON including a nonzero status bit with valid health data. Resource provider manifests are external inputs; this change does not activate them in CME or restart a managed service.
