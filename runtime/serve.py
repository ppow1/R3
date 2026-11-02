# R3 CONTROLLED SOURCE
# File: runtime/serve.py
# Component: R3-INSTITUTION-RUNTIME
# File Revision: 1.0.3
# Created: 2026-11-01 UTC (exact time not verified)
# Created By: ChatGPT GPT-6
# Purpose: Start and monitor R3 institutional scheduler and supervisor.
# Execution Model: Continuous async process; no synthetic resident tasks.
# Observability: Atomic JSON heartbeat file and SQLite event journal.
# Dependencies: Python 3.12 stdlib; runtime/institution.py.
# Authority: R3 Charter Revision 2; does not modify R2 or start inference.
# Changed: 2026-11-01 UTC | R3-RUNTIME-002 | First executable service entrypoint
# Supersedes: None
# Contracts: docs/PROJECT_CHARTER_REVISION_2_REVIEW.md
# Tests: Initial service smoke test pending
# Changed: 2026-11-02 UTC | R3-GRACE-002 | Register configured inference resident
# Changed: 2026-11-02 UTC | R3-RUNTIME-004 | Schedule Grace only when durable inbox has pending work
# Changed: 2026-11-02 UTC | R3-GRACE-005 | Wire configured existing llama.cpp tool endpoint without enabling by assumption
# History/Predecessor: Git blob 8c0e187e652dfab7a2d65b5272858e27d6c494b0
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
import tempfile
import time

from runtime.institution import Institution, Journal, Resident
from runtime.llama_tools import LlamaTools
from runtime.resident_inference import Inbox, InferenceEndpoint, ResidentInference


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


async def serve(db: Path, health_file: Path, interval: float) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    journal = Journal(db)
    institution = Institution(journal)
    inbox = Inbox(journal.db)
    endpoint_url = os.environ.get("R3_GRACE_INFERENCE_URL")
    model_name = os.environ.get("R3_GRACE_MODEL")
    grace_registered = bool(endpoint_url and model_name)
    tools_url = os.environ.get("R3_GRACE_TOOLS_URL")
    grace_tools = LlamaTools(tools_url) if tools_url else None
    if grace_registered:
        handler = ResidentInference(
            inbox, InferenceEndpoint(endpoint_url, model_name),
            tools=grace_tools,
            system_prompt=(
                "You are Grace, Riverview Director of Operations, accountable to the Steward. "
                "Distinguish evidence from inference and never claim an action occurred without "
                "a verified tool result."
            ),
        )
        institution.add(Resident(
            name="Grace", work=handler,
            ready=lambda name: inbox.db.execute(
                "SELECT EXISTS(SELECT 1 FROM resident_inbox WHERE resident=? AND status IN ('PENDING','PROCESSING'))",
                (name,),
            ).fetchone()[0] == 1,
        ))
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, institution._stop.set)
        except NotImplementedError:
            pass
    runtime_task = asyncio.create_task(institution.run(), name="r3-institution")
    try:
        while not institution._stop.is_set():
            if runtime_task.done():
                await runtime_task
                raise RuntimeError("Institution runtime exited unexpectedly")
            status = institution.health()
            status.update({
                "service": "r3-institution",
                "pid": os.getpid(),
                "observed_at": time.time(),
                "registered_residents": len(institution.residents),
                "resident_execution_connected": grace_registered,
                "resident_inference_connected": grace_registered,
                "resident_tool_execution_connected": False,
                "resident_tool_execution_configured": grace_tools is not None,
                "resident_inbox_pending": journal.db.execute(
                    "SELECT count(*) FROM resident_inbox WHERE status IN ('PENDING','PROCESSING')"
                ).fetchone()[0],
                "database_backend": "sqlite-prototype",
            })
            atomic_snapshot(health_file, status)
            await asyncio.sleep(interval)
    finally:
        await institution.stop()
        await runtime_task


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--health-file", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    asyncio.run(serve(args.db, args.health_file, args.interval))


if __name__ == "__main__":
    main()
