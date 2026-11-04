# R3 CONTROLLED SOURCE
# File: runtime/serve.py
# Component: R3-INSTITUTION-RUNTIME
# File Revision: 1.2.5
# Created: 2026-11-01 UTC (exact time not verified)
# Created By: ChatGPT GPT-6
# Purpose: Start and monitor R3 institutional scheduler and supervisor.
# Execution Model: Continuous async process; no synthetic resident tasks.
# Observability: Atomic JSON heartbeat file and SQLite event journal.
# Dependencies: Python 3.12 stdlib; runtime/institution.py.
# Authority: R3 Charter Revision 2; does not modify R2 or start inference.
# Changed: 2026-11-01 UTC | R3-RUNTIME-002 | First executable service entrypoint
# Changed: 2026-11-02 UTC | R3-VERIFY-LEARN-009 | Expose independent verification backlog.
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
# Tests: Initial service smoke test pending
# Changed: 2026-11-02 UTC | R3-GRACE-002 | Register configured inference resident
# Changed: 2026-11-02 UTC | R3-RUNTIME-004 | Schedule Grace only when durable inbox has pending work
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Wire configured existing llama.cpp tool endpoint without enabling by assumption
# Changed: 2026-11-02 UTC | R3-CONFIG-001 | Load generic residents and runtime settings from files.
# Changed: 2026-11-02 UTC | R3-TOOLS-001 | Wire configured native tool client.
# Changed: 2026-11-03T02:00:13.409Z | R3-VERIFY-WIRING-003 | Codex | Supply a read-only journal observation for criterion-level review.
# Changed: 2026-11-03T02:27:54.002Z | R3-REVIEWER-OPTIONAL-001 | Codex | Run the reviewer worker only when an optional reviewer is configured.
# Changed: 2026-11-04 UTC | R3-GRACE-OBJECTIVES-005 | Opt-in external resident credential file for actual governed tool calls; no credential or grant issuance.\n# History/Predecessor: Git blob dc5a16dd64b4865298e746cdbcf00a6afbb4f513
"""R3 runtime infrastructure entrypoint.

Starts the scheduler and supervisor without inventing resident activities.
Resident execution handlers must be explicitly registered when integrated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import sqlite3
import tempfile
import threading
import time

from runtime.institution import Institution, Journal, Resident
from runtime.native_tools import NativeTools
from runtime.configuration import load_configuration, ConfigurationError
from runtime.resident_inference import Inbox, InferenceEndpoint, ResidentInference
from runtime.verification import IndependentReviewWorker, VerificationLedger
from runtime.independent_reviewer import IndependentReviewer


def atomic_snapshot(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".r3-health-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


async def serve(db: Path, health_file: Path, config_dir: Path) -> None:
    configuration = load_configuration(config_dir)
    settings = configuration["runtime"]
    interval = settings["health_interval_seconds"]
    db.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(db)
    journal.db.execute("PRAGMA busy_timeout=" + str(int(settings["sqlite_busy_timeout_ms"])))
    institution = Institution(journal, tick_seconds=settings["scheduler_tick_seconds"])
    inbox = Inbox(journal.db)
    registered = []
    configured_tools = 0
    tool_clients = []
    for definition in configuration["residents"]:
        resident = definition["settings"]
        if not resident["enabled"]:
            continue
        inference = resident["inference"]
        tool_settings = resident["tools"]
        provider = tool_settings["provider"]
        if provider == "none":
            tools = None
        elif provider == "r3-native":
            credential_path = tool_settings.get("credential_file")
            credential_provider = None
            if credential_path is not None:
                # Read at invocation so a revoked or rotated credential is not
                # cached in the running resident. Never log the secret.
                def read_credential(path=Path(credential_path)):
                    return path.read_text(encoding="utf-8").strip()
                credential_provider = read_credential
            tools = NativeTools(
                tool_settings["endpoint"],
                timeout=tool_settings["timeout_seconds"],
                allowed_tools=tuple(tool_settings["allowed_tools"]),
                credential_provider=credential_provider,
            )
        else:
            raise ConfigurationError("Unknown tool provider")
        if tools is not None:
            configured_tools += 1
            tool_clients.append(tools)
        handler = ResidentInference(
            inbox,
            InferenceEndpoint(inference["endpoint"], inference["model"],
                              timeout=inference["timeout_seconds"]),
            tools=tools,
            system_prompt=definition["system_prompt"],
            continuation_event_types=tuple(resident.get("continuation_event_types", [])),
        )
        institution.add(Resident(
            name=resident["name"], work=handler,
            interval=resident["schedule_interval_seconds"],
            ready=lambda name: inbox.db.execute(
                "SELECT EXISTS(SELECT 1 FROM resident_inbox WHERE resident=? AND status IN ('PENDING','PROCESSING'))",
                (name,),
            ).fetchone()[0] == 1,
        ))
        registered.append(resident["name"])
    reviewer_config = configuration["reviewer"]
    reviewer_settings = None
    evaluator = None
    if reviewer_config is not None:
        reviewer_settings = reviewer_config["settings"]
        if reviewer_settings["name"] in registered:
            raise ConfigurationError("Independent reviewer must have a distinct identity from every resident")
        if reviewer_settings["manager"] not in registered:
            raise ConfigurationError("Reviewer manager must be a registered resident")
        reviewer_tools = NativeTools(
            reviewer_settings["tools"]["endpoint"],
            timeout=reviewer_settings["tools"]["timeout_seconds"],
            allowed_tools=tuple(reviewer_settings["tools"]["allowed_tools"]),
        )
        reviewer_endpoint = InferenceEndpoint(
            reviewer_settings["inference"]["endpoint"],
            reviewer_settings["inference"]["model"],
            timeout=reviewer_settings["inference"]["timeout_seconds"],
        )
        evaluator = IndependentReviewer(
            reviewer_endpoint, reviewer_tools, reviewer_config["system_prompt"], journal_path=db)
    VerificationLedger(journal.db)
    reviewer_state = {"connected": False, "last_error": None}
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, institution._stop.set)
        except NotImplementedError:
            pass
    runtime_task = asyncio.create_task(institution.run(), name="r3-institution")
    verification_stop = threading.Event()
    def verification_loop() -> None:
        # Own the reviewer connection in this dedicated thread. The scheduler keeps
        # its own SQLite connection and never shares a connection across threads.
        review_db = sqlite3.connect(str(db), timeout=settings["sqlite_busy_timeout_ms"] / 1000)
        review_db.execute("PRAGMA busy_timeout=" + str(int(settings["sqlite_busy_timeout_ms"])))
        try:
            reviewer_worker = IndependentReviewWorker(
                VerificationLedger(review_db), reviewer_settings["name"], evaluator,
                manager=reviewer_settings["manager"])
            while not verification_stop.is_set():
                try:
                    evaluator.probe()
                    reviewer_state["connected"] = True
                    reviewer_state["last_error"] = None
                except Exception as exc:
                    reviewer_state["connected"] = False
                    reviewer_state["last_error"] = type(exc).__name__
                if reviewer_state["connected"]:
                    try:
                        reviewer_worker.process_pending()
                    except Exception as exc:
                        # Keep the durable request pending; the next cycle retries it.
                        reviewer_state["last_error"] = type(exc).__name__
                verification_stop.wait(interval)
        finally:
            review_db.close()
    verification_task = None
    if reviewer_settings is not None:
        verification_task = asyncio.create_task(
            asyncio.to_thread(verification_loop), name="r3-independent-reviewer")
    try:
        while not institution._stop.is_set():
            if runtime_task.done():
                await runtime_task
                raise RuntimeError("Institution runtime exited unexpectedly")
            tool_probes = await asyncio.gather(
                *(asyncio.to_thread(client.discover) for client in tool_clients),
                return_exceptions=True,
            )
            tool_connected = bool(tool_probes) and all(
                not isinstance(result, BaseException) for result in tool_probes)
            status = institution.health()
            status.update({
                "service": "r3-institution",
                "pid": os.getpid(),
                "observed_at": time.time(),
                "registered_residents": len(registered),
                "resident_execution_connected": bool(registered),
                "resident_inference_connected": bool(registered),
                "resident_tool_execution_connected": tool_connected,
                "resident_tool_execution_configured": bool(configured_tools),
                "resident_inbox_pending": journal.db.execute(
                    "SELECT count(*) FROM resident_inbox WHERE status IN ('PENDING','PROCESSING')"
                ).fetchone()[0],
                "verification_pending": journal.db.execute("SELECT count(*) FROM verification_requests WHERE status=?",( "PENDING",)).fetchone()[0],
                "verification_accepted": journal.db.execute("SELECT count(*) FROM verification_requests WHERE status=?",( "ACCEPTED",)).fetchone()[0],
                "verification_needs_work": journal.db.execute("SELECT count(*) FROM verification_requests WHERE status=?",( "NEEDS_WORK",)).fetchone()[0],
                "verification_inconclusive": journal.db.execute("SELECT count(*) FROM verification_requests WHERE status=?",( "INCONCLUSIVE",)).fetchone()[0],
                "independent_reviewer_connected": reviewer_state["connected"],
                "independent_reviewer_last_error": reviewer_state["last_error"],
                "database_backend": "sqlite-prototype",
            })
            atomic_snapshot(health_file, status)
            await asyncio.sleep(interval)
    finally:
        await institution.stop()
        if verification_task is not None:
            verification_stop.set()
            await asyncio.gather(verification_task, return_exceptions=True)
        await runtime_task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--health-file", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(serve(args.db, args.health_file, args.config_dir))


if __name__ == "__main__":
    main()
