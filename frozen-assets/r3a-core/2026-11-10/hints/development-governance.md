<!--
R3 CONTROLLED DOCUMENT
File: hints/development-governance.md
Component: ENG-DEV-GOVERNANCE
File Revision: 1.0.4
Created: 2026-11-05 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Initial R3 development lifecycle, Definition of Done and deployment-input contract
Execution Model: Documentation / development conversation initialization
Observability: Git history and bootstrap readiness summary
Dependencies: hints/development-bootstrap.md; hints/engineering.md; hints/deployment.md
Authority: Steward direction, R3 charter, AI_HINTS.md
Changed: 2026-11-05 UTC | R3-DEPLOY-BOOTSTRAP-005 | ChatGPT GPT-6 | Require verified real activation and protected integration/fallback
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-002 | ChatGPT GPT-6 | Require local-evidence-first gateway execution and PowerShell clipboard fallback
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-001 | ChatGPT GPT-6 | Initial bootstrap guidance
Changed: 2026-11-06T04:57:50Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Establish mandatory R3A roadmap compliance and R3A-GOV-02 coordination.
Changed: 2026-11-06T05:03:56Z | R3A-BASELINE-1.0-CORRECTION | Codex GPT-6 | Require a coordination issue and integration authority for each active milestone.
Changed: 2026-11-06 | R3A-GOV-01A | Steward-directed clarification | Permit autonomous in-scope engineering and reserve approval for material deviations.
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
Tests: Link and content review; no runtime deployment
History/Predecessor: Git blob 512eb84d3611099dbe78ae51fba7fe368f9fe231
-->
# R/3 Development Governance — Initial Working Standard

**Status:** Steward-directed initial standard, intentionally lightweight and amendable. This is the R/3 working policy; historical R/2 standards are references, not automatically adopted in full.

## Development cycle

1. **Initialize:** Run [R3 Bootstrap](development-bootstrap.md) and [Development Execution](development-execution.md); use existing local evidence first, then authorized command gateway for live work, then PowerShell 7 clipboard fallback if necessary. Inspect current baseline, relevant configuration, interfaces, and ownership.
2. **Define:** State objective, acceptance behavior and scope; distinguish requirements from optional hardening.
3. **Implement:** Make focused changes in a feature branch/worktree, preserving shared capabilities and durable institutional state.
4. **Check:** Run targeted functional tests and a bounded smoke check relevant to changed behavior. Comprehensive regression gates are deferred during accelerated development.
5. **Deliver:** Supply an exact commit, change summary, configuration/API impact, test evidence and a standardized deployment input.
6. **Deploy when authorized:** Confirm a prior backup/release exists, deploy the intended revision, verify the essential function, and fix failures in place. No automatic rollback requirement.
7. **Close:** Report what actually works, what remains pending and whether the agreed acceptance criteria were met. Do not mark work complete on assertion alone.

## Definition of Done — minimum

- Requested behavior implemented at a named, retrievable commit.
- Major features/services have documented configuration; configuration changes are declared.
- Existing shared API, authentication, resident identity, credential, grant, and state contracts are not silently removed.
- Relevant targeted checks run with honest results; essential live behavior verified when deployment is part of the assignment.
- Deployment has a confirmed pre-existing backup/release; no automatic rollback is required. Fix in place is the default.
- Delivery summary identifies remaining limitations, failures and follow-up work. Independent verification remains required for institutional workflows whose acceptance explicitly calls for it; do not misrepresent unverified work as verified.

## Standard deployment input (conceptual contract)

Each team supplies the **same categories of information**, not identical code or packaging:

- Component/service name and owner; source repository, branch and exact commit or immutable artifact ID.
- Target environment and affected services; dependencies and configuration files/changes.
- API/state compatibility notes, required migration or special installation steps.
- Bounded build/start commands and essential smoke-check commands with expected results.
- Existing backup/release confirmation; secrets supplied only via approved protected channels.
- Observed outcome, failures and fix-in-place instructions.

This is a **human-readable initial contract**, not a claim that the current deployment runner can already consume all fields. Formal machine-readable schema and enforcement may evolve separately.

## R3A roadmap compliance — R3A-GOV-01

The Steward-approved, versioned [R3A Master Roadmap](../docs/architecture/R3A_MASTER_ROADMAP_AP0_AP6.md) is the authoritative development plan. Each R3A assignment must name:

- approved roadmap revision;
- AP phase and milestone;
- requirement identifiers;
- authorized scope;
- acceptance criteria; and
- an applicable Steward-approved exception ID, or `None`.

Do not begin implementation if the roadmap lacks Steward approval or the assignment omits a required field. Codex sessions, residents and engineering coordinators cannot independently change phase ownership, roadmap priorities or acceptance criteria. Proposed deviations must be recorded in the [R3A Roadmap Exception Register](../docs/architecture/R3A_ROADMAP_EXCEPTION_REGISTER.md), with reason, alternatives, impact and affected requirements. `PROPOSED` is not authorization; the Steward's approval must be explicitly recorded before any deviation work starts. Keep versioned decision and exception history; do not overwrite or erase prior dispositions.

