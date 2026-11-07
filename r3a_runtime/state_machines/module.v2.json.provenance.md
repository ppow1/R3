<!--
R3 CONTROLLED DOCUMENT
File: r3a_runtime/state_machines/module.v2.json.provenance.md
Component: R3A-MODULE-LIFECYCLE
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Record provenance for the version 2 generic module lifecycle state machine.
Execution Model: N/A; controlled state-machine definition.
Observability: Runtime entity state and lifecycle event history.
Dependencies: R3A Module Lifecycle and Contract Specification MOD-003/MOD-008/MOD-009.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-002 | Add the explicit replacement-to-stopping transition required by the generic handoff lifecycle.
Supersedes: None.
Contracts: module.lifecycle v2.
Tests: tests/test_r3a_capability_integration_demo.py.
History/Predecessor: New file.
-->
`module.v2.json` adds `REPLACING -> STOPPING`. This permits CME to keep the old provider effective while the replacement starts and passes readiness, then drain/stop the old provider with a valid durable state transition. Version 1 remains immutable for compatibility with existing runtime entities.
