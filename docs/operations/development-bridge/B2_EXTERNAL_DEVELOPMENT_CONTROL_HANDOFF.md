<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/development-bridge/B2_EXTERNAL_DEVELOPMENT_CONTROL_HANDOFF.md
Component: EXTERNAL-DEV-BRIDGE-RUNBOOK
File Revision: 1.0.0
Created: 2026-11-11 UTC (date precision)
Created By: ChatGPT GPT-6, acting on Steward instruction
Purpose: Provide the operational handoff and usage guidance for future R3A development sessions
Execution Model: External ChatGPT/GitHub/Windows development coordination; not Riverview runtime
Observability: GitHub Issue #61 execution receipts and screenshot evidence
Dependencies: ppow1/R3 Issue #61; Windows B-2 Multi-Target Bridge
Authority: Steward; external development tooling only
Changed: 2026-11-11 UTC | B2-HANDOFF-001 | ChatGPT GPT-6 | Initial publication
Supersedes: None
Contracts: B-2 GitHub dispatch and target routing as documented; not an R3A runtime contract
Tests: Evidence-linked observations; outstanding live queue-bypass test
History/Predecessor: None; initial document
-->

# Operational Handoff — External ChatGPT Development Control System

**System:** B-2 Multi-Target GitHub Bridge  
**Status:** Operational for supervised development coordination; additional reliability acceptance pending  
**Date:** November 11, 2026

## Boundary: external development tooling

**B-2 is not a Riverview module.** It is not CME, Grace autonomy, a resident capability interface, a resident runtime service, or a replacement for R3A governance. It is an external workflow that helps ChatGPT and the Steward **build Riverview**. Do not introduce its code, polling loop, or GitHub dispatch protocol into R3A's application architecture without a separate explicit decision.

## Architecture

```text
ChatGPT (plans, dispatches, verifies)
    ↓ assignments
Private GitHub ppow1/R3 Issue #61
    ↓ polled comments
Windows B-2 Multi-Target Bridge
    ├── Administrator Coordinator PowerShell → Windows operations
    └── configured Codex terminals → development work
    ↓ receipts, result comments, evidence files
Private GitHub
    ↓ retrieval
ChatGPT (inspect evidence, choose next step)
```

GitHub is the intermediate message/evidence service; this is **not a direct interactive terminal session**.

## Current concrete locations

- **Windows host:** `DESKTOP-JA3RPNQ`
- **Bridge:** `C:\Users\wille\Downloads\Riverview-B2-Administrator-Package\Riverview-GitHub-Bridge-B2-MultiTarget.ps1`
- **Target registry:** `C:\Users\wille\Downloads\Riverview-B2-Administrator-Package\Riverview-B2-targets.json`
- **Dispatch:** [private Issue #61](https://github.com/ppow1/R3/issues/61)
- **Current verified registry targets:** `Administrator Coordinator` → `Riverview B2 Administrator Coordinator`; `HR Development` → `HR - Vicky | hr-development`.
- **Local bridge state:** `%LOCALAPPDATA%\RiverviewGitHubBridge\multi-target-state.json`; bridge uses a lock file in the same directory.
- **Observed polling:** approximately ten seconds when launched with `-PollSeconds 10`. Do not assume every assignment completes within ten seconds.

## Delivery contracts

### Administrator Coordinator (PowerShell)

Post a comment on Issue #61 using an authorized account, including a unique planned-step number, **exact** target name, and fenced PowerShell:

```text
PLANNED STEP 41
TARGET: Administrator Coordinator
DELIVERY: STEER
TYPE: READ-ONLY DIAGNOSTIC

```powershell
Write-Output 'DIAGNOSTIC=PASS'
```
```

The bridge writes a local command wrapper and submits it to the Administrator Coordinator. The wrapper posts output as a GitHub `B-2 ADMIN RESULT` comment. Check the actual result, not only `WAKE-UP SENT`.

### Codex development terminal

Post `PLANNED STEP <number>` and `TARGET: <exact configured target>` with a clear, scoped development instruction. The bridge sends a short wake-up to the configured Codex terminal instructing it to read the GitHub comment, acknowledge it, perform authorized work, and post evidence. **Do not send Win32/PowerShell desktop commands to a Linux Codex terminal and assume it can execute them.**

Only the two mappings listed above have been verified in this handoff. The other visible development terminals must be onboarded and tested individually before being considered addressable.

## Standard coordination loop

1. Identify the desired outcome and the configured target.
2. Dispatch a narrowly scoped, authorized assignment on Issue #61.
3. Check the issue for a bridge `WAKE-UP SENT` receipt.
4. Check again for a **target result or acknowledgment**, not merely the wake-up.
5. Retrieve evidence: logs, tests, commits, PRs, or screenshots.
6. Independently evaluate the evidence and distinguish queued / delivered / acknowledged / executing / blocked / verified complete.
7. Follow up or correct failures. If an answer can be obtained by checking again within the same ChatGPT turn, do so instead of ending at submission.
8. For desktop-visible changes, include **capture, JPEG conversion, temporary private GitHub upload, and evidence pointer in the same PowerShell assignment** where practical, then retrieve and inspect the actual image.

For screenshots, the proven transport stores **JPEG base64 as UTF-8 text** on a temporary private GitHub branch; the GitHub connector fetches that text for visual display. Do not assume binary PNG fetches work through the same connector.

## Reliability and safety

- Reuse the existing B-2 bridge; do not invent parallel listeners, services, or command gateways.
- Do not restart or reposition Codex sessions unnecessarily.
- Preserve bridge processed-comment state; never clear it casually.
- Inspect actual source, take backups, guard hashes, and validate parser syntax before bridge patches.
- Recognize normal and `Select ` console titles. The installed patch also attempts to leave selection mode before sending input.
- A missing target should remain pending while other comments can proceed. **Static checks passed; live bypass while still unavailable remains unverified.**
- Treat `WAKE-UP SENT` as delivery, not task completion.
- Keep credentials and sensitive content out of comments and screenshot evidence.
- Respect authorized work boundaries and independent review for development changes.

## Evidence and acceptance status

| Capability | Status | Evidence |
|---|---|---|
| Administrator Coordinator execution | Verified | [Step 33 result](https://github.com/ppow1/R3/issues/61#issuecomment-6801746556) |
| Patched source and syntax/static checks | Verified | [Step 36 result](https://github.com/ppow1/R3/issues/61#issuecomment-6802035971) |
| Screenshot in same assignment | Verified | [Step 35 result](https://github.com/ppow1/R3/issues/61#issuecomment-6801854068) |
| Temporary HR title restoration | Verified | [Step 38 result](https://github.com/ppow1/R3/issues/61#issuecomment-6802076755) |
| Subsequent HR/Administrator deliveries | Verified | [Step 40 result](https://github.com/ppow1/R3/issues/61#issuecomment-6802116308) |
| Queue bypass *while* target unavailable | **Open** | Controlled test did not prove overlap |
| Exactly-once crash/restart recovery | **Open** | Not demonstrated |
| All Codex targets configured | **Open** | Only two mappings verified |

## Next work

1. Finish a timing-controlled missing-target bypass test with proof of overlap, followed by pending-target retry and nonduplicate delivery.
2. Expand `Riverview-B2-targets.json` for remaining Codex windows one by one and verify each.
3. Standardize queued/delivered/acknowledged/completed/blocked receipts and completion evidence.
4. Use the system to coordinate parallel R3A workstreams while maintaining R3A's internal autonomy and governance boundaries.

**Ownership:** External ChatGPT/Steward development infrastructure. Not a Riverview application/runtime component.
