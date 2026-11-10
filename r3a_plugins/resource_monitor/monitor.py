# R3 CONTROLLED SOURCE
# File: r3a_plugins/resource_monitor/monitor.py
# Component: R3A-PLUG-RESOURCE-MONITOR
# File Revision: 1.0.0
# Created: 2026-11-08T18:43:38Z
# Created By: Codex GPT-6
# Purpose: Collect read-only physical disk capacity/SMART evidence and installed executable inventory.
# Execution Model: CME provider child using bounded local read-only commands.
# Observability: UTC observation timestamps, source path, freshness, digest, measured/unavailable states.
# Dependencies: Python standard library, lsblk, optional smartctl.
# Authority: Issue #46; dynamic capability registry and scoped read grant; no managed runtime activation.
# Changed: 2026-11-08T18:43:38Z | R3A-RESOURCE-MONITOR-001 | Codex GPT-6 | Add bounded disk health and software environment providers.
# Supersedes: None.
# Contracts: r3a.capability-operation.v1; r3a.physical-resource-inventory.v1; r3a.software-environment-inventory.v1.
# Tests: tests/test_r3a_resource_monitor.py.
# History/Predecessor: New file in current modular plug-in worktree.
"""Read-only local disk health and software environment inventory providers.

Physical devices, installed software and callable capabilities intentionally have
separate contracts. This module reports the first two; CME's registry remains
the authority for callable operations.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Callable

MAX_COMMAND_OUTPUT = 1_000_000


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _run(command: list[str], timeout: float) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if len(result.stdout.encode()) > MAX_COMMAND_OUTPUT:
        raise ValueError("source_output_exceeds_limit")
    if result.returncode != 0:
        raise RuntimeError(f"source_exit_{result.returncode}")
    return result.stdout


def _run_smartctl(command: list[str], timeout: float) -> tuple[str, int]:
    """Preserve smartctl's bit-coded health exit status while parsing its JSON."""
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if len(result.stdout.encode()) > MAX_COMMAND_OUTPUT:
        raise ValueError("source_output_exceeds_limit")
    if not result.stdout.strip():
        raise RuntimeError(f"source_exit_{result.returncode}")
    return result.stdout, result.returncode


def parse_lsblk(payload: str, *, host_id: str, observed_at: str) -> list[dict[str, Any]]:
    """Normalize lsblk JSON without serial numbers or inferred health claims."""
    value = json.loads(payload)
    devices = value.get("blockdevices") if isinstance(value, dict) else None
    if not isinstance(devices, list):
        raise ValueError("lsblk_json_missing_blockdevices")
    rows: list[dict[str, Any]] = []
    for device in devices:
        if not isinstance(device, dict):
            raise ValueError("lsblk_json_invalid_device")
        if device.get("type") != "disk":
            continue
        name = device.get("name")
        size = device.get("size")
        if not isinstance(name, str) or not name or "/" in name:
            raise ValueError("lsblk_json_invalid_device_name")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("lsblk_json_invalid_capacity")
        rota = device.get("rota")
        rows.append({
            "resource_id": f"{host_id}:block:{name}", "host_id": host_id,
            "device": f"/dev/{name}", "name": name, "capacity_bytes": size,
            "rotational": rota if isinstance(rota, bool) else None,
            "transport": device.get("tran") if isinstance(device.get("tran"), str) else None,
            "model": device.get("model") if isinstance(device.get("model"), str) else None,
            "observed_at": observed_at,
        })
    return rows


