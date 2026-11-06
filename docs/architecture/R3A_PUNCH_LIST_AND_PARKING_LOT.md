<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_PUNCH_LIST_AND_PARKING_LOT.md
Component: R3A-PUNCH-LIST
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Track R3A requirements, dependencies, acceptance and intentionally unresolved decisions.
Execution Model: N/A; planning/control record.
Observability: Git history; requirement status and linked evidence.
Dependencies: R3A Architecture Charter; Master Roadmap; AP0 Technical Specification.
Authority: Steward directive; no implementation authorized.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial punch list and parking lot.
Supersedes: None; supplements rather than closes docs/PUNCH_LIST.md and docs/PARKING_LOT.md.
Contracts: R3A Architecture Charter; State Machine and Diagnostic Contract; Bounded Testing and Acceptance Policy.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# R3A Punch List and Parking Lot

**Status:** Requirements are PLANNED unless noted. This R3A tracker supplements the existing R3 [punch list](../PUNCH_LIST.md) and [parking lot](../PARKING_LOT.md); it does not claim those items are complete or superseded.

## Punch list

| ID | Priority | Requirement / deliverable | Depends on | Acceptance criteria | Status |
|---|---|---|---|---|---|
| R3A-001 | P0 | Keep Ring 0 minimal and persistent. | AP0 spec; host/process ownership decision. | Ring 0 starts from external configuration, supervises CME lifecycle and exposes its own health without owning resident reasoning or domain work. | PLANNED |
| R3A-002 | P0 | Run CME as a separately supervised/restartable component. | R3A-001; lifecycle contract. | CME can fail/stop and be restarted without restarting Ring 0; lifecycle events and recovery are durable and visible. | PLANNED |
| R3A-003 | P0 | Make activities, events, effective configuration revisions and continuation state database-driven. | Persistence/migration decisions; state/config contracts. | Restart restores/reconciles durable state with no silent loss; configuration values or secure references and provenance, schema versions, and event versions are recorded; PostgreSQL direction in R3 Charter Revision 2 is respected. | PLANNED |
| R3A-004 | P0 | Execute structured versioned state machines. | State Machine and Diagnostic Contract. | The same versioned definition constrains valid runtime transitions and describes diagnostics; invalid transitions are rejected and recorded. | PLANNED |
| R3A-005 | P0 | Provide minimal discoverable module and capability registries. | Module Contract; registry ownership/config decisions. | Installed/active module and registered capability metadata can be enumerated with contract version, owner, status and health; no invocation is authorized merely by discoverability. | PLANNED |
| R3A-006 | P0 | Externalize and validate operational configuration. | Config schema and source-of-truth decisions. | Runtime behavior uses validated external configuration; executable source contains no environment-specific operational values or secrets; invalid required config fails visibly. | PLANNED |
| R3A-007 | P0 | Expose actual state, transitions, timing, progress and exceptions. | R3A-003/004; diagnostic contract. | HMI/diagnostic API matches durable records and explicitly marks unknown, stale and unavailable readings. | PLANNED |
| R3A-008 | P0 | Recover CME/process interruptions and preserve recoverable work. | R3A-002/003/004; idempotency/side-effect decisions. | Restart produces a durable recovery decision; recoverable work remains open and resumable; no false completion or silent termination. | PLANNED |
| R3A-009 | P0 | Validate AP0 with bounded evidence. | Acceptance policy; isolated runtime and data. | Contract, failure/restart and operational acceptance evidence is captured for the exact revision; production R/3 remains untouched. | PLANNED |
| R3A-010 | P1 | Provide secure remote Steward operation early. | AP0 truthful diagnostics; auth/gateway and secret decisions. | Authenticated encrypted remote use supports only authorized operations and exposes real status without leaking secrets. | PLANNED |
| R3A-011 | P1 | Deliver genuine Engineering execution led operationally by Grace. | AP0; capability registry; work-order and evidence contracts. | Real authorized objectives continue through interruption to verified deliverable or explicit evidence-backed block. | PLANNED |
| R3A-012 | P1 | Support auditable escalated reasoning. | AP0 activity/evidence continuity; provider/privacy policy. | Escalation and return preserve activity identity, evidence, authorization and failure recovery. | PLANNED |
| R3A-013 | P1 | Integrate Bitwarden secrets management; reserve future TOTP/YubiKey support. | Auth/provider and machine identity decisions. | Secret values are obtained through the approved integration and never committed or emitted in diagnostics; future factors have an approved compatible path. | PLANNED |
| R3A-014 | P1 | Accommodate backup, privacy, lockdown and cryptographic erasure. | Database/key/retention ownership decisions. | Data model and interfaces preserve the ability to implement approved backup/restore, access restriction, emergency lockdown and crypto-erasure policies. | PLANNED |
| R3A-015 | P2 | Place Jessica's character-development capability in AP4. | AP0 module/identity contract; HR/privacy decisions. | Jessica's capability is a separately versioned module with authorized, provenance-preserving personnel/canon interactions. | DEFERRED — AP4 |
| R3A-016 | P2 | Place spatial/Quest presentation in AP5. | AP0 APIs; actual hardware/runtime inventory. | A spatial client presents shared actual state and cannot gate desktop/mobile functionality. | DEFERRED — AP5 |
| R3A-017 | P0 | Preserve R3 provenance and coding standards. | `hints/file-provenance.md`; explicit R3A supplement approval for any change. | All controlled files meet headers/predecessor/version requirements; no silent policy relaxation. | PLANNED |

