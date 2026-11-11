<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md
Component: R3A-MODULE-CONTRACT
File Revision: 1.0.1
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Specify module discovery, versioning and runtime lifecycle requirements for R3A.
Execution Model: N/A; contract specification.
Observability: Registry state and lifecycle event lineage.
Dependencies: R3A Architecture Charter; AP0 Technical Specification; State Machine and Diagnostic Contract.
Authority: Steward directive; field encoding and artifact trust choices remain open unless explicitly specified here.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial module contract specification.
Changed: 2026-11-06T05:18:48Z | AP0-M1-PLAN | Codex GPT-6 | Select AP0 module process binding and minimum manifest/RPC compatibility profile.
Supersedes: None.
Contracts: AD-004 through AD-008; AP0-007/AP0-008.
Tests: Not run; documentation only.
History/Predecessor: Git blob b77d4f50fd6e187b8cf7d9a7a301ba60256be15c at baseline commit f629a570d904719d1f13d2ceaddff7a2af2ce00d.
-->
# Module Lifecycle and Contract Specification

**Status:** Planned contract. The lifecycle capabilities are directed. AP0-M1 selects the local process binding and minimum compatibility shape below; installation trust, distribution and later promotion remain open.

## Contract principles

| ID | Contract requirement | Depends on | Acceptance criteria |
|---|---|---|---|
| MOD-001 | A module is an independently identifiable implementation that declares a versioned contract and dependencies. | Registry schema and artifact identity decisions. | Two module versions are independently identifiable and their contract/dependency declarations are queryable. |
| MOD-002 | Ring 0 and CME consume module metadata through a registry/loader boundary; core code must not import every module's private behavior as a fixed roster. | MOD-001; loader/binding choice. | A compatible fixture can be registered and discovered without editing Ring 0's module roster. |
| MOD-003 | Installed, active, stopped, failed, incompatible and replacement-in-progress states are durable and visible. | State Machine and Diagnostic Contract; database schema. | Each exercised lifecycle condition survives process restart and is exposed with its state-machine version. |
| MOD-004 | Installing, activating, stopping or replacing a module must not require restarting Ring 0. CME may coordinate module-specific worker/process lifecycle according to the chosen binding model. | MOD-002/003; component binding choice. | Complete each lifecycle operation while Ring 0 remains available; retain Ring 0 process identity and health evidence. |
| MOD-005 | Contract version compatibility is checked before activation. Incompatible modules remain visible with a diagnostic reason and cannot become active. | MOD-001; compatibility policy. | An incompatible fixture is denied activation with an explicit diagnostic; compatible version activates. |
| MOD-006 | Registry presence/discovery does not grant capability invocation. Authorization continues through the institutional authority/grant mechanism. | Capability registry and authority interface. | A discovered capability remains denied without an effective grant; an authorized invocation is auditable. |
| MOD-007 | Module configuration is external and schema-validated. Secrets are references resolved by an approved secret provider, never embedded values. | Configuration schema/source and Bitwarden provider decisions. | Valid config applies with a durable revision; malformed config fails visibly; diagnostics/config history contain no secret values. |
| MOD-008 | Module state and events are database-backed and namespaced/owned; upgrades declare migration/recovery compatibility before activation. | Persistence/schema and migration decisions. | Restart preserves module state/event lineage; upgrade either migrates compatibly or remains visibly incompatible without discarding prior state. |
| MOD-009 | Shutdown, replacement or failed activation preserves durable work and records whether it drained, checkpointed, resumed or remains blocked. | Activity continuation/idempotency contract; MOD-003. | Inject stop/replacement during active work and recover or show an explicit blocked state with prior work identity and lineage intact. |
| MOD-010 | The module's health and version are based on observed process/contract status; declarations alone are not health evidence. | Health probe contract; diagnostics interface. | Reported health changes with observed failure/staleness and returns only after readiness is observed. |

## Minimum declared contract information

The machine-readable representation must carry, at minimum:

