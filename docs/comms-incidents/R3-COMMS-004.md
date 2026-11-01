<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-004.md
Component: COMMS-INCIDENT
File Revision: 1.0.9
Created: 2026-10-31 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Record Camrui Comms command gateway internal failure during R3 deployment preflight
Execution Model: Comms 1.1 command task submit
Observability: Tool error and verified grant status
Dependencies: R3 deployment; Camrui command gateway
Authority: Steward instruction to log Comms failures and punch list
Changed: 2026-11-01T15:06:03.086Z | R3-P020 | ChatGPT GPT-6 | Record successful queued deployment and remaining visual acceptance
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending reproduction and gateway diagnostics
History/Predecessor: Git blob 14aa05d460ac91dfd45386ee8ffa9eddcdf22017
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


## 2026-11-01 — Windows deployment attempt blocked; grant status unavailable

- Targeted frontend fix: `a11282a6e217cadcafe9e630e6dcf6c6d9cae889`, which saves the expanded panel state and returns the minimized Engineering marker to its image-relative entrance position at 45% opacity.
- Verified locally before the attempt: the existing `Run.bat Deploy-R3 <commit-sha>` launcher and `Deploy-R3.ps1` are present; the installed script includes the SSH lock-descriptor closure (`9>&-`). No deployment code or transport was added.
- The existing Windows Comms task ran the deployer. Its SSH step returned `{"status":"denied","reason":"bounded_request_or_state_invalid"}` with SSH exit code 2; the PowerShell deployer returned exit code 1. No successful remote activation or post-deploy health result was returned. The live revision remains unverified.
- A subsequent read-only Comms5 discovery call listed `command_task_submit` as IMPLEMENTED. My first four grant-status requests omitted the required `grant:` prefix and returned `INVALID_ARGUMENT`; this was a malformed-request error, not backend unavailability. Corrected reads with full IDs confirmed all four caller/executor grants active and IMPLEMENTED, including Windows grants valid through 2026-11-02 19:55 -05:00.
- Using the verified Windows grant, a read-only Q2 check completed successfully. Then `Deploy-R3-Engineering-Panel.ps1` was staged in `A:\\AI\\Scripts\\Riverview\\Q2\\` (699 bytes; SHA-256 `E661B1A649429E0EF99FBE9DFCB42AA8C0004E5C80F37489AAE3EC4B0321A09A`). The script targets the existing deployer and commit above. It remains in Q2 pending the Steward's move into Queue; it has not executed.
- The earlier SSH denial cause remains unverified; no live change is claimed. **Punch-list reference:** `R3-P020` — objective-level recovery; preserve the failed attempt and continue through the established Q2 → Queue → Results workflow.


## 2026-11-01 — Q2 queue result and failed deployment

- The staged `Deploy-R3-Engineering-Panel.ps1` was subsequently found under `A:\\AI\\Scripts\\Riverview\\Queue\\Completed\\`, with its result at `A:\\AI\\Scripts\\Riverview\\Queue\\Results\\Deploy-R3-Engineering-Panel.ps1.txt`. The earlier Q2 read-back missed the nested Queue folders; the script did execute.
- Result timestamp: `2026-11-01T01:27:24.6186412-05:00`; target `a11282a6e217cadcafe9e630e6dcf6c6d9cae889`. It reported `Previous HEAD position was c8420b8 Use documented R3 Uvicorn process identity for safe deployment restart`, SSH exit code 1, and the deployer's failure exception. The queue wrapper's `EXIT_CODE` field was empty.
- The installed deployer source contains an exit trap that attempts rollback to its recorded prior commit if activation fails. The Queue result does not expose the rollback outcome. **Inference:** the PowerShell catch may have surfaced only the exception message and omitted later remote-shell output; this has not been independently confirmed.
- The earlier deploy task reported SSH exit 1, but the later read-only check confirms the server is now running at its target commit `a11282a6e217cadcafe9e630e6dcf6c6d9cae889` with HTTP health 200. This is inconsistent with the task's reported failure; the remote deployer's completion/rollback output remains unavailable. The current visual source changes are after the attempted target and were not part of that deployment.
- The read-only status-check script `Inspect-R3-Deployment-State.ps1` later appeared in `Queue\\Completed` with output in `Queue\\Results`. It reported remote HEAD `a11282a6e217cadcafe9e630e6dcf6c6d9cae889` (detached), the expected `admin1` Uvicorn process listening on port 8303, and `HEALTH_HTTP=200`. It read the page title `Riverview 3 · Visual prototype`, confirming the requested current UI changes were not yet deployed. The diagnostic then hit a Bash syntax error in its marker-check loop and returned `SSH_EXIT=2`; checks after the title were not completed.
- **Punch-list reference:** `R3-P020` — preserve attempt history and verify the deployment outcome before any retry.


## 2026-11-01 — current-site deployment interruption and recovery staging

- The Queue result for `Deploy-R3-Website-20261101.ps1` targeted `f5d689cf9ff307c2ae9c18edcc8a81ca44e4f6a6`. The existing deployer returned SSH exit 1 after Git reported `Previous HEAD position was a11282a`. Independent read-back showed remote HEAD at the target commit but `HEALTH_HTTP=000` (port 8303 unavailable).
- That post-deploy read-back also returned `SSH_EXIT=2` because the PowerShell diagnostic joined Bash lines using a literal backslash-n; Bash received `exit 0\r` and rejected it. The remote HEAD and unavailable listener were observed before that syntax error.
- Likely cause of the interrupted activation is PowerShell terminating the SSH pipeline on Git's normal detached-checkout message; this remains an inference pending the recovery run.
- `Recover-Deploy-R3-Website-20261101.ps1` is now staged in `A:\\AI\\Scripts\\Riverview\\Q2\\` (SHA-256 `57E43D808EEF0D3CA9A33BB10A07D294EDC0928AFCE8FEA99C30CF83B3A115F1`; PowerShell parse result `PARSE=OK`). It temporarily merges the existing deployer's Git checkout diagnostics into stdout, invokes the same `Run.bat Deploy-R3` path, restores the original deployer file, and performs a post-deploy health/page-marker read-back. It has not run yet.
- **Punch-list reference:** `R3-P020` — verify the current server recovery through the Q2 → Queue → Results workflow before further changes.


## 2026-11-01 — queued deployment recovered

- The recovery script was moved through the user's Q2 → Queue workflow and its result was read from `A:\\AI\\Scripts\\Riverview\\Queue\\Results\\Recover-Deploy-R3-Website-20261101.ps1.txt`.
- It temporarily merged Git checkout status output into stdout, ran the existing `Run.bat Deploy-R3` path, and restored the installed `Deploy-R3.ps1` (`DEPLOYER_RESTORED=True`). Deployment exited 0 and reported `DEPLOYED_COMMIT=f5d689cf9ff307c2ae9c18edcc8a81ca44e4f6a6`, `HEALTHY_PID=1815431`, and approved background HTTP 200.
- Independent read-back confirmed remote HEAD `f5d689cf9ff307c2ae9c18edcc8a81ca44e4f6a6`, health HTTP 200, title `Riverview 3`, old prototype/demo labels absent, top bar absent, Engineering status UI present, and target marker code present. The read-back shell returned exit 2 after these checks because its final `exit 0` line retained a carriage return; the deployer's own activation and health checks completed successfully.
- The recovery was temporary; the installed deployment script was restored. Browser visual acceptance remains pending.
- **Punch-list reference:** `R3-P020` — preserve this successful outcome and finish visual acceptance against the Steward's screenshot.
