<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md
Component: R3A-MASTER-ROADMAP
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Sequence R3A architecture and delivery phases AP0 through AP6.
Execution Model: N/A; planning artifact.
Observability: Phase status and acceptance evidence tracked in R3A punch list.
Dependencies: Steward Directive — R3A Architecture Baseline and AP0 Specification; R3A Architecture Charter.
Authority: Steward directive; phase details beyond stated scope are planning proposals, not authorization to implement.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial master roadmap.
Supersedes: None.
Contracts: R3A Architecture Charter; R3A Punch List and Parking Lot; AP0 Technical Specification.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# R3A Master Roadmap — AP0–AP6

**Status:** Planned. AP0 specification is authorized; implementation is not. Later phase contents are sequencing proposals that preserve the Steward's stated priorities and remain subject to change.

| Phase | Requirement IDs | Objective and scope | Dependencies | Acceptance criteria | Status |
|---|---|---|---|---|---|
| **AP0 — Institutional foundation** | R3A-001–009 | Ring 0 supervisor; independently restartable CME; durable database-backed state/events; structured state-machine execution; minimal module and capability registries; external configuration; truthful diagnostics; restart/recovery; bounded evidence-based validation. Excludes Engineering workflow, Jessica/character development, 3D, and advanced security administration. | Architecture charter; contract/state definitions; isolated dev data and configuration; production isolation. PostgreSQL direction from approved R3 Charter Revision 2 applies. | Isolated instance starts from external config; Ring 0 supervises CME lifecycle; CME can stop/restart independently while persistent state/events reconcile; registry and state definitions drive execution and diagnostics; observable failures/recovery are truthful; acceptance evidence captured without altering production. See AP0 spec. | PLANNED |
| **AP1 — Secure Steward operations and institution interface** | R3A-010, R3A-013 | Authenticated, encrypted remote Steward operation; operational control/HMI over real APIs; access/secret integration foundation around Bitwarden; protect privacy and expose status/diagnostics. Future TOTP/YubiKey integration points are reserved. | AP0 stable contracts and diagnostics; verified network/deployment ownership; authentication and privacy decisions. | Steward can remotely inspect actual health and perform explicitly authorized operations; unauthorized access is denied; no secrets leak through configuration, logs or HMI; stale/unavailable status is explicit. | PLANNED |
| **AP2 — Engineering execution and independent delivery** | R3A-011 | Grace-led Engineering work management; persistent tasks, concurrency, capability discovery, execution adapters, recovery, artifacts and independent verification. Keep job/domain state distinct from generic CME scheduling. | AP0 lifecycle/event/resource contracts; AP1 operational access as needed; work-order and verifier contracts; existing grants/capability integration. | Grace can autonomously coordinate an authorized real work order; concurrent/dependent work survives interruption; an independent verifier can reject or accept against substantive criteria; deliverable and evidence lineage are durable. | PLANNED |
| **AP3 — Escalated reasoning and institutional learning** | R3A-012 | Auditable reasoning escalation/handoff; context/evidence continuity; institutional learning signals and operational improvement without replacing resident judgment. | AP0 durable event/continuation contracts; AP2 work/evidence lineage; external reasoning/provider and privacy decisions. | Authorized escalation can be requested, resumed and traced end-to-end; external results retain source and provenance; unavailable escalation does not silently terminate the originating activity. | PLANNED |
| **AP4 — Jessica character development** | R3A-015 | Jessica's resident character-development capability, integrated with authoritative HR/personnel ownership, identity, privacy and resident onboarding. | AP0 module lifecycle and identity contracts; relevant HR/personnel and privacy decisions; character-canon ownership. | Jessica can perform authorized character-development work; changes have provenance and correct HR/character ownership; protected records are not exposed beyond authorization. | PLANNED |
| **AP5 — Spatial / Quest presentation** | R3A-016 | Spatial and Meta Quest presentation of shared authoritative state, residents and diagnostics. Preserve functional desktop/mobile interfaces; spatial UI is a client. | Stable AP0 APIs and AP1 HMI semantics; spatial/accessibility design; hardware and runtime inventory. | Spatial status agrees with source records and indicates unknown/stale state; core institutional operation remains available without spatial services. | PLANNED |
| **AP6 — Institutional resilience and extension** | R3A-014 | Mature backup/restore, privacy lifecycle, emergency lockdown, cryptographic erasure, reliability, operational scaling and broader institutional expansion. AP0 must accommodate these data/security properties from the outset. | Durable ownership/schema lineage from AP0; security design from AP1; operational evidence from AP2–AP5; Steward policy decisions. | Restore and recovery are evidenced; lockdown is enforceable and observable; privacy/erasure behavior is validated against approved policy and key lifecycle; expansion preserves contract compatibility and operational truth. | PLANNED |

## Phase gates and ordering

Phases are capability groupings, not calendar promises. AP0 is the required foundation. Secure remote Steward operation is an early requirement and must be completed before remote production administration. AP2 and AP3 are early institutional priorities after AP0, with ordering adjusted only by documented authority and dependency evidence. AP4 and AP5 stay in their named phases. Backup, privacy, lockdown and cryptographic-erasure constraints must shape AP0 data/event design even though their complete operational workflows are AP6 scope.

No phase is complete because documentation, a mock, a one-time demonstration, a code artifact, or tests alone exist. Apply the status vocabulary and evidence bar in the [charter](R3A_ARCHITECTURE_CHARTER.md) and [acceptance policy](R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md).
