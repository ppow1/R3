<!--
R3 CONTROLLED DOCUMENT
File: docs/runbooks/R3A_LAN_HTTPS_DEPLOYMENT.md
Component: R3A-AP3-WEBSITE-TRANSPORT
File Revision: 1.0.0
Created: 2026-11-09T19:23:00Z
Created By: Codex GPT-6
Purpose: Describe the LAN-only TLS route for the independently authenticated R3A Website.
Execution Model: Nginx TLS termination bound to the LAN address and a loopback-only Website backend.
Observability: Nginx configuration check, listener inspection, HTTPS probes and Website systemd health.
Dependencies: R3A native Steward auth; certificate with IP SAN 192.168.1.155; #49 and #51.
Authority: Steward directive AP3/R3A-010, 2026-11-09; no public ingress or firewall change.
Changed: 2026-11-09T19:23:00Z | AP3-R3A-010-LAN-IP | Codex GPT-6 | Establish reproducible HTTPS transport and rollback procedure for the approved LAN IP.
Supersedes: None.
Contracts: R3A Steward Website Session Contract; R3A native identity runbook.
Tests: `nginx -t`; managed HTTPS probes; R3A auth regression suite.
History/Predecessor: New file.
-->
# R3A LAN HTTPS deployment

The approved Website origin is `https://192.168.1.155:8311`. Nginx binds only to `192.168.1.155:8311` and uses `/etc/nginx/ssl/riverview-lan.crt` and its paired private key. The certificate must retain `IP Address:192.168.1.155` in its Subject Alternative Name and chain to the installed Riverview Camrui LAN Root CA. The Website service listens only on `127.0.0.1:18311` behind Nginx. This does not alter firewall rules or expose R3A publicly.

## Deployment

1. Install `deploy/systemd/r3a-ap3-website-lan-https-backend.conf` as `~/.config/systemd/user/r3a-ap3-website.service.d/95-r3a-lan-https-backend.conf` with mode 0600.
2. Run `systemctl --user daemon-reload` and restart only `r3a-ap3-website.service`.
3. Confirm the Website process is healthy on loopback port 18311 and no process listens on 0.0.0.0:8311.
4. Install `deploy/nginx/r3a-website-lan-https.conf` as `/etc/nginx/conf.d/r3a-website-lan-https.conf`, root-owned mode 0644.
5. Run `sudo nginx -t`; reload Nginx only if the check succeeds.
6. Verify `/login`, `/steward`, and `/api/v1/steward/health` return 200 with normal TLS certificate validation. Verify anonymous `/api/v1/steward/session` and `/api/v1/steward/residents` return 401.

## Rollback

Remove `/etc/nginx/conf.d/r3a-website-lan-https.conf`, run `sudo nginx -t`, then reload Nginx. Remove the Website systemd drop-in, reload the user systemd manager, and restart only the Website service to restore its previous listener. Do not alter the certificate, HTTPS listeners for other services, database state, identity records, or R3 services.

## Current deployment evidence

At Coordinator integration commit `3a3603d`, the LAN HTTPS listener is active. The installed certificate validates for `192.168.1.155` and `curl` reports TLS verify result 0. `/login`, native auth health return 200; anonymous session and resident routes return 401. This verifies the managed host trust store and server-side transport. It does not establish Steward browser trust on a separate client or prove an interactive login.
