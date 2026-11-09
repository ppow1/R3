<!--
R3 CONTROLLED RUNBOOK
File: docs/runbooks/R3A_AP3_STEWARD_DEVICE_ACCEPTANCE.md
Component: R3A AP3 Steward Access
Revision: 1.2.0
Purpose: Give a Steward a safe, reproducible browser acceptance path over supported development networks.
Authority: Issue #49; coordinate Website #51 and Coordinator #56.
Security: Uses only the existing R3 portal identity, AP3 durable session and CME authorization. Does not expose or configure a public listener.
Changed: 2026-11-09T13:10:00Z | AP3-M1 | Codex GPT-6 | Record LAN portal listener restoration and interactive acceptance boundary.
Changed: 2026-11-09T14:00:00Z | AP3-M1 | Codex GPT-6 | Diagnose provider Origin rejection and prepare coordinated allowlist correction.
-->

# Steward device acceptance

## Live LAN portal listener restoration (2026-11-09)

The configured R3 account login URL is `http://192.168.1.155:8303/login`. It was failing because port 8303 had no listener. The existing account application remains on loopback `127.0.0.1:18303`, with its existing institutional session authority on `127.0.0.1:8767`. No account store, provider, credential, database, or firewall rule was changed.

Remote Access installed [`r3-steward-login-lan.conf`](../../deploy/nginx/r3-steward-login-lan.conf) as `/etc/nginx/conf.d/01-r3-steward-login-lan.conf`, validated the complete configuration with `nginx -t`, and reloaded only Nginx. It binds only `192.168.1.155:8303`, allows `192.168.1.0/24`, validates mutation Origin against the exact configured LAN URL, and proxies to `127.0.0.1:18303`. Rollback is removal of that dedicated file followed by `nginx -t` and an Nginx reload. R2/R3/V2 application processes and AP3 were not restarted.

Live HTTP checks after reload: `/login` 200, `/api/v1/health` 200, anonymous `/api/v1/chat/session` 401, AP3 `/api/v1/steward/session` and `/status` 401, and anonymous AP3 `/operations/invoke` 401. An untrusted mutation Origin was denied 403 in an isolated Nginx proxy check. These prove listener/routing and anonymous denial only; no successful real-account login or authenticated browser session has yet been observed. AP3 website source currently running is Coordinator revision `7452b970ec04671acf26f6aa3a020162171cf558`; account app release directory is `r3-auth-3cf805d461eb`; AP3 service remains active as PID 417257, and portal app remains active as PID 1359. The Remote Access source revision is the commit recorded with this runbook change.

The next acceptance step requires a Steward to enter real account credentials directly into the browser at the LAN login page. Do not send credentials, cookies, or session-secret values in chat or issues. After login, use the same browser/device at `http://192.168.1.155:8311/steward` and follow the acceptance steps below. If sign-in succeeds but AP3 does not establish a session, capture only status codes, non-secret contract state, and correlation IDs for diagnosis.

## Follow-up login failure diagnosis (2026-11-09)

The Steward reported that `/login` opens but sign-in displays “Sign-in unsuccessful.” The request reaches Nginx port 8303 and the existing R3 app at 18303. Safe service access logs show `POST /api/v1/chat/login` from LAN client `192.168.1.88` returning 401. The app forwards the request to the authoritative account/session endpoint `127.0.0.1:8767/api/v1/auth/session`; it maps provider 401/403 responses to the generic UI response, so the UI text does not identify the internal cause.

The provider checks `Origin` before parsing the login body or looking up an account. `RIVERVIEW_PUBLIC_ORIGINS` is not set in the active service environment; its code default contains only `https://192.168.1.155` and `https://riverview.ionoge.com`. A no-credential empty-object probe with the established LAN origin returned 403 from the provider, while the configured HTTPS origin passed the Origin check and then returned 400 for the intentionally invalid request shape. Through the R3 app, the LAN-origin probe is presented as 401. This isolates the confirmed defect to the provider's Origin allowlist; password validation, account lookup/state, and session creation were not reached. No account or credential was changed.

The prepared [account-origin systemd override](../../deploy/systemd/riverview-account-lan-origin.conf) retains the two current HTTPS origins and adds only `http://192.168.1.155:8303`. The account/session authority is Coordinator-owned. After coordination, install it as `/etc/systemd/system/riverview-status-dashboard.service.d/90-r3a-lan-account-origin.conf`, run `systemctl daemon-reload`, then restart only `riverview-status-dashboard.service`. Rollback removes that dedicated file, runs `daemon-reload`, and restarts only the same service. Remote Access has not installed the override or restarted that service. Rewriting or dropping the browser Origin at Nginx would bypass the provider's CSRF boundary and is not an acceptable fix.

