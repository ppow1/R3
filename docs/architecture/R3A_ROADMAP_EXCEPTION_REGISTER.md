<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ROADMAP_EXCEPTION_REGISTER.md
Component: R3A-ROADMAP-EXCEPTION-REGISTER
File Revision: 1.0.4
Created: 2026-11-06T04:57:50Z
Created By: Codex GPT-6
Purpose: Versioned register for proposed and Steward-approved R3A roadmap deviations.
Execution Model: N/A; governance record.
Observability: Git history and per-exception status/approval references.
Dependencies: R3A Master Roadmap; R3A Architectural Decision Log; R3A development governance.
Authority: R3A-GOV-01; only explicit Steward approval authorizes a roadmap deviation.
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Establish controlled exception register.
Changed: 2026-11-11T21:59:34Z | R3A-EXC-001 | Codex GPT-6 | Record a proposed frozen-CME Grace recovery exception for explicit Steward decision.
Changed: 2026-11-11T22:06:08Z | R3A-EXC-001 | Codex GPT-6 | Record explicit Steward approval and narrow new-conversation acceptance scope.
Changed: 2026-11-11T22:12:00Z | R3A-EXC-001 | Codex GPT-6 | Record minimal frozen-baseline integration commit and isolated PostgreSQL regression evidence.
Changed: 2026-11-11T22:16:00Z | R3A-EXC-001 | Codex GPT-6 | Align release handoff with Coordinator's exact integrated candidate and same-SHA review request.
Supersedes: None.
Contracts: Roadmap changes and deviations require durable decision/exception provenance.
Tests: Documentation-only validation; no runtime tests.
History/Predecessor: Git blob cd7879bf96f265ed09db181bd50a82278fda9e1d at commit 9dfeb4ce8f2adf3a1a4bebf89f3ebbee2dfc4dfe.
-->
# R3A Roadmap Exception Register

**Status:** R3A-EXC-001 is approved for its exact bounded scope. This register is versioned under hints/file-provenance.md; every material update increments the file revision and preserves the prior Git revision.

## Required exception record

Each proposed deviation receives a stable `R3A-EXC-NNN` ID and records:

- proposal revision and UTC date;
- requesting authority/person and accountable owner;
- approved roadmap revision, AP phase/milestone and affected requirement IDs;
- exact proposed deviation and authorized scope;
- reason the approved roadmap cannot be followed as written;
- alternatives considered and why they were rejected or deferred;
- impact on dependencies, priorities, acceptance criteria, security, privacy, production isolation, schedule and other workstreams;
- risk/mitigation and rollback or recovery implications where applicable;
- status: `PROPOSED`, `APPROVED`, `REJECTED`, `WITHDRAWN`, or `SUPERSEDED`;
- explicit Steward approval or rejection reference and date;
- effective scope/revision and closure evidence, if approved.

## Authority rule

`PROPOSED` is not authorization. **No work implementing a deviation may start until the Steward's approval is explicitly recorded against that exception ID and roadmap revision.** The coordination issue, an engineering manager, a resident or any Codex session cannot grant that approval. Rejected, withdrawn and superseded proposals remain in the durable record; they are not erased or reused as approvals for later proposals.

## Register

| Exception ID | Proposed roadmap revision / affected requirements | Summary | Status | Steward approval reference |
|---|---|---|---|---|
| R3A-EXC-001 | Roadmap Baseline 1.0; AP1-M1 / R3A-019 (supporting AP0 recovery requirement R3A-018) | Permit independent review, controlled integration, and production deployment of the exact narrow CME deadline/idempotency digest correction b259a09 against frozen baseline 89eda133. Acceptance is a NEW authenticated Grace conversation; historical rows are preserved and excluded from acceptance. | APPROVED | Steward explicit approval, #67 comment 6808102641; execution order #61 comment 6808100854 (2026-11-11) |

## R3A-EXC-001 — Approved frozen-CME Grace idempotency recovery

