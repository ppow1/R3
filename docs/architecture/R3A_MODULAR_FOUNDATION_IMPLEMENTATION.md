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

## Current MOD status on the integration candidate

| MOD | Status | Evidence and remaining gap |
|---|---|---|
| MOD-001 | Partial | Engineering now declares `r3a.module-manifest.v1` with owner, binding compatibility, dependencies, external config/schema references, capability/resource refs, state namespace, migration/recovery policy, and artifact identity. Other legacy provider manifests still receive synthesized compatibility defaults; dependency ranges are recorded but not solved. |
| MOD-002 | Partial | Configured manifests discover without editing the CME roster. Loading an unlisted manifest into an already-running CME is not supported. |
| MOD-003 | Implemented; fixture-tested | Provider lifecycle rows and state events use the existing durable module registry/state machine path; tests use a Store-compatible fixture, not PostgreSQL. |
| MOD-004 | Implemented in control surface; live proof pending | A registered module can install, activate, deactivate, or replace without restarting Ring 0. Managed Ring 0 process identity/health has not been observed during those operations. |
| MOD-005 | Partial | Module manifest protocol range and provider/artifact/config refs are validated before registration; activation also checks the declared host range and worker handshake. Invalid range schema is covered, but an incompatible lifecycle-state diagnostic transition is not yet exercised against PostgreSQL or the live service. |
| MOD-006 | Verified in focused tests | Discovery does not grant access; the CME invocation path authorizes and durably records a request before starting/executing the provider. |
| MOD-007 | Partial | Provider config remains external and is validated at bootstrap; DB credential environment variables are withheld from child modules. Generic secret-reference schema validation and live config revision/reload evidence remain incomplete. |
| MOD-008 | Incomplete | Versions and artifact lineage are durable, but generic module-owned state namespaces and declared upgrade/migration/recovery contracts are not implemented. Current provider binding assumes stateless modules. |
| MOD-009 | Partial | Stop closes admission, drains in-flight invocation requests, checkpoints, then stops. A process interruption during active side effects and durable recovery were not exercised in the new module lifecycle tests. |
| MOD-010 | Partial | Activation uses a real worker handshake/readiness/health response and diagnostics expose persisted lifecycle. There is no periodic per-provider health monitor or live managed-service freshness evidence. |

## Capability ownership checkpoint

| Capability | Module-owned implementation | Shared/core boundary | Modularity status |
|---|---|---|---|
| Engineering workspace operation | `r3a_plugins/engineering_workspace/{manifest.json,config.example.json,provider.py}` now owns the digest-pinned operation and versioned module contract; `r3a_runtime/providers/isolated_workspace.py` is a compatibility import only. | `r3a_runtime/engineering.py`, `engineering_verifier.py`, work-order state machine, and CME/Store workflow orchestration remain shared/core. CME validates the historical `engineering.workspace.apply_patch` grant and work order before invoking the provider. | Provider installs/replaces/disables through generic lifecycle without a capability loader edit; workflow-handler contract and full migration remain incomplete. Work-order, evidence, verifier semantics are retained. |
| Knowledge | `r3a_plugins/institutional_knowledge/**` owns retrieval provider/config. | `r3a_runtime/knowledge.py`, CME evidence/continuation branches, grant and invocation audit remain shared/core. | K1 is integrated on the AP1 base; K2 commit `84bf406` is a separate #47 branch, not in this PR. Generic evidence obligations are not implemented. |
| Notifications | #48 branch has a source reader provider package; it is not merged into this PR. | Current N1/N2 intake, activity transitions, and durable event hooks remain in `r3a_runtime/{notifications.py,cme.py,db.py,config.py,cli.py}`. CME's source grant remains authoritative. | `r3a.activity-intake.v1` contract/schema is published, but CME binding and migration out of notification-specific core branches are incomplete. |
| Telemetry | `r3a_plugins/octominer_telemetry/**` owns provider and manifest/config. | Generic registry/lifecycle/authorization remain core. This lifecycle branch withholds DB credential environment from child modules. | Manifest can be discovered/installed with generic controls, but live telemetry child invocation and CME-owned DB observation bridge are unverified; coexistence is registry/test evidence only. |
| Authentication | #49 `steward_access.py`/session implementation is on its workstream branch; no selected identity-provider module is in this PR. | Session store, route wiring and CME authorization are shared service responsibilities. | #49/#51 share cookie/principal direction, but a configured versioned identity-provider binding and live authenticated CME trace remain incomplete. |
| Website | #51 `web/steward.*` presentation and client adapter are on its workstream branch. | `r3_app.py` gateway routes, #49 session/principal, and CME objective/activity APIs are shared service boundaries. | Presentation can be removed independently; server integration and live authenticated objective/result are not yet demonstrated. |

