<!--
R3 CONTROLLED DOCUMENT
File: docs/handoffs/R3A_GRACE_CME_EXCEPTION_DEPLOYMENT_HANDOFF_20261111.md
Component: R3A-GRACE-CME-EXCEPTION-DEPLOYMENT-HANDOFF
File Revision: 1.0.1
Created: 2026-11-11T22:06:08Z
Created By: Codex GPT-6
Purpose: Bound implementation, review, integration, activation, rollback, and acceptance evidence for the approved frozen-CME Grace correction.
Execution Model: Coordinator-controlled release; no activation command is documented or run by this handoff.
Observability: Git provenance, isolated PostgreSQL test report, Auditor review, controlled deployment report, live browser acceptance.
Dependencies: R3A-EXC-001; Steward approval #67 comment 6808102641; execution order #61 comment 6808100854; dispatch #61 comment 6808077733.
Authority: Exact R3A-EXC-001 scope only.
Changed: 2026-11-11T22:06:08Z | R3A-EXC-001 | Codex GPT-6 | Create approved-scope release handoff and record current gates.
Changed: 2026-11-11T22:12:00Z | R3A-EXC-001 | Codex GPT-6 | Record frozen-baseline integration SHA and passing isolated PostgreSQL regression.
Supersedes: None.
Contracts: Preserve historical data; only the exact deadline/idempotency digest correction may be integrated and deployed.
Tests: Isolated PostgreSQL regression evidence recorded below; production/browser acceptance not run.
History/Predecessor: None.
-->
# Grace CME Exception and Deployment Handoff

## Approved scope

Steward approval in [#67 comment 6808102641](https://github.com/ppow1/R3/issues/67#issuecomment-6808102641), executed by order [#61 comment 6808100854](https://github.com/ppow1/R3/issues/61#issuecomment-6808100854), authorizes only the reviewed CME deadline/idempotency digest correction `b259a09b3e5372717f455170e9414d82af2eff6f` against frozen production baseline `89eda1331b96fe40918e4aa67de09c5ae3f45227`, its necessary tests, independent review, controlled integration, deployment, and rollback. This is tracked as [R3A-EXC-001](../architecture/R3A_ROADMAP_EXCEPTION_REGISTER.md).

Acceptance is a **new authenticated Grace conversation** with a fresh idempotency key, a real model-generated response, a durable transcript, and successful browser refresh/reopen. Existing `hello` conversations are excluded from acceptance and must remain preserved. Do not migrate, replay, repair, or delete their rows.

## Source and test evidence

- Candidate: `b259a09b3e5372717f455170e9414d82af2eff6f`; candidate parent `29353c978ed9ea0e9991a264bc222a61fdca2f1c`.
- Candidate change: only `r3a_runtime/cme.py` in the production delta; digest normalization omits only `deadline`; deadline validation remains per attempt and semantic fields remain bound.
- Candidate source patch SHA-256: `a147e9c34b5aa36320c4d78d9a8e940289fbb6791229eabc019bc6280b66ef26`.
- Frozen-baseline integration: commit `568aae85ba43e398ed925b6f649911da449e2cda`, based directly on frozen `89eda1331b96fe40918e4aa67de09c5ae3f45227`; pushed branch [`engineering/grace-cme-frozen-integration-20261111`](https://github.com/ppow1/R3/tree/engineering/grace-cme-frozen-integration-20261111). Only `r3a_runtime/cme.py` and its focused persistence regression test changed.
- Frozen baseline: `89eda1331b96fe40918e4aa67de09c5ae3f45227`; rollback must return to this exact release.
- Independent source review: Auditor PASS recorded in #51 comment `6805687557`; confirm review scope covers the exact integrated SHA before activation.
- Isolated regression branch: `engineering/r3a-step127-postgres-regression-20261111`, test-only commits `4e5ca6201c3a78239e069530950a546a9f2c7273` and `2792c2d04e210c3d4501ac6d59115252fdc6b386`; CME source remained the candidate source.
- Command: `R3A_CHECKPOINT_TEST_DSN='host=/home/admin1/.local/state/r3a-ap0-m1/run port=55492 dbname=r3a_checkpoint_test_frozen_6808077733 user=r3a_runtime' /home/admin1/R3/.venv/bin/python -m pytest -q --tb=short tests/test_r3a_activity_checkpoint_persistence.py tests/test_r3a_engineering.py tests/test_r3a_ap1.py::ResidentVerificationFeedbackIntegrationTests`.
- Result on exact frozen-baseline integration source: **27 passed in 31.30s** on isolated PostgreSQL 16. New-row close/reopen retry and completed-result replay passed; a semantic input change under the same key remained rejected. The disposable DB was dropped and confirmed absent; isolated PG service remained healthy.
- Prior candidate-branch run: **25 passed, 2 xfailed in 10.72s**; it also diagnosed that a legacy frozen-format digest row conflicts under candidate retry. Step 137 explicitly excludes old rows from acceptance; historical rows remain untouched.

## Integration gate — open

Candidate `b259` is descended from `2cc3fe3aabad88c95a5e6489c633cb01472f7c7f`, not frozen release `89eda`; its patch does not apply directly to the frozen tree. A minimal port is prepared at `568aae85ba43e398ed925b6f649911da449e2cda`, based directly on frozen `89eda`. Auditor must independently review this exact integrated SHA, confirm semantic-field binding and per-attempt deadline validation, and record the decision before activation.

## Controlled activation checklist — not yet executed

Coordinator/Deployer must attach exact evidence for each item before activation:

1. Read-only preflight identifies the active CME host, service, checkout/release path, startup command, service owner, and exact running SHA.
2. The integrated release is immutable, built from the verified frozen baseline plus only the approved correction, and passes the focused regression on its exact source SHA.
3. Independent Auditor review is recorded against the exact integrated SHA.
4. A consistent backup/rollback target at frozen SHA `89eda1331b96fe40918e4aa67de09c5ae3f45227` is available; data and configuration remain intact.
5. Use the verified CME-specific release procedure. The repository manifest runner is plan-only and is not a CME production deployer.
6. Activate under bounded health checks. Record operator, host, timestamps, before/after SHAs, command/exit status, service identity, health result, and rollback readiness.
7. Sign in through the browser and send a new Grace message with a fresh key. Record the authenticated request/activity ID, actual generated response, durable transcript evidence, then refresh/reopen and verify the transcript remains.
8. If any check fails, restore the exact frozen release using the verified procedure, preserve all rows, record the failure and rollback evidence, and keep acceptance FAIL.

## Current status

- Approval and exception record: **APPROVED** for the exact narrow scope.
- Isolated PostgreSQL fresh-row regression: **PASS** (25 passed, 2 existing xfailed).
- Frozen-baseline source integration: **PASS**, commit `568aae85ba43e398ed925b6f649911da449e2cda`; independent review of that exact SHA: **OPEN**.
- Verified CME activation procedure, immutable release, backup/rollback evidence: **OPEN**.
- Production activation and new authenticated browser acceptance: **NOT RUN**.
- Read-only CME dashboard projection at 2026-11-11 22:05 local: service reported healthy, which is not release or chat acceptance evidence.

The production deployment runbook currently available in this repository is explicitly phase 1/plan-only and is not a CME deployer. No service was modified or activated during this handoff preparation.