| Field | Meaning |
|---|---|
| `module_id` | Stable institution-wide identity, independent of display name. |
| `module_version` | Immutable implementation release identifier. |
| `contract_id`, `contract_version` | Contract and supported major/minor version range. |
| `owner` | Institutional role/team accountable for module behavior and data. |
| `entrypoint` / `binding` | AP0-M1: executable entry point in a locally staged immutable artifact, launched as a CME-supervised child process. |
| `dependencies` | Required contract/provider identities and version ranges. |
| `configuration_schema` and `configuration_ref` | Validated schema identity and external configuration location/reference. |
| `capability_refs` | Required capability/resource identities; does not grant access. |
| `state_namespace` and `migration_contract` | Module-owned durable state and upgrade compatibility. |
| `lifecycle_state`, `health`, `diagnostic_ref` | Current observed lifecycle, health and diagnostic location. |
| `artifact_ref`, `artifact_digest` | Immutable local implementation location and content digest; signing/trust format remains deferred. |

Field names are the AP0-M1 planning vocabulary; implementation may map them to repository-conforming identifiers while preserving the required semantics and versioned manifest profile. This plan does not require another Steward design approval.

## Lifecycle semantics

Under MOD-003/MOD-005, the registry SHALL represent these logical conditions (wire state identifiers remain to be selected in the state catalog):

- **Absent:** no installed module record.
- **Installed:** artifact and contract metadata are available and integrity/compatibility checks have completed.
- **Activating:** configuration/dependencies are being bound and readiness is being checked; not yet advertised as active.
- **Active:** module is eligible to receive work under its declared contract and authority.
- **Stopping:** admission is closed; module is draining/checkpointing according to its contract.
- **Stopped:** no new work is admitted; durable state and status remain discoverable.
- **Failed:** lifecycle/health failure is recorded with exception, time, affected state and recovery classification.
- **Replacing:** a new version is being made effective while prior state/artifacts remain attributable; exact atomicity/rollback behavior is unresolved.
- **Incompatible:** dependency/contract/configuration mismatch prevents activation.

Lifecycle operations SHALL be idempotent or return a correlated existing operation. An activation failure leaves the prior effective version intact where replacement has begun; if that cannot be guaranteed by the implementation binding, the system must report an explicit blocked/degraded state and preserve artifacts and state for recovery.

## Capability/resource registry

Registry entries describe identity, kind, contract/version, owner, provider/binding reference, availability, last observation, health, configuration reference and permission mechanism. CME may use registry data for scheduling/resource decisions. Consumers discover before use and check current health. Invocation is separately authorized and audited; stale health is not availability. Resource dimensions and policies (CPU, memory, GPU, repository, concurrency, etc.) are not selected here.

## Compatibility and recovery

The compatibility evaluator MUST distinguish compatible, incompatible and unknown. Unknown is not silently compatible. A module replacement preserves prior version identity and event lineage. It records the initiating operation, actor/authority reference, old/new versions, drain/checkpoint outcome, migration result, readiness checks and effective version. Recovery can resume or leave a visible blocked operation; it must not present partial replacement as complete.

## AP0-M1 binding and protocol profile

AP0-M1 modules run in separate unprivileged child processes supervised by CME. CME communicates over a private Unix domain socket using UTF-8 JSON-lines messages. Every message carries `protocol_version`, `module_id`, immutable `module_version`, `request_id` and correlation ID; responses carry the same IDs plus explicit result/error and observation time. The minimum calls are `hello`, `health`, `prepare`, `activate`, `execute`, `checkpoint` and `stop`. Module processes do not connect directly to the institutional database; CME persists authoritative state and module output through the contract. Control requests are idempotent by request ID or return the existing correlated operation.

For AP0, compatibility requires matching protocol major version and a declared supported minor range containing the host minor version. A missing/unknown declaration is incompatible. The manifest is locally staged and immutable after registration; its digest is checked before launch. No general dependency solver or remote installer is included. AP0 may register a test/observer artifact from a local path explicitly listed by configuration; unlisted paths are rejected. This local digest check is integrity identification, not a claim of signed provenance or a complete trust policy.

CME is the sole writer of module lifecycle records. Module readiness is observed through process health and successful contract handshake. Replacement closes admission, checkpoints/drains when supported, starts and validates the new version, then records the effective version. If readiness or recovery is uncertain, the operation remains visibly blocked/degraded and the old artifact/state lineage stays attributable; there is no destructive automatic rollback that discards state.

## Remaining decisions outside the AP0-M1 minimum

Artifact signing/trust roots and distribution/promotion authority; domain-specific state migration; privacy classification/retention; emergency lockdown; AP3 secret provider and remote authentication; and capability-specific grant policy remain open as recorded in the parking lot. None changes the selected AP0 process boundary or authorizes invocation from registry presence.
