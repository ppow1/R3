<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULAR_FOUNDATION_IMPLEMENTATION.md
Component: R3A-MODULAR-FOUNDATION
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Record the minimum implementation path for the approved generic registry and module lifecycle contracts.
Execution Model: R3A core, CME-supervised capability modules, and external versioned manifests.
Observability: Durable module lifecycle state/events, capability discovery, invocation audit, and correlated diagnostics.
Dependencies: R3A Architecture Charter; Master Roadmap Baseline 1.0; AP0-M1; MOD-001–MOD-010; existing R3A capability operation contract.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Record the implementation boundary and preservation constraints before code changes.
Supersedes: None.
Contracts: r3a.capability-operation.v1; AP0-M1 module protocol; MOD-001–MOD-010.
Tests: Not run; architecture record.
History/Predecessor: New file.
-->
# R3A Modular Foundation Implementation

**Status:** Authorized implementation record. This document does not change the approved architecture requirements.

## Source findings

The existing `CapabilityRegistry` is the authoritative operation registry. It validates and discovers operation manifests, resolves versioned operations, and deliberately does not grant authority. CME performs authorization and durable invocation auditing. Preserve these responsibilities and interfaces.

AP0 already defines `r3a.module.v1`, the private Unix socket JSON-lines protocol, the durable `r3a.module_registry`, and the `module.lifecycle` state machine. CME already implements the lifecycle vocabulary for its configured resident module. The gaps are that module management is wired to the resident's single process/socket, capability providers are imported into CME, and capability registration is a static startup roster. The persisted resource/capability rows are not a replacement for operation manifest discovery.

## Minimum correction

1. Use `CapabilityRegistry` as the single manifest and operation discovery surface. Keep manifest/configuration references external, validate operation and module contract compatibility before activation, and preserve immutable artifact digests.
2. Bind capability providers through the existing AP0-M1 process protocol under a reusable CME-owned module supervisor. A provider module receives only a versioned invocation envelope; it does not receive a database connection or authorization authority.
3. Persist install, activation, stop, failure, and replacement state in `r3a.module_registry` / the existing lifecycle state machine. Record correlated lifecycle events, artifact/version lineage, readiness observations, and diagnostics without logging secret values.
4. Separate module discovery from `AuthorizationProvider` and durable capability grants. CME authorizes every invocation after discovery and before provider execution.
5. Make activation/deactivation/replacement operations target a registered `(module_id, module_version)` and maintain process/socket ownership per module. Do not special-case capability IDs or provider names in CME.
6. Preserve the resident Grace module path, Engineering workflow/verifier, K1/K2 retrieval and evidence, notification intake/recipient delivery, and observer scheduler while migrating bindings incrementally.

The first implementation milestone is a functioning generic binding/lifecycle contract and focused regression evidence. A control-plane demonstration is not live managed-runtime acceptance. Any runtime activation is a separate operation requiring the existing managed-service owner and window.

## Acceptance mapping

| Requirement | Evidence needed | Current implementation boundary |
|---|---|---|
| MOD-001 | Queryable identity, immutable version, contract and dependencies | Operation manifest has operation/provider identity and versions; generic module metadata must be bound to it. |
| MOD-002 | Install/discover a compatible manifest without changing the core roster | Operation discovery exists from external config; general dynamic module binding remains incomplete. |
| MOD-003 | Lifecycle state survives restart and appears in diagnostics | Resident module lifecycle is durable; provider lifecycle must use the same store/state machine. |
| MOD-004 | Add/remove/replace provider while Ring 0 remains healthy | Existing module control operations are process-local to the configured resident; multi-module supervision remains incomplete. |
| MOD-005 | Incompatible contract rejected with visible reason | Operation contract is validated; generic module handshake/version check must precede provider activation. |
| MOD-006 | Discovery without grant is denied; granted invocation audited | Existing CME authorization and capability invocation records are authoritative; preserve unchanged. |
| MOD-007 | External schema-validated config and secret references | Config and plugin config validation exist; lifecycle reload/revision application remains incomplete. |
| MOD-008 | Durable namespaced state and upgrade/migration lineage | Generic lifecycle must retain old version/artifact and report migration/recovery disposition. |
| MOD-009 | Stop/replace preserves work and checkpoints or reports blockage | Resident stop exists; provider drain/checkpoint semantics require generic protocol calls. |
| MOD-010 | Health/version reflect observed process handshake | Resident health is probed; provider module health must be observed through the generic supervisor. |

This record authorizes ordinary in-scope engineering toward these requirements. It does not authorize production changes or managed-runtime activation.

## Implementation slice on `engineering/r3a-modularity-lifecycle-20261107`

The current slice extends the existing operation registry to retain multiple immutable provider versions for one operation and select one effective implementation only after its readiness check. CME binds each selected provider through a separate AP0-M1 process/socket, checks the declared provider protocol and pinned artifact digests, and records lifecycle state in `module_registry` and the lifecycle state machine. CME continues to authorize and persist every invocation before the provider process is called. Provider child environments are limited to runtime basics and names explicitly referenced by that provider's external config. Stop closes admission, records `STOPPING`, drains current invocation requests, checkpoints the provider, and then records `STOPPED`.

New provider modules use lifecycle state machine v2; v1 remains immutable. V2 adds the `REPLACING -> STOPPING` path so the old provider stays active until the new version passes its handshake, then drains and stops with a durable replacement event. Focused process tests use the existing Engineering isolated-workspace provider to demonstrate an authorized CME invocation through the worker process with idempotent recovery, plus install, discover, activate, version switch, replay, and stop in a temporary workspace.

The local CME control operations are `capability.module.install`, `capability.module.activate`, `capability.module.deactivate`, `capability.module.replace`, and `capability.module.status`. Requests identify an operation and, where needed, its provider version. They operate only on manifests already loaded from `capability_operations`; activation remains separate from `capability.grant` and every invocation still requires the existing grant provider. Manifest/config validation and operation discovery happen at CME configuration load.

This is not full MOD acceptance. The current manifest catalog is loaded from configured `capability_operations` at CME startup; an unlisted manifest cannot yet be installed into a running CME through the control API. Child processes are separate and socket-restricted but still run under the CME service UID, so OS-level unprivileged isolation is not established. Lifecycle persistence is covered with a Store-compatible test fixture, not a live PostgreSQL/managed-service run. The generic activity-intake, activity-handler, and evidence-obligation contracts remain future slices; notification, Engineering workflow, and knowledge behavior have not been moved in this branch. The branch must be reconciled with the AP1 integration candidate before cross-capability claims or runtime activation.
