# R3 CONTROLLED SOURCE
# File: runtime/serve.py
# Component: R3-INSTITUTION-RUNTIME
# File Revision: 1.0.0
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
# History/Predecessor: New file
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

from runtime.institution import Institution, Journal


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
                "resident_execution_connected": False,
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
