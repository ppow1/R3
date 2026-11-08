"""Timezone presentation tests; durable values and contracts remain UTC."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from r3a_runtime.config import ConfigurationError, load_settings, sanitized_config
from r3a_runtime.timestamp_presentation import (
    DEFAULT_PRESENTATION_TIMEZONE,
    TimestampPresentationError,
    format_timestamp,
    human_report,
    resolve_timezone,
)


ROOT = Path(__file__).resolve().parents[1]


def _bootstrap(path: Path, timezone_name: str | None = None) -> Path:
    data = path.parent / "data"
    source = ROOT / "r3a_runtime/observer_module.py"
    value = {
        "schema_version": 1,
        "instance_id": "r3a_time_test",
        "paths": {
            "data_dir": str(data),
            "postgres_socket_dir": str(data / "pg"),
            "control_socket": str(data / "control.sock"),
            "diagnostics_socket": str(data / "diagnostics.sock"),
            "module_socket": str(data / "module.sock"),
            "machine_catalog_dir": str(path.parent / "machines"),
        },
        "postgres": {"database": "r3a_time_test", "user": "r3a_runtime",
                     "socket_dir": str(data / "pg"), "port": 55432},
        "module": {"module_id": "foundation.observer", "version": "1.0.0",
                   "contract_id": "r3a.module.v1", "protocol_major": 1,
                   "protocol_minor": 0, "capabilities": ["host.process.read"],
                   "owner": "R3A-test", "entrypoint": "r3a_runtime.observer_module",
                   "source": str(source),
                   "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "timing": {"observer_interval_seconds": 1, "scheduler_interval_seconds": 1,
                   "lease_seconds": 30, "heartbeat_interval_seconds": 5,
                   "heartbeat_stale_after_seconds": 15, "diagnostic_stale_after_seconds": 30,
                   "restart_initial_seconds": 1, "restart_max_seconds": 5,
                   "worker_concurrency": 1},
    }
    if timezone_name is not None:
        value["presentation_timezone"] = timezone_name
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class TimestampPresentationTests(unittest.TestCase):
    def test_winter_summer_and_dst_transition_presentations(self):
        self.assertIn("2026-01-15T07:00:00-05:00 EST [America/New_York]",
                      format_timestamp("2026-01-15T12:00:00Z"))
        self.assertIn("2026-07-15T08:00:00-04:00 EDT [America/New_York]",
                      format_timestamp("2026-07-15T12:00:00Z"))
        before_spring = format_timestamp("2026-03-08T06:59:59Z")
        after_spring = format_timestamp("2026-03-08T07:00:00Z")
        self.assertIn("01:59:59-05:00 EST", before_spring)
        self.assertIn("03:00:00-04:00 EDT", after_spring)

    def test_fall_repeated_hour_is_disambiguated_by_zone_and_utc(self):
        first = format_timestamp("2026-11-01T05:30:00Z")
        second = format_timestamp("2026-11-01T06:30:00Z")
        self.assertIn("01:30:00-04:00 EDT", first)
        self.assertIn("UTC 2026-11-01T05:30:00Z", first)
        self.assertIn("01:30:00-05:00 EST", second)
        self.assertIn("UTC 2026-11-01T06:30:00Z", second)

    def test_missing_invalid_and_naive_timestamps_are_explicit(self):
        self.assertEqual("Unavailable (timestamp missing)", format_timestamp(None))
        self.assertIn("Unconverted (invalid timestamp)", format_timestamp("not-a-time"))
        self.assertIn("timezone missing in source timestamp",
                      format_timestamp("2026-11-07T12:00:00"))
        with self.assertRaises(TimestampPresentationError):
            resolve_timezone("Invalid/Not_A_Zone")

    def test_human_report_preserves_raw_record_and_adds_local_time_zone(self):
        source_timestamp = "2026-11-06T16:36:18Z"  # Runtime evidence document creation record.
        report = human_report({"event": {"persisted_at": source_timestamp}})
        event = report["event"]
        self.assertEqual(source_timestamp, event["persisted_at"])
        self.assertIn("2026-11-06T11:36:18-05:00 EST [America/New_York]",
                      event["persisted_at_local"])
        self.assertEqual("America/New_York", report["_presentation"]["timezone"])

    def test_external_configuration_defaults_and_fails_closed_on_invalid_zone(self):
        with tempfile.TemporaryDirectory(prefix="r3a-presentation-config-") as temporary:
            config_path = Path(temporary) / "bootstrap.json"
            settings = load_settings(_bootstrap(config_path))
            self.assertEqual(DEFAULT_PRESENTATION_TIMEZONE, settings.presentation_timezone)
            self.assertEqual(DEFAULT_PRESENTATION_TIMEZONE,
                             sanitized_config(settings)["presentation_timezone"])
            bad_config = _bootstrap(config_path, "Mars/Olympus_Mons")
            with self.assertRaisesRegex(ConfigurationError, "presentation_timezone is invalid"):
                load_settings(bad_config)

    def test_aware_datetime_objects_are_converted_without_changing_input(self):
        original = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
        self.assertIn("07:00:00-05:00 EST", format_timestamp(original))
        self.assertEqual(timezone.utc, original.tzinfo)


if __name__ == "__main__":
    unittest.main()
