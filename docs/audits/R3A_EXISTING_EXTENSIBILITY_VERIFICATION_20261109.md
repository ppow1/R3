<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_EXISTING_EXTENSIBILITY_VERIFICATION_20261109.md
Component: R3A-EXISTING-EXTENSIBILITY-VERIFICATION
File Revision: 1.0.0
Created: 2026-11-09
Created By: Codex GPT-6, acting as independent Auditor
Purpose: Verify existing R3A extension boundaries and reassess proposed modularity clarifications using source and executable evidence.
Execution Model: Read-only source review plus isolated tests and disposable in-memory harnesses.
Authority: Auditor investigation under Steward directive; does not amend or approve architecture.
Changed: 2026-11-09 | R3A-AUDIT-V2 | Codex GPT-6 | Initial verification report.
Contracts: Approved R3A charter, roadmap, module lifecycle, capability, activity-intake, state/diagnostic, Website/API, and acceptance contracts.
Tests: Focused existing tests and disposable config-reload harness; details below.
-->
# R3A Existing Extensibility Verification

**Status:** Investigation finding for Steward review; no proposed requirement is approved by this report.
**Code baseline:** repository baseline `9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9`; capability-provider behavior reviewed in the auditor workspace and exercised by repository fixtures. Coordinator chat change `722a102de6e4d3166c9d1e7358fa8fa6a0aa3e4c` is not the subject of this report.
**Related:** [proposed specification](R3A_MODULARITY_COMPLIANCE_SPEC_PROPOSAL_20261109.md), [contract gap analysis](R3A_INTERFACE_CONTRACT_GAP_ANALYSIS_20261109.md).

## Conclusion

R3A is genuinely extensible for capability-provider modules: an external, digest-pinned provider can be configured, discovered, registered, activated, invoked through CME authorization, replaced, stopped, and presented through the generic Website operation interface without editing CME or Ring 0 source. Focused fixtures verify this cycle, and a disposable harness verified configuration reload and lifecycle operations without changing the running CME process ID.

That conclusion does not extend to every meaning of “module.” Resident executors remain hardwired to Observer/Grace entrypoints in configuration; generic durable module-owned activity handlers are not implemented. The durable intake consumer rejects any activity type other than `grace.objective`. The existing design therefore already meets the original independent-provider extension objective for request/response capabilities, while resident-executor extensibility and arbitrary stateful workflows require scope clarification and, if required, targeted changes at existing extension boundaries.

No live services, production database, identities, grants, credentials, or runtime configuration were modified. Tests used local fixtures, temporary dependency installation under `/tmp`, and an in-memory store-compatible harness. Live Ring 0/CME/PostgreSQL and authenticated Website acceptance remain unverified.

## Existing mechanisms and verified scope

