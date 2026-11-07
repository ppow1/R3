<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP1_N1_RUNTIME_EVIDENCE.md
Component: R3A-AP1-N1-RUNTIME-EVIDENCE
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Record bounded live prototype evidence for notification intake, duplicate replay and CME recovery.
Execution Model: Isolated PostgreSQL, Ring 0, CME and Grace instance; no shared service modification.
Observability: Durable notification activity and event IDs listed below.
Dependencies: R3A_NOTIFICATION_INTAKE_V1.md; R3A AP0 runtime; configured local 80B reasoning route.
Authority: Steward directive R3A-019, GitHub Issue #48.
Changed: 2026-11-07 | R3A-AP1-N1 | Codex GPT-6 | Capture live notification and interruption evidence.
Supersedes: None.
Contracts: r3a.notification-intake.v1; r3a.authorization-decision.v1; existing activity.generic v1.
Tests: 71 focused notification/AP1/capability regression tests passed.
History/Predecessor: Implementation commit 34f2489f44287c9d63fca78fb777e70a9de5107b.
-->
# AP1-N1 live notification evidence

**Status:** VERIFIED in an isolated local R3A development instance as of 2026-11-07. This is evidence for the implementation at `34f2489f44287c9d63fca78fb777e70a9de5107b`; the shared prototype was not changed.

## Source and intake

The final run used a native event from the isolated instance's own append-only CME event ledger. Ring 0 restarted CME after an intentional CME process interruption; the replacement CME recorded source event `19b87997-1a36-4b8a-bfd6-4f936529ba07`, type `process.state_transition`, subject `cme`, transition `STARTING → RUNNING`, occurrence time `2026-11-07 16:32:43.819457 -05:00`.

CME imported the selected event under source `r3a.institution-events` after the configured `notification.source.read` grant was issued to `resident.grace`. The import persisted Grace activity `7151eae3-701a-4222-baa7-ac7167db1aae`, key `notification:r3a.institution-events:19b87997-1a36-4b8a-bfd6-4f936529ba07`, and preserved the source correlation UUID. The notification receipt time was `2026-11-07 21:32:57.649231 UTC` (`16:32:57.649231 -05:00`).

## Interruption and outcome

Immediately after intake returned `QUEUED`, the isolated CME PID `933925` was killed. Ring 0 launched replacement CME PID `934278`. The same activity ID was claimed and completed after restart; it had one attempt, no exception, and final activity state `COMPLETED` at `2026-11-07 16:33:16.837158 -05:00`.

The durable activity used task class `objective_reasoning`, configured role `resident.primary`, route `octominer1-primary-80b`, provider `openai-compatible`, model `/root/Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf`, request reference `c1309d07-975c-4d4f-a08b-e0cbaaf604ee`, and result reference `chatcmpl-rOIzvyXiupnaw7ukm287T0Ejwoz39jqG`. Grace cited evidence `notification:r3a.institution-events:19b87997-1a36-4b8a-bfd6-4f936529ba07` and concluded that the accepted CME startup transition warranted no follow-up.

Append-only lifecycle events share the original source correlation and causation IDs:

| Lifecycle event | Event ID | Time (America/New_York) |
|---|---|---|
| `grace.notification.received` | `d6af64d8-33dc-4f86-acb1-2fc2de5551de` | 16:32:57.664510 |
| `grace.notification.actionable` | `e4257b4e-c0a7-487e-a1fd-106b1fc35a91` | 16:33:00.946755 |
| `grace.notification.acknowledged` | `80ddcd18-3a91-47e0-8ec0-e7124d19c899` | 16:33:16.813697 |
| `grace.notification.resolved` | `9f8a14be-3ea4-4df5-b02e-3d542351fda4` | 16:33:16.865125 |

Replaying the same source event returned `duplicate: true`, the same activity ID, and state `COMPLETED`. No upstream acknowledgment or external side effect was performed. No autonomic model was used for the objective.

## Isolation and checks

The runtime used a temporary PostgreSQL cluster on local Unix sockets, database `r3a_ap1_n1_demo`, port `55498`, and external bootstrap `/tmp/r3a-ap1-n1-runtime-20261107/bootstrap.json`. Its source and model configuration were derived from the existing development settings and pointed at the notification worktree. It was not the shared Ring 0/CME service.

The shared database snapshot initially showed 29 queued `foundation.observe` activities, 312,855 completed observers, 14 blocked `grace.objective` activities, and the `foundation.observer` resource unallocated. These queued records are AP0 observer work, not notification events. No notification was enqueued to that shared runtime. At the same inspection point the shared systemd Ring 0 unit had stopped, while another AP1-K1 process later appeared on the shared database/socket; the shared service and its active worktree were left untouched.

Checks run:

- `python3 -m py_compile r3a_runtime/config.py r3a_runtime/db.py r3a_runtime/cme.py r3a_runtime/notifications.py r3a_runtime/cli.py tests/test_r3a_notifications.py`
- `/home/admin1/r3a-phase0/.venv/bin/python -m unittest tests.test_r3a_notifications tests.test_r3a_ap1 tests.test_r3a_modular_autonomy tests.test_r3a_capability_contracts tests.test_r3a_capability_integration_demo` — 71 tests passed.
- `git diff --check` — clean.

The AP1-N1 worktree is based on `5f75c76` as assigned. The current #43 observer-queue correction also modifies `Store.finish_activity()` on its branch; integration should preserve both its queue serialization change and AP1-N1's notification outcome event in that transaction.
