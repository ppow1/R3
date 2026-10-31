<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3_FIRST_WEBSITE_DEPLOYMENT.md
Component: R3-DEPLOYMENT-RUNBOOK
File Revision: 1.0.3
Created: 2026-10-31 UTC (exact time unverified)
Created By: ChatGPT GPT-6
Purpose: Preserve observed first Camrui R3 website deployment and derive deployment-script requirements
Execution Model: Human-executed PowerShell 7 -> SSH alias camrui -> Ubuntu Bash; future automation proposed
Observability: Git SHA, SSH exit, PID/port, HTTP checks, image bytes, browser acceptance
Dependencies: ppow1/R3; Camrui; Python 3.12; FastAPI; Uvicorn; approved visual ZIP
Authority: Steward direction to capture first deployment before further deployment
Changed: 2026-10-31 UTC | R3-DEPLOY-006 | ChatGPT GPT-6 | Record script-file contamination and link Comms incident punch list
Supersedes: None
Superseded By: None
Contracts: docs/IMPLEMENTATION_HANDOFF.md; hints/file-provenance.md; hints/comms-failure-recovery.md
Tests: Documentation only; proposed deploy script not implemented or tested
History/Predecessor: Git blob c0a6801190a60a7bde29bef6d884ffb67c4cf384
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

## 6. Command-by-command deployment reconstruction

**Provenance:** Commands below are reconstructed from the actual assistant-issued PowerShell commands visible in the deployment conversation. They are historical evidence, **not a recommended deployment script**. Where the earlier exact command is not present in the retained conversation context, it is explicitly marked **not recoverable verbatim**; no replacement is misrepresented as historical. User-returned outputs are transcribed as excerpts rather than full pip progress logs. Do not paste the unsafe commands into production.

### 6.1 SSH alias verification and initial clone — partial record

The working transport test was:

~~~powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 camrui hostname
~~~

**Observed:** Successful SSH to Camrui. Effective alias resolved to user \`admin1\`, host \`192.168.1.155\`, \`IdentitiesOnly yes\`, identity \`C:/Users/wille/.ssh/octominer1_nopass\`. Earlier raw \`ssh admin1@192.168.1.155\` requested a password; it must **not** be treated as equivalent to the alias.

**Clone:** The exact first-clone PowerShell wrapper and remote Bash body are **not recoverable verbatim from this conversation excerpt**. The observed result was a new checkout at \`/home/admin1/R3\`, origin \`https://github.com/ppow1/R3.git\`, SHA \`e063f7d\`, \`r3_app.py\`, \`web/index.html\`, and approved ZIP present; SSH exit 0. The script must later codify idempotent clone-or-update behavior without overwriting the other Riverview checkout.

### 6.2 Virtual environment and dependencies — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
set -e
cd /home/admin1/R3

python3 -m venv .venv
.venv/bin/python -m pip install fastapi uvicorn

printf "\n=== INSTALLED VERSIONS ===\n"
.venv/bin/python -c 'import fastapi, uvicorn; print("FastAPI:", fastapi.__version__); print("Uvicorn:", uvicorn.__version__)'

printf "\n=== VIRTUAL ENVIRONMENT ===\n"
ls -l .venv/bin/python
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

$clipboard = "$result`nSSH exit code: $exitCode"
Set-Clipboard -Value $clipboard
~~~

**Observed:** \`Successfully installed\`; FastAPI \`0.162.0\`, Uvicorn \`0.54.0\`, \`.venv/bin/python -> python3\`, SSH exit 0. **Design correction:** pin and audit dependency versions; avoid unbounded install on every deploy.

### 6.3 First start and verification — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
set -e
cd /home/admin1/R3

if ss -ltn '( sport = :8303 )' | grep -q ':8303'; then
    echo "STOP: Port 8303 is already in use."
    exit 1
fi

nohup .venv/bin/uvicorn r3_app:app \
    --host 0.0.0.0 \
    --port 8303 \
    > /tmp/r3-website.log 2>&1 < /dev/null &

sleep 3

printf "=== WEBSITE PROCESS ===\n"
pgrep -af '[u]vicorn r3_app:app' || true

printf "\n=== HEALTH CHECK ===\n"
curl --max-time 5 -fsS http://127.0.0.1:8303/api/v1/health

printf "\n\n=== BACKGROUND IMAGE HTTP STATUS ===\n"
curl --max-time 15 -s -o /dev/null -w '%{http_code} %{content_type} %{size_download} bytes\n' \
    http://127.0.0.1:8303/api/v1/visual/background

printf "\n=== WEBSITE LOG ===\n"
tail -n 12 /tmp/r3-website.log
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

$clipboard = "$result`nSSH exit code: $exitCode"
Set-Clipboard -Value $clipboard
~~~

