<!--
R3 CONTROLLED RUNBOOK
File: docs/runbooks/R3A_AP3_SESSION_STORE_ACTIVATION.md
Component: R3A AP3 Steward Access
Revision: 1.0.0
Purpose: Apply the AP3 durable session schema and least-privilege local database binding in the isolated AP0 development cluster.
Authority: Issue #49 and the AP0 migration owner; isolated R3A development database only.
Security: No database password, token, browser cookie, or principal secret is included. Never copy the development socket/config to production.
-->

# AP3 durable session store activation

> **Historical prototype runbook (2026-11-09):** This document records the prior development deployment bound to the R3 account portal. It is not the procedure for independent R3A authentication and must not be followed to configure a new deployment. The R3 portal dependency is retired for the target architecture. See [R3A Authentication Independence Plan](../architecture/R3A_AUTH_INDEPENDENCE_PLAN.md). Do not migrate identities or credentials until the specified Steward approval is recorded.

This runbook binds AP3 to the isolated AP0-M1 PostgreSQL cluster and its append-only `r3a.institution_events` ledger. It does not authorize changes to production R3/V2 databases or public transport.

## Migration ownership and order

AP0 owns `r3a_runtime.db.Store.migrate()`. It acquires the `r3a-ap0-m1-migrations` advisory lock, checks each immutable SQL checksum against `r3a.schema_migrations`, and applies pending files in lexical order under the existing migration identity `r3a_runtime`.

Migration 009, `009_steward_sessions.sql`, follows 001–008. Migration 001 creates `r3a.institution_events`; migration 009 creates `r3a.steward_sessions` and its active-session index. The website role must not run migrations or own either table. The AP0 source tree must contain the exact migration 009 file before future AP0 startup/migration runs so code and database state remain reconciled.

On 2026-11-08, the isolated development database recorded migration 009 with checksum `aedc1f2347b8143a6c82053ac51aee1e08865b12a5209548ddaf8283fc0f704e`. The AP0 phase0 source checkout did not yet contain that file. The migration was run through the checked-in AP0 `Store.migrate()` implementation with the ordered AP0 migration set plus the committed AP3 migration in a temporary migration directory. No AP0, PostgreSQL, or CME service restart was used. The AP0 owner must add migration 009 to the phase0 source before subsequent startup reconciliation.

## Application role and grants

Provision a dedicated login role with local peer authentication and no password:

```sql
CREATE ROLE r3a_steward_access LOGIN
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 4;
GRANT USAGE ON SCHEMA r3a TO r3a_steward_access;
GRANT SELECT, INSERT ON r3a.steward_sessions TO r3a_steward_access;
GRANT UPDATE (revoked_at) ON r3a.steward_sessions TO r3a_steward_access;
GRANT INSERT ON r3a.institution_events TO r3a_steward_access;
```

Do not grant role membership, table ownership, schema creation, event reads/updates/deletes, session deletes, or access to capability/grant tables. AP3 session revocation uses only `UPDATE(revoked_at)`; audit writes append to the existing event ledger.

For a Website process running as the OS account `admin1`, the isolated development cluster uses this peer map in `pg_ident.conf`:

```text
r3a_ap3_steward admin1 r3a_steward_access
```

Place this database-and-role-specific rule before the existing local reject rule in `pg_hba.conf`:

```text
local r3a_ap0_m1 r3a_steward_access peer map=r3a_ap3_steward
```

Keep loopback TCP rejected. Reload PostgreSQL configuration with `SELECT pg_reload_conf()`; do not restart AP0 or CME for this mapping. Verify both `pg_hba_file_rules` and `pg_ident_file_mappings` have no parser errors, then connect over the Unix socket as `r3a_steward_access`. Confirm the current role and grants, including that it cannot update `principal_id`, delete sessions, read `institution_events`, create in schema `r3a`, or read `capability_registry`.

The development Website unit uses a local-socket libpq conninfo value, supplied only through `R3A_STEWARD_DATABASE_DSN`:

```text
host=/home/admin1/.local/state/r3a-ap0-m1/run port=55492 dbname=r3a_ap0_m1 user=r3a_steward_access connect_timeout=3 application_name=r3a-ap3-steward-access
```

This conninfo contains no password. The OS peer mapping is the authentication mechanism.

The Website's shared virtual environment does not contain psycopg. The development deployment currently adds pinned `psycopg[binary,pool]` packages through the private directory `/home/admin1/.local/share/r3a-ap3-website/python` and sets `PYTHONPATH` in the Website-owned systemd drop-in. This avoids modifying the shared R3 virtual environment. Add psycopg to the Website's managed dependency lock before rebuilding its deployment; the private package directory is a temporary development integration detail, not an AP0 or production dependency.

## Website configuration

Copy `r3a_plugins/steward_access.r3-portal.config.example.json` to an operator-owned file outside Git, set its exact LAN origin, and protect it with mode `0600`. Set `R3A_STEWARD_ACCESS_CONFIG` to that copy and `R3A_STEWARD_DATABASE_DSN` to the local-socket conninfo above in the Website-owned unit. The configured identity adapter calls the existing R3 account portal at `http://127.0.0.1:8767/api/v1/auth/session`, forwards only `rv_account_session`, and requires its `steward` role. The browser must first sign in through the existing R3 portal on the same LAN host, then begin the AP3 session. The AP3 session cookie remains HttpOnly, SameSite=Strict, scoped to `/api/v1`; HTTP development uses `Secure=false` only for the explicit LAN origin while public exposure stays false.

The Website source revision `ca07de47ddc1587471b81bffe3bd0b4b602ad2c8` integrates the Remote Access identity adapter from commit `12a30f9`. The Website-owned unit `r3a-ap3-website.service` is running on port 8311 with the shared Steward router configured by `/home/admin1/.config/systemd/user/r3a-ap3-website.service.d/30-steward-session-access.conf`; secrets are not stored in that drop-in. The external mode-0600 config is `/home/admin1/.config/r3a-ap3/steward-access.json`. It points to the existing R3 account portal at `127.0.0.1:8767`, requires its authoritative `steward` role, and uses the least-privilege AP0 socket role. Only the Website-owned development unit was restarted. AP0, PostgreSQL, and CME were not restarted.

## Live evidence status

The local AP0 migration, database role/grants, peer mapping, AP3 config, and Website router mount were verified on 2026-11-08. PostgreSQL accepts the role over the Unix socket; its session table is currently empty. The running Website returns 200 for its health/page routes and 401 for unauthenticated session, status, capability, and generic operation requests. A POST to the shared session endpoint without the existing portal cookie returns 401 and does not set a session cookie. Headless Chrome rendered `/steward` and received the same 401 status from the live API. The existing portal at `127.0.0.1:8767` returns 401 when queried without a real login cookie.

No authenticated AP3 session or successful protected operation is claimed. The exact remaining dependency is a real Steward signing in through the existing R3 portal in a browser on the configured LAN origin; no authorized authenticated portal cookie was available during this activation. After that login, the browser can establish AP3's durable cookie session and verify refresh, operation, logout, revocation, and expiry. Do not bypass the portal or insert a fabricated session. AP0 also needs to add the identical immutable migration 009 to its phase0 source migration directory before future AP0 migration reconciliation. The phase0 development config loader currently rejects a new `module_manifest` bootstrap setting, so the live migration used the AP0 `Store.migrate()` code directly with the ordered migration overlay; the AP0 owner should reconcile that source/config drift.
