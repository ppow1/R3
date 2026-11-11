# B-2 Development Bridge — Operator Runbook

**Purpose:** B-2 is the independent, currently operational development bridge between ChatGPT, private GitHub Issue #61, and existing Windows PowerShell/Codex terminals. It supports building Riverview. It is **not** the Riverview Bridge v3 modular runtime plugin.

## Architecture boundary
- **B-2:** Existing Windows PowerShell polling GitHub, selecting window targets and using SendKeys; assignments and receipts returned through GitHub. This development tool continues to operate independently while Riverview is being built.
- **Riverview Bridge v3:** Separate modular provider intended for Riverview's own runtime, subject to canonical R3A module contracts and independent acceptance. Similar communication behavior does not imply shared deployment, lifecycle, or dependency.
- Do not retire, replace, or make B-2 dependent on Bridge v3 simply because plugin development progresses. Do not introduce listeners or parallel transport for B-2 when existing routing suffices.

## Current installed Multi-Target bridge
Directory: `C:\Users\wille\Downloads\Riverview-B2-Administrator-Package`

Existing files:
- `Riverview-GitHub-Bridge-B2-MultiTarget.ps1`
- `Riverview-B2-targets.json`

Configured targets (verified by Issue #61 Step 14):
```json
{
  "Administrator Coordinator": "Riverview B2 Administrator Coordinator",
  "HR Development": "HR - Vicky | hr-development"
}
```

The original Live Modular B-2 is a **separate running instance**. Leave it alone when operating the Multi-Target bridge.

## Reload the Multi-Target bridge
In the **middle PowerShell window running B-2 Multi-Target**, press **Ctrl+C** to stop **only that instance**, then paste:

```powershell
Clear-Host
$Folder = Join-Path $env:USERPROFILE 'Downloads\Riverview-B2-Administrator-Package'
$Script = Join-Path $Folder 'Riverview-GitHub-Bridge-B2-MultiTarget.ps1'
& $Script -DispatchIssue 61 -PollSeconds 60 -Arm
```

Expected startup:
```text
Configured targets: Administrator Coordinator, HR Development
Dispatch issue: https://github.com/ppow1/R3/issues/61
Mode: ARMED; interval: 60 seconds
```

`IGNORED` entries for unmatched or already-seen GitHub comments are normal. Do not mistake them for errors. The bridge polls every 60 seconds.

## Console display
Step 16 updated the **existing installed script in place**, backed it up as `Riverview-GitHub-Bridge-B2-MultiTarget.ps1.bak-20261111-console`, and passed PowerShell parse validation (0 errors). After reload, intended display:
- Green: matching planned step **FOUND**.
- Cyan/blue: **WAKE-UP SUBMITTED**.
- Red: error/fatal.
- Countdown: one `Next poll in mm:ss` line, overwritten in place once per second (no scrolling countdown entries). Clear it when the next poll begins.

**Important:** Step 16's success verifies source patching and parsing, not yet the live countdown appearance. Verify it visually after restarting; do not claim UI acceptance before observation.

## Evidence
- Administrator inventory: https://github.com/ppow1/R3/issues/61#issuecomment-6798932664
- Installed target configuration update: https://github.com/ppow1/R3/issues/61#issuecomment-6799522125
- HR Development receipt: https://github.com/ppow1/R3/issues/61#issuecomment-6799579983
- HR Development completed acceptance: https://github.com/ppow1/R3/issues/61#issuecomment-6799601971
- Step 16 display patch: https://github.com/ppow1/R3/issues/61#issuecomment-6799620817
- Plugin workstream: https://github.com/ppow1/R3/issues/62

## Operating discipline
Use existing target JSON for new destinations. Inspect installed file structure before edits; prefer a configuration-only change, reload only the affected instance, and verify real receipts. Never package a new download or build a new subsystem for behavior already supported by B-2.
