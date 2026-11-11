<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/bridge-v3-design.md
Component: DEV-BRIDGE-V3-DESIGN
File Revision: 1.0.2
Created: 2026-11-11T13:54:20Z
Created By: Codex GPT-6
Purpose: Define the poll, batch-routing, delivery, persistence, and provisioning boundaries and track the Bridge v3 source implementation
Execution Model: Source provider and mocked acceptance; no shared service or live host execution
Observability: CME lifecycle/activity diagnostics and event evidence are canonical; no new health/event store
Dependencies: Issues #61 and #62; R3A module/activity/persistence contracts; verified Bridge v2 source and authorized Windows validation remain prerequisites
Authority: Issues #62/#63; Step 10 dispatch 6797993717; Step 11 dispatch 6798229653; R3A architecture charter and file provenance rules; no shared-service or grant authority
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Record batch poll, target routing, lifecycle states, and acceptance evidence
Changed: 2026-11-11T14:08:00Z | R3-BRIDGE-V3-STEP10 | Codex GPT-6 | Align Bridge v3 design with the existing R3A modular contracts
Changed: 2026-11-11T14:35:00Z | R3-BRIDGE-V3-STEP11 | Codex GPT-6 | Record implemented module/provider vertical slice and acceptance limits
Changed: 2026-11-11 | R3-BRIDGE-V3-STEP95 | Codex GPT-6 | Record combined-baseline contract correction and Auditor finding response
Supersedes: None
Contracts: docs/architecture/R3A_ARCHITECTURE_CHARTER.md; hints/file-provenance.md; Issue #62 requirements
Tests: 81 combined active-baseline tests passed; see `tests/test_r3a_development_bridge.py` and the registry entry
History/Predecessor: Git blob 7a7c9ec956720fa512d02ca6ee4fcfdf1173e7c9
-->
# Bridge v3 design and acceptance status

This document is a design and status record for Bridge v3 as an R3A capability module. The initial executable slice is in `r3a_plugins/development_bridge/`: a digest-pinned module-manifest v1.1.0 provider, disabled by default, with capability and activity-handler v1.0 contracts, pure dispatch planning, and an injected mocked transport boundary. It uses R3A's existing capability-provider worker, CME module lifecycle, activity/checkpoint, authorization, health, and diagnostics contracts. It does not add an authoritative registry, lifecycle, authorization plane, or event store. CME retains scheduling, enforcement, persistence, and lifecycle responsibilities; residents retain implementation judgment. No identity, permission, or runtime authority is inferred from a dispatch comment.

See the [Bridge v3 modular compliance matrix](bridge-v3-modular-compliance.md) for verified contract paths, function mapping, and explicit gaps. On the active Live Modular integration baseline, the loader accepts `r3a.module-manifest.v1` versions 1.0.0 and 1.1.0; Bridge targets 1.1.0 and the accepted activity-handler v1.0 contract. A prior branch targeted 1.2.0, which this baseline rejects; the Bridge manifest and acceptance checks were reconciled to the actual loader contract.

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

The stable dispatch identity is `(repository, issue number, comment ID)`. The current source slice computes this identity and records it in CME-compatible handler checkpoints. Its optional local SQLite cache is subordinate transport-attempt recovery state only: hashed idempotency key, target, mode, attempt state, receipt reference, and reconciliation reason. It holds no message body, target/session registry, module lifecycle, authorization, or institutional events. A crash during an attempt becomes UNCERTAIN and cannot be retried until explicit reconciliation. Durable module/activity state, retries, checkpoints, and event lineage remain CME responsibilities. The Bridge module must not write directly to the institutional database.

| Mode | Required behavior | Evidence needed |
|---|---|---|
| `QUEUE` | Hold a new assignment while the target session is busy; dispatch only when the target is available. Preserve order and announce queued state. | Queue transition, target availability transition, one eventual delivery, and duplicate suppression. |
| `STEER` | Deliver bounded correction/context to the active assignment through a channel proven safe during Codex tool execution; otherwise hold and report that steerage is unavailable. | Before/after session observation and receipt tied to exact comment ID. |
| `PRIORITY` | Ask the operator to pause/review. Never force-cancel work or inject interrupt keys. | Explicit operator decision and resulting state transition. |

