<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3_FIRST_WEBSITE_DEPLOYMENT.md
Component: R3-DEPLOYMENT-RUNBOOK
File Revision: 1.0.0
Created: 2026-10-31 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Preserve observed first Camrui R3 website deployment and derive deployment-script requirements
Execution Model: Human-executed PowerShell 7 -> SSH alias camrui -> Ubuntu Bash; future automation proposed
Observability: Git SHA, SSH exit, PID/port, HTTP checks, image bytes, browser acceptance
Dependencies: ppow1/R3; Camrui; Python 3.12; FastAPI; Uvicorn; approved visual ZIP
Authority: Steward direction to capture first deployment before further deployment
Changed: 2026-10-31 UTC | R3-DEPLOY-001 | ChatGPT GPT-6 | Initial evidence-based deployment runbook
Supersedes: None
Superseded By: None
Contracts: docs/IMPLEMENTATION_HANDOFF.md; hints/file-provenance.md; hints/comms-failure-recovery.md
Tests: Documentation only; proposed deploy script not implemented or tested
History/Predecessor: None
-->
# R3 first website deployment — observed runbook and deploy-script investigation

**Scope:** The FIRST website bootstrap on Camrui, through the successful HTTP 200 background response and the first two browser visual reviews. This is an evidence record and proposed automation specification, **not** an assertion that the website is accepted or that a deployment script exists.

## 1. Target and boundaries

| Item | Observed / required |
|---|---|
| Git repository | `ppow1/R3`, default branch `main` |
| Initial host | Camrui Ubuntu, `192.168.1.155`, user `admin1` |
| Remote access | Windows PowerShell 7 through configured `ssh camrui` alias; alias resolves with existing identity `C:/Users/wille/.ssh/octominer1_nopass` |
| R3 checkout | `/home/admin1/R3` |
| Python runtime | Python 3.12.3; dedicated `/home/admin1/R3/.venv` |
| Application | `r3_app:app`, Uvicorn listening on `0.0.0.0:8303` |
| Log used | `/tmp/r3-website.log` (temporary; not a durable logging design) |
| Artwork source | `assets/visual-concepts/Riverview3_Visual_Concept_Library.zip`, approximately 52 MiB in checkout |
| Protected preexisting installation | `/home/admin1/.local/share/riverview/engineering/Riverview` — do not overwrite or restart |
| Network/security | No authentication implemented. LAN-only prototype intended; firewall enforcement and external reachability **not verified** |

## 2. First deployment chronology — evidence versus uncertainty

1. **Remote command transport:** Riverview Comms 1.1 Camrui caller/executor grants were reported active, but two standard command submissions returned “The tool failed internally.” No remote execution confirmed. Initial fallback was wrongly written in Bash for a Windows PowerShell user. A subsequent SSH command used `admin1@192.168.1.155`, bypassing the working SSH alias and prompting for a password. See `docs/comms-incidents/R3-COMMS-002.md`.
2. **Working SSH path established:** `ssh -o BatchMode=yes -o ConnectTimeout=8 camrui hostname` succeeded. The alias specifies `admin1`, host `192.168.1.155`, `IdentitiesOnly yes`, and the existing private key. Subsequent remote commands used the alias and Windows PowerShell output capture.
3. **Repository bootstrap:** `ppow1/R3` cloned into `/home/admin1/R3`, separate from existing Riverview. Verified `origin https://github.com/ppow1/R3.git`, commit `e063f7d`, `r3_app.py`, `web/index.html`, and ZIP archive present. Clone command returned SSH exit 0.
4. **Dependencies installed:** `python3 -m venv .venv`; `.venv/bin/python -m pip install fastapi uvicorn`. Verified FastAPI `0.162.0`, Uvicorn `0.54.0`, and SSH exit 0. Versions were unpinned, so reproducibility is **not** guaranteed.
5. **Initial start:** `nohup .venv/bin/uvicorn r3_app:app --host 0.0.0.0 --port 8303 > /tmp/r3-website.log 2>&1 < /dev/null &`. Uvicorn PID `1030583`; health returned HTTP 200, but background returned HTTP 503 (53-byte JSON). Health JSON reported `artwork_directory_present:false`; that field describes the unextracted `assets/artwork/` directory, not the ZIP endpoint's validity.
6. **Artwork diagnosis:** The ZIP passed `zipfile.ZipFile(...).testzip()`. Actual entry was `Riverview3_Visual_Concept_Library/backgrounds/R3_modern_dashboard_as_is.png`, not the initial hardcoded `backgrounds/R3_modern_dashboard_as_is.png`. Fix committed `66655e4`.
7. **Failed restart:** A `git pull --ff-only origin main` advanced `e063f7d..66655e4`. The command then ran `pkill -f '[u]vicorn r3_app:app'`, after which SSH returned -1 before restart or checks. Likely the broad full-command-line match killed the SSH shell itself; this causal mechanism is plausible but not independently proven. Later read-only check showed no R3 process, no listener, HTTP 000, and a clean Uvicorn shutdown in logs. See `docs/comms-incidents/R3-COMMS-003.md`.
8. **Port race / concurrent startup:** A subsequent start command reported port 8303 occupied. Read-only inspection identified Uvicorn PID `1032826`, PPID 1, executable `/home/admin1/R3/.venv/bin/python`, serving `r3_app:app`. Health HTTP 200; background HTTP 200, `image/png`, 3,053,883 bytes; SSH exit 0. **Who/what launched PID 1032826 and its exact start time were not established.** Port occupancy by a verified healthy R3 instance must be treated as success/no-op, not an automatic failure.
9. **Browser review 1:** Screenshot showed estate image with navigation/district/status overlays already baked into raster. Translucent Engineering Foundry window rendered and opacity control worked. User reported drag and Center Window button not working, minimize producing long translucent bar. This is a browser-observed acceptance failure even though server endpoints passed.
10. **Source changes after review:** Backend changed to `Riverview3_Visual_Concept_Library/backgrounds/R3_modern_estate_clean_concept.png` in commit `c587bdb`. Frontend pointer/centering/minimize revisions committed `f4ff84b`. A deployment command was issued, but its execution output **was not supplied in this record**. Subsequent screenshot still showed baked-in labels and a long translucent minimized bar with vertical scrollbar. Therefore deployment version, cache state, clean asset content, and corrected interaction behavior **remain unverified**. Do not mark these changes accepted or deployed.

