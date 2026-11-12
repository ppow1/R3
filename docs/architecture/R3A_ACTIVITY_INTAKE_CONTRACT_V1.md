<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ACTIVITY_INTAKE_CONTRACT_V1.md
Component: R3A-ACTIVITY-INTAKE
File Revision: 1.1.0
Created: 2026-11-08
Created By: Codex GPT-6
Purpose: Specify the shared, versioned CME boundary for turning an authorized capability result into durable resident work.
Execution Model: Capability provider returns evidence; CME validates authority, deduplicates, persists, routes, and observes lifecycle.
Observability: Durable activity and event lineage using source identity, correlation, provenance, and contract revision.
Dependencies: R3A Architecture Charter; R3A Module Lifecycle and Contract Specification; r3a.capability-operation.v1; r3a.notification-intake.v1.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-08, as extended by AD-024 and R3A Modularity Compliance Specification v1.
Changed: 2026-11-08 | R3A-MODULAR-FOUNDATION-003 | Publish reusable activity-intake boundary for module integration.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Preserve intake v1 envelope and add required generic module-owned durable activity-handler extension under AD-024.
Supersedes: None.
Contracts: r3a.activity-intake.v1; r3a.capability-operation.v1.
Tests: tests/test_r3a_activity_intake_contract.py.
History/Predecessor: Generic boundary proposed in R3A modularity audit; immediate predecessor commit 7825e91866ee3bdc5ad53eef41fbebb3c96ee7ce (file blob cd4235eccfbc905bf0442f596fd5ffb00c010a6b).
-->
# R3A Activity Intake Contract v1

**Architecture status:** The v1 source-intake envelope remains the compatible input contract. Steward decision AD-024 requires a generic activity-handler consumer contract in addition to this provider-to-CME intake. The current implementation is Grace-only at persistence/dispatch and does not yet satisfy the generic handler requirement. The extension below is normative for future module implementations; it does not claim implementation completion.

## Purpose and authority boundary

`r3a.activity-intake.v1` is the generic CME boundary between a registered provider result and a durable resident activity. It is used by any module that has an externally sourced event or observation to turn into resident work. It does not create another operation/resource registry, scheduler, authorization provider, or persistence store.

The provider returns one typed intake envelope through its ordinary registered `capability_operations` invocation. CME validates the operation grant and invocation record before the provider runs, validates this envelope after the provider succeeds, then performs idempotent durable intake. CME owns activity IDs, task routing, durable event writes, and all resident authorization. Provider discovery or a valid envelope does not itself grant authority.

The provider is input/evidence only. It cannot assign authority, declare an activity completed, acknowledge work upstream, or write CME state directly. The CME adapter binding identifies the permitted task class and lifecycle event projection in externally configured, schema-validated module configuration.

## Version 1 envelope

The JSON Schema in `r3a_runtime/schemas/activity-intake.v1.schema.json` is normative. It requires:

- Contract ID and semantic version.
- Stable intake/source/event identity, source revision, source occurrence/receipt timestamps, and a source-bound idempotency key.
- Correlation and optional parent-activity lineage.
- A bounded activity request with activity type, task class, objective text, typed input, and evidence references/digests.
- Provider/module provenance, configuration revision, and source payload reference/digest.
- A namespaced lifecycle projection mapping generic CME phases (`received`, `actionable`, `acknowledged`, `resolved`, `blocked`) to append-only institutional event types. A mapping is declarative; CME determines when a phase is true.

`source.idempotency_key` is opaque to generic CME but must be stable for the same immutable source event and different for different events. CME stores and compares the complete canonical intake envelope on replay: identical replay returns the existing activity; same key with different source identity/content is rejected. CME owns the resulting activity ID and does not interpret provider-supplied source subjects as activity IDs.

`payload_ref` is a reference, not an instruction to fetch arbitrary data. `payload_sha256` and evidence digests bind the submitted evidence. Secret values and credentials are forbidden from the envelope and all diagnostic/event projections.

## Lifecycle and compatibility

Generic lifecycle storage uses existing durable activity and event APIs. The projection names preserve established domain event names during incremental migration (for example, the current `grace.notification.*` events) without adding source-specific CME conditionals. CME validates projection names against the configured module namespace and appends them only at the corresponding observed activity transition. A module may be disabled or replaced while existing activity rows and event lineage remain readable.

