<!--
R3 CONTROLLED HANDOFF
Component: R3A-AP3-WEBSITE
Purpose: Exact Website-owned Step 115 candidate, tests, and live evidence.
Dispatch: Issue #61 comment 6806630916
Security: Candidate only; no shared service restart, activation, grant, or secret handling.
-->

# Website Step 115 candidate — long-running conversation refresh

## Immutable candidate

- Repository: `ppow1/R3`
- Branch: `engineering/r3a-ap3-website-20261107`
- Website source commit: `8f6d7a3e89d14513abdc046c6cf709085060e01c`
- Exact package: [`r3a-website-8f6d7a3.tar.gz`](../../artifacts/releases/r3a-website-8f6d7a3.tar.gz)
- Package SHA-256: `733ab93e7823ae91bd4d47a3639e84d33a8d56eae370596db11dab4c502227e6`
- Package manifest: `r3a.website-release-package.v1`, source commit above, 425 file entries; package builder and exact digest verifier pass.

## Website correction

`web/steward-workspace-api.mjs` no longer pauses transcript polling after 80 checks. It continues polling the selected durable conversation at the existing 8-second maximum interval while any selected Steward turn remains pending, accepted, or processing. Changing conversations or revoking the Website session cancels the old view's polls. Completed and explicit terminal blocked/failed/rejected states stop the poll. A pending response is presented as queued. The Website continues to consume only the existing same-origin durable conversation API; it adds no resident decision logic, CME call, identity mapping, authorization path, database coupling, or fake streaming.

Permanent tests in `tests/test_steward_workspace_api.mjs` cover the previous ten-minute cutoff boundary, continued polling after 8,000 checks, capped backoff, rejection of negative counts, and pending-state presentation.

## Verification

- Source branch tests: `node --test tests/test_steward_workspace_api.mjs` — **20 passed**.
- Source Website API suite: `/home/admin1/R3/.venv/bin/python -m unittest tests.test_r3a_website -q` — **27 passed**.
- Exact extracted package tests: same commands against `website/` extracted from this archive — **20 Node + 27 Python passed**.
- Exact package runtime verifier: `RUNTIME_VERIFICATION_PASS=TRUE`, health HTTP 200, homepage HTTP 200, manifest source commit matches `8f6d7a3e89d14513abdc046c6cf709085060e01c`, candidate process stopped, `WEBSITE_ACTIVATION=NOT_RUN`. It used the existing isolated CPython 3.12 candidate environment from `/tmp/r3a-website-audit-step96/venv`; no active Website environment was changed.
- `git diff --check` passed before the source commit.

## Live observation and acceptance boundary

Read-only loopback inspection found `r3a-ap3-website.service` active (PID `1997803`, port `18311`). `GET /api/v1/website/identity` returned HTTP 200 but reports application build `3bbe100ed112eb8f24416243a1c798962ac5f083`, not this source package. The live static route `/web/steward-workspace-api.mjs` returned HTTP 200 and matched the current Website worktree bytes exactly (SHA-256 `9e9e91d80d37d06c165d4aad6e3052f4ea48a23fd98286dfd0b6804f5480d386`). This confirms only the served client asset, not loaded API code or authenticated operation.

The authenticated browser acceptance is **not claimed**. The existing Chrome instance lists `/steward` and `/login` tabs, but its local ChromeDriver attach timed out and DevTools WebSocket inspection could not issue a command (the browser rejected an unapproved origin; originless connection timed out). No cookie/session value was read, no authenticated request was issued, and no message was sent. Thus this turn did not verify roster selection, live response, or refresh persistence in a browser.

The known live Grace failure remains outside Website ownership: dispatch #61 Step 111 traced activity `89fa0d63-e52d-5ffa-bd33-ed1e3cd8ad42` to frozen CME commit `89eda1331b96fe40918e4aa67de09c5ae3f45227`, where message-derived directory replay changes the canonical request's deadline and CME rejects the retry before model inference. Dedicated recovery is tracked by [Issue #67](https://github.com/ppow1/R3/issues/67). Website source/package does not change CME, Ring0, grants, resident bindings, or Grace decisions. No actual Grace response or durable reply refresh is claimed.

## Release and next work

This exact source/package is a review candidate, not an activated release. Request an independent exact-source/package review and the Website-owned controlled release handoff. Per the Website deployment contract, only the service owner changes the active source/configuration or restarts the shared unit. After reviewed activation, use the existing authenticated Steward browser to verify current directory selection, send/receive through Grace, in-place durable completion, resident isolation, and reload persistence. Re-run the broad integrated suite after the owning CME/Knowledge/Notifications/telemetry failures are corrected; they are not changed by this Website patch.
