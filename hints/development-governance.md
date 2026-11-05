<!--
R3 CONTROLLED DOCUMENT
File: hints/development-governance.md
Component: ENG-DEV-GOVERNANCE
File Revision: 1.0.0
Created: 2026-11-05 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Initial R3 development lifecycle, Definition of Done and deployment-input contract
Execution Model: Documentation / development conversation initialization
Observability: Git history and bootstrap readiness summary
Dependencies: hints/development-bootstrap.md; hints/engineering.md; hints/deployment.md
Authority: Steward direction, R3 charter, AI_HINTS.md
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-001 | ChatGPT GPT-6 | Initial bootstrap guidance
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
Tests: Link and content review; no runtime deployment
History/Predecessor: New file; none
-->
# R/3 Development Governance — Initial Working Standard

**Status:** Steward-directed initial standard, intentionally lightweight and amendable. This is the R/3 working policy; historical R/2 standards are references, not automatically adopted in full.

## Development cycle

1. **Initialize:** Run [R3 Bootstrap](development-bootstrap.md); inspect current baseline, relevant configuration, interfaces, and ownership.
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

## Shared baseline rule

Teams can develop independently, but a shared-service deployment must reconcile against the current approved integration baseline and preserve other teams' working functionality. Do not deploy an older partial runtime over a unified release. Identify actual active commits before activation.

## Governing principles

- Keep the root [AI_HINTS.md](../AI_HINTS.md) lightweight; detailed guidance lives in `hints/` or an authoritative document linked from it.
- Every major component should have configuration owned by that component and validated at startup.
- Prefer progress and clear evidence over exhaustive predeployment testing, elaborate rollback automation or speculative redesign.
- Preserve the R/3 [file provenance](file-provenance.md) convention for all new/modified files.
- Update this standard as the Steward approves new rules; do not silently elevate suggestions into binding policy.
