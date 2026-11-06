<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ARCHITECTURAL_DECISION_LOG.md
Component: R3A-DECISION-LOG
File Revision: 1.0.1
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Record R3A architectural decisions and distinguish directives from unresolved proposals.
Execution Model: N/A; decision record.
Observability: Git history and decision status.
Dependencies: Steward Directive — R3A Architecture Baseline and AP0 Specification; R3 Charter Revision 2; Phase 0A investigation; modular architecture audit commit 7e6d8d0.
Authority: Steward directive for confirmed R3A decisions; approved R3 Charter Revision 2 for inherited institutional requirements.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial architectural decision log.
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Record corrected roadmap priorities and mandatory governance.
Changed: 2026-11-06T05:03:56Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Clarify corrected AP ownership and versioned exception tracking.
Supersedes: None.
Contracts: R3A Architecture Charter; roadmap; AP0 specification; module and state contracts.
Tests: Not run; documentation only.
History/Predecessor: Git blob b44e2a30825c86074424469bd7d8481036edad46 at baseline commit eca8b73de0fe5bd67bdb0f0b8b0a92470b07b530.
-->
# R3A Architectural Decision Log

**Status key:** `DIRECTED` means explicitly stated in the Steward's R3A directive; `INHERITED` means already established by an approved R3 charter/governance source; `PROPOSED` means a specification detail for review, not an inferred Steward decision; `OPEN` means unresolved.

## Confirmed decisions

| ID | Decision | Status / authority | Consequence |
|---|---|---|---|
| AD-001 | Ring 0 is a minimal, persistent supervisor. | DIRECTED — R3A directive, item 1. | Keep core responsibilities narrow; CME and modules own their declared work. |
| AD-002 | CME is separately supervised and restartable. | DIRECTED — item 2. | CME failure/restart is independent of Ring 0 lifecycle and must be durable/diagnosable. |
| AD-003 | CME supervises resource allocation, scheduling, progress and exceptions; Grace investigates and directs institutional corrective action. | DIRECTED — item 3. | Preserve separate operational control and resident institutional judgment. |
| AD-004 | Modules have versioned contracts and can be installed, activated, stopped and replaced without restarting the core. | DIRECTED — item 4. | Lifecycle/version compatibility is a core contract. |
| AD-005 | Structured, versioned state-machine definitions drive both execution and diagnostic interfaces. | DIRECTED — item 5. | Runtime and HMI cannot maintain divergent state catalogs. |
| AD-006 | Persistent activities, events, configuration and continuation state are database-driven. | DIRECTED — item 6. | Durable records are authoritative; process memory is not the sole state. |
| AD-007 | Institutional resources/capabilities are registered and discoverable. | DIRECTED — item 7. | Registry visibility does not by itself grant invocation authority. |
| AD-008 | Operational configuration stays outside executable source. | DIRECTED — item 8; consistent with R3 bootstrap's validated JSON guidance. | Config schemas, ownership and reload details remain to be defined. |
| AD-009 | HMI exposes genuine state, transitions, timing, progress and exceptions. | DIRECTED — item 9; inherited from R3 Charter Revision 2. | Unknown, stale and unavailable remain explicit; no mock telemetry. |
| AD-010 | Autonomy is primary; recoverable blockages do not silently terminate activities. | DIRECTED — item 10; consistent with R3 bootstrap. | Preserve continuation and evidence-backed block outcomes within authority. |
| AD-011 | Completion needs actual deliverable evidence; demos/mocks do not establish operational completion. | DIRECTED — item 11; consistent with R3 governance. | Use substantive acceptance and exact revision/environment evidence. |
| AD-012 | Testing is risk-based, bounded and proportional. | DIRECTED — item 12. | Do not turn validation into blanket gates or expand tests in this documentation task. |
| AD-013 | Engineering and escalated reasoning are early institutional priorities. | DIRECTED — item 13; Engineering is a principal output in R3 Charter Revision 2. | Grace autonomy/event continuity is AP1; Engineering, independent verification and escalated reasoning are AP2. |
| AD-014 | Secure remote Steward operation is an early requirement; mobile access and authentication are included. | DIRECTED — item 14 and corrected roadmap directive; inherited remote-access direction in R3 Charter Revision 2. | Assigned to AP3; may proceed alongside AP1/AP2 when dependencies permit. Avoid exposing internal services directly. |
| AD-015 | Secrets management uses Bitwarden; future TOTP/YubiKey must be accommodated. | DIRECTED — item 15. | Integration/provider and machine-auth details remain open. |
| AD-016 | Architecture accommodates backup, privacy, emergency lockdown and cryptographic erasure. | DIRECTED — item 16; corrected roadmap directive; backup/privacy direction inherited from R3 Charter Revision 2. | Basic recovery and backup provisions are AP0; mature backup, privacy lifecycle, lockdown and cryptographic erasure are AP6; design constraints apply from AP0. |
| AD-017 | Jessica character-development capability belongs in AP4, within broader institutional expansion. | DIRECTED — item 17 and corrected roadmap directive. | AP4 owns institutional expansion, including Jessica's capability; excluded from AP0. |
| AD-018 | Spatial institution, avatars and Quest presentation belong in AP5 and cannot block functional interfaces. | DIRECTED — item 18 and corrected roadmap directive; Quest 2 direction inherited from R3 Charter Revision 2. | AP5 owns spatial presentation over common state; later AP6 capabilities do not gate AP5 or core functional interfaces. |
| AD-019 | Existing R3 coding and provenance standards remain unless an explicit R3A supplement is approved. | DIRECTED — item 19. | `hints/file-provenance.md` governs this documentation. |
| AD-020 | PostgreSQL is the intended foundation for R3 durable structured records/history. | INHERITED — Steward-approved R3 Charter Revision 2, §11. | AP0 shall align with PostgreSQL; deployment topology, schema and migration remain open. |
| AD-021 | Existing R/3 production services/data are not modified by R3A documentation or implementation work absent separate authorization. | DIRECTED — scope and development constraints. | Isolated development only; no production migration or deployment in this task. |
| AD-022 | The Steward-approved, versioned Master Roadmap is authoritative for every R3A assignment; deviations require a versioned exception and explicit Steward approval before execution. | DIRECTED — R3A Baseline 1.0 Correction, §2. | Assignments identify approved revision, phase/milestone, requirement IDs, authorized scope, acceptance criteria and approved exception (or none). Until Roadmap Baseline 1.0 is approved, no implementation is authorized under it. |
| AD-023 | Parallel Codex work is coordinated through a designated GitHub issue per active milestone, with explicit workstreams, stable contracts, named integration authority, checkpoints and controlled merge/verification. | DIRECTED — R3A Baseline 1.0 Correction, §3 (R3A-GOV-02). | AP0 remains primarily sequential; parallel work is allowed only when contracts are stable and each session remains roadmap-compliant. The issue cannot override Steward authority or the Master Roadmap. |