| Mechanism | Implemented behavior | Evidence / limits |
|---|---|---|
| External provider configuration and registry | `Settings` loads capability operation descriptors and provider manifests/configuration from external paths; validates schemas, digests, provider identity/version, operation declarations, and capability bindings; registry discovers operations and provider state. Provider entrypoints are not restricted to a fixed module roster. | `r3a_runtime/config.py`, `capability_contracts.py`; tests in `test_r3a_modular_capability_registration.py` and `test_r3a_capability_contracts.py`. Artifact source must already be staged and importable; this is not a remote package downloader. |
| Dependency compatibility | Version range evaluator supports exact/relational, tilde, caret, and comma-AND requirements; graph validation detects missing/incompatible dependencies and cycles during config load. Runtime activates compatible dependencies. | `r3a_runtime/module_contracts.py`, `config.py`, `provider_runtime.py`; `tests/test_r3a_module_contracts.py`. |
| Provider lifecycle and replacement | CME control operations install/status/activate/deactivate and replace configured provider versions. Replacement activates the candidate and keeps/re-enables old provider if candidate activation fails; successful replacement drains/stops the old process and records replacement. | `r3a_runtime/cme.py` around capability module control operations; `provider_runtime.py`; `tests/test_r3a_capability_integration_demo.py`. The tested lifecycle is a provider module lifecycle, not arbitrary resident executor lifecycle. |
| Process/provider protocol | A provider is launched as a separate child process with a pinned artifact digest and private socket; worker handles hello/prepare/activate/health, execution, checkpoint and stop protocol. The child environment is filtered/allowlisted. CME owns authorization and canonical invocation/result recording. | `r3a_runtime/provider_runtime.py`, `capability_worker.py`, `protocol.py`, `cme.py`. The child inherits the CME service UID; no separate OS identity or sandbox is established. |
| Runtime config reload | `config.reload` loads the changed external config in a running CME, waits for safe activity boundary, rejects changes to bootstrap DB/identity/socket settings and refuses removal of active providers until deactivated. It installs updated provider bindings and revises config without process restart. | `r3a_runtime/cme.py:1298-1345`; disposable harness below. New source still must be staged, manifested, digest-pinned, and declared in config. |
| Capability discovery/invocation | Discovery reports descriptors and explicitly says authorization was not evaluated. Invocation uses canonical envelope; CME evaluates grants before provider execution and records outcome. | `r3a_runtime/cme.py`, `capability_contracts.py`; capability contract and focused authorization tests. |
| Website/API | Authenticated generic `GET /api/v1/steward/capabilities` discovers operations; generic `POST /api/v1/steward/operations/invoke` overwrites caller principal with server-authenticated identity and routes through CME. Existing Website UI renders registry operations and a generic invocation form. A unique module-specific panel is optional. | `r3a_runtime/steward_access.py:597-655`, `web/index.html`, `tests/test_r3a_steward_access.py`, `tests/test_r3a_website.py`. Source/tests only; no live authenticated session or deployed module was exercised. |
| Resident executors | Top-level resident module configuration only accepts `r3a_runtime.observer_module` and `r3a_runtime.grace_module`; Observer identity is paired to its fixed module ID. Per-resident process creation uses Grace entrypoint. | `r3a_runtime/config.py:448-451`, `r3a_runtime/cme.py` resident process path. This is a genuine limitation if independently developed resident executors are required. |
| Activity intake and durable dispatch | Existing intake contract gives providers a typed, idempotent source-to-CME boundary. CME validates authorization and persists work. The consumer currently accepts only `grace.objective` and only Grace-eligible task classes. | `r3a_runtime/db.py:1403-1413` raises `CapabilityContractError("this CME intake consumer currently accepts grace.objective activities only")`. Existing source adapter is useful, but not a generic module-owned workflow handler. |
| State ownership/migration | Manifest/config carries module state namespace, migration and recovery metadata; lifecycle records are durable. Current provider fixture path and legacy normalization are stateless-oriented. Generic module-owned durable state migration/recovery is not demonstrated end-to-end. | Module lifecycle specification, `config.py`, Store registration and tests. Do not infer stateful migration support from manifest fields alone. |
| CME domain orchestration | CME retains Engineering work-order/verifier, Knowledge evidence/continuation, notification intake/lifecycle, and Grace objective-specific paths. Some providers behind these workflows are separately registered and replaceable; therefore a CME branch does not by itself prove provider replacement is impossible. | `r3a_runtime/cme.py`, `db.py`, domain interfaces. These are concrete boundaries to assess against each approved module’s assigned ownership, not evidence for wholesale CME extraction. |

## Extension boundary exercise (ten requested steps)

This evaluates the existing capability-provider path, not a new resident executor or new arbitrary durable workflow. “Pass” here means fixture/source behavior; it is not live-service acceptance.

| Step | Result | Evidence / limit |
|---|---|---|
| 1. Add without CME/Ring 0 source changes | PASS | Existing external provider manifest/artifact/config fixtures are consumed by generic config/registry code; provider integration tests run without source edits. |
| 2. Register through existing interface | PASS | External `capability_operations` configuration plus `config.reload`; runtime harness observed changed config revision and unchanged CME PID. |
| 3. Discover through registry | PASS | `capability.discover` returns configured operation/provider descriptors. |
| 4. Activate and stop | PASS | CME lifecycle control invoked fixture provider; `ACTIVE` then `STOPPED` recorded. |
| 5. Invoke through capability contract | PASS | Integration fixture invokes provider with canonical request envelope and returns validated result. |
| 6. Authorization allow/deny | PASS | Focused grant tests exercise allowed and denied calls; discovery alone sets `authorization_evaluated:false`. |
| 7. Configure independently | PASS | Provider config and operation manifest are external and schema-validated; adding a new configured operation requires updating the external operation list and module capability declaration. |
| 8. Upgrade/replace independently | PASS | Existing two-version fixture exercises provider replacement and unrelated telemetry coexistence. |
| 9. Remove/disable cleanly | PASS WITH BOUNDARY | Provider is deactivated/stopped; config reload refuses removal while active and permits it after deactivation. No general artifact garbage collector/package uninstall was demonstrated. |
| 10. Expose through Website/API | PASS AT SOURCE/TEST LEVEL | Generic API/UI is operation-registry based; no module-specific gateway branch required. Live session/deployment not tested. |

