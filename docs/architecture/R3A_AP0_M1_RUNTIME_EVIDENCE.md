<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP0_M1_RUNTIME_EVIDENCE.md
Component: R3A-AP0-M1-EVIDENCE
File Revision: 1.0.1
Created: 2026-11-06T15:41:41Z
Created By: Codex GPT-6
Purpose: Record reproducible AP0-M1 operational evidence from the isolated R3A runtime.
Execution Model: Evidence record and local operator runbook.
Observability: PostgreSQL rows/events, systemd user units, process IDs and checksummed backup artifacts.
Dependencies: R3A AP0-M1 implementation; Issue #42 authorization; isolated development host.
Authority: Steward implementation authorization in GitHub Issue #42; no production changes permitted.
Changed: 2026-11-06T15:41:41Z | R3A-AP0-M1 | Codex GPT-6 | Record live runtime evidence and recovery/restore results.
Changed: 2026-11-06T15:48:00Z | R3A-AP0-M1 | Codex GPT-6 | Add forward-migration restore and append-only ledger verification.
Changed: 2026-11-06T15:50:58Z | R3A-AP0-M1 | Codex GPT-6 | Pin the delivered implementation commit and repeat crash recovery against that revision.
Changed: 2026-11-06T15:52:25Z | R3A-AP0-M1 | Codex GPT-6 | Confirm the production user service and system PostgreSQL cluster remained online and separate.
Supersedes: docs/architecture/R3A_AP0_M1_RUNTIME_EVIDENCE.md revision 1.0.0; adds exact implementation revision and repeated recovery evidence.
Contracts: AP0-001–013; R3A-001–009/R3A-018; AP0-M1 plan M1.0–M1.7.
Tests: Focused compile, shell syntax and actual isolated process/database acceptance operations.
History/Predecessor: Blob 5e0978616c3ccba96ff4759ecd42fdf57946374d at commit f57aceb3598c495483fb3483ee1a168cd1a283a9.
-->
# R3A AP0-M1 — First Living Water Wheel Runtime Evidence

## Scope and revision

This record covers the isolated AP0-M1 implementation authorized in GitHub Issue #42. Runtime code was committed on branch `engineering/r3a-phase0-20261105` at **`f57aceb3598c495483fb3483ee1a168cd1a283a9`**. The evidence record is documentation-only and is committed afterward. The user-scoped runtime was restarted with `R3A_IMPLEMENTATION_REVISION` set to the implementation commit so new events identify that code revision.

No production R/3 service, production database, network listener, or deployment was changed. Final read-only checks confirmed the existing user-scoped `r3-institution.service` remained active as PID 2663801 from release `r3-unified-8ab4b2ab1669`, and PostgreSQL cluster `16/main` remained online on port 5432 at `/var/lib/postgresql/16/main`. R3A used separate user-scoped service names, its own data directory and Unix socket, port 55492, and database `r3a_ap0_m1`.

## Isolated environment

| Item | Observed value |
|---|---|
| Host platform | Ubuntu 24.04; systemd user manager |
| Python / PostgreSQL | Python 3.12.3; PostgreSQL 16.15 |
| Branch / implementation commit | `engineering/r3a-phase0-20261105` / `f57aceb3598c495483fb3483ee1a168cd1a283a9` |
| Data root | `/home/admin1/.local/state/r3a-ap0-m1` |
| Bootstrap config | `/home/admin1/.config/r3a-ap0-m1/bootstrap.json` (mode 0600; external to source) |
| PostgreSQL | Dedicated cluster and data directory above; Unix socket `/home/admin1/.local/state/r3a-ap0-m1/run`; port 55492; `listen_addresses=''` |
| Database / role | `r3a_ap0_m1` / least-privilege `r3a_runtime`; OS peer mapping for local owner |
| User services | `r3a-ap0-m1-postgres.service`; `r3a-ap0-m1-ring0.service` |
| Core event schema | Migration `001_ap0.sql`; 3 versioned state-machine definitions |

The operator service is local-only. PostgreSQL rejects TCP connections. Ring 0 and PostgreSQL are enabled as user services; a host reboot was not attempted on this shared development host.

## Operational evidence

