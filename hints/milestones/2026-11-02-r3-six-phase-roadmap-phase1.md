## Configuration-first foundation requirement (Steward decision, 2026-11-02)
- HARD GATE for all six phases: operationally adjustable settings belong in persistent external configuration, not hardcoded runtime source. Applies to every resident, not just Grace: identity, role, personality/system prompt, model and inference endpoint/parameters, tool provider/endpoints, scheduling/concurrency, transport timeouts, progress checks, recovery/backoff, and logging/retention.
- Separate resident personality/prompt documents from technical configuration so Jessica can edit character definition without changing Python. Resident identity and durable state must be independent of model selection and process restarts. Runtime must be resident-neutral; adding residents must not require editing scheduler source.
- Distinguish connection/read timeout and progress observation from total objective duration. Do not impose arbitrary elapsed-time ceilings on resident work. The current inference adapter's default timeout=120.0 and serve.py's embedded Grace system prompt are existing technical debt to externalize; do not misrepresent urllib socket timeout as necessarily a total objective timeout.
- Validate settings at load, fail clearly for invalid configuration; never silently substitute source-code values. Credentials remain in protected secret storage, not plaintext settings. Protocol constants and genuine invariants may remain in code.
- Keep the implementation minimal: inspect/reuse existing R3 configuration conventions, create general-purpose version-controlled settings/prompt files and permanent regression tests, and avoid one-off tests. Preserve existing live Camrui serve.py and mcp_tools.py edits; no blind overwrite or deployment. No new governance layer or separate settings service.
- Proposed layout only, not yet implemented: config/runtime.json, config/inference.json, config/tools.json, config/residents/<resident>.json, config/residents/prompts/<resident>.md. Final paths and reload behavior require inspection of existing source.
- Phase 1 cannot close until this requirement is implemented and verified; Phase 2 R3-native MCP must consume external configuration, not deepen dependency on Comms5.

# R3 — Six-Phase Roadmap and Phase 1 Checkpoint
Date: 2026-11-02 (date precision). Status: Phase 1 investigation complete; foundation repair outstanding.
Repository: ppow1/R3. Working branch: engineering/institution-runtime-v1-20261101.
Authority: Steward. This document is a continuity checkpoint, not an authorization to weaken operational autonomy.

## Governing objective and non-negotiable rules
Build an independent, persistent, event-driven, general-purpose Riverview 3 institutional runtime in which Grace can reason, use R3-native tools, evaluate results, recover and continue autonomously. Fast and light: retain working R3 components, adapt good R1/R2 reference patterns without importing their runtime or workflow dependencies, avoid duplicate frameworks and disposable one-time tests. Engineering scope must never become an operational scope cap. No hardcoded limit on objectives, work orders, cycles, rework, tool calls, concurrent activities or total task duration. Supervision detects genuine loss of progress and enables recovery; it does not kill legitimate work for crossing an arbitrary elapsed-time threshold. Preserve Steward authorization and independently verifiable outcomes. No false success claims. All code changes must honor hints/file-provenance.md and preserve live deployment differences.

## Mandatory phase handoff protocol
At the end of EACH of the six phases, commit a durable GitHub checkpoint on this branch recording: goal; verified evidence (source paths, deployed configuration, logs); changes and commit SHAs; tests and results; remaining unknowns and risks; decisions; explicit next-phase entry point. Update this roadmap status and link the checkpoint. Do not mark a phase complete until its evidence is documented. Never claim an uncommitted change is deployed or tested. If context is lost, resume from this file and linked checkpoints, not a newly invented plan.

## Six-phase controlling roadmap
1. Baseline: reconcile GitHub and Camrui deployed source; inventory inference, journal, scheduler, MCP and failures. Document findings; do not overwrite uncommitted working code.
2. R3-native tool contract: minimal discover/invoke schema, authorization and auditing; no R2 tool catalog or workflow dependencies.
3. Local STDIO and private LAN execution: one lightweight R3 tool server/router, local Camrui tools and authorized host access (Windows, OctoMiners) without unnecessary per-host MCP layers.
4. External MCP exposure: use Ionoge only where remote clients genuinely require it; same R3 tool contract, server-side authorization and safe exposure.
5. Grace reasoning/tool/result/continuation: fix HTTP 400 with captured response evidence, durable tool intent/result and crash recovery; progress-aware supervision without artificial work-duration ceilings.
6. Production qualification and observability: verify sustained autonomous work and recovery, truthful state-machine/dashboard visibility, durable records and independently checked completion.

