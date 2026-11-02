<!--
R3 CONTROLLED DOCUMENT
File: hints/milestones/2026-11-02-grace-mcp-milestone.md
Component: R3-MILESTONE-MCP-001
File Revision: 1.0.0
Created: 2026-11-02 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Executive milestone and detailed engineering handoff for Grace MCP autonomy and Comms 3 architecture.
Execution Model: Documentation only.
Observability: User-supplied terminal outputs, Event 2 journal, R3 source inspection.
Dependencies: AI_HINTS.md; hints/engineering-test-policy.md; runtime/mcp_tools.py; runtime/resident_inference.py; runtime/serve.py
Authority: Steward-directed milestone; design pending implementation.
Changed: 2026-11-02 UTC | R3-MILESTONE-MCP-001 | Record technical chronology, successes, failures and architecture decisions.
Supersedes: None
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/file-provenance.md
Tests: No new tests; records real event evidence.
History/Predecessor: New milestone.
-->

# Milestone — Grace's first autonomous MCP tool invocation; R3 Comms architecture redesign

**Date:** November 1–2, 2026 (Steward local time, session wrapped at approximately 12:22 AM).  
**Repository:** ppow1/R3; branch engineering/institution-runtime-v1-20261101.  
**Milestone:** **ACHIEVED for autonomous MCP tool selection and invocation; NOT ACHIEVED for completed tool-result continuation.**  
**Follow-on:** R3-native Comms 3, local-first network topology, HTTP 400 root cause.

## Executive summary

Grace's persistent R3 runtime accepted a real Steward objective, sent it to the 80B model, and the model independently selected the real `comms5_examples` tool. R3 called the authenticated Riverview Comms 1.1 MCP endpoint, received the response, and wrote assistant/tool-intent/tool-result evidence into its SQLite journal. A prior direct test of the R3 MCP adapter had discovered **43 tools** and invoked the same tool successfully. This proves real model-selected MCP invocation through R3; it is not a simulated tool call.

**The objective did not complete.** R3 Event **2** ended `FAILED` after the successful tool call because the next OpenAI-compatible model completion returned `HTTPError 400: Bad Request`. The HTTP error body was not captured; the root cause remains unknown. Do not claim that R2 workflows caused the HTTP 400: the MCP tool had already returned successfully.

The Steward identified a larger architectural flaw: **Riverview Comms 1.1 exposes Riverview 2 workflows**, including seed/specification/approval/work-order operations. R3 must not present Grace with tools that can accidentally enter the R2 institutional machinery. The approved design direction is an **R3-native MCP server/catalog (Comms 3)** with no R2 workflow doorway or implicit fallback. Reuse proven implementation components when appropriate, but not R2's workflow contracts.

A second design direction is **local-first communications**: STDIO MCP for Camrui-local operations, private LAN execution for other local hosts, and an internet-facing endpoint only for genuinely remote functions (including ChatGPT/escalated reasoning). The precise topology and contracts still require investigation.

## 1. Environment and configuration observed

- R3 candidate checkout: `/home/admin1/r3-runtime-candidate` on Camrui.
- Service: systemd user `r3-institution.service`, confirmed **active** after configuration and restart.
- SQLite: `/home/admin1/.local/state/r3-runtime/institution.db`.
- Health snapshot: `/home/admin1/.local/state/r3-runtime/health.json`.
- Service overrides: `10-grace-inference.conf` and `20-mcp-client.conf` under `~/.config/systemd/user/r3-institution.service.d/`.
- Model endpoint: `http://192.168.1.160:8080/v1`, with model configured through `R3_GRACE_MODEL`.
- Original MCP URL: `https://api.sondahub.com/mcp` (wrong provider for intended Riverview work).
- Diagnostic MCP URL after change: `https://riverview-comms.ionoge.com/comms5/mcp` (R2-oriented Comms 1.1).
- A local loopback Comms URL `http://127.0.0.1:11826/mcp` had been identified but **was not tested as R3's selected endpoint**.
- Bearer token file: `~/.config/r3/comms-bearer.token`, confirmed permissions **600**, size **64 bytes**. Token bytes intentionally omitted.
- Existing R3 source: `runtime/mcp_tools.py`, `runtime/resident_inference.py`, `runtime/serve.py`, `runtime/institution.py`.

## 2. Chronology and exact outcomes

### 2.1 Initial confusion over the MCP connection

The 80B model had already been shown in a separate tool-capable interface successfully calling `comms5_examples`. A direct R3 Python MCP SDK attempt to the public Comms URL received HTTP **401** and a Bearer authentication challenge. The assistant mistakenly asserted that Grace needed a new OAuth authorization flow. The Steward corrected this: the existing integration uses a **bearer token**, not a new OAuth setup. A working UI connection does not by itself mean R3's Python client has the same headers; the correct fix was to configure the R3 adapter to supply the bearer token.

### 2.2 Token transfer failures and clipboard lesson

