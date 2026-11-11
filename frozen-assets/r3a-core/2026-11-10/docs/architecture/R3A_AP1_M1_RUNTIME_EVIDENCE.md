<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP1_M1_RUNTIME_EVIDENCE.md
Component: R3A-AP1-M1-EVIDENCE
File Revision: 1.0.0
Created: 2026-11-06T16:36:18Z
Created By: Codex GPT-6
Purpose: Record reproducible runtime acceptance evidence for Grace's first durable AP1 objective.
Execution Model: Evidence record and isolated local operator runbook.
Observability: PostgreSQL activity/event lineage, capability audit, module/process observations and model references.
Dependencies: AP1-M1 implementation commit 7978bf2dae93990a6dd33b6e6469f38758a63647; Issue #43; isolated R3A host.
Authority: Steward AP1-M1 authorization in GitHub Issue #43; no production R/3 changes.
Changed: 2026-11-06T16:36:18Z | AP1-M1 | Codex GPT-6 | Record actual objective, model, recovery, and independent runtime verification.
Supersedes: None.
Contracts: R3A-019; AP1-M1 Issue #43 acceptance criteria.
Tests: Actual local model inference and durable runtime operations documented below; no test suite expansion.
History/Predecessor: New document; source commit 7978bf2dae93990a6dd33b6e6469f38758a63647.
-->
# R3A AP1-M1 — Grace First Durable Objective Evidence

## Delivered runtime

- Branch: `engineering/r3a-phase0-20261105`
- Runtime implementation: `7978bf2dae93990a6dd33b6e6469f38758a63647` (pushed to origin)
- Isolated PostgreSQL database: `r3a_ap0_m1`, PostgreSQL 16.15 over its private Unix socket
- Running residents: Ring 0, CME, and `resident.grace@1.0.0`
- Configured model: provider `openai-compatible`; model `qwen3-0.6b-q8_0-local`; loopback endpoint `http://127.0.0.1:18796/v1/chat/completions`
- Configured knowledge source: `r3a_runtime/state_machines/process.json`, read through the registered `institution.knowledge.read` capability
- No credentials or secrets were sent to the model. Model requests are read-only inference calls; Grace has no tool or write capability in this milestone.

## Objective and durable lineage

Objective submitted through the local CME control socket:

> Assess whether the isolated R3A Ring 0, CME, PostgreSQL, and Grace resident are currently healthy from live runtime evidence. State any missing or stale evidence, cite the supplied evidence source IDs, and recommend a safe next step.

The local CLI submitted it with idempotency key `issue43-ap1m1-first-objective-v1`. Repeating the same submission returned the existing activity rather than creating another.

| Record | Value |
|---|---|
| Activity | `b181dff7-b869-4900-8e3d-e1774fc7ed55` |
| Final state / attempts | `COMPLETED` / 7 |
| Receive event | `87a735bf-d573-4015-b822-c57472e028b5` |
| Lease-expiry recovery event after CME interruption | `63431b08-e944-4a79-84bc-e91b460ef8a9` |
| Final completion event | `62ad6451-b63d-4ebf-9d34-3e8830338ab4` |
| Final attempt | `31aa5478-2017-492c-b602-cf55ab4b5e91` |
| Final implementation revision in completion event | `7978bf2dae93990a6dd33b6e6469f38758a63647` |

The CME was intentionally killed while the activity was in `RUNNING`. Ring 0 restarted it. After the activity lease expired, CME reclaimed the same activity UUID, and the same objective continued through later recoverable model attempts. The durable lineage records the lease expiry, retry states, and single completion; no second activity was created.

## Model result

Grace completed from the configured local model with `finish_reason=stop`:

```json
{
  "assessment": "healthy",
  "status": "healthy",
  "evidence_refs": ["runtime.processes", "runtime.postgres", "knowledge.1"],
  "recommended_action": "Continue monitoring the system and ensure all components are functioning as expected."
}
```

Durable model metadata on the activity and completion event:

- Request reference: `d7a28ad5-4931-499b-8f57-e1f2192fda13`
- Result reference: `chatcmpl-7uyWQuQQ02toHpe8UEHyZ1YtOT2nWhjp`
- Request SHA-256: `4dc5db05dbe070ca7374b4690d866b57b86c55af29fc8829aedacde5e43521eb`
- Result SHA-256: `b27f889275f4801ee528cb0552e3b633109af935e04ba957f23ed7d48b38d9b5`
- Usage: 929 prompt tokens, 61 completion tokens; total 990
- Knowledge evidence SHA-256: `c6fa4ddd5a93327b087d0fb57d3b45870b88d4492a391e2a2db7c3e132c8d0ac`

The returned source list does not include `runtime.modules`. The activity output is preserved as returned. An independent check below verified the Grace module's live lifecycle and OS process separately; it does not relabel that check as a model citation.

## Authorization and independent verification

Four active, read-only grants were recorded for `resident.grace`: `host.process.read`, `postgres.readiness`, `institution.knowledge.read`, and `institution.diagnostics.read`. The final attempt has successful `capability.invoked` audit events for all four, correlated to this activity.

At 2026-11-06 16:35 UTC, direct read-only inspection of PostgreSQL and `/proc` verified:

- Ring 0 PID `3649547`: state `RUNNING`, health `healthy`, OS process present.
- CME PID `3649562`: state `RUNNING`, health `healthy`, OS process present.
- Grace module PID `3649572`: registry lifecycle `ACTIVE`, health `healthy`, OS process present.
- PostgreSQL database `r3a_ap0_m1`: ready, server version 16.15, not in recovery.
- Grace capability audit rows all reported `allowed` for the activity.
- The activity row stores the model decision and result references; the append-only event ledger contains the receive, claim/recovery, and completion lineage.

Earlier model attempts exposed the actual local inference latency and malformed output. A 96-token response cap ended with `finish_reason=length`; Grace rejected that incomplete JSON and persisted the failure for retry. The configuration and prompt were corrected within AP1-M1. The accepted result above was generated by the real model, not a fixture or a hard-coded completion.

## Reproduction and verification

From the isolated R3A worktree, inspect the live projection:

```bash
.venv/bin/r3a --config /home/admin1/.config/r3a-ap0-m1/bootstrap.json status
```

Inspect the durable result and event lineage directly through the isolated PostgreSQL socket:

```bash
psql -h /home/admin1/.local/state/r3a-ap0-m1/run -p 55492 -U r3a_runtime -d r3a_ap0_m1 \
  -c "SELECT activity_id, state, attempt_count, result->'decision', result->'model' FROM r3a.activities WHERE activity_id='b181dff7-b869-4900-8e3d-e1774fc7ed55';"

psql -h /home/admin1/.local/state/r3a-ap0-m1/run -p 55492 -U r3a_runtime -d r3a_ap0_m1 \
  -c "SELECT event_id, event_type, occurred_at, implementation_revision FROM r3a.institution_events WHERE subject_type='activity' AND subject_id='b181dff7-b869-4900-8e3d-e1774fc7ed55' ORDER BY occurred_at;"
```

Validation performed: Python bytecode compilation, external configuration parsing and source-digest validation, `git diff --check`, live model inference, duplicate objective submission, CME crash/restart recovery, capability audit, and independent PostgreSQL/process verification.

All runtime work remained on the isolated R3A user service and `r3a_ap0_m1` database. No production R/3 service, database, or deployment configuration was changed.