Cross-phase foundational defects may be repaired before later phase work if required, but record them and do not confuse a small engineering change with a permanent operational restriction.

## Phase 1 — verified findings (2026-11-02)
Evidence: read-only SSH diagnostics returned by Steward from Camrui and GitHub source inspection. No production code or services changed during this baseline investigation.

- Camrui host admin1-Default-string, R3 user service active/running; unit /home/admin1/.config/systemd/user/r3-institution.service; drop-ins 10-grace-inference.conf and 20-mcp-client.conf.
- Camrui checkout /home/admin1/r3-runtime-candidate on branch engineering/institution-runtime-v1-20261101 at HEAD fba4815ce5d3258f137cff5ea28c7e63486dbe38, with modified runtime/serve.py and untracked runtime/mcp_tools.py, backups, .venv and __pycache__. These are NOT equivalent to GitHub committed source; preserve before reconciliation.
- Environment advertises R3_GRACE_INFERENCE_URL=http://192.168.1.160:8080/v1, model /root/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf, R3_GRACE_MCP_URL=https://riverview-comms.ionoge.com/comms5/mcp, R3_MCP_ALLOWED_TOOLS= (empty). Configured endpoints are not proof of live reachability. Current MCP URL is an R2 Comms catalog; must be replaced, not carried into R3.
- Deployed runtime/mcp_tools.py revision 1.0.2 is a small Python MCP Streamable HTTP adapter. discover() lists all remote tools and exposes OpenAI-compatible definitions. invoke() calls selected tool; tools without readOnlyHint=True are classified as write. Write-classified execution requires both allow_write=True and name in R3_MCP_ALLOWED_TOOLS. The empty allowlist and inference call path currently prevent such execution. MCP annotations are metadata, not a substitute for server-side authorization. Token is read from a local file; do not expose it.
- Deployed runtime/serve.py revision 1.0.4 adds MCPTools selection over LlamaTools when R3_GRACE_MCP_URL is set. Preserve this local diff before merging.
- runtime/resident_inference.py has durable resident_inbox and resident_turns; it records ASSISTANT, TOOL_INTENT and TOOL_RESULT and loops through model/tool continuation. It uses asyncio.to_thread for synchronous HTTP/MCP operations. InferenceEndpoint timeout=120s; urllib HTTPError response body is not currently retained.
- runtime/institution.py watchdog_seconds defaults to 30s and cancels a resident asyncio task after elapsed time. This conflicts with normal inference and autonomy; cancellation of to_thread awaits does not guarantee termination of the underlying network call. Replace elapsed-time cancellation with progress-aware, durable supervision; no arbitrary total task duration.
- SQLite recent inbox: Event 1 Grace STEWARD_REQUEST COMPLETED; Event 2 Grace STEWARD_OBJECTIVE FAILED. COMPLETED denotes software request processing status, NOT proof of an accomplished real-world objective, and Event 1's actual request/response have not been inspected.
- Event 2 stored result {"error": "<HTTPError 400: 'Bad Request'>"}; resident_turns: seq 0 ASSISTANT 409 bytes, seq 1 TOOL_INTENT 93 bytes, seq 2 TOOL_RESULT 19570 bytes. This establishes a recorded tool cycle followed by HTTP 400; it does NOT establish the HTTP rejection reason, nor that result size caused it. journalctl --user -u r3-institution.service --since 2026-11-01 -p warning returned no entries.
- Prior milestone: hints/milestones/2026-11-02-grace-mcp-milestone.md. It records earlier evidence of an MCP invocation and the need to remove R2 tool exposure. Do not treat an HTTP 400 as completed autonomous qualification.

## Phase 1 disposition and immediate next action
Investigation documented. Baseline code reconciliation and foundational repairs remain OPEN: (a) preserve and reconcile Camrui modified/untracked adapter with GitHub; (b) replace fixed elapsed watchdog with progress-aware supervision without a work-duration cap; (c) capture HTTP error response bodies safely to diagnose 400. Do not claim Phase 1 implementation closure until changes are reviewed, committed and verified. Begin with a minimal source reconciliation and permanent tests, then proceed to Phase 2 contract. Do not deploy/restart or overwrite Camrui working source without explicit review and verification.

