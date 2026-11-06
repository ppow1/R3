<!--
R3 CONTROLLED DOCUMENT
File: docs/architecture/R3A_PHASE_0A_TECHNICAL_INVESTIGATION.md
Component: R3A-PHASE0A-INVESTIGATION
File Revision: 1.0.1
Created: 2026-11-06T01:23:48Z
Created By: Codex GPT-6
Purpose: Record targeted source findings on R3 supervisory loops, CME and related dependencies.
Execution Model: Read-only source/document/history investigation.
Observability: Git source commits and cited audit evidence.
Dependencies: R3 modular architecture audit at commit 7e6d8d053b97837866470db4549331d839bf8ba8; deployed runtime source at 8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135.
Authority: Original Phase 0A read-only investigation directive; R3A architecture baseline documentation task.
Changed: 2026-11-06T03:48:35Z | R3A-BASELINE-001 | Codex GPT-6 | Add controlled provenance and correct historical audit reference; investigation findings unchanged.
Supersedes: None.
Contracts: R3A Architecture Charter and AP0 specification use this report as prior evidence; it does not establish new architecture decisions.
Tests: Not run; documentation metadata/reference correction only.
History/Predecessor: Git blob 18f8e57fc822b428c408e37b2c3b0b07bb57f5cb at commit 9adc3d74ae29280f9659eefcb5eff45723b67d11.
-->
# R3A Phase 0A — Targeted Technical Investigation

