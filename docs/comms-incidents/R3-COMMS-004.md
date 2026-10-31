<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-004.md
Component: COMMS-INCIDENT
File Revision: 1.0.1
Created: 2026-10-31 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Record Camrui Comms command gateway internal failure during R3 deployment preflight
Execution Model: Comms 1.1 command task submit
Observability: Tool error and verified grant status
Dependencies: R3 deployment; Camrui command gateway
Authority: Steward instruction to log Comms failures and punch list
Changed: 2026-10-31 UTC | R3-COMMS-005 | ChatGPT GPT-6 | Record further submission failure and successful transport probe
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending reproduction and gateway diagnostics
History/Predecessor: Git blob fba1fe62bac2b5c913dc5ce15d205aaaafaf8b15
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

## 2026-10-31 — repeated failure during Engineering marker deployment

- Deployment target: latest frontend marker change `a11282a6e217cadcafe9e630e6dcf6c6d9cae889` (spatial canon subsequently committed as `402392b48089ce36e286a9a6b6001b8dadee4b86`). No deployment attempted or verified through Comms.
- `comms5_command_task_submit` read-only preflight with idempotency key `r3-comms-preflight-20261031-04`, host `camrui`, standard privilege, and known active execution grant returned `The tool failed internally.` No execution result or audit ID surfaced.
- Executor grant rechecked: active, IMPLEMENTED, unlimited, valid until 2026-11-03; used_count 276 at check. Caller grant still not independently verified.
- `comms5_contract_info` succeeded: contract `riverview-comms-contract:5.0`, surface `Riverview_Comms_5`.
- `comms5_transport_probe` succeeded with `executed=true`, dashboard projection `healthy`, round-trip ~242 ms, correlation `r3-comms-deploy-diagnostic-20261031`, dashboard request `76f27fd47bd26e037c717c27`. This probes authenticated Comms request -> Camrui adapter -> dashboard loopback read API; it does **not** exercise command-task dispatch.
- `comms5_describe_operation` for `comms5_command_task_submit` returned `RIV-COMMS5-0004 operation is unknown`. Whether the describe endpoint expects a different operation identifier or is missing registration remains unverified.

**Narrowed fault domain:** General Comms transport and dashboard read projection are operational; command submission remains broken. Next diagnose command-task route registration, caller authorization, grant lookup, dispatch queue, command gateway backend logs, and error translation, using the correlation/idempotency above. Do not infer a specific root cause yet.
