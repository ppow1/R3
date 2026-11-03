# R3 CONTROLLED SOURCE
# File: runtime/admission.py
# Component: R3-SHUTDOWN-ADMISSION
# Purpose: Close write admission atomically and drain admitted database mutations.
# Tests: tests/test_admission.py
"""Thread-safe admission gate shared by API and review work during shutdown."""
from __future__ import annotations

from contextlib import contextmanager
import threading


class AdmissionGate:
    """Reject new work after closure and wait for admitted mutations to finish."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._closed = False
        self._closed_event = threading.Event()
        self._in_flight = 0

    @contextmanager
    def enter(self):
        with self._condition:
            accepted = not self._closed
            if accepted:
                self._in_flight += 1
        try:
            yield accepted
        finally:
            if accepted:
                with self._condition:
                    self._in_flight -= 1
                    if self._in_flight == 0:
                        self._condition.notify_all()

    def close(self) -> None:
        """Close admission first, then wait for mutations already admitted."""
        with self._condition:
            self._closed = True
            self._closed_event.set()
            while self._in_flight:
                self._condition.wait()

    @property
    def is_closed(self) -> bool:
        with self._condition:
            return self._closed

    def wait_closed(self, timeout: float | None = None) -> bool:
        return self._closed_event.wait(timeout)

    @property
    def in_flight(self) -> int:
        with self._condition:
            return self._in_flight