Exact account provisioning was not verified: the rejected request never queried an account, and the authenticated account-admin status endpoint is not available without a Steward session. Do not diagnose an account or password problem from this response. After Coordinator activation, the no-credential origin probe should return 400 (valid Origin, invalid empty-body shape) and foreign Origin should remain 403. Then the Steward can retry once in the browser; only the actual account response can validate the existing credential and provisioned account. Password reset remains outside this work without Steward approval.

## Current development reachability

Observed on 2026-11-09:

- Website development service revision `7452b970ec04671acf26f6aa3a020162171cf558` is listening on IPv4 `0.0.0.0:8311`; its page is reachable at `http://192.168.1.155:8311/steward` from this host. The existing R3 portal login is reachable at `http://192.168.1.155:8303/login` through the new LAN-only Nginx mount. Its session verification endpoint at `127.0.0.1:8767` remains loopback-only.
- The host LAN address is `192.168.1.155/24`. AP3's external config allows only origin `http://192.168.1.155:8311`, keeps `public_exposure=false`, and uses `Secure=false` for this HTTP-only LAN development origin. The session cookie is still `HttpOnly`, `SameSite=Strict`, scoped to `/api/v1`, and never returned in JSON.
- An existing shared Nginx service listens on IPv4 port 443. The host trusts its TLS certificate (`curl` certificate verification result 0), but `https://192.168.1.155/` serves the existing Riverview Operations site, `/steward` returns 404, and the unauthenticated API health route returns the existing R3 auth middleware's 401. It is not currently an AP3 Website route. Its virtual-host config is root-owned mode 0600; Remote Access cannot inspect or change it. Coordinator/proxy-owner confirmation is required before using that listener.
- The development host has no active VPN interface or route; an OpenVPN executable exists, but no tunnel is configured. Port 8311 and 443 are not listening on IPv6. Although the NIC has global IPv6 addresses, these services have no IPv6 listener. No public forwarding or AP3 public ingress was configured or tested; external scope of the existing shared Nginx listener is not established here.

| Device path | Current evidence | Reachability and limit |
| --- | --- | --- |
| Desktop browser on this host | Portal login and Steward page return HTTP 200; anonymous AP3 APIs return 401 in headless Chrome. | Page/API path is ready. A real login has not been performed. |
| Phone on the same local Wi-Fi | Not physically tested. Host is bound to IPv4 on all interfaces and the LAN address/ports are confirmed locally. | Expected at the same LAN URLs if the phone joins the same non-isolated LAN and LAN firewall rules allow TCP 8303/8311. Guest Wi-Fi/client isolation may prevent it. |
| Phone with VPN enabled | No VPN route or server interface is configured on this host. Existing Nginx TLS is trusted by this host but is not routed to AP3. | Not currently demonstrated. Requires Coordinator/proxy-owner approval for a private HTTPS route to port 8311 and an institution-approved VPN route, plus phone certificate trust and `Secure` cookies before remote transport can be marked configured. Do not change `public_exposure` or open a router port. |
| Phone on cellular, Wi-Fi off | Not tested from a phone. The service is private IPv4-only and has no IPv6 listener or approved public ingress. | Direct cellular access is not supported by current configuration. An approved VPN with private routing and HTTPS is required. |

Desktop's live 401 denial proves the AP3 router and fail-closed session handling are active; it does not count as an authenticated acceptance. A phone is required for actual Wi-Fi/VPN/cellular radio-path evidence. Report a timeout as unreachable, not as a successful login test.

## Steward-operated authenticated test

The Website controls and AP3 router are ready for a real Steward to run the following on desktop or a phone joined to the same trusted LAN. Do not send passwords, cookies, cookie values, or screenshots containing them to chat/issues. Record only HTTP status, contract state, principal issuer/ID if policy allows, correlation IDs, and audit event IDs.

