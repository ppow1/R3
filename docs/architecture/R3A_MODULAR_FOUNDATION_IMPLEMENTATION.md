<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULAR_FOUNDATION_IMPLEMENTATION.md
Component: R3A-MODULAR-FOUNDATION
File Revision: 1.0.1
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Record the minimum implementation path for the approved generic registry and module lifecycle contracts.
Execution Model: R3A core, CME-supervised capability modules, and external versioned manifests.
Observability: Durable module lifecycle state/events, capability discovery, invocation audit, and correlated diagnostics.
Dependencies: R3A Architecture Charter; Master Roadmap Baseline 1.0; AP0-M1; MOD-001–MOD-010; existing R3A capability operation contract.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Record the implementation boundary and preservation constraints before code changes.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Supersede stale startup-only provider/dependency statements with Auditor verification and AD-024 modular role requirements.
Supersedes: None.
Contracts: r3a.capability-operation.v1; AP0-M1 module protocol; MOD-001–MOD-010.
Tests: Not run; architecture record.
History/Predecessor: New file; immediate predecessor commit 739aa652f74d4a55d681ebca0827df63bd4f25d9 (file blob 32f72b5d0ff6e63e0ced3c3b3046a0aa921e1382).
-->
# R3A Modular Foundation Implementation

**Status:** Authorized implementation record with a superseding verification addendum below. Historical branch findings remain as of 2026-11-07; current provider findings are governed by AD-024 and the auditor verification.

**Current status correction:** Read the “AD-024 verification update” at the end before relying on earlier statements that providers are startup-only or dependency ranges are unsolved. The source/fixture evidence in the 2026-11-09 Auditor verification supersedes those implementation-status claims.

## Source findings

The existing `CapabilityRegistry` is the authoritative operation registry. It validates and discovers operation manifests, resolves versioned operations, and deliberately does not grant authority. CME performs authorization and durable invocation auditing. Preserve these responsibilities and interfaces.

AP0 defines `r3a.module.v1`, the private Unix socket JSON-lines protocol, durable `r3a.module_registry`, and `module.lifecycle`. Current provider modules use external digest-pinned manifests and a separate provider process managed through generic CME registry/lifecycle code. Compatible provider configuration can be reloaded by a running CME. The remaining extension gaps are generic resident-to-module binding and durable activity-handler routing; see the AD-024 verification update below. Persisted resource/capability rows remain distinct from operation manifest discovery.

## Minimum correction

1. Use `CapabilityRegistry` as the single manifest and operation discovery surface. Keep manifest/configuration references external, validate operation and module contract compatibility before activation, and preserve immutable artifact digests.
2. Bind capability providers through the existing AP0-M1 process protocol under the reusable CME-owned provider supervisor. A provider receives a versioned invocation envelope and no authorization authority. The child shares CME’s service UID; process separation does not by itself prevent access to resources readable by CME, and explicitly allowlisted environment references may expose configured values.
3. Persist install, activation, stop, failure, and replacement state in `r3a.module_registry` / the existing lifecycle state machine. Record correlated lifecycle events, artifact/version lineage, readiness observations, and diagnostics without logging secret values.
4. Separate module discovery from `AuthorizationProvider` and durable capability grants. CME authorizes every invocation after discovery and before provider execution.
5. Make activation/deactivation/replacement operations target a registered `(module_id, module_version)` and maintain process/socket ownership per module. Do not special-case capability IDs or provider names in CME.
6. Preserve the resident Grace module path, Engineering workflow/verifier, K1/K2 retrieval and evidence, notification intake/recipient delivery, and observer scheduler while migrating bindings incrementally.

The first implementation milestone is a functioning generic binding/lifecycle contract and focused regression evidence. A control-plane demonstration is not live managed-runtime acceptance. Any runtime activation is a separate operation requiring the existing managed-service owner and window.

## Acceptance mapping

| Requirement | Evidence needed | Current implementation boundary as verified at AD-024 |
|---|---|---|
| MOD-001 | Implemented for capability providers; extension roles remain | Provider manifests declare identity/version/digest and dependencies; the existing evaluator checks ranges, missing/incompatible dependencies and cycles. Generic resident bindings and handler role declarations remain to be implemented. |
| MOD-002 | Implemented for capability providers; role extensions remain | External provider config can be reloaded in a running CME and discovered without core edits. Generic resident-executor binding and durable activity-handler dispatch remain incomplete. |
| MOD-003 | Lifecycle state survives restart and appears in diagnostics | Provider lifecycle records use the existing durable module registry/state machine; focused tests used a Store-compatible fixture, not PostgreSQL. |
| MOD-004 | Provider source/fixture support; live proof pending | Provider config reload and lifecycle operations work without changing CME PID in the disposable harness; live Ring 0/CME evidence remains unverified. Resident/handler extension lifecycle is outstanding. |
| MOD-005 | Incompatible contract rejected with visible reason | Provider/module protocol and declared version ranges are validated before activation; dependency range grammar, missing/incompatible dependency and cycle checks are implemented. Live diagnostic durability remains unverified. |
| MOD-006 | Discovery without grant is denied; granted invocation audited | Existing CME authorization and capability invocation records are authoritative; preserve unchanged. |
| MOD-007 | Provider source/fixture support | External config/plugin schemas are validated; compatible provider changes reload in a running CME at a safe boundary and create a new config revision. |
| MOD-008 | Durable namespaced state and upgrade/migration lineage | Provider artifact/version lineage and replacement are fixture-tested; tested provider profile is stateless. Generic stateful module migration/recovery remains unverified. |
| MOD-009 | Stop/replace preserves work and checkpoints or reports blockage | Provider stop/drain/checkpoint and replacement are fixture-tested. Generic handler activity checkpoints/recovery and live durable-store interruption remain outstanding. |
| MOD-010 | Health/version reflect observed process handshake | Provider activation performs worker handshake/readiness/health observation; periodic health freshness and live managed-service evidence remain unverified. |

