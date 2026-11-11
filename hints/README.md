<!--
R3 CONTROLLED DOCUMENT
File: hints/README.md
Component: README
File Revision: 1.0.7 (provenance baseline; prior revisions untracked)
Created: Unknown (legacy; initial commit can establish earliest publication)
Created By: Unknown (legacy)
Purpose: R3 engineering reference and continuation guidance
Execution Model: N/A
Observability: N/A
Dependencies: R3 docs and hints index
Authority: R3 engineering guidance; approved charter prevails
Changed: 2026-11-11 UTC | B2-HANDOFF-001 | ChatGPT GPT-6 | Index external B-2 development coordination guidance
History/Predecessor: Git blob e5259ded576a3017e8fe8a4a08870a9d75dc2087
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-002 | ChatGPT GPT-6 | Require local-evidence-first gateway execution and PowerShell clipboard fallback
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-001 | ChatGPT GPT-6 | Index R3 development bootstrap and governance
Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | ChatGPT GPT-6 | Index manifest-driven deployment runbook and scripts
Changed: 2026-11-02 UTC | R3-AVATAR-001 | ChatGPT GPT-6 | Index resident avatar runtime notes
Changed: 2026-11-01 UTC | R3-CHAT-SETTINGS-UI-001 | ChatGPT GPT-6 | Index chat and scoped settings review drafts
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Not run (metadata-only change)
History/Predecessor: Git blob ec3ff8e22de6924c314071681d8861469b33c0f6
-->
# R3 Hints Library

This directory is the first-level reference index for the root [AI_HINTS.md](../AI_HINTS.md).

## Convention

- Keep the root `AI_HINTS.md` short: orientation, critical guardrails, and links.
- When asked to “add something to AI_HINTS,” put substantive guidance in a focused document under `hints/`, then add or update a concise root pointer.
- Link to authoritative documents elsewhere instead of copying their contents. Avoid multiple competing sources of truth.
- Name files for stable subjects; revise existing topic files instead of creating dated duplicates unless historical versioning is required.
- Keep verified implementation state separate from requirements and plans.

## Starting references

- [Development Bootstrap](development-bootstrap.md): mandatory initialization for new R3 feature-development conversations; startup phrase `R3 Bootstrap`.
- [Development Governance](development-governance.md): initial lifecycle, Definition of Done, shared baseline and deployment input requirements.
- [Development Execution](development-execution.md): local evidence first, authorized Comms gateway first for machine work, and clipboard-ready PowerShell 7 fallback.

- [Engineering and continuation](engineering.md): workflow, branch/worktree discipline, and current handoff.
- [Institutional architecture](architecture.md): charter and capability-first, durable institution principles.
- [Deployment](deployment.md): Comms-first execution, Camrui bootstrap and verification.
- [Resident avatar system](resident-avatar-system.md): shared browser runtime, animation API, asset provenance, and pending authorized backend bridge.

- [Manifest-driven website deployment runbook](../docs/runbooks/R3_MANIFEST_DEPLOYMENT.md): exact operator commands, manifest examples and phase-1 plan-only status; see [deployment hint](deployment.md).

## External development coordination (not Riverview runtime)

- [B-2 external ChatGPT development control — operational handoff](../docs/operations/development-bridge/B2_EXTERNAL_DEVELOPMENT_CONTROL_HANDOFF.md): GitHub Issue #61 dispatch contract, Administrator Coordinator PowerShell, Codex target routing, screenshot return, evidence verification, known limits, and next acceptance tests.
- [B-2 November 11 executive summary](../docs/operations/development-bridge/B2_2026-11-11_EXECUTIVE_SUMMARY.md): work completed and independently supported results. **This bridge exists to build Riverview and must not be mistaken for an R3A institutional/runtime component.**
