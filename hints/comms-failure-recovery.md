<!--
R3 CONTROLLED DOCUMENT
File: hints/comms-failure-recovery.md
Component: COMMS-RECOVERY
File Revision: 1.0.3
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Capture failed and blocked Riverview Comms operations
Execution Model: N/A
Observability: Incident ledger and punch list
Dependencies: Riverview Comms 1.1 and applicable operational runbooks
Authority: Steward direction
Changed: 2026-10-31 UTC | R3-COMMS-002 | ChatGPT GPT-6 | Require shell-aware clipboard-first manual fallback
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not applicable
History/Predecessor: Git blob c6765f8b5640f807588301ae7b4493c464b57d0e
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

## Objective-level recovery: do not abandon on first tool failure

A failed **method** is not a failed **objective**. Grace and engineering agents must maintain the objective separately from individual tool attempts.

1. **Attempt recorded:** retain requested outcome, attempted method, exact error category, and evidence.
2. **Diagnose:** distinguish authorization rejection, transient service failure, invalid arguments, tool safety block, unsupported interface, and absent capability. Do not misclassify an external tool safety block as Riverview authorization denial.
3. **Discover:** inspect registered capabilities, relevant grants, documented runbooks, and available equivalent operations. Avoid asking the Steward for information already discoverable in the institution.
4. **Recover:** when permitted, retry a corrected request or use an authorized equivalent path. For GitHub writes, possible routes include the Contents API, Git tree/commit/ref operations, or an authorized host's Git CLI. Their availability does not establish that they will succeed; verify individually. Do not bypass a security or safety decision by routing the same prohibited action through a different tool.
5. **Verify:** independently read the resulting file/commit or command output and compare against the intended objective.
6. **Escalate only when needed:** report the remaining blocker, alternatives actually tested, and a specific decision or permission needed. Bound retries; do not loop indefinitely.

**State classification:** `METHOD_FAILED` means one attempt failed; `RECOVERY_IN_PROGRESS` means alternatives are being examined; `OBJECTIVE_BLOCKED` requires evidence that all reasonable authorized paths were exhausted or a genuine authority/safety dependency prevents continuation; `OBJECTIVE_VERIFIED` requires independent outcome evidence.

**2026-10-31 learning event:** A GitHub incident-record update was initially blocked at the tool invocation layer. The assistant prematurely reported it as blocked. Following the Steward's challenge, the assistant enumerated available GitHub write operations and retried the Contents API update; the retry succeeded (commit `179e512eec4d11c33552af82245f91b7175135b6`). The Git tree/commit/ref alternative was **discovered but not exercised**. The observed defect was premature abandonment and inadequate tool discovery, not proof of a broken GitHub repository or that an alternate write interface was required.

## Manual fallback command contract

When Comms execution fails and user intervention is necessary, identify the **terminal in which the user will paste** before issuing commands. For Windows PowerShell 7, begin with `Clear-Host`, capture diagnostic output in `$result`, display it, and call `Set-Clipboard -Value $result`. To diagnose Linux from a Windows terminal, use PowerShell to invoke `ssh` explicitly and execute Bash remotely; never paste Bash syntax directly into PowerShell. For POSIX Bash, begin with `clear`, capture and display output; use a verified available clipboard utility or clearly state that copying is unavailable on that host. Record manual-fallback syntax errors as assistant workflow failures, not remote host failures.

- [R3-COMMS-002: Camrui deployment preflight and shell-format failure](../docs/comms-incidents/R3-COMMS-002.md)
