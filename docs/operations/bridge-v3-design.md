<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/bridge-v3-design.md
Component: DEV-BRIDGE-V3-DESIGN
File Revision: 1.0.0
Created: 2026-11-11T13:54:20Z
Created By: Codex GPT-6
Purpose: Define a reviewable poll, batch-routing, delivery, persistence, and provisioning design for the internal development bridge
Execution Model: Design only; no service or executable bridge implementation
Observability: Intended GitHub receipts and local SQLite health/session/event records; not implemented here
Dependencies: Issues #61 and #62; verified Bridge v2 source and authorized Windows validation remain prerequisites
Authority: Issue #62; R3 architecture charter and file provenance rules; no shared-service or grant authority
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Record batch poll, target routing, lifecycle states, and acceptance evidence
Supersedes: None
Contracts: docs/architecture/R3A_ARCHITECTURE_CHARTER.md; hints/file-provenance.md; Issue #62 requirements
Tests: No executable implementation; design review only
History/Predecessor: None; new file
-->
# Bridge v3 design and acceptance status

This document is a design record for the internal GitHub-to-Codex development bridge. It does not define an R3A runtime module and does not claim any live capability. Bridge transports authorized assignments and provisions isolated development sessions; CME retains scheduling, authorization enforcement, persistence, and lifecycle responsibilities; residents retain implementation judgment. No identity, permission, or runtime authority is inferred from a dispatch comment.

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

The durable comment key is `(repository, issue number, comment ID)`. Persist each transition transactionally in SQLite before external side effects. On restart, terminal states suppress replay. An attempt left uncertain after a crash is surfaced for operator review; it is never silently resent. Keep message bodies out of long-lived logs where possible; store safe summaries, IDs, result digests, and evidence links, never credentials.

| Mode | Required behavior | Evidence needed |
|---|---|---|
| `QUEUE` | Hold a new assignment while the target session is busy; dispatch only when the target is available. Preserve order and announce queued state. | Queue transition, target availability transition, one eventual delivery, and duplicate suppression. |
| `STEER` | Deliver bounded correction/context to the active assignment through a channel proven safe during Codex tool execution; otherwise hold and report that steerage is unavailable. | Before/after session observation and receipt tied to exact comment ID. |
| `PRIORITY` | Ask the operator to pause/review. Never force-cancel work or inject interrupt keys. | Explicit operator decision and resulting state transition. |

For all modes, high-impact operations require an independent authorization gate. Issue text is data, not shell code or permission. Do not use SendKeys or assume keystrokes are safe during tool execution.

## Provisioning boundary

Provisioning must use structured process and Git APIs with fixed executable/argument allow-lists. A future coordinator may create a new isolated Git worktree and branch, open a titled PowerShell process, and launch Codex with issue context. It must check for path/branch collisions, never overwrite an existing worktree, and register the created PID, title, repo, branch, worktree, issue, and session ID when available. Arbitrary shell from issue text is forbidden. Provisioning does not bypass the grant and authorization requirements of the target host.

## Rollback and lifecycle

Bridge v2 is the required rollback baseline, but its exact file, content digest, and launch/stop commands are not available in this Linux workspace. Do not modify or replace it until an authorized read-only copy is inspected and preserved with a cryptographic digest. Bridge v3 remains **design only** here; there are no start, stop, restart, or rollback commands to execute. Do not activate shared services or issue grants without the governing authorization.

## Acceptance ledger

| Capability | Current state | Evidence required to change state |
|---|---|---|
| Visible countdown and batch scan | Designed; not implemented | Windows PowerShell run showing one-line countdown and two targets processed in one scan |
| Explicit target routing | Designed; not implemented | Registry-based routing test with unknown target rejected |
| Durable idempotency and uncertain result | Designed; not implemented | Duplicate comment suppressed across process restart; uncertain attempt held for review |
| `QUEUE` versus `STEER` | Unverified in V2; v3 not implemented | Harmless tasks with durable state transitions and terminal/GitHub evidence |
| Isolated worktree and titled Codex session | Designed; not implemented | Authorized provisioning demonstration with no overwrite and GitHub acknowledgment |
| SQLite health/session/event registry | Requirement recorded; not implemented | Migration, restart recovery, safe export/snapshot, and read-only consumer contract |
| R3A plugin lifecycle | Planned only; not an R3A module | Separate approved module contract integration and lifecycle tests |

Source and runtime status, paths, and follow-up ownership are maintained in the [artifact registry](artifact-registry.md). Step 6 only acknowledged a distinct dispatch and did not test queue holding or duplicate suppression; see [Step 6](https://github.com/ppow1/R3/issues/61#issuecomment-6795617130) and the [Step 7 assignment](https://github.com/ppow1/R3/issues/61#issuecomment-6795946572). For V2 inspection access blocker and current evidence, see [Issue #62](https://github.com/ppow1/R3/issues/62).
