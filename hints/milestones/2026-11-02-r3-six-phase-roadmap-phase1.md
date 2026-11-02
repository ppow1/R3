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
