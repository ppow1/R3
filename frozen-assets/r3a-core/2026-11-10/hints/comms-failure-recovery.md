<!--
R3 CONTROLLED DOCUMENT
File: hints/comms-failure-recovery.md
Component: COMMS-RECOVERY
File Revision: 1.0.5
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Capture failed and blocked Riverview Comms operations
Execution Model: N/A
Observability: Incident ledger and punch list
Dependencies: Riverview Comms 1.1 and applicable operational runbooks
Authority: Steward direction
Changed: 2026-11-01 UTC | R3-COMMS-003 | ChatGPT GPT-6 | Document dashboard saturation incident and recovery
Changed: 2026-11-10T01:31:53Z | R3-COMMS-005 | Codex GPT-6 | Record R3A Website resident-directory provider artifact path failure.
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not applicable
History/Predecessor: Git blob a829c797cadf2da14acea1e484d6ac13d4bf3469
-->
# Comms failure recording and recovery

Every Riverview Comms command failure, denial, timeout, missing interface, or blocked prerequisite must generate or update a durable incident record, even if a workaround later succeeds. Distinguish **command attempted and failed** from **command not submitted because of preflight prerequisites**.

Record: incident ID, UTC time/precision, requested objective, operation, host, status/error, required grant or permission if known, whether submitted, attempted retries, verified evidence, hypotheses, impact, proposed remedy, related runbook, punch-list link, and closure evidence. Redact credentials and secrets.

For recurring errors, append evidence to the existing incident rather than multiplying tickets. Locate existing recovery runbooks before inventing scripts. Never mark an incident resolved until a successful retry or verified alternative is recorded.

The Steward reports a historical Riverview V2 grants UI issue: grants were visible but new grant initialization required a browser developer-console procedure documented in a Riverview dashboard runbook. The exact runbook path and current applicability are **not yet verified**; find and review it before following that procedure.

## Cases

- [R3-COMMS-001: Camrui command preflight blocked](../docs/comms-incidents/R3-COMMS-001.md)
- [R3-COMMS-005: R3A Website resident discovery provider artifact path mismatch](../docs/comms-incidents/R3-COMMS-005.md)

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

## R3-COMMS-003 — Comms5 dashboard request-slot saturation (2026-10-31/11-01)

**Status:** immediate outage recovered; permanent correction OPEN. [R3 punch-list R3-P021](../docs/PUNCH_LIST.md) and [Riverview issue #370](https://github.com/ppow1/Riverview-/issues/370).

**Observed failure:** `comms5_command_task_submit` to `desktop-ja3rpnq` returned `BACKEND_UNAVAILABLE`, `dashboard_operation_http_status`, `executed:false`; `comms5_transport_probe` independently returned `dashboard_http_status`. The transport probe does not require Windows command execution. Dashboard service on Camrui remained active (PID 2759636), with loopback listener 127.0.0.1:8767. Recent journal query was empty; older journal contained BrokenPipeError during dashboard HTTP response writes, but those earlier exceptions do not prove this outage's cause.

**Technical evidence:** an unauthenticated local HTTP request returned 503 with an empty body; the diagnostic script also had a here-document error, which was a test-construction error. Deployed `src/riverview_core/status_dashboard/server.py` defines `_MAX_THREADS=16`; `process_request()` sends a bare 503 (Content-Length 0) if its semaphore cannot acquire a request slot. `_process_bounded()` releases the slot after the handler exits. The running process had 18 threads and **15 CLOSE-WAIT connections** on port 8767. These observations strongly support **saturated request handlers** as the immediate fault, but the precise reason handlers remained occupied is **unverified**. `src/riverview_core/comms5/dashboard_backend.py`, `DashboardReadBackend._post_operation()`, masks unrecognized HTTP failures as `dashboard_operation_http_status`; Windows task submission timeout is 25 seconds. The dashboard's `_dispatch()` also maps unexpected Comms5 operation exceptions to generic `comms5_operation_unavailable`.

**Temporary recovery, verified:** An authorized operator restarted **only** `riverview-status-dashboard.service` on Camrui using `sudo -n systemctl restart riverview-status-dashboard.service`. Service returned `active` with new PID **1174196** and SSH exit 0. An authenticated Comms5 transport probe then returned `available`, healthy dashboard, **234.604 ms** round trip, request ID `a757772a4d7461c384b886f2`. A real Windows PowerShell command executed on `DESKTOP-JA3RPNQ` as `riverviewcmdagent`, exit **0**, execution ID `2a01531e-96d1-4c09-8976-3e53800dbcd5`. Restart interrupts active dashboard requests; it is a workaround, **not a permanent fix**. Always confirm authorization, verify active/new PID, then run authenticated transport probe and benign Windows command with valid host grants. Do not restart unrelated services or bypass authorization.

**Permanent repair required:** determine handler retention/CLOSE-WAIT cause (client disconnects, keepalive, read/write deadlines, blocked work); bound handler lifetime and reclaim slots; add sanitized saturation metrics and request correlation; improve safe HTTP error reporting; test slow/disconnected clients and slot exhaustion/recovery; deploy with rollback and verify Comms5, Windows command execution, and other dashboard/Grace endpoints. **Do not mark permanently resolved** until code correction and regression verification. A subsequent Windows-gateway SSH inspection was denied with `bounded_request_or_state_invalid`; do not treat it as a successful inspection.
