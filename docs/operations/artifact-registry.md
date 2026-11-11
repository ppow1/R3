<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/artifact-registry.md
Component: ENG-ARTIFACT-REGISTRY
File Revision: 1.0.0
Created: 2026-11-11T13:54:20Z
Created By: Codex GPT-6
Purpose: Authoritative source-controlled index of artifact locations, lifecycle state, ownership, dependencies, and verification evidence
Execution Model: N/A; registry only
Observability: Version-controlled records; no runtime polling
Dependencies: Git history; linked issues and source artifacts
Authority: Issue #62 comment 6796248868; repository file provenance convention; no deployment authorization implied
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Create canonical artifact and deployment registry
Supersedes: None
Contracts: hints/file-provenance.md; docs/operations/bridge-v3-design.md
Tests: Manual path and repository-state inspection; no runtime tests
History/Predecessor: None; new file
-->
# Artifact and deployment registry

This is the canonical index for R3 source artifacts and deployments. Keep lifecycle states separate: **PLANNED**, **CREATED**, **DEPLOYED**, and **VERIFIED**. A later state requires its own evidence; a commit alone does not prove deployment or runtime behavior. Unknown values stay explicit. Update this registry with implementation handoffs and link the governing issue.

## Bridge v2 — reported Windows baseline

| Field | Record |
|---|---|
| Artifact / purpose | Riverview GitHub-to-PowerShell-to-Codex bridge v2; rollback baseline for Bridge v3 |
| Lifecycle | **REPORTED WORKING; NOT VERIFIED in this workspace** |
| Repository / branch / commit | Source repository, branch, and commit **UNKNOWN — needs authorized inspection**; reported as a file in Windows Downloads |
| Reported source path | `C:\Users\wille\Downloads\Riverview-GitHub-Bridge-v2.ps1` |
| Path / host verification | Host and current file existence **UNKNOWN — needs verification**. This Linux worktree has no mounted Windows Downloads path. |
| Config / services / ports / runtime / worktree | **UNKNOWN — needs authorized inspection** |
| Runtime | PowerShell 7 and window title `Live Modular | live-modular` are reported by Issue #62; not independently checked here |
| Owner / work | Live Modular; [Issue #62](https://github.com/ppow1/R3/issues/62), [Step 7 dispatch](https://github.com/ppow1/R3/issues/61#issuecomment-6795946572) |
| Dependencies | GitHub issue polling and Windows PowerShell; exact versions/configuration **UNKNOWN** |
| Start / stop / restart / test / rollback | **UNKNOWN — do not infer commands**. Preserve the existing v2 file unchanged until an authorized read-only inspection and backup are available. |
| Verification evidence | Step 5 communication proof: [dispatch](https://github.com/ppow1/R3/issues/61#issuecomment-6785355807), [wake receipt](https://github.com/ppow1/R3/issues/61#issuecomment-6785426064), [Codex acknowledgment](https://github.com/ppow1/R3/issues/61#issuecomment-6785430948). This proves that dispatch only, not v2 internals or QUEUE behavior. |
| Follow-up | Provide a read-only, integrity-checked copy or authorized mounted path; inspect V2 and preserve an actual rollback copy before implementation changes. |

## Bridge v3 — development design and registry

| Field | Record |
|---|---|
| Artifact / purpose | Contract-first design for managed poll, routing, durable delivery records, and isolated coordinator provisioning |
| Lifecycle | **CREATED in source control; NOT DEPLOYED; runtime behavior NOT VERIFIED** |
| Repository / branch / commit | `ppow1/R3`; branch `engineering/r3a-bridge-v3-20261111`; design commit is recorded in the GitHub completion report and git history |
| Source paths | `docs/operations/bridge-v3-design.md`; `docs/operations/artifact-registry.md` |
| Absolute path / host | Development worktree `/home/admin1/r3a-workstreams/bridge-v3-20261111` on the current Linux host; production/runtime deployment **NOT DEPLOYED** |
| Config / services / ports / runtime / worktree | No runtime configured or created. Service, port, and deployment locations **NOT APPLICABLE / NOT DEPLOYED**. Development worktree is the absolute path above. |
| Owner / work | Live Modular; [Issue #62](https://github.com/ppow1/R3/issues/62); source dispatch [#61 comment 6795946572](https://github.com/ppow1/R3/issues/61#issuecomment-6795946572) |
| Dependencies | GitHub issue/comment APIs; future implementation choices require the verified V2 baseline and approved Windows execution context. |
| Start / stop / restart / test / rollback | No executable v3 exists. No commands are defined. Rollback remains the unchanged V2 baseline after it is inspected and preserved. |
| Verification evidence | Design/path review only. No Windows PowerShell, two-target poll, restart deduplication, queue/steer, worktree provisioning, or live invocation test has run. |
| Future plugin contract | **PLANNED; NOT IMPLEMENTED or integrated as an R3A module.** The design keeps CME scheduling/enforcement, bridge transport/provisioning, and resident implementation authority separate. |

## Registry update rule

For each new artifact, record purpose, repository, branch, commit, repository-relative source path, absolute deployed path and hostname (or `NOT DEPLOYED`), configuration, services, ports, runtime/worktree paths, owner and issue/roadmap, dependencies, lifecycle commands, verification state/time, and evidence links. Record an unknown as `UNKNOWN — needs verification`; do not fill fields by inference. The bridge coordinator, once implemented and authorized, must write newly provisioned worktree, branch, terminal, and session locations into its durable operational store and publish a safe GitHub-linked summary.
