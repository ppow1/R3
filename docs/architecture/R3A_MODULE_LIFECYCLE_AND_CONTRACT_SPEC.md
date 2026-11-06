<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md
Component: R3A-MODULE-CONTRACT
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Specify module discovery, versioning and runtime lifecycle requirements for R3A.
Execution Model: N/A; contract specification.
Observability: Registry state and lifecycle event lineage.
Dependencies: R3A Architecture Charter; AP0 Technical Specification; State Machine and Diagnostic Contract.
Authority: Steward directive; field encoding and artifact trust choices remain open unless explicitly specified here.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial module contract specification.
Supersedes: None.
Contracts: AD-004 through AD-008; AP0-007/AP0-008.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# Module Lifecycle and Contract Specification

**Status:** Planned contract. The lifecycle capabilities are directed; serialization, package format and compatibility policy are unresolved implementation decisions.

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
| `entrypoint` / `binding` | How CME invokes or supervises the module; exact mechanism TBD. |
| `dependencies` | Required contract/provider identities and version ranges. |
| `configuration_schema` and `configuration_ref` | Validated schema identity and external configuration location/reference. |
| `capability_refs` | Required capability/resource identities; does not grant access. |
| `state_namespace` and `migration_contract` | Module-owned durable state and upgrade compatibility. |
| `lifecycle_state`, `health`, `diagnostic_ref` | Current observed lifecycle, health and diagnostic location. |
| `artifact_ref`, `artifact_digest` | Immutable implementation location and integrity reference; trust/signature format TBD. |

Field names are illustrative until the Steward approves an encoding/schema. The required information categories are specification constraints.

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

## Open decisions

Package/artifact format; signing/trust roots; module process versus in-process binding; compatibility range semantics; state migration transactionality; drain deadlines and resource constraints; rollback/forward-recovery policy; config reload and secret provider APIs; registry write ownership; deployment promotion and activation authority remain OPEN in the R3A parking lot.
