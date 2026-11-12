<!--
R3 CONTROLLED DOCUMENT
File: docs/audits/R3A_INDEPENDENT_ACCEPTANCE_CHECKLIST.md
Component: R3A-INDEPENDENT-ACCEPTANCE-CHECKLIST
File Revision: 1.0.0
Created: 2026-11-09T23:28:20Z
Created By: Codex GPT-6, acting as independent Auditor
Purpose: Provide a lightweight repeatable independent review procedure for R3A module deliveries.
Execution Model: N/A; review checklist
Observability: Evidence and outcome are recorded on the existing issue or PR.
Dependencies: R3A Bounded Testing and Acceptance Policy; versioned module/interface contracts.
Authority: Steward directive — R3A Independent Auditor / Reviewer V2, 2026-11-09
Changed: 2026-11-09T23:28:20Z | R3A-AUDIT-V2 | Codex GPT-6 | Initial independent acceptance checklist.
Supersedes: None
Contracts: MOD-001–MOD-010; TAP-001–TAP-006.
Tests: N/A; documentation only.
History/Predecessor: New file; initial revision in this branch.
-->
# R3A independent module acceptance checklist

Use this on the existing delivery issue or PR. Keep the evidence there; this checklist adds no service or runtime gate.

## Before review

- [ ] Name the branch/commit or immutable artifact and intended environment.
- [ ] Cite the governing Charter/Roadmap requirement, any later Steward requirement, and applicable versioned module/interface/state/diagnostic contracts.
- [ ] Identify module owner, integration owner, configuration/schema revision, dependencies, authorization boundary, and expected Website entry point if user-facing.

## Verify

- [ ] Inspect manifest/interface and implementation: stable identity/version, external validated config, declared dependencies, owner/state namespace, no hardcoded resident roster, and no per-module private behavior added to core.
- [ ] Check lifecycle/compatibility and recovery behavior against the relevant contract; registry discovery must not imply permission.
- [ ] Review focused contract tests for allowed, denied, invalid, unavailable/stale, idempotent/retry, and persistence/restart cases relevant to the change. Tests isolate behavior; they do not establish operation.
- [ ] Observe the intended live integration boundary: module registration/configuration/activation, authorized invocation, actual result, durable state/diagnostics, and user-facing Website flow when required.
- [ ] Confirm errors, freshness, correlation/evidence and authorization are visible and truthful. For resident work, CME governs execution; the Website does not call models directly.

## Record outcome

- [ ] For every result use **PASS**, **FAIL**, **BLOCKED**, **NOT VERIFIED**, or **NOT APPLICABLE**. A blocker names its dependency and owner.
- [ ] Each FAIL states the exact requirement, observed deviation, source/revision or runtime evidence, responsible owner, and smallest corrective action.
- [ ] Separate implemented, tested, live operational, and accepted status. A green test, 200 response, or source presence alone is not operational acceptance.
- [ ] Post the concise review on the existing issue/PR. Module owner corrects; Coordinator integrates; independent reviewer records recommendation; Steward makes final acceptance/exception decisions.

Do not close the issue or approve a PR for the Steward. Do not introduce blanket suites or new review infrastructure; choose bounded checks proportional to the change under `R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md`.
