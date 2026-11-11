<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_AP0_M1_FIRST_LIVING_WATER_WHEEL_PLAN.md
Component: R3A-AP0-M1-PLAN
File Revision: 1.0.0
Created: 2026-11-06T05:18:48Z
Created By: Codex GPT-6
Purpose: Resolve AP0-M1 implementation choices and define a dependency-ordered, evidence-based first running milestone.
Execution Model: N/A; engineering plan only.
Observability: Decision records, milestone sequence, requirement traceability and acceptance evidence plan.
Dependencies: Approved R3A Master Roadmap Baseline 1.0; AP0 Technical Specification; module and state contracts; Phase 0A investigation; Issue #42.
Authority: Issue #42 authorizes planning only. Runtime implementation, operational deployment and production changes require separate authorization.
Changed: 2026-11-06T05:18:48Z | AP0-M1-PLAN | Codex GPT-6 | Resolve AP0 implementation decisions and define First Living Water Wheel milestone.
Supersedes: High-level proposed AP0-M1 sequence in AP0 Technical Specification 1.0.1; requirements and scope are unchanged.
Contracts: AD-001–AD-010, AD-020–AD-023; AP0-001–AP0-013; MOD-001–MOD-010; STM-001–STM-007; TAP-001–TAP-006.
Tests: Not run; documentation-only assignment.
History/Predecessor: New document; initial publication recorded in Git.
-->
# AP0-M1 — First Living Water Wheel Technical Plan

**Status:** Planning complete; implementation not authorized. This plan is subordinate to Steward-approved Roadmap Baseline 1.0 and Issue #42. No exception is proposed. AP0 requirements remain **PLANNED** until implemented and evidenced.

## 1. Objective and boundaries

Deliver the smallest real, restartable institutional runtime slice that demonstrates the central AP0 cycle: Ring 0 supervises CME; CME durably schedules a real observer activity; state, events and configuration survive restart; the module can be lifecycle-managed independently; and diagnostics report observations from actual processes and PostgreSQL. The “water wheel” is this recurring observe → record → schedule → execute → report cycle. It is a first independently verifiable running milestone, not AP0 completion, autonomy, an Engineering deliverable, or production readiness.

In scope are AP0-001–AP0-013, with the milestone evidence below covering a vertical slice of each. Out of scope remain AP1+ capabilities, production R/3, migration of existing R3 data, multi-host orchestration, broad package/dependency management, remote HMI, security administration and mature disaster recovery. Implement only after a separate authorization names the approved roadmap revision, milestone, requirements, scope and acceptance criteria.

## 2. Selected AP0 technical decisions

These are bounded engineering selections for AP0 implementation planning, not changes to Steward policy, roadmap or module ownership. Alternatives are recorded to make tradeoffs reviewable. Interfaces below are proposed implementation contracts, not evidence that an interface already exists.

