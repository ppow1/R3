<!--
R3 CONTROLLED DOCUMENT
File: hints/deployment.md
Component: DEPLOYMENT
File Revision: 1.0.2 (provenance baseline; prior revisions untracked)
Created: Unknown (legacy; initial commit can establish earliest publication)
Created By: Unknown (legacy)
Purpose: R3 engineering reference and continuation guidance
Execution Model: GitHub source checkout -> immutable git archive release -> Python regression -> systemd user service
Observability: PowerShell clipboard transcript, service PID/working directory, systemd logs and health
Dependencies: /home/admin1/R3 authenticated Git checkout, SSH alias camrui, Python 3, systemd user service, R3 tests
Authority: R3 engineering guidance; approved charter prevails
Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Add provenance baseline
Changed: 2026-11-01 UTC | R3-Q2-DOC-001 | ChatGPT GPT-6 | Index Q2 watched-folder runbook
Changed: 2026-11-04 UTC | R3-GRACE-DEPLOY-001 | ChatGPT GPT-6 | Document verified Grace git-archive deployment, failure avoidance, and evidence
Supersedes: None
Contracts: hints/file-provenance.md
Tests: Observed 2026-11-04 deployment b6a02b3: 84 unittest tests passed, service active, PID and working directory matched; independent autonomy not established
History/Predecessor: Git blob a22856d0bedb1ef6cd34660efb0f06106571f46f (revision 1.0.1); older predecessor 7e4420fa5c55aadeb4f96283919de0706c478ff3
-->
# Deployment and operations

- [Current implementation handoff](../docs/IMPLEMENTATION_HANDOFF.md) — Camrui target, manual bootstrap and pending work.
- [R3 capability API](../r3_app.py) — current source; verify deployed behavior separately.
- [Q2 Windows script queue](q2-script-queue.md) — write PowerShell scripts into Q2, let the watcher dispatch them, and read Queue/Results.

Try Riverview Comms 1.1 before asking the Steward to run commands. Do not claim deployment or runtime behavior without observed evidence. Keep credentials out of browser-facing code.

## Grace institution runtime — proven deployment method (2026-11-04)

**This is the authoritative R3 Grace deployment procedure. Reuse it; do not invent a new deployment mechanism or ask the Steward to supply one already recorded here.** Grace runs on Camrui as the user service `r3-institution.service`. The **authenticated Git source checkout** is `/home/admin1/R3`; release directories under `/home/admin1/.local/share/r3/releases/` are **immutable source archives, not Git clones**. Never run `git fetch origin` inside a release directory. That exact error caused exit code 128 on 2026-11-04.

### Execution transport

Prefer authorized Riverview Comms 1.1 / Q2, following [Q2 runbook](q2-script-queue.md). If the gateway refuses execution (e.g. `bounded_request_or_state_invalid`), provide **one complete copy-paste Windows PowerShell block** using `Clear-Host`, a single-quoted Bash here-string, `ssh.exe camrui 'bash -s'`, `$LASTEXITCODE`, and `Set-Clipboard` for the entire transcript. **Do not require the Steward to download files, create two scripts, or run multiple separate blocks.** Do not run Codex on Camrui.

### Deploy sequence

1. Choose the **exact tested commit SHA** and its source branch. On Camrui verify `/home/admin1/R3/.git` exists, then `git -C /home/admin1/R3 fetch origin <branch>` and `git -C /home/admin1/R3 cat-file -e '<sha>^{commit}'`. Never fetch in a release.
2. Create `/home/admin1/.local/share/r3/releases/grace-<short-sha>` with `git -C /home/admin1/R3 archive <sha> | tar -x -C <new-release>`. Do not overwrite an existing populated release; verify it corresponds to the intended revision or fail clearly. Release is a source snapshot without `.git`.
3. From the release, run `python3 -m compileall -q runtime` and the **permanent** suite `python3 -m unittest discover -s tests -p 'test_*.py' -q`. Stop if either fails. No disposable tests or artificial production limits; see [engineering test policy](engineering-test-policy.md).
4. Record existing `systemctl --user cat r3-institution.service` and `systemctl --user show ... -p ExecStart -p WorkingDirectory -p ActiveState` under `/home/admin1/.local/state/r3-runtime/deployments/<UTC-stamp>/` before modification. Inspect existing overrides and service arguments before changing them. Preserve the service's established database, credentials, intake/conversation ports, and other configuration; **do not substitute guessed service arguments**.
5. The verified 2026-11-04 release used a user-service drop-in at `/home/admin1/.config/systemd/user/r3-institution.service.d/zzzzzzzz-r3-grace-controlled-deploy.conf`, setting `WorkingDirectory=<release>` and resetting `ExecStart=` before defining the existing `/usr/bin/python3 -m runtime.serve` command. At that time the command used `--db /home/admin1/.local/state/r3-runtime/institution.db`, `--health-file /home/admin1/.local/state/r3-runtime/health.json`, `--config-dir <release>/config`, `--assignment-intake-port 8769`, `--assignment-intake-token-file /home/admin1/.local/state/r3-runtime/credentials/assignment-intake.token`, `--conversation-port 8770`, `--conversation-token-file /home/admin1/.local/state/r3-runtime/credentials/conversation-api.token`. These are **historically verified settings, not a license to overwrite future changes blindly**.
6. `systemctl --user daemon-reload`, `systemctl --user restart r3-institution.service`, then require `systemctl --user is-active` = `active`; get `MainPID` and compare `readlink -f /proc/<PID>/cwd` to the exact release path. Capture `systemctl --user show`, health-file freshness and `journalctl --user -u r3-institution.service -n 50 --no-pager`. A health snapshot may lag and show an older PID: verify the live process independently.
7. Report separately: **commit deployed**, **tests passed**, **service active**, and **autonomous behavior verified or not verified**. Service health alone does not prove Grace's recovery or independent verification. After deployment, audit real durable events/tool calls for progress and repeated `r3.status` / `r3.host.uptime` loops. Do not inject synthetic work into the live scheduler.

### Verified deployment evidence and failure history

On 2026-11-04 at 01:50–01:51 UTC, commit `b6a02b30735c73edfb8da730195b41c8c1cf2400` from branch `engineering/grace-feedback-progress-20261103` was fetched through `/home/admin1/R3`, archived to `/home/admin1/.local/share/r3/releases/grace-b6a02b30735c`, compiled, and passed **84 permanent tests** (two nonfatal ResourceWarnings about unclosed test file handles). `r3-institution.service` restarted active, MainPID `390562`, and `/proc/390562/cwd` matched that release. Deployment reported `GRACE_DEPLOY_EXIT_CODE=0`. Health reported resident inference, tool execution, assignment intake, conversation API, and independent reviewer connected; the health JSON PID was stale, so it was **not** treated as proof of current process identity. **Autonomous recovery was not yet verified**.

The immediately preceding failed attempt reported `GRACE_DEPLOY_EXIT_CODE=128` because it attempted `git fetch origin` from `.../releases/grace-61eca560-deployed` (no Git origin). The successful correction was to use the source checkout and `git archive`. Do not repeat the failed approach.

### Operational priority

When the Steward requests a runbook correction, **update this tracked file, commit it, fetch it again from GitHub, and verify the exact new text before requesting any further terminal command**. Do not proceed to runtime diagnostics until that instruction is satisfied.