This table distinguishes provider packaging from domain orchestration. Passing a provider test does not prove the managed service has loaded the manifest or that the whole capability can be removed independently.

This record authorizes ordinary in-scope engineering toward these requirements. It does not authorize production changes or managed-runtime activation.

## Implementation slice on `engineering/r3a-modularity-lifecycle-20261107`

The current slice extends the existing operation registry to retain multiple immutable provider versions for one operation and select one effective implementation only after its readiness check. CME binds each selected provider through a separate AP0-M1 process/socket, checks the declared provider protocol and pinned artifact digests, and records lifecycle state in `module_registry` and the lifecycle state machine. CME continues to authorize and persist every invocation before the provider process is called. Provider child environments are limited to runtime basics and names explicitly referenced by that provider's external config; database credentials are excluded so institutional database observations must cross CME-owned interfaces. Stop closes admission, records `STOPPING`, drains current invocation requests, checkpoints the provider, and then records `STOPPED`.

New provider modules use lifecycle state machine v2; v1 remains immutable. V2 adds the `REPLACING -> STOPPING` path so the old provider stays active until the new version passes its handshake, then drains and stops with a durable replacement event. Focused process tests exercise CME control install/activate/replace/status/deactivate, discover and install telemetry from its external manifest without granting it, then use the existing Engineering isolated-workspace capability for an authorized invocation through the worker with idempotent recovery. They replace Engineering with a distinct digest-pinned implementation, verify the replacement's changed file output and replay, confirm telemetry remains discoverable, and stop both versions in a temporary workspace. The lifecycle store in this test remains a Store-compatible fixture, not PostgreSQL.

The local CME control operations are `capability.module.install`, `capability.module.activate`, `capability.module.deactivate`, `capability.module.replace`, and `capability.module.status`. Requests identify an operation and, where needed, its provider version. They operate only on manifests already loaded from `capability_operations`; activation remains separate from `capability.grant` and every invocation still requires the existing grant provider. Manifest/config validation and operation discovery happen at CME configuration load. The existing Engineering workspace operation now has a module-owned external manifest in `r3a_plugins/engineering_workspace/manifest.json`, including validated `r3a.module-manifest.v1` owner, compatibility, dependency, config/schema, capability/resource, state namespace, migration/recovery, and artifact fields. The generic runtime consumes these declarations without a capability-specific branch. Its control-path lifecycle and distinct implementation replacement are covered by the process fixture.

This is not full MOD acceptance. The current manifest catalog is loaded from configured `capability_operations` at CME startup; an unlisted manifest cannot yet be installed into a running CME through the control API. Engineering declares `r3a.module-manifest.v1`; legacy provider manifests still use the generic synthesized compatibility profile until their owners add the versioned declaration. Child processes are separate and socket-restricted but still run under the CME service UID, so OS-level unprivileged isolation is not established. Lifecycle persistence is covered with a Store-compatible test fixture, not a live PostgreSQL/managed-service run. The generic activity-intake contract and schema are now published in `R3A_ACTIVITY_INTAKE_CONTRACT_V1.md`; they define a module-configured lifecycle projection and preserve the current N1 equivalence requirements, but CME binding and notification behavior migration are not implemented. The generic activity-handler and evidence-obligation contracts also remain future slices. Notification, Engineering workflow, and knowledge behavior have not been moved in this branch. The branch must be reconciled with the AP1 integration candidate before cross-capability claims or runtime activation.
