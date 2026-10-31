<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-003.md
Component: COMMS-INCIDENT
File Revision: 1.0.0
Created: 2026-10-31 UTC (time unverified)
Created By: ChatGPT GPT-6
Purpose: Record failed R3 restart over SSH and unsafe broad process matching
Execution Model: N/A
Observability: SSH output and subsequent diagnostic
Dependencies: R3 Camrui website deployment
Authority: Steward failure-capture directive
Changed: 2026-10-31 UTC | R3-COMMS-003 | ChatGPT GPT-6 | Initial incident
Supersedes: None
Contracts: hints/comms-failure-recovery.md; hints/file-provenance.md
Tests: Pending
History/Predecessor: None
-->
# R3-COMMS-003 — R3 restart command interrupted SSH session

**Objective:** Deploy approved-background ZIP path fix and restart R3 prototype on Camrui.
**Evidence:** PowerShell-initiated SSH output confirms `git pull --ff-only origin main` fast-forwarded `e063f7d..66655e4`, changing `r3_app.py`. Output then stopped immediately after `=== RESTART R3 ===`; reported SSH exit code `-1`. No restart, health check, or image HTTP result was obtained.
**Likely cause, not yet proven:** Remote script used `pkill -f '[u]vicorn r3_app:app'`. Because the SSH remote shell command line itself contains that pattern, `pkill -f` can match the executing shell and terminate the session.
**Correction:** Do not use broad `pkill -f` against a string embedded in the invoking shell. Inspect listener and process identity first; stop only the verified PID, restart with bounded readiness checks, and verify both health and image endpoints.
**Classification:** Assistant-authored command safety/reliability failure, not verified Riverview Comms gateway failure.
**Status:** OPEN; R3 deployment after pull unverified.
