<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md
Component: R3A-TESTING-ACCEPTANCE-POLICY
File Revision: 1.0.0
Created: 2026-11-06T03:39:05Z
Created By: Codex GPT-6
Purpose: Set risk-based, bounded validation and evidence requirements for R3A.
Execution Model: N/A; governance policy for R3A validation.
Observability: Named revision, environment, results, evidence references and acceptance status.
Dependencies: Steward Directive — R3A Architecture Baseline and AP0 Specification; R3 development governance; file provenance standard.
Authority: Steward directive; does not authorize tests or implementation beyond a task's explicit scope.
Changed: 2026-11-06T03:39:05Z | R3A-BASELINE-001 | Codex GPT-6 | Establish initial testing and acceptance policy.
Supersedes: None; R3A supplement to existing R3 development governance.
Contracts: R3A Architecture Charter; AP0 Technical Specification; State Machine and Diagnostic Contract.
Tests: Not run; documentation only.
History/Predecessor: New document; initial publication recorded in Git.
-->
# Bounded Testing and Acceptance Policy

**Status:** Planned R3A supplement. The current documentation task did not run tests or expand the test suite.

## Principles

| ID | Policy requirement |
|---|---|
| TAP-001 | Test risk and changed behavior, not repository size. Select the smallest set of evidence that establishes the contract and material failure modes. |
| TAP-002 | Keep tests bounded in scope and execution, but do not replace required operational behavior with a demo, mock, dry-run or one-time substitute. |
| TAP-003 | Use disposable isolated data for destructive/restart/failure scenarios. Do not test against or alter production R/3 services/data without separate authorization. |
| TAP-004 | Use mocks only for unit/contract isolation; operational acceptance must exercise real components/dependencies at the declared environment boundary. |
| TAP-005 | Preserve institutional autonomy and assigned authority. Tests verify allowed action and denial of unauthorized action; they do not add unapproved operational caps or gates. |
| TAP-006 | Do not expand tests or run broad suites unless requested or required by the explicitly approved implementation change. Capture why any chosen check is proportionate. |

## Validation levels

| Level | Purpose | Permitted evidence | Cannot establish alone |
|---|---|---|---|
| Static/document review | Schema/provenance/contract consistency. | Source/document inspection, diff checks, schema validation. | Runtime behavior or operational status. |
| Unit/contract | Deterministic component semantics and compatibility. | Focused tests with controlled fixtures; invalid/valid transition cases. | Process restart behavior, external integration, deliverable acceptance. |
| Integration | Real component interactions across configured boundaries. | Isolated DB, actual Ring 0/CME processes, configured adapters or explicit unavailable status. | Production deployment or substantive task quality. |
| Recovery/failure | Restart, interruption, stale health, provider failure, recoverable blockage. | Fault injection in disposable environment; durable state/event review. | Complete resilience beyond exercised scenarios. |
| Operational acceptance | Intended environment behavior and actual deliverable outcomes. | Revision/environment identified; real startup/lifecycle/recovery; actual artifact and independent review where required. | Broader claims beyond tested workload or environment. |

## AP0 minimum evidence set

For an implementation authorization and later acceptance review, the minimum planned evidence is:

1. Configuration/schema validation: valid, missing, malformed and incompatible required config; secret values absent from diagnostics.
2. Process lifecycle: start Ring 0/CME, stop/fail/restart CME while Ring 0 remains, record lifecycle and health.
3. Durable recovery: persist activity/events, interrupt CME during work, restart, and show preserved lineage plus resume or explicit blocked outcome.
4. State definition: valid and invalid transitions; runtime and diagnostics use same machine/version.
5. Registry lifecycle: install, activate, stop and replace a representative module without Ring 0 restart; verify compatibility denial and preserve state/version lineage.
6. Capability separation: discover a capability while proving discovery alone does not authorize invocation.
7. Truthful diagnostics: compare current/stale/unavailable state, progress, exception and completion against database evidence.
8. Isolation: establish that disposable development DB/config/service paths were used and production R/3 was untouched.

The exact test count, tool, duration and automation are chosen during an authorized implementation task based on actual risks and available infrastructure. Do not invent a numeric workload ceiling here. AP0 scenarios provide requirement IDs, not a mandate to build a new test framework or expand the existing suite during this documentation task.

## Evidence and acceptance record

Every acceptance record identifies requirement IDs, repository/branch/commit or immutable artifact, config/schema version, environment, exact checks and outcomes, evidence references, failures/limitations, and reviewer/acceptance owner. Distinguish:

1. **Implemented:** code/config exists at an exact revision.
2. **Verified:** defined evidence was observed at that revision/environment.
3. **Operational:** active intended environment and essential live behavior were observed.
4. **Accepted:** substantive deliverable criteria were met by the authorized independent acceptance process, where required.

A green unit suite, process running, HTTP 200, generated artifact, code presence or simulation cannot independently advance a capability to operational/accepted. Failure or an unverified dependency must be reported as BLOCKED or NOT OPERATIONAL with exact evidence and next decision.
