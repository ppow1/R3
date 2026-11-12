<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_ROADMAP_EXCEPTION_REGISTER.md
Component: R3A-ROADMAP-EXCEPTION-REGISTER
File Revision: 1.0.0
Created: 2026-11-06T04:57:50Z
Created By: Codex GPT-6
Purpose: Versioned register for proposed and Steward-approved R3A roadmap deviations.
Execution Model: N/A; governance record.
Observability: Git history and per-exception status/approval references.
Dependencies: R3A Master Roadmap; R3A Architectural Decision Log; R3A development governance.
Authority: R3A-GOV-01; only explicit Steward approval authorizes a roadmap deviation.
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Establish controlled exception register.
Supersedes: None.
Contracts: Roadmap changes and deviations require durable decision/exception provenance.
Tests: Documentation-only validation; no runtime tests.
History/Predecessor: New document; initial publication recorded in Git.
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
| None | N/A | No exception proposals or approvals are recorded in this initial register. | N/A | N/A |
