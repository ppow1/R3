<!--
R3 CONTROLLED DOCUMENT
File: config/residents/grace.json.provenance.md
Component: R3-GRACE-CONFIGURATION
File Revision: 1.0.2
Created: 2026-11-03T02:24:45.188Z
Created By: Codex
Purpose: Record provenance for Grace's resident runtime configuration.
Execution Model: Loaded by runtime.configuration at service startup.
Observability: Git revision and deployed release configuration.
Dependencies: runtime/configuration.py; config/residents/prompts/grace.md
Authority: R3 Steward-approved resident role and assignment continuity.
Changed: 2026-11-03T02:24:45.188Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Configure Grace to resume durable independent-review feedback.
Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add the narrowly scoped proposal draft capability to Grace's future model-visible list.
Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Correct and verify the predecessor config blob reference.
Supersedes: None
Contracts: hints/file-provenance.md; hints/engineering-test-policy.md
Tests: tests/test_resident_continuity.py; tests/test_configuration.py
History/Predecessor: Git blob 3175715dca43479f05d91a05b4534653fa2c8f84; predecessor config blob 6810ee2cb849cd4e60fc7fd13338fcbb8624b486
-->
# Grace configuration provenance

The configuration enables `REVIEW_FEEDBACK` as a durable continuation event and adds the optional R3 proposal-draft capability. The capability is only discoverable when the tool server is explicitly configured with its endpoint and restricted Comms5 service credential; R3 authority and Comms5 transport authorization remain independently required.