**Scope:** Supervisory loops, CME, and only the dependencies relevant to extracting or independently operating them. This supplements [the modular architecture audit](https://github.com/ppow1/R3/blob/7e6d8d053b97837866470db4549331d839bf8ba8/docs/architecture/R3_MODULAR_ARCHITECTURE_AUDIT_2026-11-05.md); it does not repeat its general inventory or recommendations.

**Evidence baseline:** Runtime source at deployed integration commit `8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135`; architecture audit commit `7e6d8d053b97837866470db4549331d839bf8ba8`. Operational status below is reported from that audit's read-only observation, not re-probed for this report. No code or production state was changed; tests were not run.

## 1. Supervisory loop

### Source and flow

`runtime/institution.py` defines `Journal`, `Resident`, and `Institution`; `runtime/serve.py:serve(...)` composes them with validated configuration and resident adapters. `Institution.add(resident)` registers each enabled configured resident and calls `Journal.register`. `Institution.run()` recovers persisted stale states, then creates exactly two `asyncio.TaskGroup` tasks: `main_loop()` (`r3-main`) and `supervisory_loop()` (`r3-supervisor`).

```text
serve(...)
  ├─ load_configuration(config_dir); open Journal(SQLite)
  ├─ create Inbox / ConversationStore on Journal's SQLite connection
  ├─ for each enabled resident: build ResidentInference → Institution.add(Resident)
  ├─ optionally start HTTP listener threads and independent reviewer worker
  ├─ create_task(Institution.run())
  │    ├─ recover persisted RUNNING/RECOVERING → READY
  │    └─ TaskGroup: main_loop ⇄ supervisory_loop
  │         main: due + ready + no active task → create _execute(resident)
  │         work: RUNNING → COMPLETED/READY or FAILED/RECOVERING
  │         supervisor: collect finished task; record escaped crash; remove active entry
  ├─ periodically write health snapshot
  └─ shutdown: stop listeners, cancel/gather resident tasks, stop reviewer, await runtime
```

### Scheduling and state

- `Institution.main_loop()` (`institution.py:147`) checks each registered resident every `tick_seconds`. It skips an unfinished task for that resident, reads its persisted `next_due`, and dispatches a named task only when due and its optional synchronous `ready(name)` predicate returns true. Concurrency is at most one active task per resident; there is no global worker pool or queue-fairness policy in this class.
- In `serve.py:118-125`, each configured handler is a `ResidentInference`. Its `ready` predicate queries the shared `resident_inbox` for `PENDING` or `PROCESSING` rows for that resident. Thus, although the `Resident` API allows `ready=None`, the integrated resident handlers are inbox-work-driven rather than continuously invoking inference on every schedule tick.
- `Journal` (`institution.py:35-101`) persists `residents(name,state,heartbeat,next_due,failures)` and an append-only `events` table in SQLite. `transition(...)` updates resident state and appends an event in one transaction. Snapshots expose resident rows, the last 30 events, and numeric states (`READY=100`, `RUNNING=200`, `RECOVERING=900`).
- `Institution.active`, task objects, loop stop event, and loop heartbeats are in memory. Resident state, due time, failure count, and journal events are in SQLite. The per-loop heartbeat ages are exposed by `Institution.health()` (`:194-200`); the service writes the combined health JSON atomically (`serve.py:54-67,234-260`).

### Failures, retries, restarts

- `_execute(resident)` (`institution.py:130`) records `RUNNING/STARTED`. Normal return records `READY/COMPLETED` and sets `next_due = now + interval`. An ordinary handler `Exception` records `RECOVERING/FAILED`, increments failures, stores truncated `repr(exc)`, and sets `next_due = now + interval`. The task then returns normally, so this is a delayed retry on a later main-loop pass, subject to `ready`.
- Cancellation records `READY/INTERRUPTED` with immediate due time and re-raises. `stop()` sets the stop event, cancels active tasks, and gathers them (`:187-192`).
- `supervisory_loop()` (`:162`) detects completed tasks. If a task escaped `_execute` with an exception, it records `RECOVERING/TASK_CRASH`, increments failures, makes it immediately due, and removes it from `active`; otherwise it only removes the completed task. It does not enforce a work-duration timeout: the source history explicitly records removal of elapsed-work cancellation.
- At startup `run()` changes persisted `RUNNING` or `RECOVERING` rows to `READY/RESTART_RECOVERY`, immediately due (`:174-185`). This recovers scheduling state; it does not by itself reconcile an external side effect or inbox item. Inbox-specific continuation/recovery is implemented by `ResidentInference`/`Inbox`, not the supervisor.
- A failure in the main or supervisory loop itself is not handled by a loop-level restart policy: `TaskGroup` failure propagates out of `run()`, and `serve()` detects an unexpectedly completed runtime task and raises (`serve.py:223-227`).

### Hardcoded, configurable, extensibility

- Hardcoded in `Institution`: two named loops and their `TaskGroup` registration; periodic sleep; per-resident active-task key; state names/numbers; event kinds; one task per resident; `asyncio` task dispatch; retry timing equal to that resident's interval; no resident execution timeout. `Resident.interval` defaults to 5 seconds and loop tick defaults to 0.25 seconds when directly instantiated.
- Configurable in integrated `serve`: `scheduler_tick_seconds`, `health_interval_seconds`, `sqlite_busy_timeout_ms`; resident enabled flag, schedule interval, inference endpoint/model/timeout, tool provider/endpoint/timeout/allowlist, continuation event types, prompt; optional reviewer, listener, and credential settings. `runtime/configuration.py:91-187` validates these JSON values and paths. The integrated service passes configured tick and per-resident interval into `Institution`/`Resident`.
- `Institution.add(Resident)` permits additional resident workers at startup, but there is no API to register arbitrary logical loops with `Institution`. `run()` hardcodes main and supervisory loops. The reviewer is an optional, separate `serve.py` worker loop (`:193-222`), not an `Institution`-registered loop; optional listeners run in their own threads.

### Key signatures

```python
Journal(path: str | Path)
Journal.transition(name, state, kind, detail="", next_due=None, failure=False)
Resident(name: str, work: Callable[[str], Awaitable[None]], interval=5.0, ready=None)
Institution(journal: Journal, *, tick_seconds=0.25)
Institution.add(resident: Resident) -> None
Institution.main_loop() / supervisory_loop() / run() / stop()  # async
Institution.health() -> dict
serve(db: Path, health_file: Path, config_dir: Path, ...) -> None  # async
```

## 2. CME

### Definition and intended responsibility

The authoritative expansion located in the repository is **Continuous Motion Engine**. `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md:139-144` says it belongs to Riverview as an institution and supports persistent scheduling, heartbeats, state observation, watchdogs, recovery, event history, and resource supervision; it expressly says it is not merely Grace's work-order mechanism. `docs/PROJECT_CHARTER.md:30` earlier identifies CME as a continuous operating environment. `docs/PUNCH_LIST.md:27` tracks resident participation (identity, state, heartbeat/scheduling slot without always-on inference) as open item R3-P003.

The audit and integrated source contain no separately named CME implementation, package, API, or registry. The nearest implemented correspondence is the generic `Institution` runtime above, plus the inbox, verification, and optional reviewer machinery composed by `serve.py`. The mapping is partial and must not be read as proof that every charter responsibility has been met.

### Current implementation and operational status

- Implemented in source: persistent resident state and event journal; scheduling and due-time checks; per-resident task dispatch; loop heartbeat ages; escaped-task supervision; failure retry timing; restart state normalization. In `serve.py`, configured resident inference is connected to inbox work, with optional assignment intake, conversation API, and independent review.
- Not found as CME implementation: a CME-named component/interface, general event subscription/dispatch API, shared resource supervisor/resource accounting, general loop-registration mechanism, or an always-on resident identity/slot registry separate from enabled resident worker configuration. The supervisor only tracks asyncio resident tasks and journal transitions.
- Operational evidence: audit `7e6d8d0`, §3 table, reports `r3-institution.service` active as PID 2663801, running `python -m runtime.serve` from immutable release source `8ab4b2a`, using `/home/admin1/.local/state/r3-runtime/institution.db` and a health file; it also records the native-tools service active. This is an audit-time observation, not a current liveness claim.
- Source metadata mismatch: `runtime/institution.py` header lines 7-11 describes the runtime as durable scheduling/supervision and says “no production deployment”; the audit's service/process observation records the integrated runtime deployed and active. The header is therefore stale or describes an earlier context.

### Interfaces and gaps against the documented design

- **Resident reasoning:** `serve.py:109-125` constructs `ResidentInference` from each enabled resident's prompt, configured HTTP inference endpoint/model, optional native-tools client, continuation event types, inbox, and conversation store. `ResidentInference.__call__` is the registered `Work` callback. The generic supervisor itself does not reason or select tools.
- **Supervision:** `Institution` owns lifecycle transitions, dispatch, watchdog collection, restart normalization, and loop heartbeat ages. `serve()` monitors runtime completion and health. No CME-level interface is declared between these pieces.
- **Events:** `Journal.events` records scheduler lifecycle transitions. Resident work events and turns live in `Inbox` tables in the same DB. `serve` adds verification tables via `VerificationLedger`; conversation and assignment components also use that database. These are adjacent data flows, not one declared CME event contract or subscriber API.
- **Persistence:** CME-like scheduler state is SQLite in `Journal`; integrated inbox, review, and conversations share the service DB/connection (reviewer uses its own thread-owned SQLite connection to the same path). The source labels the backend `sqlite-prototype`; the class doc says a PostgreSQL adapter is pending. The Charter Revision 2 review `:150-153` calls for PostgreSQL as the institutional structured-record/history foundation, so the implementation backend does not yet match that stated target.
- **Resource supervision:** the charter assigns it to CME, but the reviewed runtime exposes no shared CPU/memory/tool budget, resource claims, or resource allocation interface. Per-resident task concurrency is the only scheduler bound visible here.

## 3. Directly relevant dependencies

| Category | Evidence-based dependency |
|---|---|
| Essential execution | Python async runtime (`asyncio`, `TaskGroup`) and stdlib modules; `runtime/institution.py`; a `Journal`-compatible SQLite connection/store. For integrated startup, `runtime/serve.py` and `runtime/configuration.py` are required. The configured `ready` closures and inference handlers require the `Inbox` implementation and its schema. |
| Persistence | SQLite database file, schema initialization in `Journal`, `Inbox`, `VerificationLedger`, and optionally `ConversationStore`; filesystem access for DB parent and atomic health snapshot. SQLite WAL and busy timeout are set in `Journal`; `serve` overrides busy timeout from config. Scheduler state and inbox state are coupled to the same DB in this service. |
| Configuration | `config/runtime.json`; referenced resident JSON and prompt files under configured paths; optional reviewer JSON/prompt; optional listener and credential paths. `load_configuration(config_dir)` strictly validates required fields and rejects paths escaping the config root (`runtime/configuration.py:91-187`). Tick/health/busy-timeout and resident intervals/endpoints are configuration values; loop logic/state semantics remain code-defined. |
| Resident-specific | `ResidentInference` and its inbox semantics; configured prompt, model, inference endpoint, continuation types; optional `NativeTools` client and resident credential. These are necessary for the current configured reasoning workers but not for the generic scheduling mechanics with another `Resident.work` callback. |
| External services | Configured OpenAI-compatible inference HTTP endpoint is needed for resident reasoning. Native tool endpoint and credentials are only needed when `tools.provider == "r3-native"`; reviewer inference/tool endpoints are only needed when an independent reviewer is configured. Assignment intake and conversation listeners are optional; both require token files when enabled. |
| Incidental to the supervisory core | Independent reviewer/evaluator loop, assignment intake server, conversation API server/store, native-tool discovery probes, verification counts, and atomic health-file publication are composed by `serve()` but are not imported by `Institution` or required by its two loops. They are relevant only if operating the full current service behavior. |

## 4. Unresolved technical questions

1. Does the Steward intend “CME” to denote precisely the runtime loop, or a broader institutional operating environment? The charter specifies responsibilities but no implementation contract or formal mapping to `Institution`.
2. What resident roster/identity and non-inference heartbeat semantics satisfy R3-P003? Current registration is for enabled workers at startup; no separate persistent roster/slot service is present in the examined source.
3. What does charter “resource supervision” require, and which resource dimensions/ownership are intended? No requirement or implemented interface was located.
4. Which components count as CME event history: only `Journal.events`, or inbox, conversation, assignment, and review records as well? No unified event schema/retention/replay contract was found.
5. Is SQLite the accepted operating backend or only transitional? Runtime source calls it a prototype; the charter review names PostgreSQL as the intended structured persistence foundation.
6. Are arbitrary logical loops expected to be independently registerable? Current `Institution` registers residents only and hardcodes two loops; `serve` separately creates optional workers/listener threads.
7. What is the authoritative current operational status after the audit snapshot? This investigation relies on the audit's timestamped observation and did not inspect a live host.

## References

- `runtime/institution.py` (`Journal`, `Resident`, `Institution.add`, `_execute`, `main_loop`, `supervisory_loop`, `run`, `stop`, `health`) at deployed source commit `8ab4b2ab1669b2bbc55467ec2cdd9bdc9f489135`.
- `runtime/serve.py` (`serve`, `atomic_snapshot`, `main`) at the same source commit.
- `runtime/configuration.py` (`load_configuration`, `_service_config`, `_credential_config`) and `runtime/resident_inference.py` (`Inbox`, `InferenceEndpoint`, `ResidentInference`) at the same source commit.
- `docs/PROJECT_CHARTER_REVISION_2_REVIEW.md:139-153`, `docs/PROJECT_CHARTER.md:30`, and `docs/PUNCH_LIST.md:27` for CME definition, persistence direction, and open participation requirement.
- `docs/architecture/R3_MODULAR_ARCHITECTURE_AUDIT_2026-11-05.md:59-63,97-110,206-220` at audit commit `7e6d8d053b97837866470db4549331d839bf8ba8` for source mapping, service observation, and the audit's loop characterization.