1. Join the trusted `192.168.1.0/24` LAN. On the same browser and device, open `http://192.168.1.155:8303/login` and sign into the existing R3 account portal as a Steward using the normal institutional flow.
2. Open `http://192.168.1.155:8311/steward` and select **Begin session**. Expected: HTTP 200, `contract: r3a.steward-session.v1`, state `authenticated`, a `r3a.steward-principal.v1` principal from issuer `r3-account-portal`, and an expiry/correlation ID. The response must not contain a bearer token. In browser developer tools, verify cookie name `r3_steward_session`, `HttpOnly`, `SameSite=Strict`, path `/api/v1`; do not copy its value. `Secure` is false only for this HTTP LAN prototype.
3. Select **Refresh status**. Expected: session state remains authenticated; `GET /api/v1/steward/session` and `/api/v1/steward/status` return 200; CME freshness is shown as measured, or explicitly stale/unavailable. Reload the page. Expected: the same durable AP3 session remains authenticated until expiry/revocation; browser storage contains no session token.
4. For CME authorization, obtain from the Coordinator (#56) one currently granted, read-only invocation JSON for the actual authenticated Steward principal. Paste that canonical `r3a.capability-invocation.v1` request into the operation field and select **Run authorized operation**. Expected: 200 with CME result, correlation ID, and audit event ID. CME must evaluate the real grant. If denied (403), record the denial/audit reference and stop; do not try a mutating or broader operation.
5. Select **End session**. Expected: a revoked response and cookie expiration. Reload the page and request `/api/v1/steward/session`, `/status`, and the same operation. Each must be denied with 401; no further CME operation should run. Confirm the denial correlation/audit record through the authorized institutional audit view. AP3 logout revokes the AP3 session; it does not sign the user out of the R3 portal.
6. Optionally sign out from the existing R3 portal. A subsequent AP3 **Begin session** must fail with 401 and issue no AP3 cookie until the portal login is renewed.

The Website UI does not renew AP3 sessions silently. Page refresh reuses the durable cookie; when the eight-hour session expires, start a new AP3 session only while the existing portal identity is valid.

## Phone network checks

After the desktop LAN run succeeds, repeat steps 1–5 on a phone while it is on the trusted local Wi-Fi. Keep the same hostname/IP for portal and Website so both host-scoped cookies are sent. If it fails, record whether DNS/page load, portal login, session creation, status, operation, or revocation failed and the HTTP status. Check guest Wi-Fi isolation and local firewall before changing service exposure.

For VPN testing, wait for Coordinator/the proxy owner to confirm that the existing 443 listener is in approved scope and publish a private route from its HTTPS virtual host to Website port 8311, or provide an approved private HTTPS endpoint. Reconcile AP3's allowed origin and `Secure=true` through the Website-owned deployment. The phone must trust the presented certificate. Then connect the phone VPN, disable Wi-Fi to prove the VPN path, and repeat steps 1–5 using that HTTPS hostname. Expected: browser reports a trusted HTTPS connection; session cookie has `Secure`, `HttpOnly`, and `SameSite=Strict`; generic CME authorization and revocation match the LAN behavior. Until those prerequisites exist, classify this test `not configured`, not failed AP3 authentication.

For cellular without an approved VPN, do not attempt to expose the development listener. Expected current result is unreachable/timeout. No direct cellular acceptance can pass under the current private IPv4 and HTTP-only configuration.

## Safe configuration and diagnostics boundary

- The operator-owned AP3 configuration remains outside Git and mode `0600`. The Website UI is read-only for runtime configuration: it may show session state, expiry, CME health/freshness, and correlation/audit references after server-side authentication. It must not display/edit the database DSN, cookie/token values, portal cookies, secret references/values, arbitrary identity URLs, or public-exposure controls.
- Status must come from the existing `/api/v1/steward/session` and `/api/v1/steward/status` contracts, not client-side cached authority. A 401 means absent/expired/revoked identity; 403 means origin or authoritative grant denial; 503 means an identity, database, or CME dependency is unavailable. The browser must never turn these into a synthetic authenticated state.
- Configuration changes require the Website service owner to update the external file, validate it with `load_access_config`, verify the DB peer role and CME socket, and restart only the Website-owned development unit. Remote/VPN mode requires TLS (`Secure=true`) and a verified private route. Keep the Coordinator-owned AP0/CME service and unrelated R3 services untouched.
- AP3 config validation now refuses `remote_transport.state="configured"` unless the session cookie is Secure and every allowed origin is a bare HTTPS origin. A trusted certificate on the proxy alone is insufficient; it must actually route the AP3 Website and the phone must trust that certificate.

## Current acceptance blocker

No real Steward portal cookie has been supplied in the running browser, so the session table remains empty. A Steward-operated LAN test is now ready. The invocation payload must be provided by Coordinator #56 for a safe read-only operation granted to the authenticated Steward principal. VPN and cellular acceptance additionally require network-owner provisioning described above. No credentials or authenticated browser session are requested in chat.
