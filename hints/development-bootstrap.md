<!--
R3 CONTROLLED DOCUMENT
File: hints/development-bootstrap.md
Component: ENG-DEV-BOOTSTRAP
File Revision: 1.0.0
Created: 2026-11-05 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Standardize the start of new R3 feature-development conversations
Execution Model: Documentation / development conversation initialization
Observability: Git history and bootstrap readiness summary
Dependencies: AI_HINTS.md; hints/README.md; hints/engineering.md; hints/development-governance.md
Authority: Steward direction, R3 charter, AI_HINTS.md
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-001 | ChatGPT GPT-6 | Initial bootstrap guidance
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; hints/development-governance.md
Tests: Link and content review; no runtime deployment
History/Predecessor: New file; none
-->
# R/3 Development Bootstrap

**Startup phrase: `R3 Bootstrap`** (also recognize “R/3 development starting point”). This is a conversation convention, not an automatically installed ChatGPT command. A new conversation must have access to this repository or be given its URL and the phrase's meaning.

## Required startup procedure

1. Read repository-root [AI_HINTS.md](../AI_HINTS.md), then [hints/README.md](README.md), this document, [development governance](development-governance.md), [engineering](engineering.md), [architecture](architecture.md), [deployment](deployment.md), and [file provenance](file-provenance.md). Follow linked authoritative documents relevant to the assignment; do not blindly read the entire repository.
2. Inspect the actual target repository, current branch/worktree, active integration baseline, deployment state and affected service/API contracts. **Never assume a historical commit is still the current approved baseline.** Distinguish observed state from plans and past reports.
3. Identify the owning workstream and dependencies. Preserve parallel HR onboarding, website multi-resident Chat, Grace autonomy, avatar and infrastructure work. Coordinate shared changes rather than deploying incompatible snapshots.
4. Confirm major components have documented, validated configuration files. Prefer configuration-owned behavior over stacked systemd overrides, hidden defaults or hardcoded deployment assumptions.
5. Before coding, state the feature objective, proposed minimal change, affected interfaces/configuration, baseline, and **proportionate Definition of Done** from [development governance](development-governance.md). Ask only for genuinely missing authorization or requirements.
6. Implement and produce the standard delivery summary: source branch and exact commit, changed files, configuration/interface changes, targeted checks and results, backup confirmation if deploying, observed deployment status, and any unresolved issues. Do not claim completion without evidence.

## Deployment policy during accelerated development

**Confirm prior backup → Deploy → Essential smoke verification → Fix in place.** Automatic rollback, broad regression gates and elaborate disaster recovery are deferred. Do not erase backups or claim tests were run when they were not. Protect credentials and persistent state.

## Ready response

After reading the instructions, report the repository/ref inspected, applicable baseline, relevant constraints and readiness for the Steward's feature assignment. **Do not start coding an unspecified feature** and do not turn bootstrap into a lengthy discovery exercise.

## Copy/paste starter for a fresh chat

> R3 Bootstrap. Use https://github.com/ppow1/R3 and read the root AI_HINTS.md, then follow its hints/development-bootstrap.md pointer and linked governance. Confirm the current baseline and await my feature assignment.
