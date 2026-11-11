<!--
R3 CONTROLLED DOCUMENT
File: docs/PROJECT_CHARTER.md
Component: DOCS-PROJECT-CHARTER-MD
File Revision: 1.0.0 (provenance baseline; earlier revisions not tracked)
Created: Unknown (legacy)
Created By: Unknown (legacy)
Purpose: R3 project governance and planning reference
Execution Model: N/A
Observability: N/A
Dependencies: R3 repository
Authority: Existing document authority unchanged; see body
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Supersedes: None (see body for substantive charter revisions)
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only)
History/Predecessor: Git blob 558d631e1b9f877942446b9fb00e215e638562ac
-->
# Riverview 3 — Project Charter (Initial Draft)

**Status:** Foundational direction; design decisions and requirements remain open for review.

## Mission

Build Riverview 3 as a durable, extensible environment where Grace and other residents can reason, choose authorized tools, carry out work, observe results, recover from errors, and continue operating without a human scripting each next step.

## Preserve conceptually

- Grace as a persistent Operations Manager with real decision-making and tool use.
- CME as a continuous operating environment.
- Resident identities, distinct responsibilities, memory, and continuity.
- Human Steward authority for consequential actions, with appropriately scoped delegated permissions.
- Model routing across small autonomic, vision, and large reasoning workloads.
- Observable state transitions, durable logs, recovery, and independent outcome verification.
- Existing working capabilities, only after inventory and regression testing.

## Redesign

- Replace brittle single-task orchestration with a persistent reasoning/observe/act/verify/continue loop.
- Separate resident intent and reasoning from execution adapters, policy, authorization, and verification.
- Make actual runtime state visible through a coherent operator HMI and historian.
- Enable generalized objectives and concurrent activity without scenario-specific hardcoded ceilings.
- Distinguish technical execution success from meaningful task acceptance.
- Design restart, recovery, and continuation as first-class behavior.

## Do not carry forward automatically

- Unverified claims of working autonomy.
- Excessive gates, redundant approval stages, and duplicated control surfaces.
- False-positive verification based only on file presence or API success.
- Test-scenario limits embedded as operational policy.
- Accidental dependencies on undocumented host state or scripts.

## Initial architecture questions

1. What is the smallest end-to-end loop that demonstrates Grace independently selecting and using a tool?
2. What is the minimum event/state schema needed for continuity and a trustworthy HMI?
3. Which Riverview 2 services and interfaces are actually reusable, based on verified tests?
4. How should delegated authority be scoped and renewed without interrupting ordinary autonomous work?
5. How are resident memory, identity, and differentiated reasoning preserved?
6. What does an independent acceptance test observe beyond task completion status?

## First milestone — evidence-backed baseline

Produce an inventory of candidate Riverview 2 components, their observed status, interfaces, dependencies, and test evidence. Then specify and demonstrate one **general-purpose** persistent reasoning/tool loop. The milestone may use a single test scenario, but the architecture must not be restricted to it.

## Non-goals for initial charter stage

- No automatic migration of production services or databases.
- No claims of Riverview 2 full restore certification.
- No major refactor or deployment before architecture and evidence review.

## Success criteria

A resident can maintain intent across cycles, select an authorized tool without a human naming the next tool, act, inspect real results, recover or escalate appropriately, and continue. Every significant step is observable and verifiable, and the system can restart without silently losing active work.