The first secure prompt/SSH transfer printed `TOKEN_INSTALLED`, but the file was actually **0 bytes**. A second Base64 pipeline attempt emitted `base64: invalid input`, yet printed another misleading success while the file was **1 byte**. A temporary-file proposal was rejected as too complicated. The user explicitly preferred straightforward commands over repeated security ceremony. The final direct SSH command wrote the existing bearer token and confirmed **`TOKEN_INSTALLED permissions=600 size=64 bytes`**.

The bearer token had been inadvertently pasted into the conversation when a script failed to follow the user's clipboard-first practice. The assistant acknowledged responsibility. The Steward explicitly declined token rotation; **no rotation was performed**. Never reproduce token bytes in source, logs, or this milestone.

Recurring Windows PowerShell → Bash multiline scripts ended with `bash: ... $'\r': command not found` due to line endings, even when earlier work succeeded. Prefer robust single-line SSH or properly normalized scripts; always validate exit status and actual output. Mandatory user convention: `Clear-Host`; collect in `$Result`; display `$Result`; `$Result | Set-Clipboard`. A printed success string without validation is not success.

### 2.3 R3 adapter integration

Inspected `runtime/mcp_tools.py` revision 1.0.2: `MCPTools` used the official Python MCP SDK's `streamablehttp_client` for both discovery and invocation, but did not supply authentication headers. The existing adapter was modified in place: a `_headers()` method reads the local token file and returns `Authorization: Bearer ...`; **both** SDK connection sites now supply those headers. Backup `runtime/mcp_tools.py.bak` was written. The existing `20-mcp-client.conf` was backed up and changed from SondaHub to the Riverview Comms URL. Python syntax compilation passed; systemd daemon-reload and service restart succeeded.

Reported:
```text
ADAPTER_UPDATED
BEARER_HEADER_CONFIGURED
COMMS_ENDPOINT_CONFIGURED
SERVICE STATUS: active
R3_GRACE_MCP_URL=https://riverview-comms.ionoge.com/comms5/mcp
TOKEN FILE: permissions=600 size=64 bytes
```

### 2.4 Direct MCP adapter verification

Using R3's actual `MCPTools` adapter, a read-only diagnostic reported:
```text
DISCOVERED_TOOLS=43
COMMS5_EXAMPLES_DISCOVERED
COMMS5_EXAMPLES_RESULT=<nonempty JSON tool response>
R3_COMMS_MCP_VERIFIED
```
The response contained examples of R2-specific contracts such as `submit_steward_seed`, `store_specification`, promotion and work-order formation. This verified authentication, discovery and a real call, **not** autonomous objective completion.

A separate attempt to run a Camrui read-only inspection via Comms 1.1's command task gateway returned `bounded_request_or_state_invalid` despite grant evidence. This is a distinct R2 Comms command-gateway issue, not failure of bearer authentication or MCP tool discovery. Inspection proceeded over Windows-to-Camrui SSH.

### 2.5 R3 source contract and live Event 2

`runtime/resident_inference.py` defines `Inbox.enqueue` (durable insert), `Inbox.next` (PENDING/PROCESSING), `Inbox.record` (ordered `resident_turns`), and `Inbox.finish` (COMPLETED/FAILED). `ResidentInference.__call__` discovers tools, sends tool definitions to the model, records assistant messages and tool intent, executes selected tools, records tool results, and loops to model continuation. Pending tool intent without a result fails closed rather than replaying an uncertain operation. `runtime/serve.py` registers `Grace` and monitors her inbox.

A genuine Steward objective was enqueued via the existing database:
- `EVENT_ID=2`
- `RESIDENT=Grace`
- `EVENT_TYPE=STEWARD_OBJECTIVE`
- Objective: identify the connected MCP service using `comms5_examples`, inspect evidence, do no writes.

The actual journal returned:
- **Seq 0, ASSISTANT:** model stated it would call `comms5_examples`, and emitted a structured tool call with arguments `{}`, ID `LkBLeUzgj1izOSmR2YB0pWBPMa2tXPIT`.
- **Seq 1, TOOL_INTENT:** same ID, tool `comms5_examples`, params `{}`.
- **Seq 2, TOOL_RESULT:** matching tool-call ID, real JSON returned from Comms 1.1, recorded durably.
- **Final status:** `FAILED`, result `{"error": "<HTTPError 400: 'Bad Request'>"}`.

**Verified:** Grace independently selected a real tool, invoked it and received its result. **Not verified:** successful post-tool reasoning, final answer, full autonomous completion. The journal-display command truncated printed content for readability; no evidence establishes that the stored tool result itself was truncated.

## 3. HTTP 400: precise fault boundary

The initial 80B model request succeeded. MCP discovery succeeded. The Comms tool invocation succeeded. The **next** call to the inference endpoint failed with HTTP 400. This is the R3 **model continuation boundary**, not proof of an R2 workflow failure.

Potential explanations (unverified): assistant/tool-message shape rejected by llama.cpp, incompatible tool-call fields or chat template, oversized result/context, or another server validation error. The large `comms5_examples` response is a candidate contributor, not a demonstrated cause.

