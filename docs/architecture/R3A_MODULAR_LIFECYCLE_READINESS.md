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

## Limits and coordinator integration

- Child workers currently run under the CME OS identity. Process separation and private sockets isolate faults, but this is not a separate-user or syscall sandbox.
- Module config values are immutable for a running worker version; a changed configuration should be released as a new provider version.
- The prototype does not migrate module-owned durable state between versions. Modules declaring a migration contract still need a generic migration runner before stateful upgrades are accepted.
- Resource-reference resolution continues through the existing shared registry contract. The coordinator should integrate these lifecycle controls and manifests into the managed CME after its normal branch integration review.