## Parking lot — unresolved, not rejected

| ID | Question / idea | Needed before | Owner/authority | Status |
|---|---|---|---|---|
| R3A-L001 | Ring 0 process manager, service identity, and Ring 0's own failure/restart boundary. | AP0 implementation. | Steward / platform owner. | OPEN |
| R3A-L002 | PostgreSQL deployment topology, schema ownership, migration and connection lifecycle. Charter names PostgreSQL; concrete operational choices are unset. | AP0 implementation. | Steward / database owner. | OPEN |
| R3A-L003 | CME scheduling priority/fairness, resource dimensions, allocation policy and limits. | AP0 detailed execution contract; limits require justification/config/authority. | Steward / CME owner. | OPEN |
| R3A-L004 | Activity side-effect idempotency, lease/checkpoint semantics and recovery reconciliation. | AP0 recovery implementation; AP2 work semantics. | Steward / module owners. | OPEN |
| R3A-L005 | Module artifact/package format, trust/signature process, compatibility window and upgrade/replace atomicity. | Before module installer implementation. | Steward / security owner. | OPEN |
| R3A-L006 | Exact registry ownership and whether capability health/authorization data is local or adapter-provided. | AP0 registry implementation. | Steward / capability owner. | OPEN |
| R3A-L007 | Configuration source of truth, reload semantics, and secret-reference syntax; Bitwarden service/machine-auth method. | AP0 configuration and AP1 secrets. | Steward / security owner. | OPEN |
| R3A-L008 | Event payload classification, retention, replay, deletion and cryptographic-erasure semantics. | AP0 schema; AP6 policy validation. | Steward / privacy and data owners. | OPEN |
| R3A-L009 | Diagnostic API/HMI transport, auth, freshness thresholds, and external operator clients. | AP0 interface implementation. | Steward / HMI owner. | OPEN |
| R3A-L010 | CME resource supervision scope versus host/container/orchestrator responsibilities. | AP0 resource contract. | Steward / platform owner. | OPEN |
| R3A-L011 | Emergency lockdown semantics, emergency authority, unlock path and operator continuity. | Security design before external/production operation. | Steward. | OPEN |
| R3A-L012 | Cryptographic erasure key ownership, key rotation, backups and residual metadata policy. | AP6 detailed design. | Steward / privacy and security owners. | OPEN |
| R3A-L013 | Future TOTP/YubiKey factors and account recovery policy. | AP1/AP6 implementation. | Steward. | OPEN |
