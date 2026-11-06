<!--
R3 CONTROLLED DOCUMENT
File: docs/r3-native-tool-contract.md
Component: R3-NATIVE-TOOL-CONTRACT
File Revision: 1.2.3
Created: 2026-11-02 UTC (exact time unverified)
Created By: Unknown (legacy source)
Purpose: Define discovery, authorization, invocation, and external workflow adapter boundaries for R3-native tools.
Execution Model: N/A; interface contract.
Observability: Durable authority and tool audit records.
Dependencies: runtime/native_tools.py; runtime/tool_server.py; runtime/capabilities.py.
Authority: R3-owned operations use R3 authority; institutional operations use the owning institutional authority decision.
Changed: 2026-11-06T01:39:36Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Document the explicit proposal-draft adapter exception and state boundaries.
Changed: 2026-11-06T01:48:39Z | GRACE-PROPOSAL-P1 | Codex GPT-6 | Distinguish authorization denials from authorized backend failures.
Changed: 2026-11-06T02:15:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Add narrow proposal and objective lifecycle reads for durable continuation.
Changed: 2026-11-06T02:24:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Require correlation metadata for read and write invocations.
Changed: 2026-11-06T15:30:00Z | GRACE-INTERNAL-PROPOSAL | Codex GPT-6 | Connect proposal draft/readback to Riverview's internal registry; remove Comms5 from Grace's internal proposal path.
Changed: 2026-11-06T23:06:45Z | GRACE-AUTHORITY-ARCH-001 | Codex GPT-6 | Remove duplicate R3 proposal grant requirement; require exact HR identity resolution and institutional decision.
Supersedes: Revision 1.1.1; no broad Comms tool catalog or Steward-gated operation is exposed.
Contracts: /api/v1/internal/resident-proposals; hints/engineering-test-policy.md
Tests: tests/test_internal_proposal_tool_integration.py
History/Predecessor: Git blob 201575dffa803088fe0534098e61f87436a0a86e at cb162499a5ae94b801cbdbf9e5aa2dcd4c75ebaf.
-->
# R3 Native Tool Contract

A descriptor includes a tool name, an OpenAI-compatible function definition, and a read-only flag. Invocation takes a tool name and JSON arguments and returns a structured outcome. Every invocation carries correlation metadata; a resident tool-call ID is used when present and read-only calls otherwise receive a generated ID. Each capability declares whether R3 authority or an existing authoritative service decides the operation. Registration never grants authority. The caller is authenticated before invocation; the owning authority decision and outcome are audited. Uncertain outcomes must not be automatically replayed. Configurable transport settings belong in external configuration. No total task-duration cap.

## Internal institutional proposal capability

Grace's native `r3.proposal.submit` and `r3.proposal.status` capabilities call Riverview's resident-authenticated internal proposal API at `/api/v1/internal/resident-proposals`. R3 authenticates the native resident credential and resolves the exact institutional principal through the authoritative HR crosswalk. The institutional API authenticates its resident credential and makes the institutional action/scope policy decision. R3 does not add a duplicate proposal-specific exact grant. A 401/403 from the institutional API remains a denial; unavailable authority is not treated as permission. The status operation also verifies the returned proposal author against the HR-resolved principal.

The resident supplies structured proposal content. R3 derives principal and correlation from the authenticated invocation and HR crosswalk, then derives an idempotency key from those values. Riverview's existing PostgreSQL ProposalRegistry remains authoritative for proposal identity, revision, digest, and lifecycle status. The API returns a receipt only after authorized readback matches the persisted revision and digest. Retrying the same key and content returns the same proposal; conflicting content is rejected.

Draft submission does not approve or promote a proposal and does not create an objective or work order. Steward decision and promotion remain separate operations in the existing `ProposalLifecycle` and retain their existing Steward gates. A draft receipt is not represented as approval or as `READY_FOR_STEWARD_DECISION`. R3 returns 403 for authentication/authorization denials and 502 for an authorized capability's backend failure; both are durably audited under their distinct outcomes.

The objective-status tool is not enabled by this internal proposal adapter. The institutional objective and assignment states remain owned by Riverview's existing execution pipeline and are checked through its authorized institutional interfaces.