For all modes, high-impact operations require an independent authorization gate. Issue text is data, not shell code or permission. Do not use SendKeys or assume keystrokes are safe during tool execution.

## Provisioning boundary

Provisioning must use structured process and Git APIs with fixed executable/argument allow-lists. A future coordinator may create a new isolated Git worktree and branch, open a titled PowerShell process, and launch Codex with issue context. It must check for path/branch collisions, never overwrite an existing worktree, and register the created PID, title, repo, branch, worktree, issue, and session ID when available. Arbitrary shell from issue text is forbidden. Provisioning does not bypass the grant and authorization requirements of the target host.

## Rollback and lifecycle

Bridge v2 is the required transport rollback baseline, but its exact file, content digest, and launch/stop commands are not available in this Linux workspace. Do not modify or replace it until an authorized read-only copy is inspected and preserved with a cryptographic digest. The provider has been exercised using the existing `CapabilityWorker` prepare/activate/health/execute/checkpoint/stop protocol; this is a fixture test, not shared CME activation. Shared module transitions and diagnostics remain under CME's existing `module.lifecycle` v2 and R3A state/event contracts. No separate SQLite lifecycle or health store is allowed. Do not activate shared services or issue grants without the governing authorization.

## Acceptance ledger

| Capability | Current state | Evidence required to change state |
|---|---|---|
| Visible countdown and batch scan | Designed; not implemented | Windows PowerShell run showing one-line countdown and two targets processed in one scan |
| Explicit target routing | Implemented as pure versioned provider/activity planning; unknown/ambiguous target fails closed | `tests/test_r3a_development_bridge.py`; live canonical target/session registry remains unavailable |
| Mock transport receipts and subordinate attempt recovery | Implemented and tested with injected mock: confirmed receipt deduplicates across cache reopen; in-flight restart becomes uncertain and requires explicit reconciliation | `tests/test_r3a_development_bridge.py`; no real host delivery claim |
| `QUEUE` versus `STEER` | Planner distinguishes queue, steer pending, and review required; safe steer requires explicit adapter support | Real queue draining and active-session steer require an approved target/session source and safe Windows transport |
| Isolated worktree and titled Codex session | Designed; not implemented | Authorized provisioning demonstration with no overwrite and GitHub acknowledgment |
| Canonical R3A module manifest and lifecycle | Implemented with manifest v1.1.0 and activity-handler v1.0.0; disabled registration discovers externally; digest-pinned worker fixture passes prepare/activate/health/execute/checkpoint/stop | `tests/test_r3a_development_bridge.py` plus existing CME lifecycle suites; shared CME activation and diagnostics remain Coordinator-gated |
| CME activity-handler contract | Implemented `bridge.dispatch.plan` v1.1 request/result/progress/checkpoint validation | Contract resolver and payload validation plus worker invocation test; production durable activity submission remains unconnected |
| Authoritative dispatch/session state | CME-owned; only planning checkpoints are emitted, no provider database access | Real end-to-end activity persistence and restart recovery require a managed-runtime authorized acceptance |
| SQLite health/session/event registry | Rejected; only subordinate transport-attempt cache is present | Cache limits and explicit reconciliation tested; no lifecycle, health, session, or event registry |
| Shared runtime and host lifecycle | Not activated | Coordinator authorization, Windows v2 preservation/inspection, grant review, provider/transport health, live invocation and rollback evidence |

Source and runtime status, paths, and follow-up ownership are maintained in the [artifact registry](artifact-registry.md). The candidate was reconciled onto active baseline `2cc3fe3`; that validation exposed and corrected a manifest-version incompatibility. It also includes the Step 95 correction for fingerprint-bound idempotency. Independent review is pending; no runtime delivery is claimed. Earlier queue/steer and V2 inspection gaps remain tracked in [Issue #62](https://github.com/ppow1/R3/issues/62), including [Step 95](https://github.com/ppow1/R3/issues/61#issuecomment-6804765404).
