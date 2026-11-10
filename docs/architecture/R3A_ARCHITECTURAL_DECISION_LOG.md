<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ARCHITECTURAL_DECISION_LOG.md
Component: R3A-DECISION-LOG
File Revision: 1.0.3
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
Changed: 2026-11-06T05:18:48Z | AP0-M1-PLAN | Codex GPT-6 | Record bounded AP0-M1 technical selections without elevating them to Steward policy decisions.
Changed: 2026-11-10T00:17:40Z | R3A-MODULARITY-DECISIONS | Codex GPT-6 | Record Steward-authorized generic resident and durable-handler architecture decisions as AD-024.
Supersedes: None.
Contracts: R3A Architecture Charter; roadmap; AP0 specification; module and state contracts.
Tests: Not run; documentation only.
History/Predecessor: Git blob cb1fe6c4336c4623771df26b0a1c59afb11f9d90 at baseline commit f629a570d904719d1f13d2ceaddff7a2af2ce00d; immediate predecessor at commit 87d868d7e2a64da1d58ca71eb9899d61b5a1d2b2 (file blob 8ed6722f02fc50a6aae6dae4f2a798aa2cc728b5).
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
| AD-020 | PostgreSQL is the intended foundation for R3 durable structured records/history. | INHERITED — Steward-approved R3 Charter Revision 2, §11. | AP0 shall align with PostgreSQL; AP0-M1 selects an isolated database/schema, ordered SQL migrations and CME-owned async pool. Host version/provisioning are preflight facts. |
| AD-021 | Existing R/3 production services/data are not modified by R3A documentation or implementation work absent separate authorization. | DIRECTED — scope and development constraints. | Isolated development only; no production migration or deployment in this task. |
| AD-022 | The Steward-approved, versioned Master Roadmap is authoritative for every R3A assignment; deviations require a versioned exception and explicit Steward approval before execution. | DIRECTED — R3A Baseline 1.0 Correction, §2. | Assignments identify approved revision, phase/milestone, requirement IDs, authorized scope, acceptance criteria and approved exception (or none). Until Roadmap Baseline 1.0 is approved, no implementation is authorized under it. |
| AD-023 | Parallel Codex work is coordinated through a designated GitHub issue per active milestone, with explicit workstreams, stable contracts, named integration authority, checkpoints and controlled merge/verification. | DIRECTED — R3A Baseline 1.0 Correction, §3 (R3A-GOV-02). | AP0 remains primarily sequential; parallel work is allowed only when contracts are stable and each session remains roadmap-compliant. The issue cannot override Steward authority or the Master Roadmap. |
| AD-024 | R3A shall preserve the existing capability-provider architecture and support independently developed resident executors and durable workflow-handler modules through generic, versioned bindings and existing CME registry/lifecycle/scheduler/persistence/authorization mechanisms. Normal compatible module registration, configuration, activation, deactivation, replacement and removal do not require restarting CME or Ring 0. Current same-UID child processes are process/protocol separation, not an OS security boundary. | DIRECTED — Steward Directive “R3A Modularity Architecture Decisions,” 2026-11-09; accepted Auditor verification commit `87d868d`. | Define resident binding against existing identity/HR authority; define a generic activity-handler contract by extending existing intake/scheduler/persistence/lifecycle; preserve provider interfaces and compatibility behavior; no hardcoded resident/domain branches, duplicate HR authority, scheduler, registry, or state store; no wholesale CME/Ring 0 rewrite. Stronger sandboxing requires separate threat model/approval. See [Modularity Compliance Specification v1](R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md). |

## AP0-M1 engineering selections, not additional Steward policy decisions

| ID | AP0-M1 engineering selection | Why recorded | Selection and remaining boundary |
|---|---|---|---|
| AD-P01 | Dedicated unprivileged systemd Ring 0 service; Ring 0 owns a CME child lifecycle; CME owns module scheduling. | Directly realizes AD-001–003 with existing single-host service operations; D1/D3 in AP0-M1 plan. | Selected for AP0-M1 planning; M1.0 verifies actual host support. Separate implementation authorization remains required. |
| AD-P02 | Versioned immutable JSON state-machine definitions stored in PostgreSQL and consumed by transition validation and read-only diagnostics. | Directly realizes AD-005/006; D2/D4/D8 in AP0-M1 plan. | Encoding and AP0 compatibility behavior selected; data privacy/retention policy remains open. |
| AD-P03 | Treat registry discovery, authorization and execution as separate concerns; CME is the sole lifecycle/observation registry writer. | Preserves R3 authority model; D5/D6 in AP0-M1 plan. | AP0 write/ownership boundary selected; Steward-owned authorization grants and policy remain unchanged. |
| AD-P04 | Dedicated PostgreSQL database/schema, ordered transactional SQL migrations, and CME-owned async connection pool. | Aligns AP0 with AD-020 and AP0-004; D2. | Selected for isolated AP0-M1 planning; host version, role and peer auth are preflight facts. |
| AD-P05 | At-least-once activity execution with stable idempotency keys, durable leases/checkpoints, transactional state+event updates, and explicit blocked outcome for uncertain external effects. | Satisfies AP0-004/006 without claiming impossible exactly-once semantics; D4. | Selected for generic AP0 activity contract; domain-specific effect reconciliation remains module responsibility. |
| AD-P06 | Child-process modules over versioned local JSON-lines Unix socket; immutable local artifact manifest/digest; unknown compatibility denies activation. | Satisfies AD-004 and AP0-007 without dynamic in-process unload; D5. | Selected for AP0-M1; current source also implements dependency range evaluation and graph validation. Package signing/trust roots and general artifact distribution remain separate security decisions. |
| AD-P07 | External validated bootstrap JSON plus immutable PostgreSQL operational config revisions; explicit safe-boundary activation; secret references only. | Satisfies AD-008/AP0-009 and accommodates AP3 Bitwarden; D7. | Selected for AP0-M1; Bitwarden machine-auth and secret lifecycle policy remain open for AP3. |
| AD-P08 | Local read-only diagnostics CLI/socket with separate operator group and read-only DB access; stale/unavailable are first-class. | Satisfies AD-009/AP0-010; D8. | Selected for AP0; external transport/auth remains AP3. |
| AD-P09 | Operator-invoked `pg_dump` plus non-secret config references, restored to a separate isolated DB. | Satisfies AP0-013 with bounded AP0 recovery scope; D9. | Selected for basic AP0 provision; mature backup schedule, retention and off-host DR remain AP6. |

## Open decisions

The AP phase sequencing in this revision follows the Steward's correction. The prior roadmap revision assigned remote Steward access to AP1 and escalated reasoning to AP3; those phase placements are superseded for roadmap ownership by this correction, with remote Steward/mobile access in AP3 and escalated reasoning in AP2. No technical conflict preventing the corrected ordering was identified. AP3 work may run in parallel with AP1/AP2 only where dependencies permit.

AP0-M1 implementation choices are detailed in [First Living Water Wheel Technical Plan](R3A_AP0_M1_FIRST_LIVING_WATER_WHEEL_PLAN.md). They are engineering selections for planning and do not claim production use or deployment. The [modularity specification](R3A_MODULARITY_COMPLIANCE_SPECIFICATION_V1.md) now records the Steward-approved resident and durable-handler obligations. Stronger process isolation remains open pending a threat model. The roadmap exception register contains no exception for these clarifications; see it for any future phase/scope deviation.
