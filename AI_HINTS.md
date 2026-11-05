<!--
R3 CONTROLLED DOCUMENT
File: AI_HINTS.md
Component: ENG-AGENT-INDEX
File Revision: 1.0.6
Created: Unknown (legacy; inspect initial Git commit for earliest published version)
Created By: Unknown (legacy)
Purpose: Lightweight agent startup and knowledge index
Execution Model: N/A
Observability: N/A
Dependencies: hints/README.md
Authority: R3 engineering navigation, subordinate to approved charter
Changed: 2026-11-05 UTC | R3-HR-DOCS-INDEX | ChatGPT GPT-6 | Link HR engineering, Helen operations, and build/deployment history runbooks
Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Index manifest-driven deployment runbook and scripts
Changed: 2026-11-04 UTC | R3-GRANT-RUNBOOK-MIGRATION | ChatGPT GPT-6 | Direct all new grant/delegation runbooks to R3
Changed: 2026-11-02 UTC | R3-AVATAR-001 | ChatGPT GPT-6 | Index resident avatar implementation notes
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Index mandatory Comms incident capture
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Manual source inspection; automated validation pending
History/Predecessor: Git blob 3061d08891006f8807adcc935cc1c1e9dbe6e45a
-->
# AI_HINTS.md — Riverview 3

## How to use AI_HINTS.md

**Mandatory for every repository file:** read [file provenance and header rules](hints/file-provenance.md) before creating or changing a file. Put a complete language-appropriate header (or binary sidecar) on each file; include creation actor/time, revision, purpose, change history, and explicit supersession. Preserve the predecessor before updates.

When adding project knowledge, **store the substantive document in `hints/` and add a short index pointer here**. Update an existing topic document when appropriate; do not duplicate detailed content in this root file. The pointer should name the topic and link to its source. See [the hints index](hints/README.md) for organization and onward references.

Start with [the hints index](hints/README.md). Keep this root file short; put detailed guidance in `hints/` and link onward to authoritative documents.

**Riverview Comms:** For every failed or blocked operation, follow [Comms failure recording and recovery](hints/comms-failure-recovery.md) and create/update a durable incident with a punch-list reference. Record preflight blocks even when no command was submitted.

**Runbook ownership:** All NEW Riverview 3 engineering and operational runbooks, including grants and delegations, must be created or updated in `ppow1/R3` only. `ppow1/Riverview-` is historical/reference material, not the destination for new R3 runbooks. See [Command Access Grants and Delegations](docs/runbooks/COMMAND_ACCESS_GRANTS_AND_DELEGATIONS.md). Do not silently update legacy runbooks.

## Essential rules

- Read the approved [R3 charter](docs/PROJECT_CHARTER_REVISION_2_REVIEW.md) before architectural changes.
- Inspect actual repository and runtime state; distinguish verified behavior from requirements and plans.
- **Engineering scope is not operational scope.** Do not impose arbitrary limits on Grace or other residents based on a narrow test.
- Preserve authorization, audit, recovery, substantive verification, and truthful UI status without unnecessary bureaucracy.
- Do not migrate Riverview 2 wholesale or modify production/backups without explicit authorization.
- Favor small, testable changes and verified outcomes.

## First-level references