## Foundation repair progress (2026-11-02)
- GitHub code commit b4572cd1448d119eb00cd46c2d687168283070a8: runtime/institution.py revision 1.0.7 removes elapsed-work watchdog cancellation while retaining scheduler, supervisor, task-crash detection and shutdown cancellation. Not yet deployed or runtime-verified.
- GitHub test commit 4f5bbeeeb721e84db2d769dd1883e1a95a8d5528: tests/test_institution_supervision.py adds permanent regression for an active long-running resident. Test not yet executed on Camrui.
- No changes to deployed Camrui source, MCP adapter, service, or inference timeout. Pending: verify tests; preserve/reconcile deployed files; capture HTTP 400 body; examine and repair inference timeout behavior without an artificial overall work ceiling.

## Isolated verification evidence (2026-11-02)
- Steward executed git fetch and git archive for branch head 1b6e0af5dbb9ad8f2b3e080b4300b90f8fcdd180 in a separate /tmp/r3-verify-* directory. No live checkout modification or service restart was reported.
- Command ran `python3 -m unittest discover -s tests -p test_institution_supervision.py -v` under `set -eu` and reached `=== VERIFICATION COMPLETE ===`. This supports exit status zero for the SSH command, but Python unittest writes its result lines to stderr, which the Windows capture did not include. Exact tests-run count and `OK` output are not yet visible; re-run with stderr redirected to stdout and preserve output.
- Do not mark Phase 1 implementation fully verified or deployed on this evidence alone.

## Verified regression result (2026-11-02)
- Steward supplied full isolated Camrui unittest output for archived commit 1b6e0af5dbb9ad8f2b3e080b4300b90f8fcdd180: `test_active_work_is_not_cancelled_by_elapsed_time ... ok`; `Ran 1 test in 0.253s`; `OK`; `=== VERIFICATION COMPLETE ===`.
- Scope: permanent test verifies active resident is not cancelled during the test's elapsed waiting interval and the supervisor continues to report RUNNING with no watchdog failure. It does not prove production deployment, indefinite task behavior, or inference/tool correctness.
- Phase 1 remains OPEN for deployed source reconciliation and HTTP 400/120-second inference transport repair.

## Inference diagnostics verification (2026-11-02)
- Source commit b3af87da27790a9a20e23975fdd6079dab5ec80d updated runtime/resident_inference.py to retain upstream HTTP status and structured error type/code, without persisting raw body, request prompts, or tool outputs.
- Permanent regression commit 5f20d6ebe1ba791a106c8b142364bb0ba4e93346 added tests/test_inference_http_errors.py.
- Steward executed both tests in an isolated git-archive of 5f20d6ebe1ba791a106c8b142364bb0ba4e93346 on Camrui; observed HTTP test `Ran 1 test in 0.004s` `OK`, supervision test `Ran 1 test in 0.270s` `OK`, and `=== VERIFICATION COMPLETE ===`.
- Both focused regressions PASS. Neither source repair is yet deployed; original HTTP 400 cause remains unknown and inference request timeout remains 120 seconds.

## Checkpoint index
- Earlier MCP milestone: hints/milestones/2026-11-02-grace-mcp-milestone.md
- Phase 1 continuity checkpoint: this document
- Phase 2–6: pending; append links and commit SHAs on completion.

## Camrui deployment and live health (2026-11-02)
- Steward verified syntax and exact source diffs, then installed runtime/institution.py revision 1.0.7 and runtime/resident_inference.py revision 1.1.1 with pre-install backup at /home/admin1/.local/state/r3-runtime/source-backups/20261102T142621Z.
- r3-institution.service restarted; observed active/running, PID 2840691. Existing modified runtime/serve.py and untracked runtime/mcp_tools.py remained untouched.
- Live health: main_age_seconds 0.244, registered_residents 1, resident_execution_connected true, resident_inference_connected true, resident_tool_execution_configured true, resident_tool_execution_connected false, resident_inbox_pending 0, active empty.
- Grace journal most recent RESTART_RECOVERY to READY; earlier WATCHDOG_TIMEOUT and HTTP 400 are historical. Durable inbox objective #2 remains FAILED; do not replay automatically.
- Deployed source and service startup verified; MCP tool connectivity and real inference continuation NOT verified. HTTP 400 root cause unknown; 120-second inference timeout unchanged. Phase 1 OPEN.

## External configuration foundation verified (2026-11-02)
- Committed runtime/configuration.py, config/runtime.json, config/residents/grace.json, config/residents/prompts/grace.md, and tests/test_configuration.py on branch engineering/institution-runtime-v1-20261101, head 9ccb90a695747e9615ac6d41a9d865fa7a9c6ac3.
- Steward verified in isolated Camrui git archive: four permanent configuration tests all passed (Ran 4 tests in 0.030s, OK). Loader smoke read reports one resident, Grace, and nonempty external prompt.
- Scope: loader and files only; serve.py is NOT yet wired to configuration; no live deployment or service restart. Current tools provider in new Grace configuration is none, intentionally avoiding Comms5 as R3 dependency. Phase 1 remains OPEN.