- **Record revision/date:** 1.3; approved 2026-11-11 UTC.
- **Requestor:** Steward ppow1, dispatch [#61 comment 6807824448](https://github.com/ppow1/R3/issues/61#issuecomment-6807824448).
- **Accountable owner:** Coordinator/core owner for implementation and controlled integration; Deployer handoff through Coordinator Step 133 [#61 comment 6807890556](https://github.com/ppow1/R3/issues/61#issuecomment-6807890556). Steward remains approval authority.
- **Approved roadmap mapping:** Roadmap Baseline 1.0, AP1 milestone M1, requirement R3A-019; supporting AP0 recovery requirement R3A-018. Governing work is #43 AP1-M1 and #67 P0 Grace live chat.
- **Approved deviation and scope:** Steward approval is exact to candidate `b259a09b3e5372717f455170e9414d82af2eff6f` against frozen baseline `89eda1331b96fe40918e4aa67de09c5ae3f45227`, the deadline/idempotency digest correction, necessary regression tests, independent review, controlled integration, deployment, and rollback. The correction omits only the per-attempt deadline from the idempotency digest; deadline validation and semantic request binding remain required. No unrelated frozen-core redesign or changes to socket, request schema, authorization, grants, configuration, database schema, roadmap priority, or acceptance criteria are authorized. Acceptance is exclusively a NEW authenticated Grace conversation with a fresh idempotency key, real model-generated reply, and durable transcript surviving refresh/reopen. Historical `hello` conversation rows must remain intact; no migration, replay, repair, or deletion is part of acceptance.
- **Reason:** Frozen CME 89eda1331b96fe40918e4aa67de09c5ae3f45227 reuses the directory invocation key but rebuilds the deadline as now plus configured timeout; full-request digest changes on retry and Store rejects it before inference. Current reviewed source candidate b259a09b3e5372717f455170e9414d82af2eff6f fixes new-format retries but does not replay a row already stored with the frozen full-envelope digest. Its commit is based on 29353c978ed9ea0e9991a264bc222a61fdca2f1c, and its production patch does not apply directly to the frozen tree. Evidence: [Step 134 compatibility review, #67 comment 6807967917](https://github.com/ppow1/R3/issues/67#issuecomment-6807967917).
- **Alternatives considered:** Changing the configured timeout cannot stabilize the generated timestamp. A module cannot choose the deadline because CME constructs it before invoking the provider. Replacing a key or bypassing idempotency risks duplicate effects and is excluded. Steward explicitly excludes replay or repair of old `hello` rows from acceptance; they remain preserved.
- **Impact/dependencies:** Preserves real authenticated Grace-chat acceptance and semantic request binding. Candidate `b259` is based on `29353c978ed9ea0e9991a264bc222a61fdca2f1c`; its production patch does not apply directly to frozen tree `89eda`. Coordinator prepared the release candidate `d436cc3c8022f545d6134ba9e553b55a3aadc279` directly on frozen `89eda`, branch `integration/r3a-grace-chat-p0-20261111`; the integration contains the exact helper/call correction and regression fixture repair. Coordinator's same-SHA independent audit request is #56 comment 6808288267. Its isolated PostgreSQL suite passed 6 tests, focused integration passed 27, and exact full suite passed 512 (9 skipped, 42 subtests, 1 existing warning, zero failures), per that review request. This session also independently reproduced the frozen-baseline focused result (27 passed) at supplemental commit `568aae85ba43e398ed925b6f649911da449e2cda`; that branch is corroborating evidence, not the release target. Auditor disposition and the controlled CME release procedure remain required before activation. The approved scope does not permit substituting the whole divergent branch.
- **Risk/mitigation:** A digest rule that ignores semantic fields could permit an unsafe replay. Bind and compare every semantic field, validate each deadline on every attempt, run the fresh-row regression in an isolated PostgreSQL database, require independent Auditor review, and verify rollback readiness before activation.
- **Rollback/recovery:** Frozen release `89eda1331b96fe40918e4aa67de09c5ae3f45227` remains the rollback target. Preserve all durable activity and invocation rows. Use only a verified CME release procedure. Rollback does not repair or replay historical rows.
- **Status:** APPROVED for the exact scope above; Coordinator integration and regression-tested, exact-SHA audit and deployment not yet complete. No broader frozen-core change is approved.
- **Steward decision:** Explicit approval, #67 comment 6808102641; execution order, #61 comment 6808100854 (2026-11-11). Effective scope is this record revision 1.3. Deployment and new-conversation acceptance evidence remain open.
