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

## Checkpoint index
- Earlier MCP milestone: hints/milestones/2026-11-02-grace-mcp-milestone.md
- Phase 1 continuity checkpoint: this document
- Phase 2–6: pending; append links and commit SHAs on completion.
