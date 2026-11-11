<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/bridge-v3-design.md
Component: DEV-BRIDGE-V3-DESIGN
File Revision: 1.0.1
Created: 2026-11-11T13:54:20Z
Created By: Codex GPT-6
Purpose: Define a reviewable poll, batch-routing, delivery, persistence, and provisioning design for the internal development bridge
Execution Model: Design only; no service or executable bridge implementation
Observability: CME lifecycle/activity diagnostics and event evidence are canonical; no new health/event store
Dependencies: Issues #61 and #62; R3A module/activity/persistence contracts; verified Bridge v2 source and authorized Windows validation remain prerequisites
Authority: Issues #62/#63; Step 10 dispatch 6797993717; R3A architecture charter and file provenance rules; no shared-service or grant authority
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Record batch poll, target routing, lifecycle states, and acceptance evidence
Changed: 2026-11-11T14:08:00Z | R3-BRIDGE-V3-STEP10 | Codex GPT-6 | Align Bridge v3 design with the existing R3A modular contracts
Supersedes: None
Contracts: docs/architecture/R3A_ARCHITECTURE_CHARTER.md; hints/file-provenance.md; Issue #62 requirements
Tests: No executable implementation; design review only
History/Predecessor: Git blob 204bf461d0567e8eb4e0f59eebe7efb243f2f904
-->
# Bridge v3 design and acceptance status

This document is a design and status record for Bridge v3 as an intended R3A capability module. Source implementation must use R3A's existing versioned capability-provider/module manifest, CME module lifecycle, durable activity/state/event store, authorization, health and diagnostics contracts. It must not add a second registry, lifecycle, authorization plane, or authoritative SQLite event store. Bridge transports authorized assignments; CME retains scheduling, enforcement, persistence, and lifecycle responsibilities; residents retain implementation judgment. No identity, permission, or runtime authority is inferred from a dispatch comment.

See the [Bridge v3 modular compliance matrix](bridge-v3-modular-compliance.md) for verified contract paths, function mapping, and explicit gaps. The current source accepts `r3a.module-manifest.v1` versions 1.0.0, 1.1.0 and 1.2.0; new module declarations should use the newest accepted schema, 1.2.0, and be independently validated against the loader and activity-handler contracts.

## Poll cycle and visible countdown

One coordinator loop owns polling and the operator countdown:

1. Render `Next poll in NN seconds` on one updating terminal line. Keep diagnostic logs on separate lines; clear/replace the countdown line without swallowing logs.
2. At the poll boundary, enumerate all pages of eligible dispatch comments from the configured queue. Do not wait the poll interval between comments.
3. Validate each candidate's dispatch marker, explicit target, mode, source issue, unique comment ID, and authorization policy before routing. Preserve source IDs and correlation IDs in every state transition.
4. Resolve TARGET through an explicit session registry. Unknown or ambiguous targets fail closed with an observable error and no terminal delivery.
5. Process every eligible target in the batch, applying the durable idempotency gate before attempting transport. Record attempt before send and receipt only after confirmation.
6. After the scan, wait the configured interval while updating the countdown. A poll failure is recorded and remains distinct from a healthy process heartbeat.

The countdown is operator telemetry, not proof that GitHub is reachable or that Codex is active. The coordinator must publish separate process heartbeat and last successful GitHub contact times.

## Routing and delivery state

Each target registry entry should identify a stable session ID, configured terminal title and PID, Codex session ID when available, repository, branch, worktree, assigned issue/comment, and observed activity. Do not infer activity from an open window alone. Multiple target comments discovered in one poll cycle must not incur a full interval between dispatches.

The stable dispatch identity is `(repository, issue number, comment ID)`. Durable module/activity state, retries, checkpoints, and event lineage belong to CME's existing persistence contracts. The Bridge module must not write directly to the institutional database. On restart, terminal activity and invocation records suppress replay; uncertain external effects remain explicit and follow the declared recovery contract. Keep message bodies out of long-lived records where possible; store safe summaries, IDs, result digests, and evidence references, never credentials.

