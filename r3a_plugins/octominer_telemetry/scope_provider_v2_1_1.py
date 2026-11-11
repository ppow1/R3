"""
R3 CONTROLLED SOURCE
File: r3a_plugins/octominer_telemetry/scope_provider_v2_1_1.py
Component: R3A-PLUG-OCTOMINER-SCOPED-PROVIDER
File Revision: 1.0.0
Created: 2026-11-11T18:38:47Z
Created By: Codex GPT-6
Purpose: Enforce mandatory declared host/source target scope for telemetry provider v2.1.1.
Execution Model: In-process capability provider composed from existing read-only collectors.
Observability: Explicit scope errors before collection and source-limited result evidence.
Dependencies: Existing telemetry collectors; read-only scoped HTTP helpers; external v3 provider config.
Authority: AD-024; Modular Plugins #46 Step 70; no CME/Ring 0 changes or grants.
Changed: 2026-11-11T18:38:47Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Add a new immutable provider revision with mandatory host/source scope.
Supersedes: None.
Contracts: r3a.capability-operation.v1 target_scope_schema; r3a.octominer-independent-telemetry.config.v3.
Tests: tests/test_r3a_telemetry_target_scope.py.
History/Predecessor: New immutable version; corrects absent-target behavior from scope_provider.py in commit 132b748a311fc2ff717babb39735b19bbc2221fa and reuses v2.0 collectors.
"""
from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .history import _history_evidence, apply_freshness_and_history
from .plugin import (FILESYSTEM_QUERY, REMOTE_QUERY, _collect_source, _run_ssh_query,
                    parse_df_posix, parse_nvidia_smi_csv)
from .process_providers import PROCESS_QUERY, read_compute_apps
from .request_metrics import read_r3a_model_turns
from .scoped_http_providers import read_comfyui, read_model_servers


HISTORY_SOURCE_ID = "r3a.telemetry.history"
REQUEST_SOURCE_ID = "r3a.model.request-telemetry"


def _host_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a configured nonempty host ID")
    return value.strip()


def configured_source_ids(config: dict[str, Any]) -> set[str]:
    """Return exact source identifiers emitted by this configured provider."""
    host_id = _host_text(config.get("host_id"), "host_id")
    sources = {f"gpu.telemetry.{host_id}", f"storage.telemetry.{host_id}",
               f"gpu.processes.{host_id}", REQUEST_SOURCE_ID, HISTORY_SOURCE_ID,
               "comfyui.system", "comfyui.queue"}
    servers = config.get("model_servers", {})
    if isinstance(servers, dict) and servers:
        for service_id in servers:
            sources.add(f"model-server.{service_id}.readiness")
            sources.add(f"model-server.{service_id}.slots")
    else:
        sources.add("model-server.readiness")
    return sources


def configured_source_hosts(config: dict[str, Any]) -> dict[str, str | None]:
    """Map each non-aggregate source to its external configured host, if known."""
    host_id = _host_text(config.get("host_id"), "host_id")
    hosts: dict[str, str | None] = {
        f"gpu.telemetry.{host_id}": host_id,
        f"storage.telemetry.{host_id}": host_id,
        f"gpu.processes.{host_id}": host_id,
        REQUEST_SOURCE_ID: (config.get("request_host_id")
                            if isinstance(config.get("request_host_id"), str) else None),
        "comfyui.system": None,
        "comfyui.queue": None,
    }
    servers = config.get("model_servers", {})
    if isinstance(servers, dict) and servers:
        for service_id, source in servers.items():
            host = source.get("host_id") if isinstance(source, dict) else None
            host = host.strip() if isinstance(host, str) and host.strip() else None
            hosts[f"model-server.{service_id}.readiness"] = host
            hosts[f"model-server.{service_id}.slots"] = host
    else:
        hosts["model-server.readiness"] = None
    comfy = config.get("comfyui")
    comfy_host = comfy.get("host_id") if isinstance(comfy, dict) else None
    comfy_host = comfy_host.strip() if isinstance(comfy_host, str) and comfy_host.strip() else None
    hosts["comfyui.system"] = comfy_host
    hosts["comfyui.queue"] = comfy_host
    return hosts


