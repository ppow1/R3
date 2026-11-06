<!--
R3 CONTROLLED DOCUMENT
File: config/residents/grace.json.provenance.md
Component: R3-GRACE-CONFIGURATION
File Revision: 1.0.4
Created: 2026-11-03T02:24:45.188Z
Created By: Codex
Purpose: Record provenance for Grace's resident runtime configuration.
Execution Model: Loaded by runtime.configuration at service startup.
Observability: Git revision and deployed release configuration.
Dependencies: runtime/configuration.py; config/residents/prompts/grace.md
Authority: R3 Steward-approved resident role and assignment continuity.
Changed: 2026-11-03T02:24:45.188Z | R3-VERIFY-FEEDBACK-LOOP-001 | Codex | Configure Grace to resume durable independent-review feedback.
Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Add the narrowly scoped proposal draft capability to Grace's future model-visible list.
Changed: 2026-11-06T15:30:00Z | GRACE-INTERNAL-PROPOSAL | Codex GPT-6 | Limit the native allowlist to the internal proposal submit and readback capabilities; remove the Comms5 objective status operation.
Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Correct and verify the predecessor config blob reference.
Changed: 2026-11-06T02:15:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Add opt-in proposal and objective lifecycle read tools to Grace's future model-visible list.
Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Remove resident-local tool-name allowlist; discover central broker registrations and defer authority to the broker.
Supersedes: Revision 1.0.3's model-visible tool allowlist; does not grant execution authority.
Supersedes: None
Contracts: hints/file-provenance.md; hints/engineering-test-policy.md
Tests: tests/test_resident_continuity.py; tests/test_configuration.py
History/Predecessor: Git blob 7e525e71fd8397cdff66f546537d6cc641810631 (sidecar) and 44585a9647781f598edeb2938cd7e2d3fcd4107e (config) at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
-->
# Grace configuration provenance

The configuration enables `REVIEW_FEEDBACK` as a durable continuation event and configures Grace's native broker endpoint. Grace discovers registered broker capabilities dynamically. Discovery does not authorize invocation; the server and owning institutional authority decide each call. The confidential HR identity crosswalk remains required for proposal operations.
