<!--
R3 CONTROLLED DOCUMENT
File: hints/development-bootstrap.md
Component: ENG-DEV-BOOTSTRAP
File Revision: 1.0.5
Created: 2026-11-05 UTC (date only; exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Standardize the start of new R3 feature-development conversations
Execution Model: Documentation / development conversation initialization
Observability: Git history and bootstrap readiness summary
Dependencies: AI_HINTS.md; hints/README.md; hints/engineering.md; hints/development-governance.md
Authority: Steward direction, R3 charter, AI_HINTS.md
Changed: 2026-11-05 UTC | R3-BOOTSTRAP-ACCEPTANCE-007 | ChatGPT GPT-6 | Disallow demonstration-only, bounded one-time, and nonproduction substitutes for operational acceptance
Changed: 2026-11-05 UTC | R3-BOOTSTRAP-ACCEPTANCE-006 | ChatGPT GPT-6 | Require operational completion rather than plan-only milestones
Changed: 2026-11-05 UTC | R3-DEPLOY-BOOTSTRAP-005 | ChatGPT GPT-6 | Require verified real activation and protected integration/fallback
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-003 | ChatGPT GPT-6 | Require dated cited evidence correction
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-002 | ChatGPT GPT-6 | Require local-evidence-first gateway execution and PowerShell clipboard fallback
Changed: 2026-11-05 UTC | R3-DEV-BOOTSTRAP-001 | ChatGPT GPT-6 | Initial bootstrap guidance
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; hints/development-governance.md
Tests: Link and content review; no runtime deployment
History/Predecessor: Git blob d136a4ddf31f199615670b4c91856f5fd22a11b1
-->
# R/3 Development Bootstrap

**Startup phrase: `R3 Bootstrap`** (also recognize “R/3 development starting point”). This is a conversation convention, not an automatically installed ChatGPT command. A new conversation must have access to this repository or be given its URL and the phrase's meaning.

## Required startup procedure

1. Read repository-root [AI_HINTS.md](../AI_HINTS.md), then [hints/README.md](README.md), this document, [development governance](development-governance.md), [engineering](engineering.md), [architecture](architecture.md), [deployment](deployment.md), [file provenance](file-provenance.md), and **[Development Execution](development-execution.md)**. Follow linked authoritative documents relevant to the assignment; do not blindly read the entire repository.
2. **Use existing local and retrieved evidence first** (repository, configs, prior outputs, runbooks, issues, punch lists, parking lots). Reuse unless verified incorrect, outdated or superseded; then correct the authoritative record with a dated update, cited source and preserved predecessor. Distinguish original observation date from correction date. Treat [AI_HINTS](../AI_HINTS.md) and its references as the current miniature knowledge base; consolidate authoritative references over time without inventing a completed knowledge-base system. Follow [Development Execution](development-execution.md) for mandatory command workflow.
3. Inspect the actual target repository, current branch/worktree, active integration baseline, deployment state and affected service/API contracts. **Never assume a historical commit is still the current approved baseline.** Distinguish observed state from plans and past reports.
4. Identify the owning workstream and dependencies. Preserve parallel HR onboarding, website multi-resident Chat, Grace autonomy, avatar and infrastructure work. Coordinate shared changes rather than deploying incompatible snapshots.
5. Confirm major components have documented, validated configuration files. Prefer configuration-owned behavior over stacked systemd overrides, hidden defaults or hardcoded deployment assumptions.
6. Before coding, state the feature objective, proposed minimal change, affected interfaces/configuration, baseline, and **proportionate Definition of Done** from [development governance](development-governance.md). Ask only for genuinely missing authorization or requirements.
7. **Use authorized Riverview Comms 1.1 / command gateway first** when machine queries, code writing, execution, deployment or testing are needed. Discover capabilities and grants; if unavailable or blocked, use the documented PowerShell 7 clipboard fallback: `Clear-Host`, capture stdout/stderr/exit status in variables, display consolidated `$result`, and `Set-Clipboard -Value $result`. Do not repeat expensive tests when reliable evidence already exists.
8. Implement and produce the standard delivery summary: source branch and exact commit, changed files, configuration/interface changes, targeted checks and results, backup confirmation if deploying, observed deployment status, and any unresolved issues. Do not claim completion without evidence.

## Production activation readiness

Before attempting production activation, verify the documented runner performs a REAL activation (not a plan-only validation); inspect the live service owner, source, release path and current deployment baseline. Resolve feature-branch divergence through an isolated candidate preserving other workstreams. Do not deploy a whole outdated branch over the shared runtime, reset a dirty shared checkout, or use a legacy script whose service/port assumptions do not match live state. If the authorized Command Gateway rejects deployment-related requests despite active grants, record the blocker and use the complete PowerShell clipboard fallback for safe live preflight and activation, with observed evidence. If a safe activation procedure cannot yet be determined, report PREDEPLOY_BLOCKED, not DEPLOYED.

## Operational completion gate — no plan-only substitutions

**The requested operational outcome is the acceptance criterion.** A document, manifest, implementation plan, prototype, candidate build, tests passing, or a script that only validates a plan is an intermediate deliverable, **not completion**, when the Steward requested working functionality. Labels such as `plan-only`, `phase 1`, `pending integration`, and `ready to deploy` must not be reported as deployed, operational, or done.

Before beginning work, record the requested observable end-to-end behavior and how it will be verified on the intended host/service. For a deployment capability, the minimum acceptance is **one actual update installed through the intended procedure, the intended running revision verified, and essential live behavior checked**. A zero exit code from a manifest validator or an HTTP 200 alone does not satisfy that criterion.

**Demonstration and scope-limit guardrail:** Descriptions such as `bounded`, `one-time use`, `demonstration only`, `proof of concept`, `mock`, `stub`, `simulation`, `dry run`, `read-only demonstration`, `temporary workaround`, `pilot`, and `manual-only` do not establish production readiness or completion of a request for an ongoing, reusable capability. A successful single demonstration is evidence of that demonstration only, not proof of durable integration, repeatable operation, ongoing autonomy, or general deployment capability. Do not silently replace a requested persistent/automated/multi-use feature with a limited demonstration, nor impose artificial use counts or narrow test permissions on its operational scope. Such limits are acceptable only if the Steward explicitly requests them or they are necessary, disclosed safety/authorization boundaries. State exactly what is demonstrated versus what remains operationally unverified.

When a stage is incomplete, explicitly report **NOT OPERATIONAL / BLOCKED**, what is implemented, what remains, and the exact blocker. Do not silently move the missing activation/integration work into an unspecified future phase or declare the original request completed. Only treat a plan-only artifact as final when the Steward **explicitly requested planning only**.

Use the existing R/3 Bootstrap, deployment governance, and runbooks; do not create another manager, parallel installer, or architectural workstream to satisfy this rule. For urgent feature delivery, use an already verified safe activation path if available, and defer installer improvement without delaying the feature. Preserve live services and the dirty shared checkout.

## Deployment policy during accelerated development

**Confirm prior backup → Deploy → Essential smoke verification → Fix in place.** Automatic rollback, broad regression gates and elaborate disaster recovery are deferred. Do not erase backups or claim tests were run when they were not. Protect credentials and persistent state.

## Ready response

After reading the instructions, report the repository/ref inspected, applicable baseline, relevant constraints and readiness for the Steward's feature assignment. **Do not start coding an unspecified feature** and do not turn bootstrap into a lengthy discovery exercise.

## Copy/paste starter for a fresh chat

> R3 Bootstrap. Use https://github.com/ppow1/R3 and read the root AI_HINTS.md, then follow its hints/development-bootstrap.md pointer and linked governance. Confirm the current baseline and await my feature assignment.
