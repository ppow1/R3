"""Focused contract tests for the read-only Octo Control capability package."""
# R3 CONTROLLED SOURCE
# File: tests/test_r3a_octominer_plugin.py
# Component: R3A-PLUG-OCTOMINER-TEST
# File Revision: 1.0.0
# Created: 2026-11-07T04:19:12Z
# Created By: Codex GPT-6
# Purpose: Verify fixed-route, read-only Octo Control sampling and evidence shape.
# Execution Model: Python unittest with local HTTP fixture.
# Observability: Request verbs/routes and structured evidence assertions.
# Dependencies: Python standard library; r3a_plugins.octominer_telemetry.plugin.
# Authority: Issue #46; fixture only, no production network access.
# Changed: 2026-11-07T04:19:12Z | R3A-PLUG-001 | Codex GPT-6 | Initial tests.
# Supersedes: None.
# Contracts: r3a.capability-plugin 1.0.0; Issue #46.
# Tests: Self.
# History/Predecessor: New file; initial publication recorded in Git.

from __future__ import annotations

import json
import hashlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from r3a_plugins.octominer_telemetry.plugin import read_telemetry


class TelemetryHandler(BaseHTTPRequestHandler):
    requests: list[tuple[str, str]] = []

    def do_GET(self):
        self.requests.append((self.command, self.path))
        if self.path == "/api/v1/gpus":
            body = {"devices": [{"index": 0, "temperature": {"value": 45, "unit": "C"},
                                 "utilization": {"value": 12, "unit": "%"}}]}
        elif self.path == "/api/v1/fans":
            body = {"fans": [{"rpm": 900, "unit": "rpm"}], "psu": [{"watts": 180, "unit": "W"}]}
        else:
            self.send_error(404)
            return
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        self.requests.append((self.command, self.path))
        self.send_error(405)

    def log_message(self, *_args):
        pass


class OctoMinerPluginTests(unittest.TestCase):
    def test_manifest_is_read_only_versioned_and_digest_pinned(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "r3a_plugins/octominer_telemetry/manifest.json").read_text())
        artifact = root / "r3a_plugins/octominer_telemetry" / manifest["artifact_ref"]
        self.assertEqual(1, manifest["schema_version"])
        self.assertTrue(manifest["read_only"])
        self.assertEqual("1.0.0", manifest["contract_version"])
        self.assertEqual(manifest["artifact_sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())

    def test_reads_only_fixed_routes_and_preserves_source_units_and_freshness(self):
        TelemetryHandler.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), TelemetryHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = read_telemetry({"base_url": f"http://127.0.0.1:{server.server_port}",
                                     "bearer_token_env": None, "timeout_seconds": 2,
                                     "max_age_seconds": 30})
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
        self.assertEqual(["fresh", "fresh"], [item["freshness"]["state"] for item in result])
        self.assertTrue(all(item["observed_at"] and item["source_path"] for item in result))
        self.assertEqual("C", result[0]["content"]["data"]["devices"][0]["temperature"]["unit"])
        self.assertEqual("rpm", result[1]["content"]["data"]["fans"][0]["unit"])
        self.assertEqual([("GET", "/api/v1/gpus"), ("GET", "/api/v1/fans")], TelemetryHandler.requests)

    def test_missing_secret_returns_unavailable_evidence_without_request(self):
        TelemetryHandler.requests = []
        result = read_telemetry({"base_url": "http://127.0.0.1:9", "bearer_token_env": "R3A_TEST_MISSING_TOKEN",
                                 "timeout_seconds": 1, "max_age_seconds": 10})
        self.assertEqual(["unavailable", "unavailable"], [item["freshness"]["state"] for item in result])
        self.assertEqual([], TelemetryHandler.requests)


if __name__ == "__main__":
    unittest.main()