### Executable evidence

- `tests/test_r3a_capability_integration_demo.py`, `tests/test_r3a_module_contracts.py`, `tests/test_r3a_modular_capability_registration.py`: **24 passed**. Covers external fixture registration, dependency checks, lifecycle, authorization/invocation, replay, replacement, stop/disable and coexistence.
- `tests/test_r3a_capability_contracts.py`, `tests/test_r3a_modular_autonomy.py`, `tests/test_r3a_steward_access.py`, `tests/test_r3a_website.py`: **90 passed; 9 subtests passed**. Includes schema/contract, authorization, generic API routing and Website source behavior.
- Disposable runtime harness built a temporary config from existing provider fixture data, started with no provider, rewrote only temporary config to register an existing Engineering provider artifact, then called `config.reload`, install, activate, deactivate. Observed `operation_discovered_after_config_reload=true`, `cme_pid_unchanged=true`, provider lifecycle `ACTIVE` then `STOPPED`, and the child UID equal to the CME UID. This used a store-compatible in-memory stub; it did not exercise PostgreSQL or Ring 0. It establishes hot registration for an already staged provider artifact, not artifact download or arbitrary resident executor loading.
- `node --test tests/test_steward_workspace_api.mjs`: **14 passed** at Coordinator commit `722a102`; separate chat client evidence, not evidence for live Website acceptance.

## P-01–P-13 reassessment

Classification labels are used exactly as requested. “Implementation correction” identifies behavior needed to meet an existing obligation or correct a concrete existing mismatch; it does not authorize modifying production or imply all proposed wording is approved.

| ID | Classification | Evidence-based answer and minimum disposition |
|---|---|---|
| P-01 | DOCUMENTATION ONLY | Provider packages, capability operations, resident executors, and durable activity handlers are different scopes today. Record the distinctions; do not add new interface types for provider modules. Resident and durable-handler gaps are separately evidenced below. |
| P-02 | IMPLEMENTATION CORRECTION | MOD-002 already expects module behavior behind a core boundary. Correct only demonstrated module-owned behavior trapped in CME after assigned ownership is established. Provider implementation replacement works; no wholesale extraction warranted. |
| P-03 | ALREADY SATISFIED | Provider install/status/activate/deactivate/replace and config revision exist and are fixture-tested. Live operational evidence still required for deployment acceptance. |
| P-04 | NEW POLICY DECISION | Running CME reload works for capability providers and was exercised without process restart. Ring 0 restart avoidance is approved; stronger CME availability for package staging and all resident executor changes is not established as an approved requirement. |
| P-05 | ALREADY SATISFIED | Dependency range grammar, evaluation, cycle/missing/incompatible validation, and activation resolution exist and are tested. Update stale implementation documentation. |
| P-06 | IMPLEMENTATION CORRECTION | Existing state/recovery obligations remain; provider stateless path is verified, generic stateful migration is not. Require accurate declaration and implement migration/recovery only for modules with durable owned state. |
| P-07 | IMPLEMENTATION CORRECTION | Generic resident executor artifact binding is absent: loader allowlist and Grace entrypoint are fixed. Only correct if independently developed resident executors are within approved objective; does not imply HR API changes. |
| P-08 | DOCUMENTATION ONLY | Provider interface maps through the worker process protocol and lifecycle. Clarify adapter/error/timeout mapping where docs leave it ambiguous; no new transport is evidenced as necessary. |
| P-09 | NEW POLICY DECISION | Child provider processes are separate processes with scrubbed env/private socket but same service UID. Interpret “unprivileged” and define threat model before specifying OS sandboxing. |
| P-10 | NEW POLICY DECISION | Versioned schemas/protocol exist. Universal evolution/deprecation/unknown-field rules exceed current policy; no demonstrated failure blocks the existing provider extension flow. |
| P-11 | CONTRACT GAP | Durable activity intake is hard-limited to `grace.objective`; no arbitrary module-owned handler binding is present. A generic extension is warranted only for approved module-owned durable workflows; smallest path is extending existing intake/scheduler/lifecycle contracts. |
| P-12 | ALREADY SATISFIED | Generic capability Website/API supports discovery/invocation and session-derived identity through CME. A unique module panel is unnecessary. Live use is unverified. |
| P-13 | ALREADY SATISFIED | Fixture suite demonstrates positive provider extension cycle, authorization allow/deny, replacement, stop/disable and coexistence. Existing fixture tests are not live Ring 0/DB acceptance. |

## Major architectural questions

### A. Generic activity handling