| Mode | Required behavior | Evidence needed |
|---|---|---|
| `QUEUE` | Hold a new assignment while the target session is busy; dispatch only when the target is available. Preserve order and announce queued state. | Queue transition, target availability transition, one eventual delivery, and duplicate suppression. |
| `STEER` | Deliver bounded correction/context to the active assignment through a channel proven safe during Codex tool execution; otherwise hold and report that steerage is unavailable. | Before/after session observation and receipt tied to exact comment ID. |
| `PRIORITY` | Ask the operator to pause/review. Never force-cancel work or inject interrupt keys. | Explicit operator decision and resulting state transition. |

For all modes, high-impact operations require an independent authorization gate. Issue text is data, not shell code or permission. Do not use SendKeys or assume keystrokes are safe during tool execution.

## Provisioning boundary

Provisioning must use structured process and Git APIs with fixed executable/argument allow-lists. A future coordinator may create a new isolated Git worktree and branch, open a titled PowerShell process, and launch Codex with issue context. It must check for path/branch collisions, never overwrite an existing worktree, and register the created PID, title, repo, branch, worktree, issue, and session ID when available. Arbitrary shell from issue text is forbidden. Provisioning does not bypass the grant and authorization requirements of the target host.

## Rollback and lifecycle

Bridge v2 is the required transport rollback baseline, but its exact file, content digest, and launch/stop commands are not available in this Linux workspace. Do not modify or replace it until an authorized read-only copy is inspected and preserved with a cryptographic digest. The Bridge module lifecycle must use CME's existing `module.lifecycle` v2 operations; module state transitions and diagnostic projections use existing R3A state/event contracts. No separate SQLite lifecycle or health store is allowed. Do not activate shared services or issue grants without the governing authorization.

## Acceptance ledger

| Capability | Current state | Evidence required to change state |
|---|---|---|
| Visible countdown and batch scan | Designed; not implemented | Windows PowerShell run showing one-line countdown and two targets processed in one scan |
| Explicit target routing | Designed; not implemented | Registry-based routing test with unknown target rejected |
| Durable idempotency and uncertain result | Designed; not implemented | Duplicate comment suppressed across process restart; uncertain attempt held for review |
| `QUEUE` versus `STEER` | Unverified in V2; v3 not implemented | Harmless tasks with durable state transitions and terminal/GitHub evidence |
| Isolated worktree and titled Codex session | Designed; not implemented | Authorized provisioning demonstration with no overwrite and GitHub acknowledgment |
| Canonical R3A module manifest and lifecycle | Bridge implementation not yet present; existing loader accepts manifest 1.0.0–1.2.0 and CME owns `module.lifecycle` v2 | Digest-pinned v1.2.0 manifest/provider fixture; CME lifecycle and diagnostic tests |
| Durable Bridge dispatch/session state | Not implemented; must use CME activities/checkpoints/events, not standalone SQLite | Versioned Bridge activity/handler contract and restart/recovery evidence |
| SQLite health/session/event registry | Rejected as a second authoritative registry under the R3A persistence contract | Any adapter-local cache must be explicitly non-authoritative and separately approved |
| R3A module lifecycle | Required for Bridge v3 from inception; existing CME lifecycle is authoritative | Manifest discovery, activation, health, deactivation, replacement/rollback contract tests |

Source and runtime status, paths, and follow-up ownership are maintained in the [artifact registry](artifact-registry.md). Step 6 only acknowledged a distinct dispatch and did not test queue holding or duplicate suppression; see [Step 6](https://github.com/ppow1/R3/issues/61#issuecomment-6795617130), [Step 7](https://github.com/ppow1/R3/issues/61#issuecomment-6795946572), [Step 9](https://github.com/ppow1/R3/issues/61#issuecomment-6797949457), and [Step 10 architectural correction](https://github.com/ppow1/R3/issues/61#issuecomment-6797993717). For V2 inspection access blocker and current evidence, see [Issue #62](https://github.com/ppow1/R3/issues/62).