def _selection(config: dict[str, Any], target: Any) -> tuple[set[str], set[str], bool]:
    if not isinstance(target, dict) or set(target) - {"host_ids", "source_ids"}:
        raise ValueError("telemetry target scope has unsupported fields")
    if not target or "host_ids" not in target or "source_ids" not in target:
        raise ValueError("telemetry target requires explicit host_ids and source_ids")
    available = configured_source_ids(config)
    hosts = configured_source_hosts(config)
    raw_source_ids = target.get("source_ids")
    explicit_sources = "source_ids" in target
    if explicit_sources:
        if (not isinstance(raw_source_ids, list) or not raw_source_ids
                or any(not isinstance(item, str) or not item.strip() for item in raw_source_ids)
                or len(set(raw_source_ids)) != len(raw_source_ids)):
            raise ValueError("source_ids must be a nonempty unique list of configured source IDs")
        requested_sources = set(raw_source_ids)
        unknown = requested_sources - available
        if unknown:
            raise PermissionError("target scope names an unconfigured telemetry source")
    else:
        requested_sources = set(available)

    raw_host_ids = target.get("host_ids")
    explicit_hosts = "host_ids" in target
    if explicit_hosts:
        if (not isinstance(raw_host_ids, list) or not raw_host_ids
                or any(not isinstance(item, str) or not item.strip() for item in raw_host_ids)
                or len({item.strip() for item in raw_host_ids}) != len(raw_host_ids)):
            raise ValueError("host_ids must be a nonempty unique list of configured host IDs")
        requested_hosts = {item.strip() for item in raw_host_ids}
        configured_hosts = {host for host in hosts.values() if host is not None}
        if requested_hosts - configured_hosts:
            raise PermissionError("target scope names a host without configured provider sources")
        if explicit_sources:
            nonaggregate_sources = requested_sources - {HISTORY_SOURCE_ID}
            if any(hosts.get(source_id) not in requested_hosts for source_id in nonaggregate_sources):
                raise PermissionError("requested telemetry source is outside the requested host scope")
            selected = nonaggregate_sources
            if requested_sources == {HISTORY_SOURCE_ID}:
                selected = {source_id for source_id, host in hosts.items()
                            if host in requested_hosts}
        else:
            selected = {source_id for source_id, host in hosts.items()
                        if host in requested_hosts}
        if not selected:
            raise PermissionError("target host scope has no configured telemetry sources")
        history_scope = selected
        include_history = not explicit_sources or HISTORY_SOURCE_ID in requested_sources
    else:
        if explicit_sources and requested_sources == {HISTORY_SOURCE_ID}:
            selected = set(available) - {HISTORY_SOURCE_ID}
        else:
            selected = requested_sources - {HISTORY_SOURCE_ID}
        history_scope = selected
        include_history = not explicit_sources or HISTORY_SOURCE_ID in requested_sources

    if not selected and include_history:
        raise PermissionError("history target requires at least one configured telemetry source")
    return selected, history_scope, include_history


def _scoped_history(config: dict[str, Any], source_ids: set[str]) -> dict[str, Any]:
    """Read history for only the selected source IDs without creating or mutating the journal."""
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    path_env = config.get("history_path_env")
    path_value = os.environ.get(path_env) if isinstance(path_env, str) else None
    if not path_value:
        return _history_evidence({"available": False,
                                  "error": "history_path_environment_not_configured",
                                  "samples": []}, observed_at)
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        return _history_evidence({"available": False, "error": "history_not_available",
                                  "samples": []}, observed_at)
    limit = int(config.get("history_limit", 8))
    samples = []
    try:
        uri = path.as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2) as conn:
            for source_id in sorted(source_ids):
                rows = conn.execute(
                    "SELECT state,observed_at,attempted_at,content_json,sha256 "
                    "FROM telemetry_samples WHERE source_id=? ORDER BY sample_id DESC LIMIT ?",
                    (source_id, limit)).fetchall()
                samples.extend({"source_id": source_id, "state": row[0], "observed_at": row[1],
                                "attempted_at": row[2], "content": json.loads(row[3]),
                                "sha256": row[4]} for row in rows)
        content = {"available": True,
                   "window_seconds": int(config.get("history_window_seconds", 300)),
                   "capacity_per_source": int(config.get("history_capacity_per_source", 128)),
                   "samples_per_source": limit, "samples": samples}
    except (OSError, sqlite3.Error, TypeError, ValueError):
        content = {"available": False, "error": "history_read_failed", "samples": []}
    return _history_evidence(content, observed_at)


