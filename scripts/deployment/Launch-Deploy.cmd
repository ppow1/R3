@echo off
rem R3 CONTROLLED SOURCE
rem File: scripts/deployment/Launch-Deploy.cmd
rem Component: R3-MANIFEST-DEPLOY
rem File Revision: 1.0.0
rem Created: 2026-11-05 UTC (exact time unverified)
rem Created By: ChatGPT GPT-6
rem Purpose: Double-clickable plan-only manifest validator
rem Execution Model: cmd.exe -> PowerShell 7
rem Observability: Console and clipboard
rem Dependencies: Deploy-R3.ps1, pwsh.exe, website.example.json
rem Authority: Steward R3 deployment directive
rem Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-001 | Initial launcher
rem Supersedes: None
rem Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
rem Tests: Not executed on Windows
rem History/Predecessor: New repository path
cd /d "%~dp0"
pwsh.exe -NoProfile -File "%~dp0Deploy-R3.ps1" -Manifest "%~dp0manifests\website.example.json"
echo.
pause