## Specification proposals, not additional Steward decisions

| ID | Proposal | Why recorded | Decision needed |
|---|---|---|---|
| AD-P01 | Model Ring 0 and CME as separately observable process lifecycles, with Ring 0 supervising CME and CME owning module scheduling. | Directly realizes AD-001–003. | Approve process/host service ownership and Ring 0's own supervision boundary before implementation. |
| AD-P02 | Keep state-machine definitions as versioned data consumed by both runtime and diagnostic/API projections. | Directly realizes AD-005. | Select encoding, compatibility policy and state-definition publication process. |
| AD-P03 | Treat registry discovery, authorization, and execution as separate concerns. | Preserves existing R3 authority model and avoids implicit grants. | Confirm registry/auth interfaces and ownership. |

## Open decisions

The AP phase sequencing in this revision follows the Steward's correction. The prior roadmap revision assigned remote Steward access to AP1 and escalated reasoning to AP3; those phase placements are superseded for roadmap ownership by this correction, with remote Steward/mobile access in AP3 and escalated reasoning in AP2. No technical conflict preventing the corrected ordering was identified. AP3 work may run in parallel with AP1/AP2 only where dependencies permit.

See [R3A Punch List and Parking Lot](R3A_PUNCH_LIST_AND_PARKING_LOT.md#parking-lot--unresolved-not-rejected) for remaining technical decisions, including database deployment/migrations; process manager; scheduling/resource policy; module artifact trust/compatibility; configuration reload/secrets; event retention/privacy/erasure; diagnostics transport/auth; and recovery/idempotency semantics. See the [roadmap exception register](R3A_ROADMAP_EXCEPTION_REGISTER.md) for versioned deviations; none is currently approved.
