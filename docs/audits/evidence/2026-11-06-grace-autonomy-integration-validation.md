# Grace Autonomy Integration Validation

**Date:** 2026-11-06
**R3 development branch:** `engineering/grace-autonomy-recovery-20261106`
**Production R3 release inspected read-only:** `8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135`
**Comms5 Camrui package inspected read-only:** `b6b5ce715508590cc8e56051c00bf7ed17fdbf79`
**Grace Execution package inspected read-only:** `9f56cb72f3bd2961babf2527a26bd843526e18ce`

## Engineering path and authority

The existing Engineering execution path is the narrowest demonstrated path to reuse:

1. Comms5 `form_and_queue_work` validates explicit Steward confirmation, the promoted objective, its ready stage, and the exact active `objective.submit` grant. It appends one idempotent `work_order.dispatch_requested` event and reports `dispatched: false` while awaiting Grace Execution.
2. The running Grace Execution Service polls its PostgreSQL objective ledger. It calls `GraceExecutionPipeline.authorize_and_dispatch`; the assignment ID and idempotency key are derived from the objective and step.
3. `AuthorizedAssignmentIntake` checks the exact `assignment.create` grant and atomically writes the assignment and `assignment.created` event in the same PostgreSQL transaction.
4. The existing event processor advances the assignment to ready. A registered worker claims it under the existing lease and execution-grant checks. The independent verifier records its own decision. Grace Execution reconciles objective completion only when accepted verification evidence is durable.

The worker destination is the existing M33 PostgreSQL assignment ledger, event processor, worker adapter, and verifier path. The Grace Execution service runs with systemd-delivered dispatch, resident, worker, and verifier credentials. M33 assignment intake runs under the `riverview` service identity and obtains its database credential through systemd. Comms5 Camrui runs under its dedicated service identity; the OAuth ingress attests `steward`, and the internal dashboard hop uses a separate service token. No credential values were read.

## Integration defects confirmed

The Grace Execution dispatcher’s `_proposed` query selects objectives in `PROPOSED` or `WORK_ORDER_CREATED` by scope. It does not select or require the `work_order.dispatch_requested` event written by Comms5. Thus the Comms5 Steward queue gate and the service dispatch loop are not connected as a single enforced transition. The exact `assignment.create` grant remains enforced, but it does not prove that the separate Comms5 queue request was made. A correct production repair must make the existing dispatcher consume the durable, authorized request before creating an assignment, or establish an equivalently reviewed, versioned authorization record. No second assignment or Engineering system is needed.

The installed Comms5 MCP ingress accepts the Caddy-attested principal `steward`. Its backend operation layer derives the actor from that transport identity; `Comms5Operations._actor` requires a `steward:` principal. The R3 proposal adapter supplies the Grace principal as operation data and a bearer token but cannot change the authenticated transport principal. The current production contract therefore cannot accept a Grace-authored draft as Grace. Sending a Steward marker or Steward credential from the R3 resident would impersonate the Steward and is not an acceptable workaround. Comms5 needs a resident/service identity route limited to proposal draft creation and authorized readback; prepare-for-decision, approval, promotion, and work-order queue operations must remain Steward-gated.

The development-only R3 `/v2/work-orders/dispatch` endpoint was exercised against an isolated fixture, but the installed Comms5 dispatcher does not call it and the endpoint would create a parallel R3 assignment store. It has been removed from the development branch. R3’s existing version 1 resident activity intake and exact-grant blocked-resumption API remain separate from Engineering dispatch.

## Isolated test evidence

All PostgreSQL-backed checks below used a new PostgreSQL 16 cluster created under `/tmp`, with only a loopback listener/private socket, a disposable database schema per test, generated test credentials, and exact test-only grants. The installed release source and production database were read only. PyJWT’s declared test dependency was installed only under that temporary test directory; the production venv and services were unchanged.

The following existing Grace Execution package tests passed:

- `tests.test_proposal_work_order_lifecycle`: **9 passed**. Covers explicit revision-bound Steward decisions, denial before approval, exact objective/work-order grants, Comms5’s idempotent durable queue-request receipt, proposal promotion, artifact execution, independent verification, and proposal result linkage. The queue-request test deliberately confirms that queue creation alone does not claim dispatch.
- `tests.test_grace_execution.GraceExecutionTests.test_dashboard_submission_persistent_restart_worker_verification_and_projection`: **1 passed**. A controlled objective reaches `GraceExecutionService.dispatch_proposed`, creates one M33 assignment, survives service reconstruction, executes one worker attempt, receives one independent accepted verification, and projects objective state as `COMPLETED` only after acceptance.
- Rejected-work recovery, retry exhaustion, and single-step/single-dispatch regressions: **3 passed**. Rejection remains durable through rework; exhausted retries stop with actionable pending state; repeated dispatch does not create a second assignment.

Total across these targeted existing-package runs: **13 passed**. Separately, the R3 branch regression suite passed **225 tests** before removal of the unused v2 dispatch route; focused R3 continuation/resumption and health tests are rerun with the route cleanup.

These results validate the existing Engineering components in isolation. They do not demonstrate that the Comms5 queue event gates the active Grace Execution dispatcher, nor that R3 Grace can submit an authenticated draft through the deployed Comms5 ingress. The website-clock workflow has not passed end-to-end acceptance.

After removing the unused R3 dispatch endpoint, the focused `tests/test_assignment_resume_api.py` suite passed **3 tests**. The full R3 suite was attempted with both system Python and `/opt/riverview-core/.venv`; both environments lack the repository's FastAPI, Starlette, and MCP test dependencies. Discovery reached 178 tests but ended with 14 import errors for those missing packages, so this is not a full-suite pass. The branch's prior full-suite result of 225 passed predates the endpoint cleanup.

## Deployment and rollback plan

No deployment is prepared for activation. Before any release is eligible:

1. Integrate a narrowly scoped Comms5 resident/service identity for proposal draft-write and readback without exposing Steward-only operations.
2. Change the existing Grace Execution dispatcher to require the Comms5 durable queued-work event and validate the exact objective, stage, authority, and idempotency identity before `assignment.create`.
3. Run the website-clock flow end to end against isolated services and test databases, including the independent verifier and bounded rejection/inconclusive paths.
4. Build a versioned immutable R3 release, compare its manifest and configuration, and run read-only health/auth smoke checks before activation.

For a later separately authorized activation, preserve the current immutable production release `8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135` as the rollback target. Activation must use the established atomic release-pointer/service procedure with a verified backup. On any failed smoke or workflow acceptance, restore that exact release pointer and its recorded service configuration, then verify the website/runtime health endpoints. This recovery branch has not changed production configuration, PostgreSQL, credentials, grants, or services.