The current `InferenceEndpoint.complete()` raises `urllib.error.HTTPError` without capturing its response body. First permanent diagnostic improvement: preserve a **sanitized** server error body, request-shape metadata, and relevant model/server configuration in the existing journal. Then correct the actual protocol issue, with reusable regression coverage. Do **not** guess by rewriting message formats or arbitrarily truncating tool results. Changing MCP transport alone will not necessarily fix this 400.

## 4. Architectural decision: no R2 doorway in R3

The Steward rejected exposing R2's entire 43-tool catalog to Grace. Even if Grace chooses correctly most of the time, a mistaken call could enter R2's seed, approval, specification or work-order pipeline and produce confusing downstream state. This is an architectural hazard, not merely a prompt-engineering issue.

**Direction:** Riverview Comms 3 should have its **own MCP endpoint, tool catalog, implementation ownership and R3 authority contract**. Proven SSH, PowerShell, Bash, Codex, transport, and escalated-reasoning functions may be copied or adapted. R2 workflow functions and implicit routes must not be present in the R3-facing interface. Do not merely hide tools from Grace while leaving them callable. No R2 fallback. Existing Comms 1.1 remains a diagnostic connection only until replaced.

The MCP service supplies capabilities; **R3's institutional runtime** supplies objective interpretation, resident roles, Steward authority, coordination, evaluation, recovery and completion. Do not rebuild R2's workflow machinery under a new MCP name.

## 5. Communications topology requiring investigation

**Local STDIO:** MCP client starts a local server process and exchanges protocol messages over stdin/stdout. For Camrui-local state, files, services, residents and databases, this avoids a public HTTP server and an Ionoge round trip. STDIO is local transport, **not a guarantee of no network egress by tools**.

**Private LAN:** Windows development desktop, Camrui, OctoMiner1 and OctoMiner2 should communicate through appropriately authorized LAN routes (e.g. SSH, private HTTP/MCP, or existing host agents) when work is local. Avoid Camrui → Ionoge → Camrui/other LAN host for a purely local action.

**External endpoint:** Maintain a separately controlled internet-facing path on Ionoge where external ChatGPT access, escalated reasoning, or other remote integration genuinely requires it. Reuse proven external reasoning functionality without importing R2's institutional workflow. Define separate client identity, auth, permissions and exposed tool subsets.

Prefer a coherent R3 tool contract across appropriate transports, but do not assume every client should see every tool. Exact service/process count, endpoint design, subprocess supervision, authentication, network policy, retry semantics and operational deployment are **not yet decided**.

## 6. Open engineering investigations and priorities

1. **P0 — Comms 3 isolation:** inventory 43 Comms 1.1 tools and dependencies; distinguish transport primitives from R2 workflows; design R3-only catalog; prove no R2 workflow route is callable.
2. **P0 — HTTP 400:** capture sanitized inference-server response body; inspect actual llama.cpp rejection and tool-message compatibility; repair generic continuation; validate model → tool → model → completion.
3. **P0 — Permanent engineering policy:** obey `hints/engineering-test-policy.md`. No throwaway tests, synthetic production work, artificial task/loop caps, timing-dependent deployment gates, or special-case runtime restrictions.
4. **P1 — STDIO:** SDK compatibility, lifecycle/supervision, stdout protocol cleanliness, logging, permissions, restart and failure behavior.
5. **P1 — LAN transport:** host-specific command/Codex execution and evidence without unnecessary external relay; preserve authorization and audit.
6. **P1 — External access:** Ionoge endpoint, ChatGPT and escalated-reasoning integration, cost/provenance, auth and tool exposure.
7. **P1 — Write authorization:** current `MCPTools.invoke` requires `allow_write` and `R3_MCP_ALLOWED_TOOLS`; override is empty and resident invokes without `allow_write`. Design proper R3 Steward authorization, not arbitrary blanket read-only restrictions or an unsafe bypass.
8. **P1 — Recovery:** uncertain tool intent must not be blindly replayed; preserve durable IDs, idempotency and reconciliation.
9. **P1 — Observability:** `runtime/serve.py` hardcodes `resident_tool_execution_connected=False`; distinguish configured, connected, last successful tool call, model continuation and objective status.
10. **P2 — Deployment:** provenance headers, backups, service lifecycle, health, config, secrets handling, rollback, durable documentation and versioned R3 contracts.

## 7. Final milestone disposition

**Passed:** persistent R3 inbox ingestion; 80B model-selected Comms 1.1 tool call; authenticated MCP discovery of 43 tools; real tool result; durable assistant/intent/result journal.

**Failed:** Event 2 post-tool model continuation (HTTP 400); no completed objective.

**Architectural decision:** isolate R3 from R2 workflows with an R3-native Comms 3 catalog; reuse proven low-level implementation selectively.

**Further investigation required:** local STDIO, LAN/private routing, external Ionoge gateway, escalation, authority and continuation compatibility.

**Do not proceed as though Comms 3 is implemented or R3 autonomy is qualified.** Preserve the successful evidence and fix the remaining failures within the permanent R3 architecture.
