<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/state_machines/engineering_work_order.json
Component: R3A-AP2-WORK-ORDER-MACHINE
File Revision: 1.0.0
Created: 2026-11-07T05:28:24Z
Created By: Codex GPT-6
Purpose: Define the versioned durable lifecycle for AP2 engineering work orders.
Execution Model: Loaded and enforced by the existing PostgreSQL state-machine registry.
Observability: Immutable definition digest and append-only transition events linked to activity lineage.
Dependencies: r3a_runtime/db.py; r3a.engineering-work-order.v1; existing activity.generic machine.
Authority: AP2 R3A-011/R3A-012, Issue #43; unified capability decision, Issue #46 comment 6702794200; isolated R3A only.
Changed: 2026-11-07T05:28:24Z | AP2-IMPLEMENTATION | Codex GPT-6 | Add durable work-order transition definition.
Changed: 2026-11-07T05:45:10Z | AP2-IMPLEMENTATION | Codex GPT-6 | Start the order lifecycle after institutional authorization; retain recoverable wait and verification transitions.
Supersedes: None.
Contracts: engineering.work-order state machine v1.
Tests: tests/test_r3a_engineering.py.
History/Predecessor: New file; no predecessor.
-->