## Generic resident configuration integration — isolated verification (2026-11-02)
- Commit 5127acee5a4a66fbd8a7faa55de45f6f020cac45 wires runtime/serve.py to external config and generic resident registration.
- Steward executed isolated git-archive verification on Camrui: py_compile of runtime/configuration.py and runtime/serve.py PASS; all four tests/test_configuration.py regressions PASS; configuration loaded one resident (Grace) and nonempty prompt.
- Verification limit: no running service startup test, no full regression suite, and no live deployment yet. Live service still uses legacy environment-based Comms5 adapter. New config explicitly selects tools.provider=none, so deploying it would remove existing configured tool access. Do not treat this as a production-ready MCP replacement.
- Next roadmap priority: complete Phase 1 service integration and compatibility validation without silently changing live tool behavior; then Phase 2 R3-native tool contract. Do not expand configuration into a separate campaign.

## Full permanent test suite verified (2026-11-02)
- Steward executed isolated git archive at 6f6438676cbe2df930c838eeeca0e32ab2f57b67: 8 tests passed in 1.071s, including two-resident external-config service startup, configuration validation, inference error diagnostics, and supervisor no-elapsed-time-cancellation regression.
- Live Camrui remains running older code with local uncommitted MCP adapter; deployment and live health verification remain outstanding. Configured provider 'none' is not equivalent to current Comms5-backed tool setup. Preserve live behavior until R3-native MCP is ready or explicit cutover approved.

## Phase 2 implementation verification (2026-11-02)
- Steward verified isolated git archive at 630674ef3bcd195714e8ebc2a676efa9958e2d0f: python3 compileall -q runtime tests succeeded; 14/14 permanent tests passed in 1.087 seconds.
- New R3-owned client runtime/native_tools.py, loopback tool server runtime/tool_server.py, native provider wiring in runtime/serve.py, validation in runtime/configuration.py; tests/test_native_tools.py and tests/test_tool_server.py cover discovery, read-only invocation, denial and durable audit.
- The initial server only implements r3.status and does not yet provide host execution. No live Grace-to-R3-native invocation or deployment verified. Phase 2 remains OPEN pending integration evidence; Phase 3 will add local/LAN execution. Preserve live Camrui legacy MCP code and existing service until controlled cutover.

## Phase 2 end-to-end verification and handoff (2026-11-02)
- Goal: independently discover, invoke, authorize and audit R3-owned tools, with durable resident continuation and no R2/Comms5 dependency.
- Verified by Steward on Camrui isolated archive of commit 31650acddffd0ffbf446319ea4a054aa9aadd18f: 15/15 permanent tests passed in 1.754 seconds. tests/test_native_integration.py exercised actual loopback HTTP GET /v1/tools and POST /v1/tools/invoke (both 200), resident TOOL_INTENT/TOOL_RESULT, completion, and persistent SQLite audit with simulated inference.
- Files: runtime/native_tools.py, runtime/tool_server.py, runtime/serve.py, runtime/configuration.py, tests/test_native_tools.py, tests/test_tool_server.py, tests/test_native_integration.py, docs/r3-native-tool-contract.md. Phase 2 code path VERIFIED in isolation; production live 80B and service deployment NOT verified.
- Limits: only read-only r3.status is implemented. Write execution and server-side grants are not yet supported; legacy Comms5 live service remains untouched. Phase 3 entry: implement configurable local/LAN host execution, authorization and audit without importing R2 tool catalog; then reconcile and deploy safely.

## Phase 3 local execution verification (2026-11-02)
- Steward ran isolated archive of commit e610084c6f78cc560fb94fbd69a6cb32244d4e15 on Camrui. Python compileall passed; 17/17 permanent tests passed in 2.116 seconds.
- Verified: configuration-defined shell-free local command execution, denial of unapproved arguments/write-classified catalog entries, SQLite execution audit, and previously tested native resident HTTP tool continuation.
- Files: runtime/host_execution.py, runtime/tool_server.py, config/host-tools.json, tests/test_host_execution.py.
- Phase 3 remains OPEN: LAN remote host access, host-specific authorization, and production Grace integration are not implemented or verified. Live Camrui checkout and user service unchanged. Next: implement LAN execution with independently controlled authorization and durable audit, then validate against real hosts.

