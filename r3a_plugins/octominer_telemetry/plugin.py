"""Read-only Octo Control telemetry adapter; only fixed GET routes are exposed."""
# R3 CONTROLLED SOURCE
# File: r3a_plugins/octominer_telemetry/plugin.py
# Component: R3A-PLUG-OCTOMINER
# File Revision: 1.0.0
# Created: 2026-11-07T04:19:12Z
# Created By: Codex GPT-6
# Purpose: Read GPU and fan/PSU evidence from documented Octo Control API routes.
# Execution Model: In-process read-only capability adapter, invoked by CME after authorization.
# Observability: Per-endpoint source IDs, digest, retrieval timestamp, source timestamp, and freshness.
# Dependencies: Python standard library; Octo Control v0.6.1 GET /api/v1/gpus and /api/v1/fans.
# Authority: Issue #46; read-only; no endpoint other than fixed GET routes is callable.
# Changed: 2026-11-07 | R3A-PLUG-001 | Codex GPT-6 | Initial version.
# Supersedes: None.
# Contracts: r3a.capability-plugin 1.0.0; r3a.octominer-telemetry.config.v1; Issue #46.
# Tests: tests/test_r3a_octominer_plugin.py.
# History/Predecessor: New file; initial publication recorded in Git.

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


ENDPOINTS = ("/api/v1/gpus", "/api/v1/fans")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read_endpoint(base_url: str, path: str, config: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat()
    request = urllib.request.Request(base_url.rstrip("/") + path, headers=headers, method="GET")
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=float(config["timeout_seconds"])) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            raw = response.read(1_000_000)
            value = json.loads(raw)
            if not isinstance(value, (dict, list)):
                raise ValueError("telemetry response must be a JSON object or array")
            server_date = response.headers.get("Date")
            source_timestamp = None
            if server_date:
                try:
                    source_timestamp = parsedate_to_datetime(server_date).astimezone(timezone.utc).isoformat()
                except (TypeError, ValueError, OverflowError):
                    source_timestamp = None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, RuntimeError) as exc:
        detail = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
        return {
            "source_id": f"octominer{path.replace('/', '.')}",
            "source_path": path,
            "content": {"available": False, "error": detail},
            "sha256": hashlib.sha256(detail.encode()).hexdigest(),
            "observed_at": observed_at,
            "source_timestamp": None,
            "source_timestamp_basis": "unavailable",
            "units": "as reported by Octo Control; unavailable",
            "freshness": {"state": "unavailable", "age_seconds": None,
                          "max_age_seconds": float(config["max_age_seconds"])},
        }
    digest = hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "source_id": f"octominer{path.replace('/', '.')}",
        "source_path": path,
        "content": {"available": True, "data": value},
        "sha256": digest,
        "observed_at": observed_at,
        "source_timestamp": source_timestamp,
        "source_timestamp_basis": "HTTP Date header" if source_timestamp else "not supplied by source",
        "units": "as reported by Octo Control payload; original fields retained",
        "freshness": {"state": "fresh", "age_seconds": 0,
                      "max_age_seconds": float(config["max_age_seconds"])},
    }


def read_telemetry(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return two freshness-stamped evidence records without exposing credentials."""
    base_url = str(config["base_url"]).rstrip("/")
    headers = {"Accept": "application/json"}
    token_env = config.get("bearer_token_env")
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            return [{"source_id": f"octominer{path.replace('/', '.')}", "source_path": path,
                     "content": {"available": False, "error": "credential_unavailable"},
                     "sha256": hashlib.sha256(b"credential_unavailable").hexdigest(),
                     "observed_at": datetime.now(timezone.utc).isoformat(),
                     "source_timestamp": None, "source_timestamp_basis": "unavailable",
                     "units": "as reported by Octo Control; unavailable",
                     "freshness": {"state": "unavailable", "age_seconds": None,
                                   "max_age_seconds": float(config["max_age_seconds"])} }
                    for path in ENDPOINTS]
        headers["Authorization"] = f"Bearer {token}"
    return [_read_endpoint(base_url, path, config, headers) for path in ENDPOINTS]
