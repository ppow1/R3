<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_PUNCH_LIST_AND_PARKING_LOT.md
Component: R3A-PUNCH-LIST
File Revision: 1.0.6
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Track R3A requirements, dependencies, acceptance and intentionally unresolved decisions.
Execution Model: N/A; planning/control record.
Observability: Git history; requirement status and linked evidence.
Dependencies: R3A Architecture Charter; Master Roadmap; AP0 Technical Specification.
Authority: Steward directive; no implementation authorized.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial punch list and parking lot.
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Align phase ownership and add roadmap/coordination governance requirements.
Changed: 2026-11-06T05:03:56Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Record milestone issue/integration authority prerequisite.
Changed: 2026-11-06T05:18:48Z | AP0-M1-PLAN | Codex GPT-6 | Link AP0-M1 decision plan and separate selected implementation details from deferred policy decisions.
Changed: 2026-11-09T16:32:39Z | R3A-AUTH-INDEPENDENCE-001 | Codex GPT-6 | Clarify R3A-owned authentication acceptance for R3A-010 and record identity provisioning approval dependency.
Changed: 2026-11-09T17:04:07Z | R3A-AUTH-INDEPENDENCE-APPROVED | Codex GPT-6 | Record approved identity association/enrollment design while retaining live identity verification and Steward participation gates.
Changed: 2026-11-09T17:06:17Z | R3A-AUTH-INDEPENDENCE-SECURE-LAN | Codex GPT-6 | Require trusted HTTPS for private-LAN authentication and sessions.
Changed: 2026-11-09T17:54:09Z | R3A-AUTH-COOKIE-ISOLATION | Codex GPT-6 | Require a dedicated R3A hostname to prevent cross-port cookie transmission to R3.
Changed: 2026-11-09T19:23:00Z | AP3-R3A-010-LAN-IP | Codex GPT-6 | Accept the approved LAN IP origin with an IP-SAN certificate and a narrow Steward API cookie path.
Supersedes: None; supplements rather than closes docs/PUNCH_LIST.md and docs/PARKING_LOT.md.
Contracts: R3A Architecture Charter; State Machine and Diagnostic Contract; Bounded Testing and Acceptance Policy.
Tests: Not run; documentation only.
History/Predecessor: Git blob 287cb3cd599a4f746adf3a30365a78cc13d3d8e5 at baseline commit f629a570d904719d1f13d2ceaddff7a2af2ce00d.
-->
# R3A Punch List and Parking Lot

**Status:** Requirements are PLANNED unless noted. This R3A tracker supplements the existing R3 [punch list](../PUNCH_LIST.md) and [parking lot](../PARKING_LOT.md); it does not claim those items are complete or superseded.

## Punch list