| Decision | Selected approach and rationale | Interface / dependency | Verification evidence |
|---|---|---|---|
| **D1 — Process ownership and Ring 0 boundary** | Run Ring 0 as a dedicated, unprivileged systemd service on the isolated development host. systemd restarts Ring 0 after process exit and supplies its process-level watchdog; Ring 0 itself supervises CME as a distinct child process and owns CME start, stop, heartbeat, exit detection and restart. Keep Ring 0 limited to validated bootstrap configuration, CME lifecycle and its own health. Do not make it host resident reasoning, scheduler policy, registries or module code. | Dedicated R3A-only unit/account and paths; Ring 0 ↔ CME private Unix domain control socket; child process readiness/heartbeat/shutdown contract. Depends on platform preflight and service-account provisioning. The Phase 0A audit describes two asyncio loops in an existing runtime but does not provide arbitrary loop registration or the independent CME boundary. | Show systemd unit/process identity and Ring 0/CME PIDs; stop/kill CME and show durable detection and restart while Ring 0 PID remains; stop Ring 0 and show the host manager restores it. No production unit/path/database access. |
| **D2 — PostgreSQL and migrations** | Use a dedicated local PostgreSQL database and least-privilege R3A role in the isolated dev environment; one R3A-owned schema, no shared production database. Use a host-supported maintained PostgreSQL server version and pin the observed version in preflight evidence. Use Psycopg 3 async connections/pool from CME. Keep migrations as ordered, immutable SQL files with a `schema_migrations` ledger and transaction/advisory-lock serialization. PostgreSQL is required by the approved Charter direction; SQLite prototype is not the R3A persistence target. | Ring 0 bootstrap reads only the DB endpoint/role reference; CME owns pool and migration runner. Tables in §3. Depends on host/server version, database/role/schema provisioning and credential mechanism. No data migration from R3. | On disposable R3A DB, migrate from empty schema, restart migration runner safely, verify schema ledger and required tables; concurrent startup cannot apply a migration twice. Capture DB identity proving separation from production. |
| **D3 — CME supervision, scheduling and resources** | CME is a separately restartable process. Ring 0 uses heartbeat plus child exit status; failed CME restarts with externally configured capped exponential delay and no fixed retry exhaustion. CME owns durable queue claiming and module workers. Claim eligible activities oldest-ready-first with explicit dependency readiness and PostgreSQL `FOR UPDATE SKIP LOCKED`; avoid adding priority/fairness policy not required by AP0. Resource/capability records declare resource identity, capacity and observed availability. A claim obtains a durable resource lease in the same transaction as activity claim; unavailable resources leave work waiting with a reason. AP0 manages declared logical claims; host OS remains responsible for machine-wide CPU/memory enforcement. | CME supervisor control protocol; scheduler transaction API; versioned resource registry. Backoff, lease TTL and capacities are required external settings, validated at startup; no hidden defaults that purport to be institutional limits. Depends on DB/migrations and config schema. | Run two eligible activities and observe deterministic claims, no duplicate simultaneous claim, lease/release events; mark a resource unavailable and see work remain waiting; fail CME repeatedly and show continued restart attempts and explicit status. |
| **D4 — Durable transitions, recovery and idempotency** | Persist each current entity state plus append-only versioned events in a single PostgreSQL transaction. Generate stable activity/event/idempotency IDs before dispatch. Use a renewable worker lease and durable checkpoint reference; on expired lease after CME restart, reconcile to `RECOVERING` and requeue only when the module declares the operation safe to resume. Delivery semantics are at-least-once. Do not claim exactly-once external effects. For an uncertain effect, require a module idempotency key or reconciliation result; otherwise keep the activity visibly `BLOCKED`/`RECOVERY_REQUIRED` for authorized direction rather than blind replay or false completion. | `activity_id`, `attempt_id`, `idempotency_key`, event ID, machine/version, correlation/causation, worker lease, checkpoint ref; transition API validates catalog version in transaction. Depends on D2, machine definitions and module checkpoint/idempotency declaration. | Kill CME before/after a database commit boundary: prove no split state/event transaction, no duplicate active claim, event lineage preserved, safe operation resumes once by key, and uncertain operation remains explicitly blocked. |
| **D5 — Module lifecycle and binding** | Run each module in its own unprivileged child process, launched and supervised by CME; communicate over a private local Unix domain socket using a versioned JSON-lines envelope. This satisfies replacement without Ring 0 restart and avoids unsafe Python in-process unload. AP0 installs immutable, locally staged artifacts by manifest and digest; no general package resolver or remote installer. A module manifest declares module/version, contract ID/version, entry point, dependencies, configuration schema/ref, capability/resource refs, state namespace, artifact digest and recovery/idempotency support. Compatibility is exact major-version match plus declared supported minor range; unknown compatibility denies activation. | Minimum RPCs: `hello`, `health`, `prepare`, `activate`, `execute`, `checkpoint`, `stop`; each request/response has protocol version and correlation ID. CME registry authoritatively records lifecycle; module replies supply observations, not self-asserted authority. Depends on state/event store, manifests, compatibility validator and process control. | Install/register a real observer module; activate, stop and replace its version without Ring 0 restart; incompatible and unknown protocol versions remain visible and inactive; preserve prior artifact/state/event lineage. |
| **D6 — Module and capability/resource registries** | Store registries in PostgreSQL as normalized records with versioned JSONB contract/config schema metadata where extensibility helps. CME is the sole writer for lifecycle/resource observation; modules may report observations through their contract but cannot change their own authoritative lifecycle or grant access. Registry discovery is read-only metadata. Invocation authorization remains a separate existing institutional authority boundary; no AP0 implicit grant is created. | `module_registry`, `capability_registry`, `resource_registry`, `module_artifact`/version and lifecycle event relations; references keyed by stable IDs and contract versions. Depends on D2, D5 and authority adapter boundary. | Query registrations and observed health; prove registry presence alone cannot invoke an ungranted capability; stale module/resource observation reports stale or unknown. |
| **D7 — Configuration and secrets** | Bootstrap from strict external JSON under an R3A-only config directory. It contains only local DB/socket paths, component settings and `secret_ref` identifiers. Operational revisions are immutable PostgreSQL JSONB records with schema version, digest, source/provenance, activation timestamp and actor; a small current-revision pointer changes transactionally. Startup rejects missing/unknown required fields. Reload is explicit revision activation: validate fully, apply at a safe boundary, or retain old effective revision and report failure. AP0 secret resolution is a provider interface with local peer-authenticated DB role where available; never persist/log values. Bitwarden is the required future provider integration (AP3); no competing vault is selected. | `BootstrapConfig` file schema; `ConfigRevision`/`SecretRef`; CME configuration reload operation, recorded against every activity/transition. Depends on host identity/peer auth and DB bootstrap connectivity. | Exercise valid and invalid JSON, valid revision activation and failed activation rollback; restart and verify effective revision continuity; inspect diagnostics/events/logs for absence of secret values. |
| **D8 — Diagnostics** | Provide a read-only local CLI and Unix domain socket API, not a network listener in AP0. Restrict the socket to the dedicated operator group and read-only database role/view set. Ring 0/CME control socket is separate from diagnostics. Report process observations with monotonic/UTC observation times and DB-backed state/events; compute freshness against validated per-source threshold. If the process probe or DB is unavailable/stale, return `unknown`, `stale` or `unavailable`, never cached healthy. Definitions are read from the same versioned machine catalog used by transition validation. | `r3a status` CLI → diagnostics socket → read-only projection; fields defined in STM contract. Depends on D1–D7. AP3 remote access can later place an authenticated gateway over this boundary. | Compare output to process IDs and SQL records across healthy, stopped, restarting and DB-unavailable conditions; confirm no diagnostic operation mutates state and no stale response claims healthy. |
| **D9 — Basic backup/restore** | Provide a documented operator-invoked `pg_dump` custom-format backup of the isolated database plus a versioned copy of non-secret bootstrap/config reference files. Restore only into a newly named isolated target DB; run forward migrations, reconcile effective config references, then verify event/activity/config lineage. Protect artifacts with filesystem permissions. Scheduling, off-host retention and mature disaster recovery remain AP6. | Backup/restore procedure and manifest records source schema/config revision, time and artifact digests; secret values are excluded and references must resolve independently. Depends on D2/D7 and target storage. | Restore disposable source to separate target; verify migration level, effective config revision, representative activity/event IDs and diagnostics. Record checksum and result. |