_TARGET_UNSET = object()


def read_scoped_telemetry(config: dict[str, Any], target: Any = _TARGET_UNSET) -> list[dict[str, Any]]:
    if target is _TARGET_UNSET:
        raise ValueError("telemetry target scope is required")
    selected, history_scope, include_history = _selection(config, target)
    if (isinstance(target, dict)
            and target.get("source_ids") == [HISTORY_SOURCE_ID]):
        return [_scoped_history(config, history_scope)]
    host_id = _host_text(config.get("host_id"), "host_id")
    samples: list[dict[str, Any]] = []
    gpu_id, storage_id, process_id = (f"gpu.telemetry.{host_id}",
                                      f"storage.telemetry.{host_id}",
                                      f"gpu.processes.{host_id}")
    if gpu_id in selected:
        samples.append(_collect_source(config, source_kind="gpu", value_key="gpus",
                                       remote_command=REMOTE_QUERY, parser=parse_nvidia_smi_csv))
    if storage_id in selected:
        samples.append(_collect_source(config, source_kind="storage", value_key="filesystems",
                                       remote_command=FILESYSTEM_QUERY, parser=parse_df_posix))
    if process_id in selected:
        samples.append(read_compute_apps(config, lambda command: _run_ssh_query(config, command)))

    model_ids = {source_id for source_id in selected
                 if source_id.startswith("model-server.")}
    if model_ids:
        samples.extend(read_model_servers(config, model_ids))
    comfy_ids = selected.intersection({"comfyui.system", "comfyui.queue"})
    if comfy_ids:
        samples.extend(read_comfyui(config, comfy_ids))
    if REQUEST_SOURCE_ID in selected:
        samples.append(read_r3a_model_turns(config))

    if include_history:
        if not samples:
            # A history-only request reads stored, scoped records and does not trigger fresh collectors.
            samples.append(_scoped_history(config, history_scope))
            return samples
        samples, history_record = apply_freshness_and_history(samples, config)
        samples.append(history_record)
    elif samples:
        samples, _ = apply_freshness_and_history(samples, config)
    return samples


class ScopedOctoMinerTelemetryProvider:
    """New immutable provider version enforcing its published target selectors."""

    def __init__(self, configuration: dict[str, Any]):
        if not isinstance(configuration, dict):
            raise ValueError("telemetry configuration must be an object")
        _host_text(configuration.get("host_id"), "host_id")
        _host_text(configuration.get("request_host_id"), "request_host_id")
        servers = configuration.get("model_servers", {})
        if not isinstance(servers, dict):
            raise ValueError("model_servers must be an object")
        for service_id, source in servers.items():
            if not isinstance(source, dict):
                raise ValueError(f"model_servers.{service_id} must be an object")
            _host_text(source.get("host_id"), f"model_servers.{service_id}.host_id")
        comfy = configuration.get("comfyui")
        if comfy is not None:
            if not isinstance(comfy, dict):
                raise ValueError("comfyui must be an object")
            _host_text(comfy.get("host_id"), "comfyui.host_id")
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> list[dict[str, Any]]:
        if arguments:
            raise ValueError("octominer telemetry read accepts no input fields")
        if not isinstance(context, dict):
            raise ValueError("provider invocation context must be an object")
        if "target" not in context:
            raise ValueError("telemetry target scope is required")
        target = context["target"]
        return read_scoped_telemetry(self.configuration, target)


def create_provider(configuration: dict[str, Any]) -> ScopedOctoMinerTelemetryProvider:
    return ScopedOctoMinerTelemetryProvider(configuration)
