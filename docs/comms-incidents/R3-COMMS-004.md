<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-004.md
Component: COMMS-INCIDENT
File Revision: 1.0.0
Created: 2026-10-31 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Record Camrui Comms command gateway internal failure during R3 deployment preflight
Execution Model: Comms 1.1 command task submit
Observability: Tool error and verified grant status
Dependencies: R3 deployment; Camrui command gateway
Authority: Steward instruction to log Comms failures and punch list
Changed: 2026-10-31 UTC | R3-COMMS-004 | ChatGPT GPT-6 | Initial incident and remediation
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending reproduction and gateway diagnostics
History/Predecessor: None
-->
# R3-COMMS-004 — Camrui command task submission fails internally

**Status:** OPEN / punch-list remediation required.

**Objective:** Execute second R3 website deployment through Riverview Comms 1.1, starting with a read-only preflight.

**Operation:** `comms5_command_task_submit`; host `camrui`; privilege `standard`; idempotency key `r3-deploy2-preflight-20261031-v1`. Requested command read Git HEAD, target commit existence, working-tree status, listener/process, and script presence. **No deployment/restart command was attempted via Comms.**

**Grant verification:** `comms5_get_delegation_grant_status` returned active, IMPLEMENTED grant `grant:8327c8d7a74b4bf78e5529e53057fe69`, grantee `service:command-gateway`, action `comms5.command.execute.task.camrui.standard`, scope `host:camrui`, unlimited uses, expiration 2026-11-03T16:53:07-05:00. This verifies executor grant only; exact caller authorization was not separately proven.

**Observed error:** Tool invocation returned `The tool failed internally.` No task ID, status, command output, or exit code returned. Submission/execution cannot be established. Do not classify as grant rejection or successful execution.

**Impact:** Comms route could not confirm preflight, forcing separate manual deployment path. The 12-second command gateway timeout is a separate architectural concern for a long-running deployment, not the proven cause of this failure.

**Punch list:** Investigate gateway submission failure with correlation/audit logs; distinguish caller authorization, schema validation, gateway transport, command dispatch, and result handling; prove a read-only Camrui command can be submitted and polled; then qualify durable async deployment job with status polling and recovery. Keep the existing incident open until a verified successful retry.

**Related:** `docs/runbooks/R3_FIRST_WEBSITE_DEPLOYMENT.md`; `docs/comms-incidents/R3-COMMS-002.md`.