- [Engineering and current handoff](hints/engineering.md)
- [Institutional architecture and durable state](hints/architecture.md)
- [Deployment and command execution](hints/deployment.md) — [manifest-driven runbook](docs/runbooks/R3_MANIFEST_DEPLOYMENT.md) and [deployment scripts](scripts/deployment/Deploy-R3.ps1) (currently plan-only; no live activation)
- **HR personnel files:** [Engineering and operations runbook](docs/runbooks/HR_PERSONNEL_SYSTEM.md) · [Helen's operating guide](docs/HELEN_HR_GUIDE.md) · [Tool construction and deployment history](docs/runbooks/HR_TOOLS_BUILD_AND_DEPLOYMENT_HISTORY.md)
- [Resident avatar system](hints/resident-avatar-system.md) — replaceable website avatar runtime, browser animation API, and pending authorized backend connection

When asked to add material to AI_HINTS, update a focused `hints/` document and add or adjust a concise pointer here only if needed.

---

## Grace integration guidance — preserved source

The following guidance is preserved from the approved Grace integration revision. Where instructions conflict, the Steward's R3 independence and unified-release directive takes precedence.

<!--
R3 CONTROLLED DOCUMENT
File: AI_HINTS.md
Component: ENG-AGENT-INDEX
File Revision: 1.0.7
Created: Unknown (legacy; inspect initial Git commit for earliest published version)
Created By: Unknown (legacy)
Purpose: Lightweight agent startup and knowledge index
Execution Model: N/A
Observability: N/A
Dependencies: hints/README.md
Authority: R3 engineering navigation, subordinate to approved charter
Changed: 2026-11-04 UTC | R3-RUNTIME-ROUTING-001 | ChatGPT GPT-6 | Index canonical live routing and auth runbook
Changed: 2026-11-02 UTC | R3-MISTAKE-001 | ChatGPT GPT-6 | Index mistakes log and MCP autonomy failure case
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Index mandatory Comms incident capture
Changed: 2026-11-01 UTC | R3-Q2-DOC-001 | ChatGPT GPT-6 | Index Q2 watched-folder runbook
Changed: 2026-11-01 UTC | R3-IMAGE-PUBLISH-001 | ChatGPT GPT-6 | Index verified image publishing policy
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Manual source inspection; automated validation pending
History/Predecessor: Git blob a3d9aa48e679ed07fe27ef9e31a283b55d582c8f
-->
# AI_HINTS.md — Riverview 3

## How to use AI_HINTS.md

**Mandatory for every repository file:** read [file provenance and header rules](hints/file-provenance.md) before creating or changing a file. Put a complete language-appropriate header (or binary sidecar) on each file; include creation actor/time, revision, purpose, change history, and explicit supersession. Preserve the predecessor before updates.

When adding project knowledge, **store the substantive document in `hints/` and add a short index pointer here**. Update an existing topic document when appropriate; do not duplicate detailed content in this root file. The pointer should name the topic and link to its source. See [the hints index](hints/README.md) for organization and onward references.

Start with [the hints index](hints/README.md). Keep this root file short; put detailed guidance in `hints/` and link onward to authoritative documents.

**Riverview Comms:** For every failed or blocked operation, follow [Comms failure recording and recovery](hints/comms-failure-recovery.md) and create/update a durable incident with a punch-list reference. Record preflight blocks even when no command was submitted.

**MANDATORY HARD GATE:** Before any engineering change, read [no one-time tests or test-shaped production restrictions](hints/engineering-test-policy.md). Never introduce scenario-specific throwaway tests, artificial runtime limits, or temporary qualification checks as permanent deployment gates.

## Essential rules

- Read the approved [R3 charter](docs/PROJECT_CHARTER_REVISION_2_REVIEW.md) before architectural changes.
- Inspect actual repository and runtime state; distinguish verified behavior from requirements and plans.
- **Engineering scope is not operational scope.** Do not impose arbitrary limits on Grace or other residents based on a narrow test.
- Preserve authorization, audit, recovery, substantive verification, and truthful UI status without unnecessary bureaucracy.
- Do not migrate Riverview 2 wholesale or modify production/backups without explicit authorization.
- Favor small, testable changes and verified outcomes.

## First-level references

- [Mistakes log: reasoning failures and corrective lessons](hints/mistakes/README.md) — includes R3-MISTAKE-001, the unauthorized MCP read-only restriction during Grace autonomy integration.
- [Engineering and current handoff](hints/engineering.md)
- [Grace MCP autonomy milestone and Comms 3 architecture (2026-11-02)](hints/milestones/2026-11-02-grace-mcp-milestone.md) — verified Event 2 tool invocation, HTTP 400 continuation failure, R2 isolation, STDIO/LAN/external topology and follow-up investigations.
- [Institutional architecture and durable state](hints/architecture.md)
- [Deployment and command execution](hints/deployment.md)
- **[R3 live runtime routing, service identification and authentication boundary](hints/r3-runtime-routing.md)** — read before website diagnostics or deployment; includes observed 404s, upstreams and legacy deploy-script warning.
- [Q2 watched script queue: submit, dispatch, and retrieve results](hints/q2-script-queue.md)
- [ChatGPT-generated image publishing: Download → A: → GitHub](hints/chatgpt-image-publishing.md)

When asked to add material to AI_HINTS, update a focused `hints/` document and add or adjust a concise pointer here only if needed.


## Unified R/3 integration baseline v1
- `docs/integration/UNIFIED_BASELINE_V1.md`: shared architecture, contracts, invariants and verification.
- `docs/integration/TEAM_HANDOFF_V1.md`: Website, HR and Grace autonomy handoff.
