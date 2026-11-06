<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/evidence/2026-11-05-live-observations.md
Component: AUDIT-GRACE-AUTONOMY-EVIDENCE
File Revision: 1.0.0
Created: 2026-11-06T00:41:22Z
Created By: Codex GPT-6, acting on Steward instruction
Purpose: Record sanitized, reproducible evidence supporting the Grace autonomy audit
Execution Model: N/A; evidence record
Observability: Read-only local service probes, SQLite read-only aggregates, source/config/history review, and Issue #41 coordination
Dependencies: Local R3 host and repository at the audit baseline; deployed candidate release 8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135
Authority: Steward directive in Issue #41; inspection only; no production changes, deployments, grants, or institutional writes
Changed: 2026-11-06T00:41:22Z | RIVERVIEW-CORE-AUDIT-2026-11-05 | Codex GPT-6 | Initial evidence record
Supersedes: None
Contracts: Read-only inspection of R3 runtime, authority/tool, verification, and Comms5 contracts
Tests: N/A; test suite not run or modified during this audit
History: New evidence record for companion audit report
-->
# Live and historical evidence record

This record contains only operational facts and aggregate counts needed for the [functional audit](../2026-11-05-riverview-core-autonomy-functional-audit.md). Credential values, message text, proposal content, and full sensitive record identifiers are intentionally excluded.

## Observation scope and safety

Evidence was collected on 2026-11-05 local time and summarized through 2026-11-06 00:41 UTC. Queries against the institution SQLite file used SQLite URI `mode=ro`; no SQL writes were issued. HTTP checks were GET requests to health, tool discovery, and unauthenticated protected paths. No assignment was created, no authenticated command was sent, no grant or credential was changed, no service was restarted, and no deployment action was taken. Issue #41 comments were read and the Grace workstream start status was posted there.

## Process and service observations

- User unit `r3-institution.service` was active under PID 2663801 from immutable release `r3-unified-8ab4b2ab1669`; its exact source revision is `8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135`. It runs `runtime.serve`, uses the persistent institution SQLite file, and reads configuration from that release.
- Website process PID 2663804 was active on `0.0.0.0:8303` from the same immutable release. Local `GET /api/v1/health` returned HTTP 200 and service status `running` with HR storage `ready`.
- The institution health file reported one configured resident, assignment intake and conversation API enabled, tool discovery/execution connected, inference connected, and an independent reviewer connected. Source inspection shows inference-connected is based on whether a resident is registered; tool-execution-connected is based on discovery, not a real authorized invocation. The reviewer probe is a direct evaluator health check.
- The configured large-model endpoint returned HTTP 200 for read-only `/v1/models`; this establishes API reachability, not successful generation. A separate small local model process was not the configured Grace endpoint.
- Listener roles observed: website 8303; assignment intake 8769 loopback; conversation API 8770 loopback; native tool server 8765 loopback. Additional staging/experimental listeners were present. The staging `r3-website.service` uses a separate old checkout on loopback 18303 and is not the 8303 website process.
- The active native tool server was a separate service from release family `hr-native-010c2d971828`, with catalog from an older release directory and no available Git metadata. Its source file SHA256 differed from the unified release candidate’s `runtime/tool_server.py` SHA256 (`dd0a8758...f181c` versus `4a62b306...a41347`). This proves separate artifact provenance; it does not alone prove a runtime incompatibility.
- Anonymous GET to native `/v1/tools` returned HTTP 200 with eight descriptors: status, host uptime, local resource snapshot, GPU capacity assessment, evidence recording, and three HR operations. Grace’s deployed configuration filters the visible allowlist to status and host uptime. Anonymous requests to assignment detail, resident conversations, chat session, and resident directory returned HTTP 401.
- Two attempted public health URLs returned HTTP 404. The correct public route was not confirmed, so no conclusion about public website availability is made.

## Durable-state aggregates

Read-only inspection found SQLite integrity `ok`. Counts are from the audit snapshot and may change after collection.

| Store or table | Observation |
|---|---|
| Resident registry/configuration | One resident, Grace; reviewer is separate service |
| Assignment intake | 8 rows, created Nov 3–4 UTC |
| Resident inbox | 25 `RESIDENT_ACTIVITY` events: 24 `COMPLETED`, 1 `FAILED` |
| Review feedback | 270 `REVIEW_FEEDBACK` events, all `COMPLETED`; one root and one unbranched chain of 270 via `previous_event_id` |
| Feedback delivery | One durable delivery row; schema makes `request_id` the primary key and `event_id` unique |
| Verification | 10 `ACCEPTED`, 1 `INCONCLUSIVE`; zero pending in the snapshot; 44 findings, 42 pass and 2 insufficient-evidence |
| Conversation store | 4 conversations, 18 messages at the read-only snapshot |
| Inbox lineage | 13 distinct resident-activity lineages, maximum 5 events in a lineage |
| HR store | 13 records; zero records with a confidential `authority_principal` association |