## Phase 3 LAN transport regression verification (2026-11-02)
- Steward ran isolated archive at e28e38cce04d60f397167165a0662cf5bc227bf2 on Camrui: compileall passed; 20/20 permanent tests passed in 2.296 seconds.
- runtime/host_execution.py supports fixed-command SSH transport with BatchMode=yes and StrictHostKeyChecking=yes; tests/test_lan_execution.py verifies command construction, unsafe alias/argument rejection and fail-closed unauthorized arguments. SSH execution in these tests was mocked, NOT a real LAN host connection.
- Next Phase 3 evidence: verify actual Camrui SSH connectivity and command execution against known hosts, validate tool-server audit, and reconcile live deployment without overwriting uncommitted files. Phase 3 remains OPEN.

## Phase 3 external host registry verification (2026-11-02)
- Steward verified isolated archive at cf14f68fa3204dd6cd642d99abfe5b4e2e9c22c7 on Camrui: compileall passed, 23/23 permanent tests passed in 2.152 seconds.
- External host registry controls address, user, port, SSH identity and known-hosts path. New permanent tests cover configured SSH argument construction, unknown-host rejection and malformed-profile rejection.
- Operational discovery: Windows SSH alias octo1 authenticated to OctoMiner1 as root and executed hostname/whoami/uptime. Camrui -> OctoMiner1 at 192.168.1.160 reaches port 22 and recognizes host key but admin1 login failed; Camrui's correct remote identity and trust/credential setup are not verified. Do not equate Windows SSH success with Camrui SSH access.
- Next: establish Camrui->OctoMiner1 credential using existing documented infrastructure, then execute real native tool invocation and verify audit; no live service changes. Phase 3 OPEN.

## Phase 3 real LAN invocation evidence (2026-11-02)
- Camrui authenticated to OctoMiner1 as root using existing /home/admin1/.ssh/octominer1_nopass, strict host-key verification, and returned uptime with SSH exit 0.
- R3 isolated archive from branch at checkpoint 20759e0: native ToolRouter discovered r3.host.uptime, HostExecutor invoked OctoMiner1 via configured SSH registry, HTTP-style router code 200, subprocess returncode 0, uptime stdout, empty stderr; SQLite audit row ('r3.host.uptime','OK'). All Python qualification assertions passed and printed QUALIFICATION PASSED.
- Important qualification caveat: outer shell script exited abnormally because malformed here-document closing delimiter caused Python NameError: name 'PY' is not defined after assertions. The real execution and audit were demonstrated, but clean process exit is NOT verified. Repeat using corrected command if clean-exit evidence is required.
- Phase 3 still OPEN pending live resident-to-host execution and safe service integration. No live Grace service modifications.


## Real 80B resident-to-native-host qualification (2026-11-02, 13:30 EST onward)
- Candidate commit fda9875996474b79d7e95ee8904753c2f9629f85 staged in /home/admin1/.local/share/r3/releases/fda9875; external Grace config uses r3-native endpoint http://127.0.0.1:8765 with explicit read-only allowlist r3.status and r3.host.uptime.
- Steward verified isolated candidate permanent regression suite: 24 tests, OK, 4.553 seconds. Production service reported active.
- In isolated candidate state /home/admin1/.local/state/r3-qualification/fda9875, real Qwen3-Next-80B inference on OctoMiner1 processed resident event ID 1; resident_inbox status COMPLETED; durable resident_turns sequence [(0, ASSISTANT), (1, TOOL_INTENT), (2, TOOL_RESULT), (3, ASSISTANT)]; tool_audit reported [('r3.host.uptime', 'OK')].
- This is verified real-model native tool selection, local Camrui command invocation, durable result and model continuation. It is not yet persistent institutional scheduler deployment or sustained autonomous recovery qualification. No assertion about final assistant response content was collected.
- Steward subsequently checked production service using correct unit name: active, MainPID=2840691, ActiveState=active, SubState=running. A follow-up sqlite3 CLI query failed because sqlite3 executable is not installed; earlier Python sqlite3 audit result remains valid. Do not interpret CLI absence as database failure.
- Phase 3 principal real-model integration demonstrated in isolation; Phase 5 first real tool cycle demonstrated. Remaining: safe controlled deployment, ongoing event-driven operation/recovery, remote MCP and production observability. Preserve current live modified/untracked checkout and database; no in-place reset.


