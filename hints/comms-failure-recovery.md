<!--
R3 CONTROLLED DOCUMENT
File: hints/comms-failure-recovery.md
Component: COMMS-RECOVERY
File Revision: 1.0.1
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Capture failed and blocked Riverview Comms operations
Execution Model: N/A
Observability: Incident ledger and punch list
Dependencies: Riverview Comms 1.1 and applicable operational runbooks
Authority: Steward direction
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Require institutional discovery before reporting a grant unavailable
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not applicable
History/Predecessor: Git blob 5ae182c7bbb669f799685d4cfc76a9b07ce03ed0
-->
# Comms failure recording and recovery

Every Riverview Comms command failure, denial, timeout, missing interface, or blocked prerequisite must generate or update a durable incident record, even if a workaround later succeeds. Distinguish **command attempted and failed** from **command not submitted because of preflight prerequisites**.

Record: incident ID, UTC time/precision, requested objective, operation, host, status/error, required grant or permission if known, whether submitted, attempted retries, verified evidence, hypotheses, impact, proposed remedy, related runbook, punch-list link, and closure evidence. Redact credentials and secrets.

For recurring errors, append evidence to the existing incident rather than multiplying tickets. Locate existing recovery runbooks before inventing scripts. Never mark an incident resolved until a successful retry or verified alternative is recorded.

The Steward reports a historical Riverview V2 grants UI issue: grants were visible but new grant initialization required a browser developer-console procedure documented in a Riverview dashboard runbook. The exact runbook path and current applicability are **not yet verified**; find and review it before following that procedure.

## Cases

- [R3-COMMS-001: Camrui command preflight blocked](../docs/comms-incidents/R3-COMMS-001.md)

## Mandatory discovery-first preflight

Before concluding that a tool, grant, or command pathway is unavailable, agents (including Grace) must inspect the institutional capability/resource registry and current authority/delegation registry, consult the relevant runbook index, and compare the required action, principal, host scope, expiry and use limits with existing grants. If an existing grant ID is known, verify it through the Comms grant-status operation. Record which sources were consulted and their observation times. Only then classify the problem as absent authority, expired authority, undiscoverable reference, missing interface, or actual execution failure. Do not ask the Steward to recreate information already available in the institution. Historical IDs are pointers, not permanent authority.

**Known case:** On 2026-10-31 the assistant initially failed to discover existing Camrui grants visible in V2. The Steward supplied the V2 authority-registry snapshot; both grant IDs were then independently confirmed active using `comms5_get_delegation_grant_status`. This was an **agent discovery/workflow failure**, not a missing grant. A later command submission was blocked by a separate tool-level safety check; do not conflate that with grant authorization.