1. **Boot and vertical slice:** The user-managed PostgreSQL and Ring 0 units started. Ring 0 launched a separate CME process; CME migrated the isolated database, activated the external configuration revision, loaded the state-machine definitions, registered the observer module/capabilities/resource, and exposed separate control and diagnostics Unix sockets. The observer ran as its own process and completed recurring `foundation.observe` activities containing process PIDs/heartbeat ages and PostgreSQL version/database/readiness observations.
2. **Capability boundary:** The first activity was durably denied and marked `BLOCKED` because no capability grants existed. The denial appears in the event ledger. Two explicit operator grants were then recorded for `host.process.read` and `postgres.readiness`, both read-only. Thereafter activities completed with observations. No implicit module grant was installed.
3. **Module lifecycle:** `foundation.observer` 1.0.0 stopped and reactivated; it was replaced by registered version 1.0.1 and then back to 1.0.0. Both replacements returned `cme_pid_unchanged: true`. The live Ring 0 and CME PIDs were also observed unchanged during the two replacements. A registered protocol-major-99 fixture was rejected and persisted as lifecycle `INCOMPATIBLE`; no incompatible module process was launched.
4. **CME crash and durable activity recovery:** Recovery was repeated against implementation revision `f57aceb3598c495483fb3483ee1a168cd1a283a9`. CME PID 3609892 was frozen after durable observer activity `f635918b-0810-4be5-8811-01c64644023d` acquired a three-second lease, then killed. Ring 0 PID 3609886 stayed running and relaunched CME as PID 3610393. The same activity ID and idempotency key were preserved; its first lease expired, the event ledger recorded `safe_to_resume=true`, and CME completed it on attempt 2. The stored completion payload contains real observations of both process IDs, PostgreSQL 16.15/database readiness and the second attempt ID. SQL verification showed `COMPLETED`, attempt count 2, no current lease/exception, and both Ring 0 and replacement CME observations healthy. CME also reconciles and reaps a same-user orphaned observer child before launching a fresh module process.
5. **Truthful diagnostics:** `r3a status` returned current PostgreSQL-backed process IDs, heartbeat age/freshness, module lifecycle/health/freshness, configuration digest, resource allocation, activity states, machine IDs/digests and event count. `r3a events` returned the bounded recent event projection; `r3a definitions` returned the catalog used by transition validation. A stopped historical module version correctly appeared stale while the active version remained fresh. The status projection is approximately 11 KB, below the 64 KiB frame bound.
6. **Backup and restore:** Operator-invoked `pg_dump` created `/home/admin1/.local/state/r3a-ap0-m1/backups/r3a_ap0_m1-20261106T153300Z.dump`, mode 0600, SHA-256 `ac2b6eede66667dfccd07751715be28b0f07554066fddc71f95a1a4b1c9b6341`. Its manifest records 1,153 events, 102 activities, configuration revision `3d7d79b06ff6831bfe168a73e4c4c97cca31c588bc1a7f386cd79bfba67c50f9`, and schema migration `001_ap0.sql`. Restore to `r3a_ap0_m1_restore3` verified same-version row lineage. A second restore from that 001 backup to separate database `r3a_ap0_m1_restore4` ran forward migrations and verified 1,153 events, 102 activities, 1 configuration revision, 3 state machines, the same effective config revision, and final migration `003_reusable_leases_and_grants.sql`.
7. **Append-only event ledger:** Migration 002 installed a database trigger. An actual `UPDATE` attempt against an event row failed with `r3a.institution_events is append-only`; event count remained unchanged.

## Bounded checks performed

- `.venv/bin/python -m compileall -q r3a_runtime` — passed after implementation changes.
- `bash -n scripts/r3a-ap0-m1-provision.sh` — passed.
- `git diff --check` — passed before delivery commit.
- Fresh project-local package install resolved Psycopg 3.3.8 and psycopg-pool 3.3.3.
- Actual user-service boot, status/events/definitions queries, capability denial/grant, module stop/activate/replace, forced CME termination, lease-expiry recovery, backup, checksum verification, and restore to a distinct isolated database — passed as recorded above.

No broad R/3 test suite was run. Test output alone was not used as acceptance evidence.

## Requirement evidence summary

| Requirements | Status from this run |
|---|---|
| AP0-001/002/011 | Ring 0 and separately supervised CME were operational under isolated user services; forced CME crash/restart kept Ring 0 alive. Host reboot itself was not exercised. |
| AP0-003/004/005/006/008 | Real scheduled observer activities, atomic state/event records, resource leases, durable attempt/idempotency lineage and safe expired-lease recovery were observed. |
| AP0-007 | Separate module process registration, compatibility denial, activation, stop and replacement were observed. |
| AP0-009 | Strict external bootstrap config was active with a persisted revision; secrets were not configured or persisted. |
| AP0-010 | Local read-only diagnostics reported DB-backed state and source freshness. |
| AP0-012 | Validation remained bounded to syntax/package checks plus live operational acceptance operations. |
| AP0-013 | Protected custom-format backup and verified restore to a distinct R3A-only database completed. |
| R3A-001–009 / R3A-018 | AP0 runtime contracts and operational evidence above are implemented for this milestone; later-phase resident autonomy, engineering execution, remote access, mature security, HMI, and spatial work remain outside AP0. |

## Limits and handoff

- This is an AP0-M1 development instance, not a production deployment or independent operational acceptance. The Steward retains integration and acceptance authority.
- Basic backup is manual. Scheduling, off-host retention, disaster recovery, remote Steward access, Bitwarden/TOTP/YubiKey, mature security administration, privacy and cryptographic-erasure policy remain later-phase work.
- The resource registry enforces declared logical activity capacity; it does not enforce host CPU or memory quotas.
- Ring 0 automatic user-service start is configured, but host reboot and system-level user-manager persistence were not verified. The shared development host also runs production R/3; it was deliberately not rebooted.
- Failed early bootstrap/restore attempts exposed and were corrected before final verification. Disposable restore test databases remain confined to the R3A cluster; no production data or database was used.

## Local operator commands

```bash
.venv/bin/r3a --config "$HOME/.config/r3a-ap0-m1/bootstrap.json" status
.venv/bin/r3a --config "$HOME/.config/r3a-ap0-m1/bootstrap.json" events
.venv/bin/r3a --config "$HOME/.config/r3a-ap0-m1/bootstrap.json" definitions
.venv/bin/r3a --config "$HOME/.config/r3a-ap0-m1/bootstrap.json" backup
```

The provisioner creates the isolated cluster, peer-authenticated role/database, external config and user-scoped units. Review its fixed local port/data paths before using on another development host. Do not point the config at production or use it to migrate R/3 data.
