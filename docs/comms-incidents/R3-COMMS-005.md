<!--
R3 CONTROLLED DOCUMENT
File: docs/comms-incidents/R3-COMMS-005.md
Component: R3A-WEBSITE-RESIDENT-DISCOVERY-INCIDENT
File Revision: 1.0.1
Created: 2026-11-10T01:31:53Z
Created By: Codex GPT-6
Purpose: Record the R3A Website resident-directory 503 and its managed provider recovery.
Execution Model: AP3 authenticated Website request through CME and a digest-pinned read-only directory provider.
Observability: Website request ID, AP3 session audit, provider lifecycle record, CME invocation, and PostgreSQL directory provenance.
Dependencies: R3A AP3 Website, CME control socket, provider manifest and authoritative Riverview directory.
Authority: Steward incident directive on Issue #51; no authorization bypass or resident grant changes permitted.
Changed: 2026-11-10T01:40:00Z | R3-COMMS-005 | Codex GPT-6 | Recover configured directory provider and record targeted regression results; live authenticated acceptance remains pending.
Supersedes: None.
Contracts: r3a.steward-conversation.v1; r3a.capability-operation.v1; r3a.module-manifest.v1.
Tests: `R3A_PROVIDER_BINDING_CONFIG=... python -m unittest tests.test_r3a_deployed_provider_artifact_bindings -v` (pass); `python -m unittest tests.test_r3a_steward_conversations -v` (6 pass); `python -m unittest tests.test_r3a_website -q` (20 pass).
History/Predecessor: New file.
-->
# R3-COMMS-005 — R3A Website resident directory unavailable

**Status:** Provider recovery deployed; authenticated Website roster and live conversation acceptance remain pending.

## Incident

- **Reported:** 2026-11-10 UTC (Steward directive; exact browser request time is represented by Website logs at 2026-11-10 01:19:41–01:19:49 UTC).
- **Host/service:** R3A managed host; `r3a-ap3-website.service` → `r3a-ap0-m1-ring0.service` / CME.
- **User-visible result:** Resident roster and managed CME operation unavailable; blocked before resident selection.
- **Website request/correlation ID:** `9c674089-da70-44e1-8226-f821022c2471` (provided by Steward; it is the Website response request ID and was not present in journald or CME audit rows).
- **Attempt status:** Authenticated Website GET reached `/api/v1/steward/residents` and returned HTTP 503. At the same time `/api/v1/steward/session` returned HTTP 200 for the same browser host. No conversation or message was created.
- **Authorization:** Existing `resident:grace` → `resident.objective.execute` grant remains active; no grant was changed. CME and Ring0 were healthy. The failure is not the Grace execution grant.

## Evidence and diagnosis

- Website journal records the authenticated session GET returning 200 and three resident-roster GETs returning 503 from `192.168.1.88` at 2026-11-10 01:19:41, 01:19:46, and 01:19:49 UTC. Other unrelated Engineering endpoints returned 401, but those do not explain the roster route and are not used by chat.
- The active directory provider is `r3a.institutional-directory@1.1.1`; its CME module lifecycle record was `FAILED` with `RuntimeError` after the Ring0/CME start.
- An exact read-only provider activation attempt through CME returned `RuntimeError: provider entrypoint resolved outside its pinned artifact`.
- The deployed bootstrap referenced provider manifests from `/home/admin1/r3a-workstreams/coordinator/`, while the active Ring0/CME `WorkingDirectory` and Python import resolve to `/home/admin1/r3a-workstreams/coordinator-20261109-v2/`. Directory plugin and manifest artifact digests match between the trees; strict worker path binding rejected the different resolved path.
- CME capability invocation and invocation-persistence records do not show a directory invocation in the 503 request window. This is consistent with provider startup failing before source access; no authoritative resident rows were returned by that request.
- The 80B model role was independently ready by catalog probe only. No model inference was attempted.
- After recovery, the Website process remained active without restart. An unauthenticated local request to `/api/v1/steward/residents` returned HTTP 401 (`Steward session unavailable`), confirming the protected route still rejects callers without a session. No authenticated browser request has reached the Website after recovery, so a successful roster response is not yet evidenced.

## Recovery and verification

- **Cause class:** Runtime provider source/configuration binding mismatch. Authentication passed; this was not a missing Grace grant or an observed directory identity denial.
- **Correction:** Align the existing external capability-operation manifest references to the running Coordinator V2 source checkout after verifying every staged artifact/supporting-artifact digest. Apply through CME `config.reload`, then activate only the existing read-only directory provider through its CME lifecycle operation.
- **Deployed configuration:** Bootstrap `/home/admin1/.config/r3a-ap0-m1/bootstrap.live-modular-e7a6f56.json`; active config revision/SHA-256 `ddb8de5eb022d8e59982e70e50b5062fa0677e1bb71fb07cc5406dc4a3374f5e`. The previous file is preserved mode 0600 at `/home/admin1/.local/state/r3a-ap0-m1/config-backups/bootstrap.live-modular-e7a6f56.json.pre-resident-discovery-path-fix-20261110T0132Z`.
- **Provider readback:** `r3a.institutional-directory@1.1.1` is `ACTIVE`, health `healthy`, module state `ACTIVE`; its existing read-only configuration and grants were not changed.
- **Regression evidence:** The deployment binding test passes against the active bootstrap. Six conversation tests and 20 Website tests pass. These tests verify regression behavior, not live directory data or model inference.
- **Rollback:** Preserve the exact prior bootstrap file and permission metadata before editing. If reload or provider health fails, restore that file atomically and reload the prior configuration through CME. Do not alter grants, resident identity records, or authorization enforcement.
- **Regression:** Run the deployed-bootstrap provider-entrypoint/pinned-artifact path test.
- **Live boundary still required:** An authenticated browser roster request after recovery, Steward session identity, fresh measured HR-backed directory snapshot containing canonical Grace, Grace availability, conversation creation/message response, actual configured model request/result, PostgreSQL transcript, refresh continuity, correct authorization denial, and confirmation that Website chat continues to route only through CME. No new Grace grant was created.

**Punch list:** R3-P025 in `docs/PUNCH_LIST.md`; coordination Issue #51.
