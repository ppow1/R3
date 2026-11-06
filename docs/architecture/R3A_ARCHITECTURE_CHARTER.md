<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ARCHITECTURE_CHARTER.md
Component: R3A-ARCHITECTURE-CHARTER
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Establish the authorized R3A architecture baseline and requirement vocabulary.
Execution Model: N/A; documentation and specification.
Observability: Git revision and linked evidence documents.
Dependencies: Steward Directive — R3A Architecture Baseline and AP0 Specification; approved R3 Charter Revision 2; AI_HINTS.md; hints/file-provenance.md.
Authority: Steward directive; this document supplements rather than silently supersedes the approved R3 Charter Revision 2.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial R3A baseline.
Supersedes: None.
Contracts: R3A master roadmap, AP0 specification, module lifecycle and contract specification, state machine and diagnostic contract, bounded testing and acceptance policy.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# R3A Architecture Charter

**Status:** Authorized architectural baseline; implementation not authorized by this document.
**Repository/worktree:** `ppow1/R3`, isolated worktree `/home/admin1/r3a-phase0`, branch `engineering/r3a-phase0-20261105`.
**Purpose:** Establish a modular, autonomous institutional runtime that can evolve independently without interrupting production R/3.

## Authority and inherited intent

The Steward Directive — R3A Architecture Baseline and AP0 Specification authorizes documentation and specification only. Approved R3 Charter Revision 2 remains the institutional charter. This baseline refines the runtime direction for R3A; it does not repeal charter responsibilities, past approvals, or operational authority. Where this baseline and an earlier approved document appear inconsistent, record the conflict and seek Steward resolution; do not silently rewrite history.

The baseline preserves these sources:

| Source | Verified location/state in this investigation | Preserved intent |
|---|---|---|
| `AI_HINTS.md` | Present at branch HEAD | Keep orientation concise; honor provenance, charter, local-evidence-first, autonomy within granted authority, and actual operational acceptance. |
| `hints/file-provenance.md` | Present at branch HEAD | Every controlled file has provenance; retain real predecessor references and increment revision on edits. |
| `hints/development-bootstrap.md` | Present at branch HEAD | Inspect the true baseline; prefer documented configuration; do not add silent limits or substitute a demo for requested operation. |
| `hints/development-governance.md` | Present at branch HEAD | Isolated work, proportional checks, honest evidence, deployment only when authorized. |
| `hints/development-execution.md` | Present at branch HEAD | Authorized command gateway first for machine actions; no runtime action is authorized in this directive. |
| `docs/architecture/R3A_PHASE_0A_TECHNICAL_INVESTIGATION.md` | Present at branch HEAD | Records source-level loop and CME findings against deployed integration source `8ab4b2a` and audit `7e6d8d0`. |
| `docs/architecture/R3_MODULAR_ARCHITECTURE_AUDIT_2026-11-05.md` | Not in this branch's tree; recovered from audit commit `7e6d8d053b97837866470db4549331d839bf8ba8` and the dedicated audit worktree | Prior architecture inventory and assessment; used as a baseline, not repeated or silently adopted as R3A decisions. |
| `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md` | Present at branch HEAD; Steward-approved 2026-10-31 | Institutional mission, roles, PostgreSQL direction, CME responsibilities, truthful HMI, autonomy, privacy, backup and spatial goals. |
| `docs/IMPLEMENTATION_HANDOFF.md`, `docs/PUNCH_LIST.md`, `docs/PARKING_LOT.md` | Present at branch HEAD | Capability-first institution, durable state, pending concerns and intentionally deferred ideas. |

No missing required source material was found in repository objects. The modular audit is absent from the current branch tree, so its cited commit is the retrievable historical path. Existing R3 punch-list and parking-lot entries remain source inputs; this R3A list supplements them and does not close them.

## Mission and operating principles

R3A is the institutional execution foundation for persistent resident activity. Its leading product objective is for Grace to manage and execute real Engineering work, recover interruptions, discover and use institutionally available authorized capabilities, escalate reasoning when needed, and deliver results supported by independent evidence with minimal Steward intervention.

R3A SHALL:

