# R3 CONTROLLED SOURCE
# File: r3a_plugins/resource_monitor/host_diagnostics.py
# Component: R3A-PLUG-HOST-DIAGNOSTICS
# File Revision: 1.0.0
# Created: 2026-11-08T19:26:31Z
# Created By: Codex GPT-6
# Purpose: Read Linux host load, memory, uptime, configured filesystem capacity and optional sensor values.
# Execution Model: CME provider child; bounded read-only procfs/statvfs and optional sensors command.
# Observability: Host-scoped source ID, UTC observation timestamp, freshness, content digest and per-source status.
# Dependencies: Python standard library; Linux procfs; optional lm-sensors executable.
# Authority: Issue #46; local source configuration and existing scoped CME grant; no managed runtime changes.
# Changed: 2026-11-08T19:26:31Z | R3A-HOST-DIAGNOSTICS-001 | Codex GPT-6 | Add bounded host diagnostics provider.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.host-diagnostics.v1.
# Tests: tests/test_r3a_host_diagnostics.py.
# History/Predecessor: New file.
"""Read-only local Linux host diagnostic provider."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_SENSOR_OUTPUT_BYTES = 262144


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_meminfo(path: Path = Path("/proc/meminfo")) -> dict[str, int]:
    fields: dict[str, int] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        key, separator, rest = line.partition(":")
        if not separator:
            continue
        values = rest.split()
        if values and values[0].isdigit():
            # Linux meminfo reports kB; convert explicitly to bytes.
            fields[key] = int(values[0]) * 1024
    if "MemTotal" not in fields or "MemAvailable" not in fields:
        raise ValueError("meminfo_required_fields_unavailable")
    return fields


def _sensor_values(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key.endswith("_input") and isinstance(child, (int, float)) and not isinstance(child, bool):
                unit = "degC" if key.startswith("temp") else "rpm" if key.startswith("fan") else "unknown"
                rows.append({"sensor_id": path, "value": child, "unit": unit})
            else:
                rows.extend(_sensor_values(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_sensor_values(child, f"{prefix}[{index}]"))
    return rows


def _collect_sensors(timeout: float) -> dict[str, Any]:
    executable = shutil.which("sensors")
    if not executable:
        return {"state": "unavailable", "observations": [], "reason": "sensors_unavailable"}
    try:
        result = subprocess.run([executable, "-j"], capture_output=True, text=True,
                                timeout=timeout, check=False)
        if len(result.stdout.encode()) > MAX_SENSOR_OUTPUT_BYTES:
            raise ValueError("sensor_output_exceeds_limit")
        if result.returncode != 0:
            raise RuntimeError(f"sensors_exit_{result.returncode}")
        values = _sensor_values(json.loads(result.stdout))
        return {"state": "measured" if values else "unavailable", "observations": values,
                "reason": None if values else "no_numeric_sensor_inputs_reported"}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        reason = str(exc) if str(exc).startswith(("sensors_exit_", "sensor_output_")) else type(exc).__name__
        return {"state": "unavailable", "observations": [], "reason": reason}


def collect_host_diagnostics(configuration: dict[str, Any]) -> dict[str, Any]:
    observed_at = _now()
    host_id = configuration["host_id"]
    timeout = float(configuration["timeout_seconds"])
    try:
        meminfo = _read_meminfo(Path(configuration.get("meminfo_path", "/proc/meminfo")))
        total = meminfo["MemTotal"]
        available = meminfo["MemAvailable"]
        memory = {"state": "measured", "total_bytes": total, "available_bytes": available,
                  "used_percent": round((total - available) * 100.0 / total, 2) if total else None}
    except (OSError, ValueError, KeyError) as exc:
        memory = {"state": "unavailable", "total_bytes": None, "available_bytes": None,
                  "used_percent": None, "reason": type(exc).__name__}

    try:
        uptime_seconds = float(Path(configuration.get("uptime_path", "/proc/uptime")).read_text().split()[0])
        uptime = {"state": "measured", "seconds": uptime_seconds}
    except (OSError, ValueError, IndexError):
        uptime = {"state": "unavailable", "seconds": None}

    filesystems = []
    for mountpoint in configuration["filesystem_paths"]:
        try:
            total, used, free = shutil.disk_usage(mountpoint)
            filesystems.append({"mountpoint": mountpoint, "state": "measured", "total_bytes": total,
                                "used_bytes": used, "available_bytes": free,
                                "used_percent": round(used * 100.0 / total, 2) if total else None})
        except OSError as exc:
            filesystems.append({"mountpoint": mountpoint, "state": "unavailable", "total_bytes": None,
                                "used_bytes": None, "available_bytes": None, "used_percent": None,
                                "reason": type(exc).__name__})

    try:
        load = os.getloadavg()
        load_average = {"state": "measured", "one_minute": load[0],
                        "five_minutes": load[1], "fifteen_minutes": load[2]}
    except (AttributeError, OSError):
        load_average = {"state": "unavailable", "one_minute": None,
                        "five_minutes": None, "fifteen_minutes": None}

    content = {"schema_id": "r3a.host-diagnostics.v1", "host_id": host_id,
               "observed_at": observed_at,
               "cpu": {"logical_processors": os.cpu_count(), "load_average": load_average},
               "memory": memory, "uptime": uptime, "filesystems": filesystems,
               "sensors": _collect_sensors(timeout)}
    payload = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    envelope = {"source_id": f"host-diagnostics.{host_id}",
                "source_path": "/proc/meminfo; /proc/uptime; os.getloadavg; statvfs; sensors -j",
                "content": content, "sha256": hashlib.sha256(payload).hexdigest(),
                "observed_at": observed_at, "source_timestamp": None,
                "source_timestamp_basis": "R3A collection time; procfs/statvfs snapshot time unavailable",
                "freshness": {"state": "fresh", "age_seconds": 0,
                              "max_age_seconds": configuration["max_age_seconds"]}}
    return envelope


class HostDiagnosticsProvider:
    def __init__(self, configuration: dict[str, Any]):
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("host diagnostics read accepts no input fields")
        if not isinstance(context, dict):
            raise ValueError("provider invocation context must be an object")
        target = context.get("target", {})
        host_ids = target.get("host_ids", []) if isinstance(target, dict) else None
        if (not isinstance(host_ids, list)
                or any(host_id != self.configuration["host_id"] for host_id in host_ids)):
            raise ValueError("target scope exceeds configured host")
        return collect_host_diagnostics(self.configuration)


def create_provider(configuration: dict[str, Any]) -> HostDiagnosticsProvider:
    return HostDiagnosticsProvider(configuration)
