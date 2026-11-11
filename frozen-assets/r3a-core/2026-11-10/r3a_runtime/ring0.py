"""
R3 CONTROLLED SOURCE
File: r3a_runtime/ring0.py
Component: R3A-RING0-SUPERVISOR
File Revision: 1.0.1
Created: 2026-11-06T15:25:00Z
Created By: Codex GPT-6
Purpose: Provide the minimal persistent Ring 0 process and supervise CME start, health, failure and restart.
Execution Model: systemd user service with independent CME child process and process watchdog notification.
Observability: PostgreSQL process transitions, heartbeat, exit code and restart outcome.
Dependencies: PostgreSQL; external R3A bootstrap JSON; r3a_runtime.db/control.
Authority: AP1 / R3A-019 authorized by Steward; isolated R3A service only.
Changed: 2026-11-06T15:25:00Z | R3A-AP0-M1 | Codex GPT-6 | Implement Ring 0 CME watchdog/restart loop.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Add startup grace, schema readiness guard and watchdog notification during CME backoff.
Changed: 2026-11-06T18:16:39Z | R3A-019 | Codex GPT-6 | Bound CME termination and kill only the isolated child after the configured grace interval.
Supersedes: None.
Contracts: AP0-001/002/011; AP0-M1 D1/D3; STM-001/003.
Tests: tests/test_r3a_ap1.py; live isolated R3A restart verification pending this revision.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from .config import Settings, load_settings
from .control import control_request
from .db import Store
from .timestamp_presentation import format_timestamp


def systemd_notify(message: str) -> None:
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):  # systemd abstract namespace
        address = "\0" + address[1:]
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.connect(address)
        sock.sendall(message.encode("utf-8"))
    finally:
        sock.close()


class Ring0:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.shutdown = asyncio.Event()
        self.child: asyncio.subprocess.Process | None = None
        self.last_child_pid: int | None = None
        self.store: Store | None = None
        self.restart_failures = 0
        self.ready_recorded = False
        self.child_started_at: float | None = None
        self.repo_root = Path(__file__).resolve().parent.parent

    def _log(self, message: str, *, error: bool = False) -> None:
        timestamp = format_timestamp(datetime.now(timezone.utc), self.settings.presentation_timezone)
        print(f"{timestamp} ring0 {message}", file=sys.stderr if error else sys.stdout, flush=True)

    async def _ensure_store(self) -> Store | None:
        if self.store is not None:
            return self.store
        try:
            store = Store(self.settings)
            await store.open()
            self.store = store
            return store
        except Exception as exc:
            self._log(f"database observation unavailable: {type(exc).__name__}: {exc}", error=True)
            return None

    async def _record(self, component: str, pid: int, state: str, health: str,
                      reason: str, details: dict | None = None, *, initial: bool = False) -> None:
        store = await self._ensure_store()
        if store is None:
            return
        try:
            ready = await store.rows(
                "SELECT to_regclass('r3a.runtime_entities') IS NOT NULL AS ready"
            )
            if not ready[0]["ready"]:
                return
            await store.record_process_state(component, pid, state, health, reason,
                                             details or {}, initial=initial)
        except Exception as exc:
            self._log(f"could not persist {component} {state}: {type(exc).__name__}: {exc}", error=True)

    async def _heartbeat(self, state: str, details: dict | None = None) -> None:
        store = await self._ensure_store()
        if store is None:
            return
        try:
            ready = await store.rows("SELECT to_regclass('r3a.config_current') IS NOT NULL AS ready")
            if not ready[0]["ready"]:
                return
            await store.process_heartbeat("ring0", os.getpid(), state,
                                          "healthy" if state == "RUNNING" else "degraded",
                                          details or {})
        except Exception as exc:
            self._log(f"heartbeat persistence unavailable: {type(exc).__name__}: {exc}", error=True)

    async def _start_cme(self) -> None:
        self.child = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "r3a_runtime.cme", "--config", str(self.settings.source_path),
            cwd=self.repo_root,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=None,
            start_new_session=True,
        )
        self.last_child_pid = self.child.pid
        self.child_started_at = asyncio.get_running_loop().time()
        self._log(f"launched cme pid={self.child.pid}")

    async def _stop_cme(self) -> None:
        child = self.child
        if child is None or child.returncode is not None:
            return
        try:
            await control_request(self.settings.control_socket, "stop", timeout=2.0)
        except Exception:
            pass
        try:
            await asyncio.wait_for(child.wait(), timeout=self.settings.heartbeat_stale_after_seconds)
        except asyncio.TimeoutError:
            child.terminate()
            try:
                await asyncio.wait_for(child.wait(), timeout=self.settings.heartbeat_stale_after_seconds)
            except asyncio.TimeoutError:
                child.kill()
                await child.wait()

    async def _check_cme(self) -> tuple[bool, dict]:
        child = self.child
        if child is None:
            return False, {"reason": "CME process has not been created"}
        if child.returncode is not None:
            return False, {"reason": "CME process exited", "exit_code": child.returncode,
                           "pid": child.pid}
        try:
            result = await control_request(self.settings.control_socket, "health", timeout=2.0)
        except Exception as exc:
            grace = max(10.0, self.settings.heartbeat_stale_after_seconds * 2)
            startup_age = (asyncio.get_running_loop().time() - (self.child_started_at or 0))
            if startup_age <= grace:
                return True, {"pid": child.pid, "state": "STARTING",
                              "health": "unknown", "startup_age_seconds": startup_age,
                              "startup_grace_seconds": grace,
                              "reason": f"CME startup probe pending: {type(exc).__name__}: {exc}"}
            return False, {"reason": f"CME health probe failed: {type(exc).__name__}: {exc}",
                           "pid": child.pid}
        age = result.get("scheduler_tick_age_seconds")
        if not isinstance(age, (int, float)) or age > self.settings.heartbeat_stale_after_seconds:
            return False, {"reason": "CME scheduler heartbeat is stale", "pid": child.pid,
                           "scheduler_tick_age_seconds": age, "health_result": result}
        return True, {"pid": child.pid, "scheduler_tick_age_seconds": age,
                      "module_pid": result.get("module_pid"), "module_id": result.get("module_id"),
                      "module_version": result.get("module_version")}

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.shutdown.set)
            except NotImplementedError:
                pass
        systemd_notify("STATUS=Ring 0 starting isolated CME supervision")
        await self._start_cme()
        systemd_notify("READY=1\nSTATUS=Ring 0 supervising CME")
        watchdog_usec = int(os.environ.get("WATCHDOG_USEC", "0") or 0)
        notify_interval = min(self.settings.heartbeat_interval_seconds,
                              max(0.1, watchdog_usec / 2_000_000) if watchdog_usec else self.settings.heartbeat_interval_seconds)
        while not self.shutdown.is_set():
            healthy, details = await self._check_cme()
            if healthy:
                self.restart_failures = 0
                store = await self._ensure_store()
                state = "RUNNING" if details.get("health") != "unknown" else "STARTING"
                if store is not None and state == "RUNNING" and not self.ready_recorded:
                    await store.begin_process("ring0", os.getpid())
                health = "healthy" if state == "RUNNING" else "degraded"
                await self._record("ring0", os.getpid(), state, health,
                                   "Ring 0 supervision active", details,
                                   initial=not self.ready_recorded)
                if state == "RUNNING":
                    self.ready_recorded = True
                await self._heartbeat(state, details)
                systemd_notify("WATCHDOG=1\nSTATUS=CME " + str(details.get("state", "healthy"))
                               + "; pid=" + str(details.get("pid")))
                try:
                    await asyncio.wait_for(self.shutdown.wait(), timeout=notify_interval)
                except asyncio.TimeoutError:
                    pass
                continue

            reason = details.get("reason", "CME unavailable")
            self._log(f"detected cme failure: {reason}", error=True)
            if self.ready_recorded:
                await self._record("ring0", os.getpid(), "DEGRADED", "degraded",
                                   "CME health check failed", details)
            if self.last_child_pid is not None:
                await self._record("cme", self.last_child_pid, "FAILED", "unavailable",
                                   reason, details)
            await self._heartbeat("DEGRADED", details)
            systemd_notify("WATCHDOG=1\nSTATUS=CME restart pending")
            await self._stop_cme()
            if self.shutdown.is_set():
                break
            delay = min(self.settings.restart_initial_seconds * (2 ** min(self.restart_failures, 20)),
                        self.settings.restart_max_seconds)
            self.restart_failures += 1
            try:
                await asyncio.wait_for(self.shutdown.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                pass
            await self._record("cme", self.last_child_pid or os.getpid(), "RESTARTING", "starting",
                               "Ring 0 starting replacement CME process",
                               {"retry_number": self.restart_failures, "backoff_seconds": delay})
            try:
                await self._start_cme()
            except Exception as exc:
                self._log(f"could not create CME process: {type(exc).__name__}: {exc}", error=True)

        await self._record("ring0", os.getpid(), "STOPPING", "stopping", "Ring 0 shutdown requested")
        await self._stop_cme()
        await self._record("ring0", os.getpid(), "STOPPED", "stopped", "Ring 0 shutdown complete")
        if self.store:
            await self.store.close()
        systemd_notify("STOPPING=1\nSTATUS=Ring 0 stopped")


async def run(config_path: str) -> None:
    settings = load_settings(config_path)
    await Ring0(settings).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="R3A AP0 Ring 0 supervisor")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