For the 270-event review-feedback chain, a hash-only summary of `decision.next_step` had four distinct signatures with occurrence counts 170, 91, 7, and 1. Hashes of `decision.evidence` were distinct for all 270 events. Protected content was not printed. This supports a repetitive next-step pattern coupled with changing evidence; it cannot establish whether evidence meaningfully progressed.

Live tool audit aggregates showed 303 successful `r3.status` calls and 303 successful `r3.host.uptime` calls. The audit also recorded denied attempts for invalid/ungoverned tool names and for resource/evidence/HR write operations without matching active grants. Active `resident:Grace` grants in the inspected authority ledger were HR directory read and HR read; no HR write grant was present. Only aggregate names/counts are retained here.

## Comms5 workflow evidence

Read-only Comms5 status and objective projections identify a workflow separate from the R3 runtime:

- Comms5 contract version: `riverview-comms-contract:5.0`.
- Seed submission is classified draft-write; seed promotion and work-order creation are Steward-gated writes. Work-order creation queues one idempotent Codex engineering order; it does not itself execute Codex.
- One Oct 28 objective reached `COMPLETED`; lineage included proposal, Codex dispatch, verified execution step, and objective completion. Its Grace engineering worker execution was independently accepted.
- One Oct 29 objective created a work order that was later rejected for rework; subsequent rework/escalation was pending.
- One Nov 3 objective remained `PROPOSED`, with no assignment and zero dispatches.
- CME status counts of 7 registered workers and 3 enabled workers describe the Comms worker registry, not R3 residents.
- No proposal body-read operation or code path connecting Comms5 dispatch to R3 assignment intake was observed during this audit.

## Historical source and requirement references

| Evidence | What it supports |
|---|---|
| `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md` (Steward-approved Oct 31) | Expected resident autonomy, Grace Director responsibilities, durable institutional operations, peer communication, capability discovery, and honest verification/recovery |
| `hints/verification-and-learning.md` | Some learning/verification feedback behavior is explicitly labeled proposed and not yet implemented |
| `docs/IMPLEMENTATION_HANDOFF.md` | Separate institutional PostgreSQL/history DB is pending; current SQLite assumptions remain relevant |
| `hints/milestones/2026-11-02-grace-mcp-milestone.md` | Real 80B model tool request and durable tool records, followed by HTTP 400 on subsequent model completion |
| `hints/milestones/2026-11-02-r3-six-phase-roadmap-phase1.md` | Live host-status activity completion; restart recovery; later tool calls; unreliable explicit two-stage continuation; one configured resident |
| `hints/deployment.md` | Runtime topology and caution about legacy website listener/process confusion |
| `runtime/assignment_intake.py` | Authenticated assignment API creates resident activity events; it is not proposal intake |
| `runtime/conversations.py`, `runtime/r3_chat_api.py` | Separate durable conversation path and API |
| `runtime/serve.py`, `config/runtime.json`, `config/residents/grace.json` in deployed candidate | Scheduler, one-resident registry, reviewer separation, model endpoint, tool endpoint, narrow allowlist, and continuation event types |
| `runtime/verification.py::queue_review_feedback` | One idempotent feedback delivery per verification request |
| Issue #41 latest integration comment at audit checkpoint | Reports candidate deployment and 284 passing combined integration tests plus 284 passing immutable-release tests; authenticated acceptance and live recovery are unverified |

Historical implementation markers in repository history: supervisor `f495c7e`; scheduler `7dfc0cc`; llama tool `fba4815`; native tool server `0a8f862`; isolated HTTP tool cycle `31650ac`; assignment intake `7fb6031`; conversation API `cfdd032`; independent reviewer `fc76a18`; objective continuation work `96fc020` and `cd6b264`; auth routing `33f0edb`. These demonstrate implementation milestones, not by themselves live acceptance.

## Test-scope evidence

Issue #41’s integration handoff reports 284 tests passing twice (development release and immutable release build). This audit did not rerun the suite. Source review found representative integration tests use temporary databases, fake model endpoints, in-process/local HTTP servers, and test clients. They exercise real component wiring in a test environment but do not prove production configuration, grants, identity mapping, deployment provenance, or a complete Steward-to-verified-objective workflow. See the main audit’s missing acceptance-test inventory.

## Reproduction guidance

Reproduction should be performed only against a similarly authorized read-only environment. The checks behind this record were:

1. Inspect user systemd service status and process arguments; read the health JSON without opening credential files.
2. GET the local health endpoint, model-list endpoint, native tool catalog, and protected endpoints without credentials.
3. Open the institution SQLite database with SQLite URI `mode=ro`; run `PRAGMA integrity_check`, inspect schema, and perform aggregate counts only. For feedback chaining, parse `previous_event_id` and hash result fields before summarizing; do not print payload or model text.
4. Read Comms5 capability/contract/status projections and objective status using read-only operations only.
5. Compare deployed candidate source/configuration and active tool service artifact path/hash; do not restart or replace processes.

No command in this audit requires a write-mode database connection or an authenticated mutating API call.