### Deliberate AP0 technical limits

- One host, one PostgreSQL instance/database, one Ring 0 service, one CME process and local Unix sockets. High availability, multi-host scheduling and network APIs are later work.
- AP0's first module is a real read-only **foundation observer**. It observes Ring 0/CME process health and PostgreSQL readiness through explicitly registered read-only capabilities, emits durable observation activities/events and has no external side effects. It is not a mock and does not stand in for later resident reasoning.
- No generic package ecosystem, automatic schema rollback, arbitrary extension loading, undocumented resource ceilings, or fixed retry cap is required for this milestone.
- Bootstrap peer authentication and secret-reference abstractions do not satisfy AP3 Bitwarden, remote access, MFA or production security acceptance.

## 3. Durable interface and data outline

This is a concrete implementation guide; exact SQL names may follow repository naming conventions without changing semantics.

1. **Versioned catalog:** `state_machine_definition(machine_id, machine_version, definition_json, digest, installed_at)`; immutable after use. Definition JSON contains states, transitions, guards and terminal/recoverable classifications. Runtime validator and diagnostics load the same row/digest.
2. **Current records:** process, module, resource and activity tables carry stable ID, state, machine/version, observed/transition time, effective config revision and optimistic version. Mutable current state is a projection, never the sole history.
3. **Event ledger:** append-only `institution_event` with unique event ID, type/schema version, UTC occurrence and persistence times, subject, machine/version, prior/next state, actor, correlation/causation, outcome, implementation/config revision, and classified evidence/checkpoint reference. No unbounded binary payloads in event rows.
4. **Activities and claims:** activity rows carry due/eligibility, dependency set, idempotency key, attempt counter/ID, lease owner/expiry, progress timestamp/value, checkpoint reference and exception/recovery state. Claim plus resource lease plus event are transactional. Checkpoint blobs/artifacts are content-addressed files under isolated R3A state storage; DB stores digest/path/classification. AP0 observer emits small structured data in event payloads.
5. **Registries/config:** versioned module artifacts/manifests, capability and resource identities/contracts/owners/observation refs, config revisions and secret references. Registry rows never encode a grant. Secret values and tokens do not enter SQL, logs, events or diagnostics.

