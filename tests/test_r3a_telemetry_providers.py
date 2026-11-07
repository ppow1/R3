"""Representative R3A telemetry provider, provenance, and history fixtures."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from r3a_plugins.octominer_telemetry import history, http_providers, process_providers, request_metrics
from r3a_runtime.grace_module import provider_usage_record


class FakeResponse:
    status = 200
    headers = {"Date": "Sat, 07 Nov 2026 04:27:00 GMT"}

    def __init__(self, value):
        self.data = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size=-1):
        return self.data[:size]


class FakeOpener:
    def __init__(self, fixtures):
        self.fixtures = fixtures
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if request.get_method() != "GET":
            raise AssertionError("telemetry providers may issue GET only")
        path = request.full_url.rsplit("/", 1)[-1]
        return FakeResponse(self.fixtures[path])


class ProviderTests(unittest.TestCase):
    def test_model_server_and_comfyui_are_direct_get_count_only_sources(self):
        fixtures = {
            "health": {"status": "ok"},
            "slots": [{"id": 0, "is_processing": True}, {"id": 1, "is_processing": False}],
            "system_stats": {"system": {"comfyui_version": "fixture-version"},
                             "devices": [{"type": "cuda", "name": "Fixture GPU",
                                          "vram_total": 800, "vram_free": 600}]},
            "queue": {"queue_running": [["prompt-secret"]], "queue_pending": []},
        }
        opener = FakeOpener(fixtures)
        model_config = {"model_servers": {"reasoning": {"base_url_env": "FIXTURE_MODEL_URL",
                                                           "timeout_seconds": 2, "max_age_seconds": 30}}}
        comfy_config = {"comfyui": {"base_url_env": "FIXTURE_COMFY_URL", "timeout_seconds": 2,
                                     "max_age_seconds": 30}}
        env = {"FIXTURE_MODEL_URL": "http://127.0.0.1:8180", "FIXTURE_COMFY_URL": "http://127.0.0.1:8188"}
        with patch.dict(os.environ, env), patch.object(http_providers.urllib.request, "build_opener",
                                                       return_value=opener):
            model = http_providers.read_model_servers(model_config)
            comfy = http_providers.read_comfyui(comfy_config)
        self.assertEqual(1, model[1]["content"]["active_slots"])
        self.assertEqual(2, model[1]["content"]["configured_slots"])
        self.assertEqual(600, comfy[0]["content"]["cuda_devices"][0]["vram_free_bytes"])
        self.assertEqual(1, comfy[1]["content"]["running_count"])
        self.assertNotIn("prompt-secret", json.dumps(comfy))
        self.assertEqual({"GET"}, {request.get_method() for request, _ in opener.calls})
        self.assertEqual({2}, {timeout for _, timeout in opener.calls})
        self.assertEqual("fresh", model[1]["freshness"]["state"])

    def test_http_sources_fail_closed_on_missing_endpoint_and_public_plain_http(self):
        source = {"base_url_env": "MISSING_TELEMETRY_ENDPOINT"}
        result = http_providers.read_model_servers({"model_servers": {"model": source}})
        self.assertEqual("unavailable", result[0]["freshness"]["state"])
        with self.assertRaisesRegex(ValueError, "endpoint_must_use_https"):
            http_providers._safe_base_url("http://example.com")

    def test_process_to_gpu_mapping_preserves_observed_identity_and_config_provenance(self):
        sample = "GPU-ABC, 4132, llama-server, 12288\nGPU-DEF, 71, python, N/A\n"
        result = process_providers.parse_compute_apps(
            sample, host_id="fixture-host", observed_at="2026-11-07T04:00:00Z",
            model_process_names={"llama-server": "fixture-model"})
        self.assertEqual("GPU-ABC", result[0]["nvidia_uuid"])
        self.assertEqual(4132, result[0]["pid"])
        self.assertEqual("fixture-model", result[0]["model_id"])
        self.assertEqual("configured", result[0]["model_mapping_state"])
        self.assertEqual("unmapped", result[1]["model_mapping_state"])
        self.assertIn("nvidia-smi --query-compute-apps", result[0]["process_gpu_provenance"])

    def test_r3a_request_projection_uses_provider_tokens_and_measured_wall_time(self):
        now = datetime(2026, 11, 7, 4, 30, tzinfo=timezone.utc)
        started = datetime.fromisoformat("2026-11-07T04:29:59+00:00")
        finished = datetime.fromisoformat("2026-11-07T04:30:00+00:00")
        usage = provider_usage_record({"prompt_tokens": 19, "completion_tokens": 7},
                                      request_ref="fixture-request", route_id="route-a",
                                      provider="fixture-provider", model="fixture-model",
                                      started_at=started, finished_at=finished, elapsed_ms=1000)
        rows = [{"activity_id": "fixture-activity", "state": "COMPLETED",
                 "result_turns": [{"request_ref": "fixture-request", "usage": usage,
                                   "observed_at": "2026-11-07T04:30:00Z"}]}]
        evidence = request_metrics.project_turns(rows, now=now, window_seconds=300, max_rows=100)
        item = evidence["content"]["requests"][0]
        self.assertEqual(19, item["prompt_tokens"])
        self.assertEqual(7, item["completion_tokens"])
        self.assertEqual(1000, item["elapsed_ms"])
        self.assertEqual(7.0, evidence["content"]["completed_output_tokens_per_provider_call_second"])
        self.assertIsNone(evidence["content"]["native_model_token_rate"])
        self.assertEqual("unavailable_no_timestamped_stream_deltas",
                         evidence["content"]["streaming_cadence_state"])

    def test_r3a_database_provider_is_read_only_and_selects_no_prompt_or_response_text(self):
        import psycopg
        request_finished = datetime.now(timezone.utc)
        request_started = request_finished.replace(microsecond=0)
        started = request_started.isoformat().replace("+00:00", "Z")
        finished = request_finished.isoformat().replace("+00:00", "Z")
        usage = provider_usage_record({"prompt_tokens": 19, "completion_tokens": 7},
                                      request_ref="db-request", route_id="route-a",
                                      provider="fixture-provider", model="fixture-model",
                                      started_at=request_started, finished_at=request_finished,
                                      elapsed_ms=max(1, (request_finished-request_started).total_seconds()*1000))
        row = {"activity_id": "db-activity", "state": "COMPLETED",
               "result_turns": [{"request_ref": "db-request", "usage": usage,
                                 "observed_at": finished}], "checkpoint_turns": None}

        class ReadOnlyConnection:
            def __init__(self):
                self.statements = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, statement, _params=None):
                self.statements.append(statement)
                return self

            def fetchall(self):
                return [row]

            def commit(self):
                pass

        connection = ReadOnlyConnection()
        config = {"request_database_dsn_env": "FIXTURE_R3A_DSN", "history_window_seconds": 300,
                  "request_activity_limit": 5, "max_age_seconds": 30}
        with patch.dict(os.environ, {"FIXTURE_R3A_DSN": "fixture-secret-dsn"}), \
                patch.object(psycopg, "connect", return_value=connection) as connect:
            result = request_metrics.read_r3a_model_turns(config)
        connect.assert_called_once()
        self.assertEqual("SET TRANSACTION READ ONLY", connection.statements[0])
        query = connection.statements[1]
        self.assertIn("FROM r3a.activities", query)
        self.assertNotIn("input", query)
        self.assertNotIn("model_content", query)
        self.assertEqual("db-request", result["content"]["requests"][0]["request_ref"])

    def test_stream_cadence_requires_timestamped_app_deltas(self):
        self.assertIsNone(request_metrics.normalize_stream_deltas(None))
        result = request_metrics.normalize_stream_deltas([
            {"observed_at": "2026-11-07T04:00:00Z", "delta_characters": 4},
            {"observed_at": "2026-11-07T04:00:02Z", "delta_characters": 6},
        ])
        self.assertEqual(5.0, result["characters_per_second"])
        self.assertIn("not model tokens/s", result["measurement_basis"])

    def test_history_is_bounded_and_keeps_stale_separate_from_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            history_file = str(Path(directory) / "samples.sqlite3")
            config = {"history_path_env": "FIXTURE_HISTORY_PATH", "history_window_seconds": 300,
                      "history_capacity_per_source": 8, "history_limit": 2, "max_age_seconds": 300}
            observed = datetime.now(timezone.utc).isoformat()
            good = {"source_id": "fixture.gpu", "content": {"available": True, "measurement": 42},
                    "observed_at": observed, "collection_finished_at": observed,
                    "freshness": {"state": "fresh", "max_age_seconds": 300}}
            bad = {"source_id": "fixture.gpu", "content": {"available": False, "error": "timeout"},
                   "observed_at": datetime.now(timezone.utc).isoformat(),
                   "freshness": {"state": "unavailable", "max_age_seconds": 300}, "error": "timeout"}
            with patch.dict(os.environ, {"FIXTURE_HISTORY_PATH": history_file}):
                history.apply_freshness_and_history([good], config)
                stale, history_record = history.apply_freshness_and_history([bad], config)
            self.assertEqual("stale", stale[0]["freshness"]["state"])
            self.assertEqual(42, stale[0]["content"]["measurement"])
            self.assertLessEqual(len(history_record["content"]["samples"]), 2)


if __name__ == "__main__":
    unittest.main()