## MOD status at the existing-extensibility verification

| MOD | Status | Evidence and remaining gap |
|---|---|---|
| MOD-001 | Implemented for capability providers; extension roles remain | Provider manifests declare identity/version/digest and dependencies; the existing evaluator checks ranges, missing/incompatible dependencies and cycles. Generic resident bindings and handler role declarations remain to be implemented. |
| MOD-002 | Implemented for capability providers; role extensions remain | External provider config can be reloaded in a running CME and discovered without core edits. Generic resident-executor binding and durable activity-handler dispatch remain incomplete. |
| MOD-003 | Implemented; fixture-tested | Provider lifecycle rows and state events use the existing durable module registry/state machine path; tests use a Store-compatible fixture, not PostgreSQL. |
| MOD-004 | Provider source/fixture support; live proof pending | Provider config reload and lifecycle operations work without changing CME PID in the disposable harness; live Ring 0/CME evidence remains unverified. Resident/handler extension lifecycle is outstanding. |
| MOD-005 | Partial | Module manifest protocol range and provider/artifact/config refs are validated before registration; activation also checks the declared host range and worker handshake. Invalid range schema is covered, but an incompatible lifecycle-state diagnostic transition is not yet exercised against PostgreSQL or the live service. |
| MOD-006 | Verified in focused tests | Discovery does not grant access; the CME invocation path authorizes and durably records a request before starting/executing the provider. |
| MOD-007 | Provider source/fixture support | External config/plugin schemas are validated; compatible provider changes reload in a running CME at a safe boundary and create a new config revision. |
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

This is not full MOD acceptance. The 2026-11-07 slice documented then-current startup configuration; subsequent source and fixture evidence demonstrates compatible provider config reload and lifecycle operation without CME restart. The provider artifact still must be staged and declared before reload; there is no remote package installer. Provider children share CME’s service UID, so there is no OS-level privilege separation. Lifecycle persistence evidence uses a Store-compatible fixture, not live PostgreSQL. The source-to-CME `r3a.activity-intake.v1` envelope is published, but general activity-handler routing remains unimplemented. Generic resident-to-module binding is also missing. Existing Engineering, Knowledge and Notification domain workflows remain in shared CME code where assigned; migration must be incremental and tied to explicit module ownership, with no wholesale rewrite. See AD-024 update below and the final compliance specification.

## AD-024 verification update — 2026-11-10

The preceding status tables and narrative describe the implementation candidate available on 2026-11-07. The following evidence-based corrections supersede statements above about provider registration and dependency evaluation:

- Capability-provider modules are externally configured, digest-pinned, registry-discoverable, and lifecycle-managed through existing generic code. A running CME `config.reload` accepts changed provider configuration at a safe activity boundary; a disposable harness added a staged provider, then installed, activated and deactivated it without changing the CME PID. The artifact must already be staged and declared; this is not a remote installer.
- Existing source implements dependency range evaluation, missing/incompatible dependency checks, cycle detection and compatible activation. Statements above that ranges are only recorded or providers are startup-only are stale and are superseded by source/tests at Auditor evidence commit `87d868d`.
- Provider process children share the CME service UID. Filtered environment and private sockets do not establish OS isolation; explicitly allowlisted environment references can expose configured values. No sandbox is claimed.
- The tested provider extension is stateless. Generic stateful migration/recovery remains unverified and must not be inferred from manifest metadata.
- Two fundamental extensions remain required by AD-024 and are not implemented: generic resident-to-module binding (top-level entrypoint is restricted to Observer/Grace and secondary profiles launch Grace) and generic durable activity-handler routing (current Store intake accepts only `grace.objective`). Use existing registry, lifecycle, resident profile, activity intake, scheduler, persistence and authorization mechanisms; see [Modularity Compliance Specification v1](R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md) and [interface gap analysis](../audits/R3A_INTERFACE_CONTRACT_GAP_ANALYSIS_20261109.md).
- Focused provider and contract/Website fixture suites passed as recorded in [the Auditor verification report](../audits/R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md). No live PostgreSQL, Ring 0, managed CME, or authenticated Website acceptance was performed. The correction does not declare runtime operations accepted.