**Observed:** PID \`1030583\`, health \`{"service":"r3","status":"running","repository_present":true,"artwork_directory_present":false}\`, image \`503 application/json 53 bytes\`, SSH exit 0. **Design correction:** script must fail if a required endpoint returns non-2xx; SSH exit 0 was a false overall success.

### 6.4 Inspect approved ZIP — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
cd /home/admin1/R3
.venv/bin/python -c 'import zipfile; p="assets/visual-concepts/Riverview3_Visual_Concept_Library.zip"; z=zipfile.ZipFile(p); print("ZIP VALID:", z.testzip() is None); print("MATCHING BACKGROUNDS:"); [print(n) for n in z.namelist() if "dashboard" in n.lower() or "background" in n.lower()]'
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Observed:** \`ZIP VALID: True\`; entries include \`Riverview3_Visual_Concept_Library/backgrounds/R3_modern_dashboard_as_is.png\` and \`Riverview3_Visual_Concept_Library/backgrounds/R3_modern_estate_clean_concept.png\`; SSH exit 0. Source ZIP-path correction commit: \`66655e4\`.

### 6.5 Failed update/restart — exact issued command; UNSAFE, DO NOT REUSE

~~~powershell
Clear-Host

$remoteCommand = @'
set -e
cd /home/admin1/R3

printf "=== UPDATE SOURCE ===\n"
git pull --ff-only origin main

printf "\n=== RESTART R3 ===\n"
pkill -f '[u]vicorn r3_app:app' || true
sleep 2

nohup .venv/bin/uvicorn r3_app:app \
    --host 0.0.0.0 \
    --port 8303 \
    > /tmp/r3-website.log 2>&1 < /dev/null &

sleep 3

printf "\n=== HEALTH CHECK ===\n"
curl --max-time 5 -fsS http://127.0.0.1:8303/api/v1/health

printf "\n\n=== BACKGROUND IMAGE ===\n"
curl --max-time 20 -s -o /dev/null \
    -w 'HTTP %{http_code} | %{content_type} | %{size_download} bytes\n' \
    http://127.0.0.1:8303/api/v1/visual/background

printf "\n=== DEPLOYED COMMIT ===\n"
git rev-parse --short HEAD
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Observed:** Fast-forward \`e063f7d..66655e4\`, then \`=== RESTART R3 ===\`, SSH exit **-1**. No later steps verified. The pattern can match its own SSH shell. **Never use broad \`pkill -f\` as an automated restart.**

### 6.6 Post-failure read-only check — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
printf "=== R3 PROCESS ===\n"
ps -eo pid,comm,args | grep '[u]vicorn' || true

printf "\n=== PORT 8303 ===\n"
ss -ltn '( sport = :8303 )'

printf "\n=== HEALTH ===\n"
curl --max-time 5 -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8303/api/v1/health

printf "\n=== BACKGROUND ===\n"
curl --max-time 15 -s -o /dev/null -w 'HTTP %{http_code} | %{content_type} | %{size_download} bytes\n' http://127.0.0.1:8303/api/v1/visual/background

printf "\n=== LOG ===\n"
tail -n 10 /tmp/r3-website.log
'@

$result = & ssh -o BatchMode=yes -o ConnectTimeout=5 camrui $remoteCommand 2>&1 |
    Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Observed:** No Uvicorn process or listener, health/background HTTP 000, clean shutdown of PID \`1030583\`, SSH exit 0. **Design correction:** transport success and service failure must have different statuses.

### 6.7 Start attempt after failure — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
set -e
cd /home/admin1/R3

printf "=== START R3 ===\n"

if ss -ltn '( sport = :8303 )' | grep -q ':8303'; then
    echo "STOP: Port 8303 is occupied."
    exit 1
fi

nohup .venv/bin/uvicorn r3_app:app \
    --host 0.0.0.0 \
    --port 8303 \
    > /tmp/r3-website.log 2>&1 < /dev/null &

sleep 3

printf "\n=== HEALTH ===\n"
curl --max-time 5 -fsS http://127.0.0.1:8303/api/v1/health

printf "\n\n=== APPROVED BACKGROUND ===\n"
curl --max-time 20 -s -o /dev/null \
    -w 'HTTP %{http_code} | %{content_type} | %{size_download} bytes\n' \
    http://127.0.0.1:8303/api/v1/visual/background

printf "\n=== DEPLOYED COMMIT ===\n"
git rev-parse --short HEAD

printf "\n=== LOG ===\n"
tail -n 8 /tmp/r3-website.log
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Observed:** \`STOP: Port 8303 is occupied.\`, SSH exit 1. **Design correction:** race-aware, idempotent inspect-and-adopt healthy R3 rather than assuming all occupancy is failure.

### 6.8 Port owner identification — exact issued command

~~~powershell
Clear-Host

$remoteCommand = @'
printf "=== PORT 8303 OWNER ===\n"
ss -ltnp '( sport = :8303 )'

printf "\n=== LISTENING PROCESSES ===\n"
sudo -n fuser -v 8303/tcp 2>&1 || fuser -v 8303/tcp 2>&1 || true

printf "\n=== R3 PROCESSES ===\n"
ps -eo pid,ppid,comm,args | grep -E '[u]vicorn|[r]3_app' || true

printf "\n=== HEALTH CHECK ===\n"
curl --max-time 5 -s -o /dev/null \
    -w 'HTTP %{http_code}\n' \
    http://127.0.0.1:8303/api/v1/health

printf "\n=== BACKGROUND CHECK ===\n"
curl --max-time 15 -s -o /dev/null \
    -w 'HTTP %{http_code} | %{content_type} | %{size_download} bytes\n' \
    http://127.0.0.1:8303/api/v1/visual/background
'@

$result = & ssh `
    -o BatchMode=yes `
    -o ConnectTimeout=5 `
    camrui `
    $remoteCommand 2>&1 | Out-String

$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Observed:** \`0.0.0.0:8303\` owned by \`admin1\` Uvicorn PID \`1032826\`, PPID 1, correct executable and module; health 200, background 200 \`image/png\` 3,053,883 bytes; SSH exit 0. Source of this running process remains unknown.

### 6.9 Second visual correction deploy — exact command issued; outcome UNVERIFIED

The following was issued after commits \`c587bdb\` and \`f4ff84b\`. The conversation contains **no returned execution output** for this command. It must not be classified as successful.

~~~powershell
Clear-Host

$remoteCommand = @'
set -e
cd /home/admin1/R3

printf "=== UPDATE R3 ===\n"
git pull --ff-only origin main

printf "\n=== IDENTIFY R3 SERVER ===\n"
pid=$(ss -ltnp '( sport = :8303 )' | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)

if [ -n "$pid" ]; then
    args=$(ps -p "$pid" -o args=)
    case "$args" in
        *"/home/admin1/R3/.venv/bin/uvicorn r3_app:app"*)
            echo "Stopping verified R3 PID $pid"
            kill "$pid"
            for i in 1 2 3 4 5; do
                if ! kill -0 "$pid" 2>/dev/null; then break; fi
                sleep 1
            done
            ;;
        *)
            echo "STOP: Port belongs to an unrecognized process: $args"
            exit 1
            ;;
    esac
fi

if ss -ltn '( sport = :8303 )' | grep -q ':8303'; then
    echo "STOP: Port 8303 remains occupied."
    exit 1
fi

printf "\n=== START UPDATED R3 ===\n"
nohup .venv/bin/uvicorn r3_app:app --host 0.0.0.0 --port 8303 \
    > /tmp/r3-website.log 2>&1 < /dev/null &

sleep 3

printf "\n=== HEALTH ===\n"
curl --max-time 5 -fsS http://127.0.0.1:8303/api/v1/health

printf "\n\n=== CLEAN BACKGROUND ===\n"
curl --max-time 20 -s -o /dev/null \
    -w 'HTTP %{http_code} | %{content_type} | %{size_download} bytes\n' \
    http://127.0.0.1:8303/api/v1/visual/background

printf "\n=== DEPLOYED COMMIT ===\n"
git rev-parse --short HEAD
'@

$result = & ssh -o BatchMode=yes -o ConnectTimeout=5 camrui $remoteCommand 2>&1 | Out-String
$exitCode = $LASTEXITCODE

Clear-Host
$result
"SSH exit code: $exitCode"

Set-Clipboard -Value "$result`nSSH exit code: $exitCode"
~~~