1. Keep Ring 0 as a minimal persistent supervisor.
2. Run CME as a separately supervised, independently restartable component. CME supervises resource allocation, scheduling, progress and exceptions; Grace investigates and directs institutional corrective action.
3. Support versioned module contracts and install, activate, stop and replace operations without restarting the core.
4. Use structured, versioned state-machine definitions as the source for both execution and diagnostics.
5. Store persistent activities, events, configuration references and continuation state in database-backed institutional records.
6. Register and expose discoverable institution resources and capabilities.
7. Keep operational configuration outside executable source.
8. Expose actual state, transitions, timings, progress and exceptions in the HMI; unknown or stale values remain explicit.
9. Preserve activity through recoverable blockages. A recoverable failure cannot silently discard or terminate its activity.
10. Require actual deliverable evidence for completion. Mocks, demonstrations, source presence and successful API responses alone are not operational completion.
11. Treat autonomy as the primary posture within assigned authority; avoid unnecessary Steward gates and developer-imposed limits.
12. Apply risk-based, bounded validation proportional to changed behavior without weakening substantive acceptance.
13. Make Engineering and escalated reasoning early institutional priorities.
14. Treat secure remote Steward operation as an early requirement.
15. Plan secrets integration around Bitwarden; future TOTP and YubiKey authentication must fit without embedding secrets in source/configuration.
16. Accommodate backup/restore, privacy controls, emergency lockdown and cryptographic erasure architecturally.
17. Place Jessica's resident character-development capability in AP4.
18. Place spatial/Quest presentation in AP5; it cannot gate functional interfaces.
19. Retain R3 coding and provenance standards unless the Steward explicitly approves an R3A supplement.

## Scope and ownership

R3A owns the new institutional runtime architecture and its durable execution contracts. It does not imply authorization to alter, migrate, stop or deploy production R/3. Existing R/3 services, data, grants, identities and behavior are protected inputs until a separate activation and migration authority is given.

Ring 0 supervises CME process lifecycle and exposes core health. CME coordinates registered execution and resource scheduling and records progress/exceptions. Modules own their domain behavior and state under declared contracts. Grace has operational coordination/corrective-action responsibility within her authority; CME does not replace Grace's institutional judgment. The HMI observes authoritative runtime records and does not fabricate activity.

## Status vocabulary

Every R3A requirement and deliverable uses one of these labels, with evidence and revision when applicable:

| Label | Meaning |
|---|---|
| **PLANNED** | Requirement or design is recorded; no implementation claim. |
| **IMPLEMENTED** | Code/configuration exists at a named revision; behavior may still be unverified. |
| **VERIFIED** | The defined acceptance evidence was observed against a named revision and environment. |
| **OPERATIONAL** | The verified capability is active in its intended operating environment, with date, revision and health evidence. |
| **BLOCKED** | A specific dependency, failure or authority decision prevents progress; record evidence and owner. |
| **DEFERRED** | Deliberately assigned to a later AP or parking lot; not rejected. |

Documentation delivery does not advance an executable requirement beyond PLANNED. A passing test does not by itself establish OPERATIONAL.

## Baseline documents

- [Master Roadmap AP0–AP6](R3A_MASTER_ROADMAP_AP0_AP6.md)
- [R3A Punch List and Parking Lot](R3A_PUNCH_LIST_AND_PARKING_LOT.md)
- [Architectural Decision Log](R3A_ARCHITECTURAL_DECISION_LOG.md)
- [AP0 Technical Specification](R3A_AP0_TECHNICAL_SPECIFICATION.md)
- [Module Lifecycle and Contract Specification](R3A_MODULE_LIFECYCLE_AND_CONTRACT_SPEC.md)
- [State Machine and Diagnostic Contract](R3A_STATE_MACHINE_AND_DIAGNOSTIC_CONTRACT.md)
- [Bounded Testing and Acceptance Policy](R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md)
- [Phase 0A technical investigation](R3A_PHASE_0A_TECHNICAL_INVESTIGATION.md) (source-level findings; report commit `9adc3d7`).
- Modular architecture audit at commit `7e6d8d053b97837866470db4549331d839bf8ba8`, file `docs/architecture/R3_MODULAR_ARCHITECTURE_AUDIT_2026-11-05.md` (not present in this branch tree; retained in repository history/audit worktree).
