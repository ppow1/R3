# R3A unified capability contract v1

The canonical contract is shared by read, isolated-write, and external-write operations. Effect is descriptor metadata that the invocation dispatcher must enforce with operation, caller, target, grant, and work-order context. Registry discovery makes no authorization decision.

## Published schemas and provider API

- `r3a_runtime/schemas/capability-operation.v1.schema.json` defines an operation descriptor: identity/revision, provider and digest, typed input/output schemas, effect class, caller constraints, target-scope schema, required grants, evidence and verification obligations, idempotency/reconciliation, timeout/retry behavior, and desired lifecycle state.
- `r3a_runtime/schemas/capability-invocation.v1.schema.json` defines strict request and result shapes. Requests cannot carry grants or authorization decisions. Results contain the CME provider/allowed decision, decision and audit references, policy/config revisions, effect disposition, typed output/error, evidence, retryability, and reconciliation reference.
- `r3a_runtime/capability_contracts.py` validates descriptors and the supported self-contained JSON Schema subset; validates invocation inputs/targets and provider outputs; defines `CapabilityProvider.invoke(arguments, context=...)`; and implements the one dynamic `CapabilityRegistry` API (`register`, `discover`, `resolve`). Discovery reports registration/health observation only.
- API fixtures are in `tests/fixtures/capabilities/`. `tests/test_r3a_capability_contracts.py` is the provider/registry conformance suite.

The schema documents use JSON Schema Draft 2020-12. The in-process validator supports primitive/object/array types (including type unions), required/properties, additional-properties policies, items, enum/const, lengths/counts, numeric bounds, patterns, uniqueness, and date-time. External `$ref`, composition keywords, and remote schema loading are intentionally rejected for provider-owned IO schemas; operation IO schemas are self-contained.

## Registry and invocation ownership

`Settings.capability_registry` is built once from `capability_operations` after schema, configuration, entrypoint, and artifact-digest validation. The prior root key `capability_plugins` remains an input alias during migration; specifying both is rejected. The registry rejects duplicate operation IDs and unsupported contract versions. `CME._resident_tools()` now derives discovery from that registry; the runtime database capability row is a durable authorization/audit projection of the same operation, not another provider registry. The existing CME authorization and durable activity path remains the only dispatcher.

The provider interface is synchronous and declares a timeout/retry disposition in its descriptor. Providers receive typed arguments and activity/attempt/correlation/operation context. They return an output validated against the descriptor schema. CME must enforce invocation deadlines; providers cannot authorize themselves, write grant decisions, or decide AP2 acceptance.

The current Grace action request remains available as a compatibility projection while AP2 adopts the canonical invocation envelope in its isolated worktree. That projection maps the canonical operation ID, typed input schema, and provider output into the existing resident tool surface and continues through CME's existing authorization/dispatch path. The compatibility projection only offers `read` operations; an effectful operation cannot execute through this pre-canonical request adapter. It does not create a second registry, provider dispatcher, or grant mechanism. Canonical request/result validators and fixtures are published for AP2 integration.

## Telemetry operation

The OctoMiner manifest now declares canonical operation `infrastructure.octominer.telemetry.read`, effect `read`, one required grant matching that operation ID, Grace caller restriction, explicit source/host target schema, evidence obligations, replay-safe read semantics, and the canonical provider factory. The former top-level `read_only`/resident-tool fields remain only as temporary compatibility input/projection. In canonical manifests they are optional; when present their value must agree with the operation's effect. Legacy manifests are adapted only if they explicitly declare `read_only: true`; a missing/false legacy value never becomes write authority.

Provider helpers and telemetry collection behavior are detailed in `R3A_OCTOMINER_TELEMETRY_PLUGIN.md`. No OctoMiner legacy application service is used.

## Validation boundaries

The registry validates identity, schemas, versions, provider entrypoint binding, and artifact pins. CME/AP0 owns invocation-time authorization decisions and durable audits. AP2 owns work-order context, scoped executor operations, independent verification, reconciliation policy for Engineering effects, and terminal completion. Registering or discovering an operation creates no grant. The current grant provider still supports only existing grant semantics; effectful operations remain unusable until the AP2/CME dispatcher and authorization provider implement the approved scoped policy.
