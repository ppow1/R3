<!--
R3 CONTROLLED DOCUMENT
File: docs/operations/SHELL_WRAPPERS.md
Component: R3-SSH-WRAPPER
File Revision: 1.0.0
Created: 2026-11-01 UTC (exact time not verified)
Created By: ChatGPT GPT-6
Purpose: Define canonical cross-host shell execution for R3 engineering.
Execution Model: Local wrapper executes local Bash script remotely over SSH.
Observability: Captured output and exit code; optional clipboard.
Dependencies: Configured SSH aliases on initiating host.
Authority: Steward instruction; R2 is read-only reference.
Changed: 2026-11-01 UTC | R3-SSH-001 | Initial R3-only runbook
Supersedes: None
Contracts: hints/deployment.md; scripts/operations/*
Tests: Host execution pending
History/Predecessor: New file
-->
# R3 canonical SSH wrappers

These are R3 source files. Never modify the frozen R2 repository to maintain R3 tooling.

From **Windows PowerShell**, run:

```powershell
Clear-Host
& .\scripts\operations\Invoke-RiverviewSsh.ps1 -Alias camrui -ScriptPath .\diagnostics.sh -CopyToClipboard
```

From **Linux Bash**, run:

```bash
clear
bash ./scripts/operations/invoke-riverview-ssh.sh TARGET_ALIAS ./diagnostics.sh --clipboard
```

The Bash wrapper requires an SSH alias configured on the **calling Linux host**; Windows aliases are not automatically inherited. Neither wrapper embeds credentials, IP addresses, or host keys. Both normalize CRLF to LF, preserve literal Bash dollar variables, report SSH exit codes, and support optional clipboard capture. A remote command's nonzero exit code is distinct from a gateway-level authorization denial.

**Verification:** Files committed to R3 engineering branch; functional host tests are not yet recorded. Do not report them as verified until exercised.