| ID | Priority | Requirement / deliverable | Depends on | Acceptance criteria | Status |
|---|---|---|---|---|---|
| R3A-001 | P0 | Keep Ring 0 minimal and persistent. | AP0 spec; AP0-M1 plan D1 and host preflight. | Ring 0 starts from external configuration, supervises CME lifecycle and exposes its own health without owning resident reasoning or domain work. | PLANNED |
| R3A-002 | P0 | Run CME as a separately supervised/restartable component. | R3A-001; lifecycle contract. | CME can fail/stop and be restarted without restarting Ring 0; lifecycle events and recovery are durable and visible. | PLANNED |
| R3A-003 | P0 | Make activities, events, effective configuration revisions and continuation state database-driven. | AP0-M1 plan D2/D4/D7; state/config contracts. | Restart restores/reconciles durable state with no silent loss; configuration values or secure references and provenance, schema versions, and event versions are recorded; PostgreSQL direction in R3 Charter Revision 2 is respected. | PLANNED |
| R3A-004 | P0 | Execute structured versioned state machines. | State Machine and Diagnostic Contract. | The same versioned definition constrains valid runtime transitions and describes diagnostics; invalid transitions are rejected and recorded. | PLANNED |
| R3A-005 | P0 | Provide minimal discoverable module and capability registries. | AP0-M1 plan D5/D6; Module Contract. | Installed/active module and registered capability metadata can be enumerated with contract version, owner, status and health; no invocation is authorized merely by discoverability. | PLANNED |
| R3A-006 | P0 | Externalize and validate operational configuration. | AP0-M1 plan D7; strict bootstrap/config revision schema. | Runtime behavior uses validated external configuration; executable source contains no environment-specific operational values or secrets; invalid required config fails visibly. | PLANNED |
| R3A-007 | P0 | Expose actual state, transitions, timing, progress and exceptions. | R3A-003/004; AP0-M1 plan D8; diagnostic contract. | HMI/diagnostic API matches durable records and explicitly marks unknown, stale and unavailable readings. | PLANNED |
| R3A-008 | P0 | Recover CME/process interruptions and preserve recoverable work. | R3A-002/003/004; AP0-M1 plan D4; module recovery declaration. | Restart produces a durable recovery decision; recoverable work remains open and resumable; no false completion or silent termination. | PLANNED |
| R3A-009 | P0 | Validate AP0 with bounded evidence. | Acceptance policy; isolated runtime and data. | Contract, failure/restart and operational acceptance evidence is captured for the exact revision; production R/3 remains untouched. | PLANNED |
| R3A-010 | P1 | Provide secure Steward operations in AP3 through R3A-owned authentication/session services; may proceed alongside AP1/AP2 where dependencies permit. | AP0 actual diagnostics/API; R3A-owned AP3 auth/gateway and privacy decisions. | R3A login is served by R3A and returns to R3A; `https://192.168.1.155:8311` uses trusted HTTPS with the LAN IP SAN; valid canonical Steward principal receives an R3A session cookie restricted to `/api/v1/steward`; R3A auth remains functional without R3 live services; authorized operations use CME grants; expiry, logout, revocation, and anonymous denial are verified. Remote/mobile scope remains LAN-only until separately authorized. | INTEGRATED — identity association and Steward enrollment pending |
| R3A-011 | P1 | Deliver genuine Engineering execution led operationally by Grace. | AP0; AP1 Grace autonomy/continuity; capability, work-order and evidence contracts. | Real authorized objectives continue through interruption to independently verified deliverable or explicit evidence-backed block. | PLANNED — AP2 |
| R3A-012 | P1 | Support auditable escalated reasoning. | AP0 activity/evidence continuity; AP1 continuation; AP2 work/evidence contracts; provider/privacy policy. | Escalation and return preserve activity identity, evidence, authorization and failure recovery. | PLANNED — AP2 |
| R3A-013 | P1 | Integrate Bitwarden secrets management; reserve future TOTP/YubiKey support. | AP3 auth/provider and machine identity decisions. | Secret values are obtained through approved Bitwarden integration and never committed or emitted in diagnostics; future factors have an approved compatible path. | PLANNED — AP3 |
| R3A-014 | P1 | Deliver mature backup/restore, privacy lifecycle, emergency lockdown and cryptographic erasure; AP0 basic provisions are separate. | AP0 basic backup/recovery; database/key/retention ownership and Steward policy decisions. | Mature operation is recoverable and evidenced; privacy/lockdown/erasure follow approved policy and key lifecycle. | PLANNED — AP6 |
| R3A-015 | P2 | Place Jessica's character-development capability in AP4. | AP0 module/identity contract; HR/privacy decisions. | Jessica's capability is a separately versioned module with authorized, provenance-preserving personnel/canon interactions. | DEFERRED — AP4 |
| R3A-016 | P2 | Place spatial institution, avatars and Quest integration in AP5. | AP0 APIs; actual hardware/runtime and avatar inventory. | Spatial clients present shared actual state and cannot gate desktop/mobile functionality. | DEFERRED — AP5 |
| R3A-017 | P0 | Preserve R3 provenance and coding standards. | `hints/file-provenance.md`; explicit R3A supplement approval for any change. | All controlled files meet headers/predecessor/version requirements; no silent policy relaxation. | PLANNED |
| R3A-018 | P0 | Establish basic AP0 database/configuration backup and restore provisions alongside recovery. | AP0-M1 plan D9; AP0 schema/config; isolated storage. | A consistent backup of disposable AP0 state/config references can be restored and reconciled; evidence records source revision/schema/config and restore result. No production state is used. | PLANNED — AP0 |
| R3A-019 | P1 | Establish Grace autonomy, event-driven continuation, model routing, knowledge use and notifications. | AP0 module/event/recovery/registry contracts; model, knowledge and notification source inventory. | Grace repeatedly receives real events, continues authorized work across interruption, routes models and grounds knowledge through configured providers, and observes notification outcomes or explicit blockers. | PLANNED — AP1 |
| R3A-021 | P2 | Support institutional expansion, onboarding and resident responsibilities, including Jessica's character-development role. | AP0 module/identity; AP1 continuity; HR/personnel and privacy ownership. | Additional institutional responsibilities enter through versioned contracts with verified ownership, authorization and provenance. | PLANNED — AP4 |
| R3A-023 | P3 | Advance future capabilities, mature resilience and approved deferred enhancements. | AP0–AP5 durable contracts; Steward decisions for each deferred capability. | Each addition preserves compatibility, recoverability and truthful status; acceptance is defined per approved work item. | DEFERRED — AP6 |
| R3A-GOV-01 | P0 | Enforce approved roadmap traceability and deviation control. | Steward-approved roadmap revision; exception register. | Every assignment cites the required roadmap fields; no deviation executes until its versioned exception has explicit Steward approval. | PLANNED — governance |
| R3A-GOV-02 | P0 | Coordinate parallel Codex engineering through one milestone GitHub issue and a designated integration authority. | Assignment scope; stable contracts; separate worktrees/branches; Steward roadmap governance. | Each concurrent stream has owner/boundaries, progress/dependency/blocker/handoff reports and issue checkpoints; integration authority controls merge/verification; all work remains roadmap-compliant. | PLANNED — governance |