def parse_smartctl(payload: str) -> dict[str, Any]:
    """Extract only fields directly supplied by smartctl JSON, including SAS."""
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("smartctl_json_invalid")
    smart_status = value.get("smart_status")
    passed = smart_status.get("passed") if isinstance(smart_status, dict) else None
    temperature = None
    candidates = [
        value.get("temperature"), value.get("scsi_temperature"),
        value.get("nvme_smart_health_information_log", {}).get("temperature")
        if isinstance(value.get("nvme_smart_health_information_log"), dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and isinstance(candidate.get("current"), (int, float)):
            temperature = candidate["current"]
            break
    capacity = value.get("user_capacity")
    capacity_bytes = capacity.get("bytes") if isinstance(capacity, dict) else None
    return {
        "health_state": "measured" if isinstance(passed, bool) else "unavailable",
        "smart_passed": passed if isinstance(passed, bool) else None,
        "temperature_c": temperature,
        "smart_capacity_bytes": capacity_bytes if isinstance(capacity_bytes, int) and not isinstance(capacity_bytes, bool) else None,
        "device_protocol": value.get("device", {}).get("protocol") if isinstance(value.get("device"), dict) else None,
    }


def _validate_target(context: dict[str, Any], host_id: str, source_id: str) -> None:
    target = context.get("target", {})
    if not isinstance(target, dict):
        raise ValueError("target scope must be an object")
    host_ids = target.get("host_ids", [])
    source_ids = target.get("source_ids", [])
    if (not isinstance(host_ids, list) or any(item != host_id for item in host_ids)
            or not isinstance(source_ids, list) or any(item != source_id for item in source_ids)):
        raise ValueError("target scope exceeds configured resource source")


def collect_disk_inventory(configuration: dict[str, Any], *, run: Callable[[list[str], float], str] = _run) -> dict[str, Any]:
    observed_at = now_utc()
    host_id = configuration["host_id"]
    timeout = float(configuration["timeout_seconds"])
    lsblk_path = shutil.which("lsblk")
    smartctl_path = shutil.which("smartctl")
    disks: list[dict[str, Any]] = []
    try:
        if not lsblk_path:
            raise RuntimeError("lsblk_unavailable")
        disks = parse_lsblk(run([lsblk_path, "--json", "--bytes", "--output", "NAME,TYPE,SIZE,ROTA,TRAN,MODEL"], timeout),
                            host_id=host_id, observed_at=observed_at)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, TypeError, KeyError) as exc:
        reason = str(exc) if str(exc).endswith("unavailable") or str(exc).startswith("source_exit_") else type(exc).__name__
        content = {"schema_id": "r3a.physical-resource-inventory.v1", "host_id": host_id,
                   "observed_at": observed_at, "availability": "unavailable", "disks": [], "error": reason}
        return _source_record(f"physical-resources.{host_id}", content, observed_at, configuration,
                              "unavailable", "lsblk --json --bytes; smartctl --json --all")

    for disk in disks:
        if not smartctl_path:
            disk["health"] = {"health_state": "unavailable", "smart_passed": None,
                              "temperature_c": None, "smart_capacity_bytes": None,
                              "device_protocol": None, "reason": "smartctl_unavailable"}
            continue
        try:
            # smartctl -a reads attributes/logs and supports SCSI/SAS devices.
            # Do not issue SMART tests, enable/disable commands, or device writes.
            if run is _run:
                raw, smartctl_status = _run_smartctl(
                    [smartctl_path, "--json", "--all", disk["device"]], timeout)
            else:
                raw, smartctl_status = run([smartctl_path, "--json", "--all", disk["device"]], timeout), 0
            health = parse_smartctl(raw)
            health["smartctl_exit_status"] = smartctl_status
            health["reason"] = None if health["health_state"] == "measured" else "smart_status_not_reported"
            disk["health"] = health
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError, TypeError) as exc:
            reason = str(exc) if str(exc).startswith("source_exit_") else type(exc).__name__
            disk["health"] = {"health_state": "unavailable", "smart_passed": None,
                              "temperature_c": None, "smart_capacity_bytes": None,
                              "device_protocol": None, "reason": reason}
    measured = bool(disks)
    content = {"schema_id": "r3a.physical-resource-inventory.v1", "host_id": host_id,
               "observed_at": observed_at, "availability": "measured" if measured else "unavailable",
               "disks": disks, "error": None if measured else "no_physical_disks_reported"}
    freshness = "fresh" if measured else "unavailable"
    return _source_record(f"physical-resources.{host_id}", content, observed_at, configuration,
                          freshness, "lsblk --json --bytes; smartctl --json --all")


def _source_record(source_id: str, content: dict[str, Any], observed_at: str,
                   configuration: dict[str, Any], freshness: str, source_path: str) -> dict[str, Any]:
    return {"source_id": source_id, "source_path": source_path,
            "content": content, "sha256": _digest(content),
            "observed_at": observed_at, "source_timestamp": None,
            "source_timestamp_basis": "R3A collection time; device sample timestamp unavailable",
            "freshness": {"state": freshness, "age_seconds": 0 if freshness == "fresh" else None,
                          "max_age_seconds": configuration["max_age_seconds"]}}


def collect_software_inventory(configuration: dict[str, Any]) -> dict[str, Any]:
    observed_at = now_utc()
    executables = {}
    for name in configuration["executables"]:
        path = shutil.which(name)
        executables[name] = {"availability": "installed" if path else "unavailable",
                             "resolved_path": path}
    content = {"schema_id": "r3a.software-environment-inventory.v1",
               "host_id": configuration["host_id"], "observed_at": observed_at,
               "python": {"version": sys.version.split()[0], "executable": sys.executable},
               "executables": executables}
    return _source_record(f"software-environments.{configuration['host_id']}", content, observed_at, configuration,
                          "fresh", "Python runtime and PATH executable resolution")


class DiskHealthProvider:
    def __init__(self, configuration: dict[str, Any]):
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("physical resource read accepts no input fields")
        if not isinstance(context, dict):
            raise ValueError("provider invocation context must be an object")
        host_id = self.configuration["host_id"]
        _validate_target(context, host_id, f"physical-resources.{host_id}")
        return collect_disk_inventory(self.configuration)


class SoftwareInventoryProvider:
    def __init__(self, configuration: dict[str, Any]):
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        if arguments:
            raise ValueError("software environment read accepts no input fields")
        if not isinstance(context, dict):
            raise ValueError("provider invocation context must be an object")
        host_id = self.configuration["host_id"]
        _validate_target(context, host_id, f"software-environments.{host_id}")
        return collect_software_inventory(self.configuration)


def create_disk_provider(configuration: dict[str, Any]) -> DiskHealthProvider:
    return DiskHealthProvider(configuration)


def create_software_provider(configuration: dict[str, Any]) -> SoftwareInventoryProvider:
    return SoftwareInventoryProvider(configuration)
