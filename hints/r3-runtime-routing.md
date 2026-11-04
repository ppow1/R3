<!--
R3 CONTROLLED DOCUMENT
File: hints/r3-runtime-routing.md
Component: R3-RUNTIME-ROUTING
File Revision: 1.0.0
Created: 2026-11-04 UTC (exact time not independently verified)
Created By: ChatGPT GPT-6
Purpose: Persistent R3 runtime, proxy, release and authentication discovery reference; prevent repeated rediscovery.
Execution Model: Read-only Windows PowerShell 7 -> SSH alias camrui -> Bash; deployment separately controlled.
Observability: Captured HTTP status, Nginx upstream, listeners, service/process, release target, revision and SSH exit.
Dependencies: AI_HINTS.md; hints/deployment.md; hints/q2-script-queue.md; scripts/Deploy-R3.ps1
Authority: Steward instruction to retain known website operational facts and distinguish observations from hypotheses.
Changed: 2026-11-04 UTC | R3-RUNTIME-ROUTING-001 | ChatGPT GPT-6 | Record verified historical topology and current 404 diagnostic; prescribe canonical checks.
Supersedes: None
Superseded By: None
Contracts: hints/file-provenance.md; hints/engineering-test-policy.md
Tests: Source inspection and Steward-provided read-only Camrui diagnostic; no production change.
History/Predecessor: New file; preserve subsequent versions in Git history.
-->
# R3 website: runtime topology, routing and authentication discovery

**Read this before diagnosing or deploying R3. Do not repeatedly ask the Steward to rediscover these basics.** The R3 website has multiple generations of deployment and may have multiple independently routed applications. Never infer that `r3.service` is the live website service, that `/home/admin1/.local/share/r3/current` is a valid symlink, or that an arbitrary Nginx upstream is R3.

## Known hosts, transport and source

- Windows development host: `desktop-ja3rpnq` (PowerShell 7); SSH alias `camrui` targets Camrui host `admin1-Default-string`, account `admin1`. Camrui was previously observed at `192.168.1.155`; verify current address before using it.
- Source: `ppow1/R3`. Active engineering branch at documentation time: `engineering/institution-runtime-v1-20261101`; default `main` is not automatically the active release. Historical R2: `ppow1/Riverview-`, read-only.
- Website public hostname: `riverview.ionoge.com`; intended R3 prefix `/r3/`. **A public URL is not proof that the local Camrui Nginx instance owns it.** Inspect Host/SNI, DNS target and the effective Nginx `server_name` and `location` blocks before attributing a 404.
- R3 source script `scripts/Deploy-R3.ps1` targets **legacy** `/home/admin1/R3`, uvicorn `r3_app:app` port **8303**, Git `main`, and local `http://192.168.1.155:8303/`. This script is **not qualified** for the newer immutable-release deployment; never run it blindly against current production.
- Another previously observed release pattern is `/home/admin1/.local/share/r3/releases/grace-<commit>`. The exact service name, symlink target and public routing must be discovered; do not assert them from this path alone.
- Existing Nginx upstream ports observed in Camrui config: **2586, 8303, 8767**. Which upstream handles the current public `/r3/` must be determined by reading the surrounding location/server blocks; a bare grep of `proxy_pass` does not establish ownership.

## Verified read-only diagnostic: 2026-11-03 20:25 EST

Steward ran Windows PowerShell -> `ssh.exe ... camrui bash -s`; remote host `admin1-Default-string`, SSH exit **0**. From **Camrui**, `curl -k` against `https://riverview.ionoge.com` returned **404** for `/r3/`, `/r3/api/v1/health`, `/r3/api/v1/institution/runtime`, `/r3/api/v1/chat/session`, `/api/v1/steward/delegation-grant-requests`, and `/api/v1/steward/delegated-grants`. `systemctl is-active r3.service` returned **inactive**. `readlink -f /home/admin1/.local/share/r3/current` printed the same path, **not a resolved release directory**. Nginx `proxy_pass` lines included ports 2586, 8303 and 8767.

**Interpretation:** These results do **not** prove R3 is down, that any specific upstream is R3, or that auth is working. The requests could hit the wrong virtual host, proxy or location; `r3.service` may not be the deployed unit; and a self-printing `readlink -f` is not evidence of a valid `current` symlink. The test used `-k`, so TLS trust/certificate correctness was not verified. Preserve these distinctions in status reports.

## Mandatory discovery before editing authentication or deploying

1. Read this file, `AI_HINTS.md`, `hints/deployment.md`, `hints/q2-script-queue.md`, `hints/comms-failure-recovery.md`, and the current deployment script. Identify the current R3 release/commit and service owner; do not assume legacy `main`.
2. Inspect `sudo -n nginx -T` **with server blocks, listen/server_name, locations and proxy_pass context**, plus `ss -ltnp`, `systemctl list-units --all --type=service`, `ps`, `ls -ld` and `readlink`. Distinguish Camrui-local Nginx from public edge/proxy routing.
3. Probe loopback ports 2586, 8303, 8767 with short timeouts and paths `/`, `/r3/`, `/api/v1/health`. Separately probe public host, and if necessary force the local Nginx virtual host with `curl --resolve riverview.ionoge.com:443:127.0.0.1` (only when local Nginx listens on 443). Record HTTP code **and** effective endpoint, not just code.
4. Determine the actual authentication/session backend and site-wide server-side authorization enforcement. R3 Chat-only login is **not** acceptable protection for Infrastructure, Engineering, artwork or grants. Do not add a second login or expose delegation endpoints before the shared session and Steward authorization are proven.
5. For deployment, follow the **actual current release mechanism**, immutable-release/rollback procedure and Q2 watcher as appropriate. Do not run `scripts/Deploy-R3.ps1` merely because its name sounds correct; its source targets legacy 8303/main.
6. Run permanent regression tests and verify unauthenticated 401/redirect, authenticated Steward access, unauthorized 403, CSRF rejection, and live browser behavior. Never interpret 404 as proof of access control.

## Execution and clipboard procedure

Try authorized Riverview Comms 1.1 first. If blocked/stalled, provide the Steward **one complete, copy-paste PowerShell 7 block** beginning `Clear-Host`, using the `camrui` SSH alias. Normalize here-string CRLF to LF before piping to `ssh.exe ... camrui bash -s`. Capture stdout **and stderr**, `$LASTEXITCODE`, and the full results to clipboard with `Set-Clipboard`; save a timestamped local log when useful. A gateway submission, SSH exit 0, HTTP 200, and a successfully deployed release are distinct evidence. For automated work use Q2 numeric `.ps1` queue and read its matching `Queue/Results` output; never move Q2 jobs manually. Do not use Camrui Codex.

## Remaining unknowns

Effective public DNS/edge routing, exact live R3 service and upstream, active release commit, shared website session implementation, current authentication boundary, and current grant API deployment are **not yet verified**. Update this document with observed evidence when these are established; do not replace unknowns with assumptions.
