# R3 CONTROLLED SOURCE
# File: tests/test_admission.py
# Component: R3-SHUTDOWN-ADMISSION-REGRESSION
# Purpose: Permanently verify admission closes atomically and drains admitted mutations.
# Tests: python3 -m unittest tests.test_admission
from __future__ import annotations

import threading
import unittest

from runtime.admission import AdmissionGate


class AdmissionGateTests(unittest.TestCase):
    def test_close_rejects_racing_admission_and_drains_existing_mutation(self):
        gate = AdmissionGate()
        entered = threading.Event()
        finished = threading.Event()
        release = threading.Event()
        close_started = threading.Event()
        close_returned = threading.Event()

        def admitted_mutation():
            with gate.enter() as admitted:
                if admitted:
                    entered.set()
                    release.wait(timeout=2)
                    finished.set()

        def close_gate():
            close_started.set()
            gate.close()
            close_returned.set()

        writer = threading.Thread(target=admitted_mutation)
        writer.start()
        self.assertTrue(entered.wait(timeout=2))
        closer = threading.Thread(target=close_gate)
        closer.start()
        self.assertTrue(close_started.wait(timeout=2))
        self.assertTrue(gate.wait_closed(timeout=2))

        with gate.enter() as admitted:
            self.assertFalse(admitted)
        self.assertEqual(1, gate.in_flight)
        self.assertFalse(close_returned.is_set())

        release.set()
        writer.join(timeout=2)
        closer.join(timeout=2)
        self.assertFalse(writer.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertTrue(close_returned.is_set())
        self.assertTrue(finished.is_set())
        self.assertEqual(0, gate.in_flight)

    def test_new_gate_is_open_for_normal_operation_after_restart(self):
        gate = AdmissionGate()
        with gate.enter() as admitted:
            self.assertTrue(admitted)
        self.assertFalse(gate.is_closed)
        self.assertEqual(0, gate.in_flight)


if __name__ == "__main__":
    unittest.main()