## Production scheduler-driven Grace qualification (2026-11-02, Steward-observed)
- Controlled production cutover: user systemd service `r3-institution.service` switched to immutable release `/home/admin1/.local/share/r3/releases/fda9875`, using `runtime.serve --db /home/admin1/.local/state/r3-runtime/institution.db --health-file /home/admin1/.local/state/r3-runtime/health.json --config-dir /home/admin1/.local/share/r3/releases/fda9875/config`. Observed active/running PID 3035012. Native tool server `r3-native-tools.service` active PID 3032116. Prior checkout and SQLite online backup preserved.
- Permanent generic event CLI committed: `runtime/inbox_cli.py` at e5135a12343de53e4e2f30540f3fc5ce58be4046 and `tests/test_inbox_cli.py` at ec352c00db3aed93e86ca91647a0eb03e707e6a7. Staged separate archive `/home/admin1/.local/share/r3/releases/event-cli-20261102` at ec352c0; full permanent suite **28/28 PASS** in 2.933 seconds. CLI does not replace the running institution service.
- **Real production execution:** permanent CLI submitted `resident_inbox.id=3`, resident Grace, event type `HOST_STATUS_REQUEST`, payload requesting Camrui uptime. The running institution scheduler independently processed it to `COMPLETED`. Durable `resident_turns` sequence: `0 ASSISTANT`, `1 TOOL_INTENT`, `2 TOOL_RESULT`, `3 ASSISTANT`. Production `native-tools.db` audit: `(1, 'r3.host.uptime', 'OK')`. Final model `/root/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf`; 434 tokens total. Both services remained active.
- Qualification conclusion: persistent production event pickup, real 80B reasoning, native read-only tool invocation, audit and completion **PASS for this event**. Completion is software event completion, not independent proof of broader real-world objective completion.
- Remaining Phase 5/6 gates: restart recovery with pending and interrupted work; uncertain tool-outcome fail-closed behavior without duplicate invocation; queued events; failure handling; sustained operation and truthful health/dashboard visibility. Do not claim these passed based on the single event.
- Next action: qualify restart recovery safely with a durable PENDING event submitted while the institution service is stopped, then start the service and verify completion and exactly one tool audit. Separately verify interrupted tool-intent recovery with permanent tests before attempting any live interruption of an executing tool.


## Production pending-event restart recovery — PASS (2026-11-02)
- Steward stopped only `r3-institution.service`, leaving `r3-native-tools.service` running. Submitted durable `resident_inbox.id=4` (`RESTART_RECOVERY_CHECK`) using permanent `runtime.inbox_cli`; verified `PENDING` before institution restart.
- Restarted institution service and observed event 4 `COMPLETED` via the live scheduler and Qwen3-Next-80B-A3B. Durable turns: `0 ASSISTANT`, `1 TOOL_INTENT`, `2 TOOL_RESULT`, `3 ASSISTANT`. Tool intent `r3.host.uptime`; production audit appended `(2, 'r3.host.uptime', 'OK')`, following event 3 audit `(1, 'r3.host.uptime', 'OK')`.
- Final service state: institution active PID 3042258; native tools active PID 3032116. **Pending-event restart recovery PASS.**
- Qualification scope: persistence and processing of a previously PENDING event across orderly institution stop/start. Not evidence of recovery from a process crash during an in-flight tool call, nor exactly-once execution under uncertain outcome; those require independent permanent regression and correlation tests. Camrui host uptime is not institution service uptime.


## Core autonomy focus: objective continuity (2026-11-02)
- Source inspection confirms `runtime/institution.py` schedules only when the resident inbox has PENDING/PROCESSING work. `runtime/resident_inference.py` can make multiple tool calls within one event but marks that event COMPLETED whenever the model returns a final assistant message; there is no durable, explicitly modeled unfinished-objective continuation across independent scheduler activations.
- This is the next **core autonomy** blocker, not an edge-case recovery exercise. Implement a resident-neutral durable objective-continuation contract within the existing journal/inbox and scheduler, with model-controlled progress/continuation, evidence, permanent regression tests, and no hardcoded number of cycles or elapsed objective ceiling. Preserve existing simple event behavior.
- Do not infer that a model-generated text answer proves objective accomplishment. Separate reported progress from independently verified completion. Avoid building a second work-order engine or scripted demonstration loop.
- Prioritize this work over additional speculative crash simulations. Retain fail-closed uncertain-tool-outcome behavior as an existing safety invariant, to be qualified later.
