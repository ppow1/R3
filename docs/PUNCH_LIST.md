<!--
R3 CONTROLLED DOCUMENT
File: docs/PUNCH_LIST.md
Component: DOCS-PUNCH-LIST-MD
File Revision: 1.0.1
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 project governance and planning reference
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Track Comms grant discovery and failure recovery
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob 0e66e1873cd2827a65b3c19dc095f98fdcd5fc6b
-->
# R3 — Punch List

Status: initial working list; items are requirements or investigations, not verified implementations.

| ID | Priority | Item | Acceptance / next action | Status |
|---|---|---|---|---|
| R3-P001 | P0 | Resident roster and onboarding | Reconcile full Estate roster; Evelyn (not Ellen); Vicky Engineering Manager; Chloe Chief Architect; Alyssa replaces Alfred; Jen is Jennifer | Open |
| R3-P002 | P0 | Resident communications | Durable Steward↔resident and resident↔resident chat, messages, email-style correspondence, tracing | Open |
| R3-P003 | P0 | CME resident participation | Every resident has identity, state, heartbeat/scheduling slot without requiring always-on inference | Open |
| R3-P004 | P0 | Capability/resource registry | First-class searchable registry of tools, services, models, hosts, scripts, resources and access grants | Open |
| R3-P005 | P0 | Fast responsive chat | Inspect R2 implementation; preserve verified low-latency mechanisms; evaluate Residential Gateway rather than assume reuse | Open |
| R3-P006 | P0 | Notification triage | Audit ntfy event sources, deduplication, severity, routing, user preferences and unexplained stall notices; no change until observed | Open |
| R3-P007 | P0 | PostgreSQL V3 design | Separate V3 database; durable messages, resident states, work orders, historian, audit | Open |
| R3-P008 | P1 | Voice-first interaction | Win+H dictation and paste baseline; robust handling of dictated text; evaluate microphone paths | Open |
| R3-P009 | P1 | Escalated reasoning | ChatGPT-based consultation for Chloe/Jessica and authorized residents; auditable results | Open |
| R3-P010 | P1 | Continuous learning | Separate episodic history, durable resident memory, lessons and reviewed knowledge; assess Honcho | Open |
| R3-P011 | P1 | Engineering Foundry management | Vicky owns work orders and rework; tools/Python execute, not replace manager | Open |
| R3-P012 | P1 | HMI and telemetry | Live operational state, minimizable overlays, resource indicators, drilldowns, historian | Open |
| R3-P013 | P1 | R2 reuse inventory | Verify which services and UI mechanisms are actually reusable | Open |
| R3-P014 | P1 | Charter Revision 2 | Incorporate institution-wide onboarding, roles, CME, registry, comms, governance and HMI | Open |

| R3-P015 | P0 | Jessica–Helen character/personnel workflow | Jessica owns resident character design and evolving canon; Helen HR owns authoritative personnel files; define what is shared, approvals, provenance, versioning, and access boundaries | Open |
| R3-P016 | P1 | Progressive character onboarding | Seed each resident with a basic definition and expand character continuity over time; no requirement to complete every character at launch | Open |
| R3-P017 | P1 | Resident communication profile settings | Define master defaults and per-resident overrides for verbosity, initiative, interests, tone and roleplay latitude; align with Jessica character canon and Helen personnel files; verify settings affect behavior without compromising professional competence | Open |
| R3-P018 | P1 | Epistemic classification and audit prototype | Test opt-in residents; classify text spans (inline, async or hybrid), retain provenance and original labels, independently audit category correctness, show pending/pass/mismatch/indeterminate message status; measure response and audit latency | Open |
| R3-P019 | P1 | Epistemic monitoring settings and assurance policies | Build master enable and per-resident controls, evidence-class assurance thresholds, selective substantive verification, alarm severity, acknowledgement/escalation policy; never equate confidence percentage with permission to mislabel facts | Open |
| R3-P020 | P1 | Late-arriving chat audit alerts | Persist mismatch alarms when user has scrolled away; whole-message warning, striped disputed spans, consolidated alert count, jump-to-source and return navigation, acknowledge versus resolve, historian trail | Open |


| R3-P019 | P0 | Riverview Comms failure capture and grant recovery | [R3-COMMS-001](comms-incidents/R3-COMMS-001.md): locate V2 grant runbook, verify grant status, run Camrui header checker, and establish repeatable incident logging | Open |
