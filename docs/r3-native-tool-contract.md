<!--
R3 CONTROLLED DOCUMENT
File: docs/r3-native-tool-contract.md
Component: R3-NATIVE-TOOL-CONTRACT
File Revision: 1.1.1
Created: 2026-11-02 UTC (exact time unverified)
Created By: Unknown (legacy source)
Purpose: Define discovery, authorization, invocation, and external workflow adapter boundaries for R3-native tools.
Execution Model: N/A; interface contract.
Observability: Durable authority and tool audit records.
Dependencies: runtime/native_tools.py; runtime/tool_server.py; runtime/capabilities.py.
Authority: R3 canonical exact-grant authority; Steward-directed Grace Autonomy P1 permits one narrowly scoped Comms5 draft adapter.
Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Document the explicit proposal-draft adapter exception and state boundaries.
Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Distinguish authorization denials from authorized backend failures.
Supersedes: Revision 1.0.0; no other tool catalog or approval contract is exposed.
Contracts: riverview-comms-contract:5.0; hints/engineering-test-policy.md
Tests: tests/test_proposal_submission_integration.py
History/Predecessor: Git blob 92a7abf6bcfa53d0eb998ca983fb47aa26a34038
-->
# R3 Native Tool Contract

A descriptor includes a tool name, an OpenAI-compatible function definition, and a read-only flag. Invocation takes a tool name and JSON arguments and returns a structured outcome. The R3 server independently authorizes execution against the exact resident, resource, action, operation, and scope, then audits authorization and outcome. Uncertain outcomes must not be automatically replayed. Configurable transport settings belong in external configuration. No total task-duration cap.

## Comms5 proposal draft adapter

The explicitly Steward-authorized Grace recovery adapter may expose only `r3.proposal.submit`. R3 authenticates the resident credential and requires a separate exact R3 write grant before forwarding a draft to Comms5 contract `riverview-comms-contract:5.0` through an authenticated Comms5 transport. The adapter calls only `submit_steward_seed` and its read-only `seed_status` operation; it does not discover or proxy the general Comms5 tool catalog.

The resident supplies only proposal text. R3 derives authenticated principal and correlation from the verified invocation context and derives an idempotency key from that context. Comms5 remains authoritative for durable proposal identity and lifecycle status. R3 returns the Comms5 proposal ID, revision, and actual lifecycle state after a matching readback. Readback failure is reported as unverified and must be reconciled before retry; it is not reported as successful persistence.

Draft submission does not approve or promote a proposal and does not create an objective or work order. `prepare_proposal_for_decision`, promotion, and work-order operations remain outside Grace's capability catalog and retain their existing Steward gates. A Comms5 draft status must not be presented as Steward approval or as `READY_FOR_STEWARD_DECISION` unless the authoritative Comms5 response says so. R3 returns 403 for authentication/authorization denials and 502 for an authorized capability's backend failure; both are durably audited under their distinct outcomes.
