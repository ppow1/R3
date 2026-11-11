<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/artifact-registry.md
Component: ENG-ARTIFACT-REGISTRY
File Revision: 1.0.2
Created: 2026-11-11T13:54:20Z
Created By: Codex GPT-6
Purpose: Authoritative source-controlled index of artifact locations, lifecycle state, ownership, dependencies, and verification evidence
Execution Model: N/A; registry only
Observability: Version-controlled records; no runtime polling
Dependencies: Git history; linked issues and source artifacts
Authority: Issue #62 comment 6796248868; Step 11 dispatch 6798229653; repository file provenance convention; no deployment authorization implied
Changed: 2026-11-11T13:54:20Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Create canonical artifact and deployment registry
Changed: 2026-11-11T13:57:29Z | R3-BRIDGE-V3-STEP7 | Codex GPT-6 | Record published source commit SHA
Changed: 2026-11-11T14:40:00Z | R3-BRIDGE-V3-STEP11 | Codex GPT-6 | Register executable modular provider, tests, and live acceptance limits
Changed: 2026-11-11 | R3-BRIDGE-V3-STEP95 | Codex GPT-6 | Record active-baseline manifest alignment and idempotency audit correction
Supersedes: None
Contracts: hints/file-provenance.md; docs/operations/bridge-v3-design.md
Tests: 81 combined active-baseline unit/contract tests passed; no shared runtime tests
History/Predecessor: Git blob 0f4b19ce13e4f9582bf00e84c379b846ad45ff21
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

## Bridge v3 — source module vertical slice

| Field | Record |
|---|---|
| Artifact / purpose | Disabled-by-default R3A Bridge capability provider: versioned routing planner, activity handler, and injected host-transport boundary |
| Lifecycle | **CREATED and contract-tested in source control; NOT DEPLOYED; shared runtime behavior NOT VERIFIED** |
| Repository / branch / commit | `ppow1/R3`; PR branch `engineering/r3a-bridge-v3-20261111`; source/idempotency correction commit `7950e52`; active-baseline contract alignment commit `7a59b4a` |
| Source paths | `r3a_plugins/development_bridge/{manifest.json,provider.py,config.example.json}`; provenance sidecars; `tests/test_r3a_development_bridge.py`; design and compliance matrix in `docs/operations/` |
| Artifact integrity | `provider.py` SHA-256 `b97a41e8dae48c880f5ce504d60cbd289906fa5713a405773b44f679c18077e8`; pinned by the manifest and checked in tests |
| Absolute path / host | Development worktree `/home/admin1/r3a-workstreams/bridge-v3-20261111` on Linux; production/runtime deployment **NOT DEPLOYED** |
| Config / services / ports / runtime / worktree | Example transport is `unavailable`; no service, port, grant, host adapter, or shared runtime configured. Development worktree is the absolute path above. |
| Owner / work | Live Modular; [Issue #62](https://github.com/ppow1/R3/issues/62); source dispatch [#61 comment 6798229653](https://github.com/ppow1/R3/issues/61#issuecomment-6798229653); [PR #64](https://github.com/ppow1/R3/pull/64) |
| Dependencies | Active Live Modular baseline `2cc3fe3`; module-manifest v1.1.0, capability-provider worker, module lifecycle, activity-handler v1.0, and CME authorization/persistence. Real target/session source, safe Windows v2 transport, and Coordinator-approved shared activation remain prerequisites for live acceptance. |
| Start / stop / restart / test / rollback | No shared start/stop command is authorized. On the rebased candidate, the combined source/contract suite is `python3 -m pytest -q tests/test_r3a_development_bridge.py tests/test_r3a_module_contracts.py tests/test_r3a_module_extensions.py tests/test_r3a_module_extension_lifecycle.py tests/test_r3a_activity_handler_interop.py tests/test_r3a_capability_integration_demo.py`; local subordinate transport-attempt recovery requires explicit reconciliation after uncertain sends. Revert the source increment `7950e52` before deployment; preserve V2 unchanged. |
| Verification evidence | 81 combined active-baseline tests pass. Includes default-disabled discovery, digest pinning, worker lifecycle, activity schema, mocked routing/receipts, duplicate suppression and reconciliation, plus regressions that changed target, mode, or summary fails closed with no reused receipt or second transport call. Provider artifact SHA-256 `b208529353b2abf053ce051dab3644be46ebf5f54f5c3ef0ec6317678ed645e0` is pinned by the manifest. No Windows poll, real host delivery, live invocation, or shared runtime lifecycle test has run. |
| Follow-up | Coordinator authorization plus approved read-only grant, provider/transport health checks, managed runtime activation, real invocation evidence, rollback verification, and installation-time measurement. Independent Auditor review remains associated with PR #64. |

## Registry update rule

For each new artifact, record purpose, repository, branch, commit, repository-relative source path, absolute deployed path and hostname (or `NOT DEPLOYED`), configuration, services, ports, runtime/worktree paths, owner and issue/roadmap, dependencies, lifecycle commands, verification state/time, and evidence links. Record an unknown as `UNKNOWN — needs verification`; do not fill fields by inference. The bridge coordinator, once implemented and authorized, must write newly provisioned worktree, branch, terminal, and session locations into its durable operational store and publish a safe GitHub-linked summary.