**Known weaknesses:** \`git pull\` modifies the active checkout before a validated staged release; \`kill -0\` can stay true for a zombie process; PID inspection is not a supervisor ownership contract; HTTP checks lack strict failure handling; visual acceptance not automated.

### 6.10 Future deployment-script acceptance checklist

- [ ] Preserve exact invocation, stdout/stderr, exit status and Git SHA per step.
- [ ] No credentials, destructive broad process matching, or foreign service restarts.
- [ ] Dependency versions pinned; ZIP member name and content validated pre-restart.
- [ ] Lock deployment, stage candidate, verify expected process owner, activate with bounded health checks.
- [ ] Handle healthy preexisting R3 on port 8303 as idempotent success when revision matches.
- [ ] Fail deployment if **any** required HTTP status, content type, content hash, or version check fails.
- [ ] Expose revision and asset manifest for browser cache diagnosis.
- [ ] Keep visual acceptance separate from server readiness.
- [ ] Preserve rollback and a durable failure report.

**Important:** This appendix reconstructs the available issued commands. It does not assert that all were executed or successful. It does not include unknown early bootstrap commands as invented exact transcripts.

## 7. First scripted-deployment retrieval failure (2026-10-31)

The assistant issued a PowerShell 7 wrapper that attempted to download `scripts/Deploy-R3.ps1` from `https://raw.githubusercontent.com/ppow1/R3/c081fbbb5aba3ae3d7f7798ab412d7664ad7dd87/scripts/Deploy-R3.ps1` with `Invoke-WebRequest -OutFile`. The user observed **404 Not Found**. No script execution or website deployment is evidenced. GitHub connector `fetch_file` successfully fetched the file at the exact commit and path; thus the file exists, while unauthenticated raw URL access failed (private repository access is a plausible explanation, not independently proven). Corrective design: use the existing authenticated Camrui Git checkout, or an authenticated artifact transport; do not rely on unauthenticated raw GitHub URLs. Verify fetched SHA and script presence before execution. Capture and propagate download errors and do not run a stale temp copy.

## 8. Script retrieval contamination and Comms punch list (2026-10-31)

- **Comms:** Read-only Camrui preflight via `comms5_command_task_submit` returned `The tool failed internally.` The executor grant was verified active; execution was **not** verified. Open incident and remediation punch list: [R3-COMMS-004](../comms-incidents/R3-COMMS-004.md).
- **Manual fallback defect:** A PowerShell wrapper used `ssh ... 'git fetch ... && git show ...'` with `2>&1 | Out-String`, then wrote the combined output to `Deploy-R3.ps1`. The user showed the resulting file started `From https://github.com/ppow1/R3` followed by Git fetch progress and then the actual script. Executing it caused `ParserError ... :1`, `The 'from' keyword is not supported in this version of the language.` **The deployment script never executed; no website change was evidenced.** The prior `SSH exit code: 0` proved remote command success, **not script integrity**.
- **Punch list:** Separate stderr and stdout; do not mix Git fetch progress into file content. Prefer `git show COMMIT:path` alone on stdout after a distinct fetch, or fetch authenticated source through GitHub tooling; validate file begins with expected provenance header, parse with PowerShell's parser, verify Git blob or SHA-256, and only then execute. Never run a file saved from merged diagnostics. Maintain Comms gateway repair as a separate open item.