Provider capabilities can perform request/response operations and may use the existing source activity-intake API for the Grace objective path. The generic activity contract defines source identity, idempotency, provenance, and CME persistence, but the current Store consumer rejects every non-`grace.objective` type. It also limits task class to Grace-supported execution. Therefore a general module-owned durable activity lifecycle cannot be demonstrated through current intake. If an AP assignment actually requires such workflows, extend the existing intake/scheduler/module lifecycle boundary with a declared target handler and owner state contract. A separate registry/service is not supported by the evidence. Clarify whether this belongs to original scope or requires Steward approval before enforcing it.

### B. Domain-specific CME behavior

CME appropriately owns authorization, scheduling, lifecycle, persistence primitives, and generic observability. Its Engineering work-order/verifier paths, Knowledge evidence continuations, notification lifecycle branches, and Grace objective semantics are domain-specific code in shared orchestration. This is evidence of coupling, but provider implementations for some operations can already be swapped behind capability contracts. A branch is an architectural violation only where it prevents a module from implementing behavior that the approved assignment says it owns. Record exact behavior and migrate only the proven owner-specific portion through an existing or minimally extended boundary. No evidence supports a wholesale CME rewrite.

### C. Registration and CME restarts

Capability-provider operation manifests/config can be added to external configuration, reloaded by `config.reload`, then installed and activated without restarting CME or Ring 0. The harness demonstrated unchanged CME PID. Artifact staging and trust/digest configuration remain outside that control operation. Resident executor config is not generically reloadable because entrypoints are whitelisted. Existing approval protects Ring 0 availability; any broader promise for CME or arbitrary executors is a policy decision.

### D. Process isolation

Provider is a distinct OS process, launched with a scrubbed environment and private socket directory, but no `user=` or privilege change is supplied; it inherits CME's service UID. Thus current isolation is process/protocol separation, not reduced OS privileges or a strong sandbox. The lifecycle contract’s “unprivileged” wording conflicts with this implementation. Steward should decide intended threat model and contract meaning before an isolation requirement is proposed. Do not infer that same-UID providers are isolated from all CME-readable resources.

### E. State and dependencies

Dependency graph validation and range resolution exist and are exercised. Provider module lifecycle persists registration/state, and the tested provider is stateless. Manifest fields for namespace/migration/recovery do not prove those mechanisms are operational for stateful plugins; no generic state migration/recovery exercise established this. Minimum correction is to state the supported stateless profile truthfully and define a stateful acceptance path only where a module requires durable private state. Avoid designing a new state subsystem before identifying a module requirement the current store boundary cannot meet.

### F. Website extensibility

The existing generic capabilities endpoint and invocation UI can expose an operation via registry metadata, without a module-specific route in `r3_app.py` or Website gateway. Session identity is server-derived and invocation returns through CME authorization. Reusable generic views suit operations with a common shape; a unique panel may be justified for domain tasks requiring tailored workflows, but is not a modularity prerequisite for every module. No live authenticated Website session was exercised.

## Smallest corrections and approval decisions

1. Correct stale implementation documentation that says dependency ranges are unsolved or capability registration is startup-only; document the tested provider reload boundary and its staging constraint.
2. Reconcile the word “unprivileged” with same-UID process reality; no security-boundary claim should exceed verified controls until a threat model is approved.
3. Enforce truthful stateless/stateful manifest claims and do not represent untested migration metadata as working stateful replacement.
4. If independently developed resident executors are in scope, add a targeted, versioned resident-to-module binding/loader path at the existing configuration/lifecycle boundary. If that is not an approved requirement, do not add it.
5. If module-owned durable workflows are required, extend current intake/scheduler/lifecycle contracts so an activity can resolve to an authorized, declared handler and its owner state boundary. The exact current blocker is the `grace.objective` restriction in `Store.submit_activity_intake`; use this as the minimum correction point.
6. For domain branches in CME, require the owner assignment and specific replacement failure before proposing extraction. Existing registered provider replacement is already proven.
7. Keep live Ring 0/CME/PostgreSQL and authenticated Website checks as separate operational acceptance evidence, not prerequisites for claiming source-level provider extensibility.

Decisions requiring Steward authority are limited to: (a) whether arbitrary resident executors and generic durable module-owned workflows are within the original modularity objective; (b) whether “without restarting” applies to CME or only the existing Ring 0 guarantee; (c) the intended security meaning/threat model for “unprivileged”; and (d) whether universal contract evolution policy beyond current versioned schemas/protocol should be adopted. None is silently made mandatory here.
