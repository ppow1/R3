<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ROADMAP_EXCEPTION_REGISTER.md
Component: R3A-ROADMAP-EXCEPTION-REGISTER
File Revision: 1.0.1
Created: 2026-11-06T04:57:50Z
Created By: Codex GPT-6
Purpose: Versioned register for proposed and Steward-approved R3A roadmap deviations.
Execution Model: N/A; governance record.
Observability: Git history and per-exception status/approval references.
Dependencies: R3A Master Roadmap; R3A Architectural Decision Log; R3A development governance.
Authority: R3A-GOV-01; only explicit Steward approval authorizes a roadmap deviation.
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Establish controlled exception register.
Changed: 2026-11-11T22:04:57Z | R3A-EXC-001 | R3A Coordinator | Record Steward-approved narrow frozen-CME deadline-digest exception for fresh Grace chat recovery.
Supersedes: None.
Contracts: Roadmap changes and deviations require durable decision/exception provenance.
Tests: Documentation-only validation; no runtime tests.
History/Predecessor: Revision 1.0.0 Git blob cd7879bf96f265ed09db181bd50a82278fda9e1d; original publication recorded in Git.
-->
# R3A Roadmap Exception Register

**Status:** No approved exceptions recorded. This register is versioned under `hints/file-provenance.md`; every material update increments the file revision and preserves the prior Git revision.

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
| R3A-EXC-001 | Approved Roadmap Baseline 1.0; AP0 / R3A-003 and R3A-008; AP1 / R3A-019 | Permit only the reviewed CME capability-invocation digest correction from `b259a09b3e5372717f455170e9414d82af2eff6f` to be integrated against frozen/deployed `89eda1331b96fe40918e4aa67de09c5ae3f45227` and controlled-deployed. Exclude the per-attempt deadline from the idempotency digest while continuing to validate it; keep all semantic request fields bound. Fresh-conversation acceptance only; no old-row migration, deletion, grant, schema, interface, or unrelated core changes. Preserve `89eda1331b96fe40918e4aa67de09c5ae3f45227` as rollback. | APPROVED — implementation and acceptance evidence pending | Steward explicit approval in #61 comment 6808100854 and #67 comment 6808102641, 2026-11-11. |

## R3A-EXC-001 — approved scope and traceability

- **Owner:** Coordinator / CME integration. **Requesting authority:** Steward.
- **Reason:** On every retry of a capability request, CME refreshes the validated per-attempt deadline while reusing the stable idempotency key. Full-envelope digesting changes despite identical semantic operation, principal, target and input, so the frozen Store rejects the retry before Grace inference. A module/config-only correction is unavailable; the exact runtime trace is recorded in #51 comment 6805697745 and #67 comment 6807773289.
- **Alternatives considered:** No supported configuration or module hook controls this digest. Keeping the full envelope preserves the reproduced false conflict. Historical row conversion is excluded from this exception and from the fresh-conversation P0 acceptance.
- **Impact:** One generic digest helper/call site and its permanent regression only. Deadline validation remains on every attempt. Operation, identity, activity, attempt, target, input and other semantic values remain digest-bound. No authorization rule/grant, database schema, public contract/socket, or resident-specific routing changes.
- **Acceptance and safeguards:** Run exact integrated candidate tests and an isolated disposable PostgreSQL fresh-row retry across Store/CME restart; prove semantic-field changes still conflict. Obtain Auditor review of the exact integrated SHA. Then deploy under the controlled release process and verify a NEW authenticated Steward-to-Grace turn through actual configured model inference, durable transcript, and refresh/reopen. Do not delete or rewrite historical transcript/invocation rows. If controlled live acceptance fails, restore the exact frozen SHA above and retain all data.
- **Approval:** Steward Step 141 dispatch #61 comment 6808100854 explicitly approves this exact patch, integration and controlled deployment; #67 records the same approval at comment 6808102641. This exception does not authorize scope expansion.
- **Closure evidence:** pending; record exact integrated/deployed SHA, PostgreSQL test result, same-SHA Auditor disposition, runtime/model/activity evidence, transcript recovery and rollback readiness here or by linked durable report.