## Parking lot — unresolved decisions and preflight facts

| ID | Question / idea | Needed before | Owner/authority | Status |
|---|---|---|---|---|
| R3A-L001 | Host-specific availability of systemd, unprivileged service identity and isolated paths for the selected Ring 0 boundary. | AP0-M1 preflight. | Platform owner. | FACT TO VERIFY — design selected in AP0-M1 D1 |
| R3A-L002 | Host PostgreSQL version, peer-auth availability and provisioning for dedicated R3A database/schema/role. | AP0-M1 preflight. | Platform/database owner. | FACT TO VERIFY — design selected in AP0-M1 D2 |
| R3A-L003 | Actual configured capacities and lease/backoff values for a named isolated environment. | AP0 implementation configuration. | CME/platform owner. | CONFIGURATION INPUT — scheduler semantics selected in AP0-M1 D3 |
| R3A-L004 | Domain module's idempotency/reconciliation behavior for its external effects. | Before each module with external side effects. | Module owner. | DEFERRED BY CONTRACT — generic AP0 semantics selected in AP0-M1 D4 |
| R3A-L005 | Artifact signing/trust roots and general package distribution/promotion authority. | Before remote/general module distribution or production activation. | Steward/security owner. | OPEN — AP0 uses local immutable artifact and digest only |
| R3A-L006 | Existing institutional grant authority adapter and policy for individual capabilities. | Before capability invocation implementation. | Existing authority owner / Steward. | OPEN — AP0 registry/write boundary selected in AP0-M1 D6 |
| R3A-L007 | Bitwarden machine identity/authentication and later provider deployment; AP0 bootstrap/config/reload profile is selected. | AP3 secret integration. | Steward/security owner. | OPEN — AP0 config decision in AP0-M1 D7 |
| R3A-L008 | Event payload classification, retention, replay, deletion and cryptographic-erasure semantics. | Before classified/long-retention data; AP6 policy validation. | Steward / privacy and data owners. | OPEN — AP0 minimizes payloads |
| R3A-L009 | Remote diagnostics authentication and external operator clients; AP0 local socket/group boundary selected. | AP3 secure remote operations. | Steward/security owner. | OPEN — AP0 transport decision in AP0-M1 D8 |
| R3A-L010 | Machine-wide CPU/memory isolation and enforcement beyond CME logical resource claims. | Before resource-intensive modules or multi-tenant operation. | Platform owner. | DEFERRED — AP0 boundary selected in AP0-M1 D3 |
| R3A-L011 | Emergency lockdown semantics, emergency authority, unlock path and operator continuity. | Security design before external/production operation. | Steward. | OPEN |
| R3A-L012 | Cryptographic erasure key ownership, key rotation, backups and residual metadata policy. | AP6 detailed design. | Steward / privacy and security owners. | OPEN |
| R3A-L013 | Future TOTP/YubiKey factors and account recovery policy. | AP3/AP6 implementation. | Steward. | OPEN |
| R3A-L014 | Coordination issue and integration authority for active AP0-M1 planning. | For this milestone. | Steward. | RESOLVED — Issue #42; Steward is integration authority until explicitly reassigned there |
| R3A-L015 | Initial canonical Steward-to-R3A-principal association and fresh credential enrollment/recovery procedure; credential-hash migration is excluded. | Before real account activation: verified authoritative identity, governed association, Steward-controlled enrollment, and live acceptance. | HR authority, Remote Access #49, Website #51, Coordinator #56, Steward. | APPROVED FOR IMPLEMENTATION — Steward approved the identity-provenance and fresh-enrollment policy on 2026-11-09. No account or credential is active until verified and the Steward completes enrollment. |

The AP0-M1 selections and dependency-ordered running milestone are in [First Living Water Wheel Technical Plan](R3A_AP0_M1_FIRST_LIVING_WATER_WHEEL_PLAN.md). “Selected” means planning choice, not implemented or operational. Environmental facts and deferred policy decisions remain open with the owners and gates above.
