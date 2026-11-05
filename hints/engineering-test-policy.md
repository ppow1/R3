<!--
R3 CONTROLLED DOCUMENT
File: hints/engineering-test-policy.md
Component: ENG-PRODUCTION-TEST-BOUNDARY
File Revision: 1.0.0
Created: 2026-11-02 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Steward-mandated hard gate against one-time tests and test-shaped production restrictions.
Execution Model: Engineering governance; not runtime logic.
Observability: Source review, explicit exception reporting, production telemetry.
Dependencies: AI_HINTS.md; hints/engineering.md
Authority: Steward direct instruction 2026-11-01; project-wide mandatory engineering rule.
Changed: 2026-11-02 UTC | R3-GATE-001 | Establish permanent no-one-time-test gate
Supersedes: No prior charter; overrides contrary engineering habits or test instructions.
Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md; hints/file-provenance.md
Tests: Documentation review; no runtime execution.
History/Predecessor: New document.
-->
# HARD GATE — No one-time tests or test-shaped production restrictions

**Steward directive. Applies to every R3 engineer, assistant, resident, automation, deployment, and future feature. Read before changing code.**

1. **Do not create, embed, commit, or require one-time, scenario-specific, throwaway, qualification-only, or timing-dependent tests as part of the production project or deployment path.** Never add a temporary test that becomes a standing gate, service dependency, scheduler condition, resident limit, or acceptance bottleneck.
2. **Never change production behavior to satisfy an artificial test scenario.** No hardcoded resident names, objective counts, task counts, loop limits, test-specific intervals, fixed transient-state assertions, or artificial concurrency/operational ceilings. Engineering scope is not operational scope.
3. **Permanent automated tests are allowed only when they validate durable, general-purpose contracts and remain useful across normal production evolution.** They must not depend on arbitrary wall-clock sleeps, exact momentary asynchronous states, or a one-off scenario. Prefer event invariants, state transition contracts, and real operational telemetry. Testing must not create synthetic work inside the production resident scheduler.
4. **Keep engineering verification separate from production execution.** A diagnostic or qualification exercise must not be wired into normal startup, resident operation, or deployment as a permanent hard gate. Deployment verifies source identity, service health, real telemetry, and genuine capability; never silently suppress a real failure.
5. **Before adding any test or gate, ask:** Is this a durable product contract? Will it remain valid after the current task? Does it constrain the institution for the convenience of a test? Could it block future deployments after the original scenario is irrelevant? If the answer is uncertain, do not introduce it; escalate the design question to the Steward.
6. **Audit and remove existing violations.** Remove transient scenario-specific tests and their dependencies; do not delete legitimate reusable regression coverage indiscriminately. Record what was removed and what remains. Correct production defects on independent evidence, not solely to make a brittle test green.
7. **This rule is a hard gate on engineering changes, not a new runtime restriction.** It must not be implemented as a hardcoded operational constraint or an excuse to halt all engineering work. Preserve authorization, independent verification, and truthful reporting without manufacturing one-time hurdles.

**Known violation and correction:** `tests/test_institution_runtime.py::test_watchdog_timeout_is_single_and_remains_recovering` asserted a transient state after a 120 ms sleep and was made a mandatory deployment gate. Remove that test from the normal suite; inspect the watchdog independently for actual defects. Do not modify runtime timing solely to satisfy that assertion.

**Authority:** This policy records the Steward's explicit direction. If another instruction or generated plan conflicts, stop that proposed test/gate, follow this policy, and request Steward clarification when necessary.