Data retention/classification, user privacy/deletion semantics and cryptographic erasure remain governed by later Steward decisions. AP0 should minimize payloads and retain provenance without presuming global visibility or indefinite content retention.

## 4. Dependency-ordered implementation sequence

Every step below is planned only. Steps advance only under a separate AP0 implementation authorization that specifies requirements and acceptance. Execute primarily sequentially; parallelization is unnecessary until contracts and worktree ownership are stable. Coordination remains Issue #42; integration authority is Steward as stated in the issue.

| Order | Work package and requirements | Depends on | Bounded verification gate |
|---|---|---|---|
| **M1.0 Preflight** | Confirm isolated host/service account, systemd version/permissions, supported PostgreSQL version and peer-auth option, storage paths/permissions, and no production endpoint/path reuse. AP0-001/011/013. | Authorization and issue scope. | Read-only inventory and explicit isolated resource map; no service/database/config changes. Resolve environmental feasibility before edits. |
| **M1.1 Contracts/config** | Freeze AP0 process, control, module RPC, registry, config and diagnostics schemas from this plan; add strict bootstrap JSON schema and startup validation. AP0-001/009; MOD-001/002/005/007; STM-001/002. | M1.0. | Schema validity/compatibility cases and documented protocol fixtures; no broad suite. |
| **M1.2 Persistence base** | Provision dev-only DB/role/schema; implement ordered migrations, immutable machine catalog, config revisions, registry tables, activity/current state and event transaction APIs. Establish backup/restore procedure before accepting useful records. AP0-004/005/009/013; STM-001–004/007. | M1.0–1.1. | Empty DB migration, restart/idempotent migration, atomic state+event, disposable DB backup/restore. |
| **M1.3 Ring 0 and CME** | Implement Ring 0 service/child control lifecycle and CME database connection/startup/recovery loop; health heartbeat, configured restart delay, lifecycle event recording. AP0-001/002/011. | M1.1–1.2. | Actual two process IDs, CME fail/restart while Ring 0 PID stays constant, Ring 0 host restart evidence. |
| **M1.4 Scheduler and generic recovery** | Implement oldest-ready durable claims, dependency/resource leases, transition validation, attempt/idempotency keys, checkpoint and lease reconciliation. AP0-003–006/008; STM-003–005. | M1.2–1.3. | Real persisted activity, concurrent claim contention, CME kill/restart, safe replay or explicit blocked uncertain effect. |
| **M1.5 Module lifecycle/registries** | Implement manifest registration and compatibility check; CME-launched module process/RPC health, activate/stop/replace; capability/resource discovery distinct from grants. AP0-007/008; MOD-001–010. | M1.1–1.4. | Real foundation observer install/activate/stop/replace while Ring 0 stays running; incompatible fixture denied; authorization denial without grant. |
| **M1.6 Diagnostics** | Implement read-only CLI/socket projections joining actual process probes, machine catalog, current state/event history, config and registry observations. AP0-010; STM-006. | M1.2–1.5. | Compare queries to process and database evidence; exercise stale and unavailable source. |
| **M1.7 First Living Water Wheel evidence** | Run the integrated vertical slice below on isolated revision; capture proportionate evidence and limitations. AP0-001–013. | M1.0–1.6. | Named revision/environment evidence pack; each covered requirement marked implemented/verified/operational separately; acceptance remains pending reviewer authority. |

## 5. First independently verifiable running milestone

