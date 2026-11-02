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
Changed: 2026-11-02 UTC | R3-MISTAKE-001 | ChatGPT GPT-6 | Index mistakes log and MCP autonomy failure case
Changed: 2026-10-31 UTC | R3-COMMS-001 | ChatGPT GPT-6 | Index mandatory Comms incident capture
Changed: 2026-11-01 UTC | R3-Q2-DOC-001 | ChatGPT GPT-6 | Index Q2 watched-folder runbook
Changed: 2026-11-01 UTC | R3-IMAGE-PUBLISH-001 | ChatGPT GPT-6 | Index verified image publishing policy
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Manual source inspection; automated validation pending
History/Predecessor: Git blob 3471309641de45c32c58e484fc9b1045a5c3dff1
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
- [Institutional architecture and durable state](hints/architecture.md)
- [Deployment and command execution](hints/deployment.md)
- [Q2 watched script queue: submit, dispatch, and retrieve results](hints/q2-script-queue.md)
- [ChatGPT-generated image publishing: Download → A: → GitHub](hints/chatgpt-image-publishing.md)

When asked to add material to AI_HINTS, update a focused `hints/` document and add or adjust a concise pointer here only if needed.