### Execution autonomy within approved objectives — R3A-GOV-01A

The approved roadmap governs **the destination, not every engineering step**. Once a milestone is authorized, Engineering and Codex have broad discretion to investigate, design implementation details, write necessary supporting code, debug, refactor within scope, run proportionate checks, coordinate workstreams and recover from ordinary failures **without seeking repeated Steward approval**. Technical approaches, corrective fixes and incidental changes necessary to satisfy the assigned acceptance criteria are not roadmap deviations, provided they stay inside the authorized objective, interfaces, safety/production boundaries and acceptance criteria.

A failure or unexpected dependency should ordinarily trigger diagnosis, a reasonable alternative and continued execution toward verified completion. Do not end an assignment merely because the first attempt or a test failed. Escalate only when an actual authority boundary, material scope/priority/acceptance change, unresolved architecture decision with consequential tradeoffs, or genuine external blocker prevents responsible continuation. Record what was tried and the narrow decision required.

A **material deviation** changes the authorized objective, phase ownership, priorities, protected boundaries or acceptance criteria; it requires the existing versioned exception and explicit Steward approval. Do not misclassify ordinary implementation choices, bug fixes or supporting work as deviations. Production deployment and destructive changes remain separately authorized. Bounded testing must establish real acceptance, not become an endless cycle of speculative hardening or unrelated tests.

## Parallel Engineering Coordination — R3A-GOV-02

Multiple Codex sessions may work concurrently only under a designated GitHub coordination issue for the active AP milestone. The issue is the shared communication/orchestration record; it does not amend the Master Roadmap, grant authority, or approve a deviation.

Before parallel work begins, the assignment/issue records:

- approved roadmap revision, AP phase/milestone, requirement IDs, authorized scope and acceptance criteria for each stream;
- one owner per workstream and explicit file/interface boundaries, exclusions, dependencies and handoff points;
- stable, versioned interface contracts shared by the streams; parallel implementation must wait until required contracts are stable;
- separate branches/worktrees for each workstream;
- one named integration authority for the milestone, solely responsible for coordinating integration and merge to the milestone/integration branch.

Each stream reports progress through the issue using: status; branch/worktree and latest commit; completed scope/evidence; current work; blockers/dependencies; changed or at-risk contracts/files; and next handoff. The session owner must read and acknowledge new coordination messages at these checkpoints: (1) assignment/start, (2) before changing a shared contract or crossing a stated boundary, (3) after each meaningful implementation checkpoint/commit, (4) before reporting blocked or handing off, and (5) immediately before integration, merge or acceptance request. Incorporate applicable messages before proceeding.

The integration authority checks ownership and roadmap traceability, reviews the full diff against stable contracts, coordinates a controlled merge, and records proportionate verification/acceptance evidence in the issue. Only the designated integration authority performs the milestone merge unless the Steward explicitly changes that assignment. Every participating session remains bound by the approved roadmap and its own authorized scope.

AP0 is primarily sequential. Parallel work in subsequent milestones is appropriate only when interfaces/contracts and dependencies are stable enough to support independent branches and controlled integration. Every active R3A milestone has a designated coordination issue and one named integration authority, including sequential AP0 work. A milestone assignment is not ready to start until both are recorded.

## Production activation readiness

Deployment readiness requires an independently verified activation-capable procedure, actual service and release topology, and integration of the exact delivered feature against the current live baseline. A plan-only manifest validation is never a deployment. Preserve dirty shared checkouts, unrelated runtime/services and existing release. An authorized gateway probe succeeding does not establish that deployment commands are permitted; when substantive requests fail, record the reason and use the PowerShell 7 clipboard fallback. Report PREDEPLOY_BLOCKED rather than attempt an unverified activation.

## Shared baseline rule

Teams can develop independently, but a shared-service deployment must reconcile against the current approved integration baseline and preserve other teams' working functionality. Do not deploy an older partial runtime over a unified release. Identify actual active commits before activation.

## Governing principles

- Keep the root [AI_HINTS.md](../AI_HINTS.md) lightweight; detailed guidance lives in `hints/` or an authoritative document linked from it.
- Every major component should have configuration owned by that component and validated at startup.
- Prefer progress and clear evidence over exhaustive predeployment testing, elaborate rollback automation or speculative redesign.
- Use AI_HINTS and its linked punch lists, parking lots and runbooks as a miniature knowledge base pending future consolidation; do not duplicate competing sources of truth.
- Preserve the R/3 [file provenance](file-provenance.md) convention for all new/modified files.
- Update this standard as the Steward approves new rules; do not silently elevate suggestions into binding policy.
