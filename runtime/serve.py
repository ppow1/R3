# R3 CONTROLLED SOURCE
# File: runtime/serve.py
# Component: R3-INSTITUTION-RUNTIME
# File Revision: 1.2.4
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
# History/Predecessor: Git blob dc5a16dd64b4865298e746cdbcf00a6afbb4f513
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
from runtime.resident_credentials import load_resident_credential
from runtime.assignment_intake import create_server as create_assignment_intake_server
from runtime.conversations import ConversationStore, create_server as create_conversation_server
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


async def serve(db: Path, health_file: Path, config_dir: Path, credential_dir: Path | None = None,
               assignment_intake_port: int | None = None,
               assignment_intake_token_file: Path | None = None,
               assignment_intake_authority_db: Path | None = None,
               conversation_port: int | None = None,
               conversation_token_file: Path | None = None) -> None:
    configuration = load_configuration(config_dir)
    settings = configuration["runtime"]
    interval = settings["health_interval_seconds"]
    db.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(db)
    journal.db.execute("PRAGMA busy_timeout=" + str(int(settings["sqlite_busy_timeout_ms"])))
    institution = Institution(journal, tick_seconds=settings["scheduler_tick_seconds"])
    inbox = Inbox(journal.db)
    conversation_store = ConversationStore(journal.db)
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
            tools = NativeTools(
                tool_settings["endpoint"],
                timeout=tool_settings["timeout_seconds"],
                allowed_tools=tuple(tool_settings["allowed_tools"]),
                credential=load_resident_credential(
                    credential_dir, resident["name"]
                ),
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
            conversation_store=conversation_store,
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

    intake_server = None
    intake_thread = None
    if (assignment_intake_port is None) != (assignment_intake_token_file is None):
        raise ConfigurationError("Assignment intake requires both port and token file")
    if assignment_intake_authority_db is not None:
        if assignment_intake_port is None:
            raise ConfigurationError("Assignment resumption authority requires assignment intake")
        if not assignment_intake_authority_db.is_absolute():
            raise ConfigurationError("Assignment intake authority database must be absolute")
    if assignment_intake_port is not None:
        continuing = {
            definition["settings"]["name"]
            for definition in configuration["residents"]
            if "RESIDENT_ACTIVITY" in definition["settings"].get("continuation_event_types", [])
        }
        intake_server = create_assignment_intake_server(
            db, assignment_intake_token_file, set(registered), continuing,
            host="127.0.0.1", port=assignment_intake_port,
            authority_db=assignment_intake_authority_db)
        intake_thread = threading.Thread(
            target=intake_server.serve_forever, name="r3-assignment-intake", daemon=True)
        intake_thread.start()

    conversation_server = None
    conversation_thread = None
    if (conversation_port is None) != (conversation_token_file is None):
        raise ConfigurationError("Conversation API requires both port and token file")
    if conversation_port is not None:
        resident_actions = {
            definition["settings"]["name"]: list(definition["settings"]["tools"]["allowed_tools"])
            for definition in configuration["residents"]
            if definition["settings"]["enabled"]
        }
        conversation_server = create_conversation_server(
            db, conversation_token_file, set(registered), resident_actions,
            port=conversation_port)
        conversation_thread = threading.Thread(
            target=conversation_server.serve_forever, name="r3-conversation-api", daemon=True)
        conversation_thread.start()

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
            inference_response_observed = journal.db.execute(
                "SELECT EXISTS(SELECT 1 FROM resident_turns t "
                "WHERE t.kind='ASSISTANT')"
            ).fetchone()[0]
            status.update({
                "service": "r3-institution",
                "health_schema_version": 2,
                "pid": os.getpid(),
                "observed_at": time.time(),
                "registered_residents": len(registered),
                "resident_execution_configured": bool(registered),
                "resident_active_executions": status["active"],
                "resident_inference_configured": bool(registered),
                "resident_inference_response_observed": bool(inference_response_observed),
                "resident_tool_discovery_connected": tool_connected,
                "resident_tool_execution_status": "unverified",
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
                "assignment_intake_enabled": intake_server is not None,
                "assignment_intake_connected": bool(intake_thread and intake_thread.is_alive()),
                "conversation_api_enabled": conversation_server is not None,
                "conversation_api_connected": bool(conversation_thread and conversation_thread.is_alive()),
                "database_backend": "sqlite-prototype",
            })
            atomic_snapshot(health_file, status)
            await asyncio.sleep(interval)
    finally:
        if intake_server is not None:
            await asyncio.to_thread(intake_server.shutdown)
            intake_server.server_close()
            if intake_thread is not None:
                intake_thread.join(timeout=5)
        if conversation_server is not None:
            await asyncio.to_thread(conversation_server.shutdown)
            conversation_server.server_close()
            if conversation_thread is not None:
                conversation_thread.join(timeout=5)
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
    parser.add_argument("--resident-credential-dir", type=Path)
    parser.add_argument("--assignment-intake-port", type=int)
    parser.add_argument("--assignment-intake-token-file", type=Path)
    parser.add_argument("--assignment-intake-authority-db", type=Path)
    parser.add_argument("--conversation-port", type=int)
    parser.add_argument("--conversation-token-file", type=Path)
    args = parser.parse_args()
    # Runtime JSON is authoritative when a capability is configured there.
    # Legacy command-line options remain supported for older deployments.
    runtime_settings = load_configuration(args.config_dir)["runtime"]
    conversation = runtime_settings["_conversation_api"]
    intake = runtime_settings["_assignment_intake"]
    credential_dir = runtime_settings["_resident_credentials"]

    def resolve_listener(name, configured, cli_port, cli_token):
        if configured is None:
            return cli_port, cli_token
        if cli_port is not None and cli_port != configured["port"]:
            raise ConfigurationError(f"{name} CLI port conflicts with runtime.json")
        if cli_token is not None and cli_token != configured["token_file"]:
            raise ConfigurationError(f"{name} CLI token file conflicts with runtime.json")
        return configured["port"], configured["token_file"]

    conversation_port, conversation_token_file = resolve_listener(
        "conversation_api", conversation, args.conversation_port, args.conversation_token_file)
    intake_port, intake_token_file = resolve_listener(
        "assignment_intake", intake, args.assignment_intake_port, args.assignment_intake_token_file)
    configured_authority_db = intake.get("authority_database") if intake is not None else None
    if (configured_authority_db is not None and args.assignment_intake_authority_db is not None
            and configured_authority_db != args.assignment_intake_authority_db):
        raise ConfigurationError("Assignment intake authority database conflicts with runtime.json")
    authority_db = configured_authority_db or args.assignment_intake_authority_db
    if authority_db is not None and not authority_db.is_absolute():
        raise ConfigurationError("Assignment intake authority database must be absolute")
    if credential_dir is not None and args.resident_credential_dir is not None:
        if credential_dir != args.resident_credential_dir:
            raise ConfigurationError("Resident credential directory conflicts with runtime.json")
    asyncio.run(serve(
        args.db, args.health_file, args.config_dir,
        credential_dir=credential_dir or args.resident_credential_dir,
        assignment_intake_port=intake_port,
        assignment_intake_token_file=intake_token_file,
        assignment_intake_authority_db=authority_db,
        conversation_port=conversation_port,
        conversation_token_file=conversation_token_file,
    ))


if __name__ == "__main__":
    main()