**Milestone name:** First Living Water Wheel (M1.7). **Observable claim:** On an isolated R3A development host, a host-managed Ring 0 process supervises a separate CME process; CME connects to the dedicated PostgreSQL database, reads the versioned machine catalog and validated effective configuration, claims a durable observer activity, launches a registered compatible foundation-observer module, records actual process/database observations and transition events, and exposes matching read-only diagnostics. CME interruption does not terminate Ring 0; restart reconciles and continues the same activity lineage safely. A disposable backup restores to a separate target with the lineage intact.

Minimum evidence bundle:

1. Exact code revision, branch, config revision, schema migration level, host identity, process IDs and isolated DB identity.
2. SQL/event evidence for activity creation, claim, progress/observation, completion evidence, config/machine versions, worker lease and CME lifecycle transitions.
3. Captured diagnostic output matching SQL and process observations in healthy, stopped/restarting and stale/unavailable cases.
4. CME termination/restart showing unchanged Ring 0 process identity and preserved activity/event lineage; state is resumed only under the recorded module idempotency/recovery declaration.
5. Module activate/stop/replace result and incompatible-version denial, with Ring 0 still running; capability discovery without authorization remains denied.
6. `pg_dump` artifact checksum and restore-to-separate-database result including verified event/activity/config IDs and diagnostic status.
7. A requirement trace showing evidence and residual gaps. No claim of AP0 completion until all AP0 acceptance rows are evidenced at one named integration revision and independently accepted.

The observer is a real running component making real read-only observations. A mock process, fabricated event, simulated successful restore or health value asserted by the module itself does not meet the milestone.

## 6. Bounded validation plan

Use the [Bounded Testing and Acceptance Policy](R3A_BOUNDED_TESTING_AND_ACCEPTANCE_POLICY.md). Select only focused checks that cover schema/contract validity, transactional event/state consistency, lifecycle compatibility, process failure/restart, claim/idempotency recovery, truthful diagnostics, isolation and backup restore. Use disposable databases and a local isolated service. Do not expand the suite or run broad repository tests absent task authorization. Retain raw commands/results or query output necessary to reproduce claims; report unexercised conditions as limitations. Tests are not run for this planning assignment.

## 7. Decisions still requiring Steward authority or external facts

No AP0 design contradiction or roadmap deviation requires escalation. The following boundaries are deliberately not guessed:

| Item | Classification | Handling |
|---|---|---|
| Production use, deployment, real-data migration, external/network exposure, elevated host privileges, or any roadmap/scope change. | Steward authorization required. | Not in this plan's implementation authority; must be separately named and approved. No exception exists. |
| Privacy/data classification, content retention/deletion, cryptographic erasure/key lifecycle, emergency lockdown authority, and Bitwarden machine-auth policy. | Steward/policy decisions; not needed to invent AP0 observer behavior. | AP0 stores minimal records and secret references only; later phases must supply approved policy before affected data/use. |
| Existing host service manager/version, PostgreSQL availability/version/peer auth, unprivileged service identity and isolated storage availability. | Environmental facts, not architectural decisions. | M1.0 preflight verifies; if unavailable, report exact dependency and pause affected execution for platform support. Do not substitute SQLite or point at production. |
| Actual resource capacity values and activity lease/backoff thresholds. | Environment-specific configuration. | Set from observed host/service requirements with explicit validated config and evidence; no arbitrary global limits are embedded in code. |
| Steward integration authority for Issue #42. | Explicitly settled in issue body: Steward until a named engineering integration owner is designated. | Preserve that assignment; do not nominate an owner by inference. |

These items do not block producing or reviewing this plan. They may constrain an implementation environment or later acceptance claims, but they do not require another architecture review cycle.

## 8. Traceability

| Requirements | Plan coverage |
|---|---|
| AP0-001/002 | D1/D3; M1.3; M1.7 |
| AP0-003/004/005/006 | D2–D4; M1.2/M1.4; M1.7 |
| AP0-007/008 | D5/D6; M1.5; M1.7 |
| AP0-009 | D7; M1.1/M1.2; M1.7 |
| AP0-010 | D8; M1.6; M1.7 |
| AP0-011 | M1.0 and isolation evidence in M1.7 |
| AP0-012 | §6 and M1.7 evidence bundle |
| AP0-013 | D9; M1.2 and M1.7 |
