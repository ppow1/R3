<!--
R3 CONTROLLED HANDOFF
File: docs/handoffs/R3A_WEBSITE_RELEASE_HANDOFF_20261111_8f6d7a3.md
Component: R3A-AP3-WEBSITE
File Revision: 1.1.0
Created: 2026-11-11 (original commit; exact time not independently captured)
Created By: Codex GPT-6
Purpose: Exact Website-owned Step 115 candidate, tests, and live evidence.
Execution Model: Candidate handoff; production activation remains service-owner controlled.
Observability: Source/package digests, isolated candidate runtime, live Website identity and service unit inspection.
Dependencies: R3A Website release package contract; systemd Website unit; native AP3 session configuration.
Authority: Issue #61 comments 6806630916 and 6807889164; Step 131 prohibits activation absent separate authorization.
Changed: 2026-11-11T21:59:30Z | STEP-131 | Codex GPT-6 | Add exact Website-only activation/rollback preflight and identify the unresolved prior-runtime rollback gap.
Supersedes: None; extends the Step 115 handoff while preserving its source/package identity.
Security: Candidate only; no shared service restart, activation, grant, or secret handling.
Tests: See exact-package verification below; this revision changes only release handoff documentation.
History/Predecessor: Git blob b7b526b70ca26248319d9aba95b0b45653546f31.
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

## Step 131 — Website-only activation and rollback handoff (PREDEPLOY_BLOCKED)

This is a reviewed handoff plan, not an activation command. The exact Website candidate above is package SHA-256 `733ab93e7823ae91bd4d47a3639e84d33a8d56eae370596db11dab4c502227e6`, source `8f6d7a3e89d14513abdc046c6cf709085060e01c`, package build 425 files. It passed the focused source and extracted-package suites (20 Node + 27 Python) and the isolated candidate loopback health/homepage check. Independent exact-package review and a separate release authorization are still required. Do not restart or edit the running unit under this handoff.

### Observed Website target

- User unit: `r3a-ap3-website.service`; manager reports it active, PID `1997803`, started `2026-11-10 20:34:07 EST`.
- Listener: loopback `127.0.0.1:18311`; LAN TLS proxy `192.168.1.155:8311`.
- Effective `WorkingDirectory`: `/home/admin1/r3a-workstreams/ap3-website`; effective executable: `/home/admin1/R3/.venv/bin/python -m uvicorn r3_app:app --host 127.0.0.1 --port 18311`.
- The effective drop-ins are `10-website-identity.conf`, `20-account-portal-login.conf`, `30-steward-session-access.conf`, `40-unified-candidate-source.conf`, `90-r3a-native-auth.conf`, `95-r3a-lan-https-backend.conf`, `zzz-coordinator-v2-source.conf`, and `zzzz-coordinator-website-3bbe100.conf`. They layer identity, AP3/session/database, `PYTHONPATH`, native-auth `EnvironmentFile`, LAN backend, and Coordinator source/build settings. Preserve these; do not replace the unit or copy secret-bearing environment-file values into source control or issue comments.
- Live `/api/v1/website/identity` reports `3bbe100ed112eb8f24416243a1c798962ac5f083`. Repository HEAD is the Step 131 handoff commit; its Website source/package remains pinned to `8f6d7a3e89d14513abdc046c6cf709085060e01c`. The served static client has already been observed matching the newer worktree bytes, while the API identity remains the older configured label. Thus the complete in-process application source is not attested by one immutable SHA; do not treat `3bbe100` alone as a proven rollback image.

### Rollback readiness finding

The package builder was run against exact commit `3bbe100ed112eb8f24416243a1c798962ac5f083` to test whether the configured live build label can serve as an exact rollback package. It failed closed with `PACKAGE_ERROR=package is missing required Website/runtime/config files`; that commit lacks `web/browser-preferences.js` and `assets/visual-concepts/Riverview3_Visual_Concept_Library/backgrounds/R3_modern_estate_clean_concept.png`, both required by the current Website release contract. `r3_app.py` also differs between `3bbe100` and the Step 115 branch head (43 additions, 19 deletions). The running Python process has not exposed an attested loaded-file digest. Therefore there is no proven complete previous package/config snapshot to restore after a failed activation. This is a concrete release gate, not a reason to guess a fallback.

### Controlled activation sequence after the gates clear

1. Independent Auditor reviews this exact source/package pair and records the disposition on #51. Steward/Coordinator separately authorize the exact release and identify the service operator. This handoff grants no activation authority.
2. The service owner confirms the release root and free space on the host. Proposed isolated path: `/home/admin1/.local/share/r3a-ap3-website/releases/8f6d7a3/`; it is not yet an observed or approved production path. Do not overwrite an existing path.
3. Copy the archive to the host using the approved transfer mechanism; verify its SHA-256 before extraction. Extract `website/` to `release/source/` and the root manifest to `release/source/WEBSITE_PACKAGE_MANIFEST.json`; create an isolated `release/venv` and install only `source/requirements-deploy.lock` with `pip --require-hashes`. From `release/source/`, run `../venv/bin/python -m unittest tests.test_r3a_website -q`, `node --test tests/test_steward_workspace_api.mjs`, then `../venv/bin/python scripts/deployment/verify_candidate_runtime.py --candidate-root ..`. Require exact source identity, health HTTP 200, homepage HTTP 200, and clean candidate shutdown before activation. Keep the active `/home/admin1/R3/.venv` unchanged.
4. Before changing systemd, capture the exact current unit and all drop-in files in a service-owner-only mode-0600 backup, record their hashes/paths without exposing credential contents, archive/verify the current complete source tree and applicable non-secret assets, record the current dependency/runtime identity, and obtain an attested rollback image that satisfies the current package contract. The failed `3bbe100` package build means this prerequisite is currently unmet.
5. Once rollback is independently verified, use one final, release-specific systemd drop-in to set only the candidate `WorkingDirectory`, candidate venv `ExecStart` with the already-observed loopback bind/port, and matching `R3_WEBSITE_BUILD_COMMIT`. Leave AP3/native-auth `EnvironmentFile`, auth/session/database settings, all other drop-ins, Nginx, CME, Ring0, database records, grants, and resident bindings unchanged. Run `systemctl --user daemon-reload`, restart only `r3a-ap3-website.service`, then verify the PID/command/cwd, `/api/v1/website/identity`, health, TLS/login route, anonymous 401 boundaries, and the candidate-specific API/static assets.
6. For failure, restore only the saved Website drop-in set and point the Website unit to the verified immutable prior Website source/runtime, daemon-reload, restart only the Website unit, and repeat its identity/health/auth-boundary probes. Do not run an automatic fallback to the mutable worktree, and do not reload Nginx unless its configuration was intentionally changed (it is out of scope here).
7. Report build, regression, deployment, and authenticated browser acceptance separately. Browser acceptance still waits for Steward approval and controlled CME recovery; a healthy site or successful asset request does not prove a Grace reply.

**Current disposition:** `PREDEPLOY_BLOCKED`. The exact package is ready for independent review, but the previous loaded Website source/runtime/config is not yet represented by a complete, verified rollback image. The live unit remains untouched. The service owner must attest or produce that rollback image before an activation can be considered safe.