## 3. Script design contract derived from the investigation

### A. Preflight and transport
- Prefer authorized Riverview Comms command execution; if it fails, record exact tool error and use the proven `ssh camrui` alias. Never silently replace alias with raw user@IP or alter keys.
- PowerShell manual wrapper starts `Clear-Host`, captures stdout/stderr in `$result`, prints it and `$LASTEXITCODE`, and copies both to clipboard. Remote POSIX script should start `clear` when used interactively; for machine-readable remote output, avoid clearing diagnostics.
- Confirm expected host/user, target path, Git remote, current branch, working-tree cleanliness, and SSH noninteractive reachability. Stop on mismatch. Do not touch the preexisting Riverview checkout.
- Validate Python/venv, requirements lockfile (to be created), disk space, ZIP existence/integrity, required ZIP member names, frontend files, and port ownership. Reject missing or wrong artwork **before** stopping the working server.
- Define explicit trusted-LAN binding/firewall policy; do not assume `0.0.0.0` is private by itself.

### B. Update and restart
- Record before/after SHA, source status, package versions, deployment operator/method, timestamp, host, and port. `git fetch` then validate target SHA; use `git pull --ff-only` only when checkout is clean and expected branch is correct.
- Never use broad `pkill -f` or kill a PID based on a name alone. Resolve the exact listener PID, verify executable, command line, user, working directory, and ownership; reject foreign owners. Avoid killing the SSH command shell.
- If the port is already occupied by the **expected** R3 server at the **target SHA** and passes all checks, return “already deployed” without restart. If the server is the old version, use controlled stop/start. If foreign process, stop without killing it.
- A persistent supervisor (e.g. a scoped systemd unit) should replace unmanaged `nohup`; **not yet implemented**. Avoid concurrent deploys with a lock and bounded wait.
- Stage/prevalidate the candidate before replacing the running version; prefer an atomic release/symlink strategy and explicit rollback to last verified release. These are future design requirements, not existing capabilities.

### C. Verification and acceptance
- Bounded readiness checks: process alive, expected PID and port, `/api/v1/health` HTTP 200, root page HTTP 200, background HTTP 200 `image/png` and nonzero size; compare exact expected artwork bytes/hash to archive member, not merely image MIME.
- Version/manifest endpoint must expose deployed Git SHA and asset revision so browser caching and wrong-version deployments can be distinguished. **Not yet implemented.** Cache-busting or proper ETag headers should accompany asset changes.
- Test UI with actual browser evidence: clean unlabeled estate image, district overlays as independent elements, window drag, resize, true center, compact minimize/restore, no unwanted scrollbar, opacity slider, responsive layout. Do not infer UI acceptance from curl.
- Log failed checks and rollback outcome. Distinguish `DEPLOYED`, `HEALTHY`, and `VISUALLY ACCEPTED`; a healthy server is not a visually accepted website.
- Preserve exact evidence (Git SHA, command exit, process identity, HTTP codes, asset size/hash, screenshot/test results) in a durable deployment report. Redact credentials and sensitive paths in public logs.

### D. Failure behavior
- Fail closed on mismatched target, dirty tree, invalid ZIP, unexpected port owner, missing prerequisites, or unknown runtime. Never stop a healthy instance until candidate preflight passes.
- If SSH disconnects after a stop request, reconnect **read-only first** to determine actual state. Do not blindly restart or kill.
- If port becomes occupied between check and start, inspect owner; healthy expected R3 is not an error, unknown owner is a stop condition.
- Maintain incidents for both connector failures and assistant-authored manual command failures. Document evidence separately from inferred root cause.

## 4. Proposed script phases (not implemented)

`discover -> preflight -> acquire_lock -> fetch_and_validate -> stage_candidate -> inspect_running -> stop_if_required -> activate -> readiness_and_asset_tests -> browser_acceptance_gate -> record_result -> release_lock`.

For a production-safe future implementation, staging and reversible activation must be designed before automating stop/start; a blind single-checkout `git pull` is not atomic.

## 5. Open questions and next investigation

- What launched PID `1032826` after the interrupted restart? Is there an existing supervisor or another actor?
- Is the clean estate PNG truly free of baked-in district labels? Verify pixels/asset contents, not just filename.
- Did commit `f4ff84b` reach Camrui? What Git SHA is served by the process, and was the browser cache refreshed?
- Why does minimized panel show a vertical scrollbar? Confirm CSS computed styles and overflow behavior in the actual browser.
- What are the intended authentication, firewall, deploy operator identity, and rollback policies?
- Which CI/browser-test runner and durable deployment journal should be used?

**Next gate:** Do not deploy again until the deployment runbook has been reviewed and a minimal repeatable deployment script design is agreed. This document records findings; it does not claim the script or its tests exist.