The initial notification mapping must preserve current N1 behavior: event receipt is not upstream acknowledgment; `actionable` follows a scheduler claim; `acknowledged` follows a real Grace response; `resolved` follows a durable successful outcome; `blocked` follows a durable blocked outcome. Source/event IDs, exact `notification:<source>:<event>` idempotency, source correlation, occurrence/receipt timestamps, payload reference, source digest, evidence, and provenance must survive the mapping. The current N1 path remains authoritative until the generic binding passes those equivalence checks.

## Generic activity-handler extension required by AD-024

`r3a.activity-intake.v1` remains the generic source/evidence envelope and keeps its current version and fields. A handler binding consumes an accepted intake/activity and routes durable work to a registered module through the existing CME scheduler. The schema's `activity_type` is already a string; the limitation is the current consumer/dispatcher, which accepts only `grace.objective`, not the v1 envelope shape.

The required adjacent consumer contract is `r3a.activity-handler.v1`. A module declares, in validated external configuration/manifest metadata:

- stable handler ID and handler contract version/range;
- supported namespaced activity types and request/result/progress/checkpoint schema references;
- module ID/version/artifact digest and configuration revision;
- required capability references (not grants), concurrency/resource limits, and activity recovery/idempotency behavior;
- whether state is stateless or module-owned, and for module-owned state its namespace, checkpoint/migration/recovery contract.

CME resolves each activity type to exactly one compatible registered handler. The resolved handler/module version and binding/config revisions are stored with the durable activity. Missing, ambiguous, disabled, unauthorized, or incompatible targets fail closed with a durable diagnostic. Handler selection is configuration/registry driven; CME must not add per-domain activity-type branches.

CME owns institutional activity identity, idempotency/replay conflict detection, authorization decisions, leases, scheduling, lifecycle/event records, progress timestamps, routing, diagnostics, and recovery coordination. The module handler owns domain decisions, workflow policy, task-specific evidence obligations, and its declared private state. The handler receives validated inputs and authorized references, and returns validated progress/outcome/evidence/checkpoint references correlated to activity ID, handler ID/version, and attempt. It cannot write CME-owned state or grant itself authority.

Handler execution uses existing module `execute`, `checkpoint`, `health`, and `stop` process lifecycle calls and existing durable activity/event mechanisms. Delivery is at least once; stable idempotency keys and explicit reconciliation are required for effects. On stop, replacement, or restart, CME preserves the activity and event lineage, records handler/binding versions and checkpoint, and resumes, reconciles, or leaves a truthful blocked outcome under the declared recovery contract. No second scheduler, registry, database, or orchestration service is introduced.

The Grace objective intake remains a compatible existing handler during incremental migration. Other module-owned workflows enter this generic path as they are assigned; this document does not order immediate migration of all Engineering, Knowledge, or Notification behavior.

The current Grace `task_class` allowlist applies to Grace objective execution only. A non-Grace handler declares its own supported activity types and validated handler schemas; CME must not force every module-owned workflow into Grace task classes. CME still validates the handler binding, current authorization, resource limits, and generic durable activity envelope before dispatch.

Engineering's generic activity-handler contract is a separate consumer-side boundary. This intake contract does not move Engineering execution, work-order, or verifier behavior into CME. Knowledge evidence obligations are also a separate contract; intake evidence is provenance input and does not waive them.

## Integration handoff

The #48 source adapter `notification.source.read@1.0.0` already returns the source facts needed by this schema. Bind its output to this contract in CME only after adapter conformance covers the normative schema and the existing N1 lifecycle regression suite passes unchanged. The #43 CME owner owns the generic persistence and activity lifecycle bridge; #48 owns source parsing and notification policy; #46 owns operation/module registration and authorization contracts. This contract creates no new live-runtime claim.

Conformance must cover grant denial before provider execution, exact replay, conflicting replay rejection, parent/correlation lineage, restart recovery, evidence digest retention, lifecycle projection on actual observed transitions, notification N1 equivalence, and coexistence with observer and other capabilities.
