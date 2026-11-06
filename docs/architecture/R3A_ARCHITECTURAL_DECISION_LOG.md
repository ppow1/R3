<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ARCHITECTURAL_DECISION_LOG.md
Component: R3A-DECISION-LOG
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Record R3A architectural decisions and distinguish directives from unresolved proposals.
Execution Model: N/A; decision record.
Observability: Git history and decision status.
Dependencies: Steward Directive — R3A Architecture Baseline and AP0 Specification; R3 Charter Revision 2; Phase 0A investigation; modular architecture audit commit 7e6d8d0.
Authority: Steward directive for confirmed R3A decisions; approved R3 Charter Revision 2 for inherited institutional requirements.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial architectural decision log.
Supersedes: None.
Contracts: R3A Architecture Charter; roadmap; AP0 specification; module and state contracts.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
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
| AD-013 | Engineering and escalated reasoning are early institutional priorities. | DIRECTED — item 13; Engineering is a principal output in R3 Charter Revision 2. | AP2/AP3 are early after AP0, subject to dependencies and evidence. |
| AD-014 | Secure remote Steward operation is an early requirement. | DIRECTED — item 14; inherited remote-access direction in R3 Charter Revision 2. | AP1 is early; avoid exposing internal services directly. |
| AD-015 | Secrets management uses Bitwarden; future TOTP/YubiKey must be accommodated. | DIRECTED — item 15. | Integration/provider and machine-auth details remain open. |
| AD-016 | Architecture accommodates backup, privacy, emergency lockdown and cryptographic erasure. | DIRECTED — item 16; backup/privacy direction inherited from R3 Charter Revision 2. | Design constraints begin in AP0; full capabilities are later work. |
| AD-017 | Jessica character-development capability belongs in AP4. | DIRECTED — item 17. | Excluded from AP0. |
| AD-018 | Spatial/Quest presentation belongs in AP5 and cannot block functional interfaces. | DIRECTED — item 18; Quest 2 direction inherited from R3 Charter Revision 2. | Spatial is a later client over common state. |
| AD-019 | Existing R3 coding and provenance standards remain unless an explicit R3A supplement is approved. | DIRECTED — item 19. | `hints/file-provenance.md` governs this documentation. |
| AD-020 | PostgreSQL is the intended foundation for R3 durable structured records/history. | INHERITED — Steward-approved R3 Charter Revision 2, §11. | AP0 shall align with PostgreSQL; deployment topology, schema and migration remain open. |
| AD-021 | Existing R/3 production services/data are not modified by R3A documentation or implementation work absent separate authorization. | DIRECTED — scope and development constraints. | Isolated development only; no production migration or deployment in this task. |

## Specification proposals, not additional Steward decisions

| ID | Proposal | Why recorded | Decision needed |
|---|---|---|---|
| AD-P01 | Model Ring 0 and CME as separately observable process lifecycles, with Ring 0 supervising CME and CME owning module scheduling. | Directly realizes AD-001–003. | Approve process/host service ownership and Ring 0's own supervision boundary before implementation. |
| AD-P02 | Keep state-machine definitions as versioned data consumed by both runtime and diagnostic/API projections. | Directly realizes AD-005. | Select encoding, compatibility policy and state-definition publication process. |
| AD-P03 | Treat registry discovery, authorization, and execution as separate concerns. | Preserves existing R3 authority model and avoids implicit grants. | Confirm registry/auth interfaces and ownership. |

## Open decisions

See [R3A Punch List and Parking Lot](R3A_PUNCH_LIST_AND_PARKING_LOT.md#parking-lot--unresolved-not-rejected). In particular, database deployment/migrations; process manager; scheduling and resource policy; module artifact trust and compatibility; configuration reload/secrets; event retention/privacy/erasure; diagnostics transport/auth; and recovery/idempotency semantics remain unsettled. This log records no decision on those matters.
