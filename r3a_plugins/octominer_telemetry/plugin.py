"""R3A-owned, read-only NVIDIA telemetry over pinned-key OpenSSH."""
# R3 CONTROLLED SOURCE
# File: r3a_plugins/octominer_telemetry/plugin.py
# Component: R3A-PLUG-OCTOMINER
# File Revision: 3.0.0
# Created: 2026-11-07T04:19:12Z
# Created By: Codex GPT-6
# Purpose: Collect direct host, model server, ComfyUI, request and bounded-history telemetry.
# Execution Model: In-process adapter uses fixed SSH commands and configured HTTP GET sources.
# Observability: Source IDs, collection times, metric units, digests, provenance and freshness states.
# Dependencies: Python standard library; OpenSSH client; remote nvidia-smi; R3A database read-only DSN.
# Authority: Issue #46; explicit R3A capability grant; strict host-key verification; no legacy service calls.
# Changed: 2026-11-07 | R3A-PLUG-002 | Codex GPT-6 | Add measured GPU fan and filesystem capacity sources.
# Changed: 2026-11-07 | R3A-PLUG-003 | Codex GPT-6 | Add model, ComfyUI, process, request and rolling-history providers.
# Changed: 2026-11-07 | R3A-PLUG-001 | Codex GPT-6 | Replace legacy API reader with independent R3A SSH collection.
# Supersedes: Revision 2.0.0; add measured per-GPU fan and mounted-filesystem capacity.
# Supersedes: Revision 1.0.0; remove Riverview Octo Control runtime dependency per steward correction.
# Contracts: r3a.capability-operation.v1; temporary resident-tool projection; r3a.octominer-independent-telemetry.config.v2.
# Tests: tests/test_r3a_octominer_plugin.py; tests/test_r3a_telemetry_providers.py.
# History/Predecessor: Git commit dee12de54618e36cce42b8002d7fb5cf1f436ec8.

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .history import apply_freshness_and_history
from .http_providers import read_comfyui, read_model_servers
from .process_providers import PROCESS_QUERY, read_compute_apps
from .request_metrics import read_r3a_model_turns


QUERY_FIELDS = (
    "uuid,name,pci.bus_id,driver_version,memory.total,memory.used,memory.free,"
    "utilization.gpu,temperature.gpu,power.draw,fan.speed"
)
REMOTE_QUERY = f"nvidia-smi --query-gpu={QUERY_FIELDS} --format=csv,noheader,nounits"
FILESYSTEM_QUERY = "df -P -B1 -x tmpfs -x devtmpfs"
FIELD_UNITS = {
    "memory_total_mib": "MiB", "memory_used_mib": "MiB", "memory_free_mib": "MiB",
    "utilization_percent": "%", "temperature_c": "degC", "power_draw_w": "W",
    "fan_speed_percent": "%", "filesystem_size_bytes": "B",
    "filesystem_used_bytes": "B", "filesystem_available_bytes": "B",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _number(value: str) -> float | None:
    value = value.strip()
    if not value or value.upper() in {"N/A", "[N/A]", "[NOT SUPPORTED]"}:
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nvidia-smi returned a non-finite metric")
        return number
    except ValueError as exc:
        raise ValueError("nvidia-smi returned a non-numeric metric") from exc


def parse_nvidia_smi_csv(output: str, *, host_id: str, collected_at: str) -> list[dict[str, Any]]:
    """Normalize the fixed eleven-column CSV query without trusting runtime ordinals."""
    devices: list[dict[str, Any]] = []
    for fields in csv.reader(io.StringIO(output)):
        if len(fields) != 11:
            raise ValueError("nvidia-smi returned malformed telemetry columns")
        gpu_uuid, name, pci_bus_id, driver = (item.strip() for item in fields[:4])
        if not gpu_uuid or not name:
            raise ValueError("nvidia-smi omitted physical GPU identity")
        devices.append({
            "resource_id": f"{host_id}:nvidia:{gpu_uuid}", "host_id": host_id,
            "nvidia_uuid": gpu_uuid, "name": name, "pci_bus_id": pci_bus_id or None,
            "driver_version": driver or None, "memory_total_mib": _number(fields[4]),
            "memory_used_mib": _number(fields[5]), "memory_free_mib": _number(fields[6]),
            "utilization_percent": _number(fields[7]), "temperature_c": _number(fields[8]),
            "power_draw_w": _number(fields[9]), "fan_speed_percent": _number(fields[10]),
            "observed_at": collected_at,
            "evidence_source": "nvidia-smi over R3A-configured OpenSSH",
        })
    if not devices:
        raise ValueError("nvidia-smi returned no GPU rows")
    return devices


def parse_df_posix(output: str, *, host_id: str, collected_at: str) -> list[dict[str, Any]]:
    """Parse POSIX df rows into byte-accurate, per-filesystem measurements."""
    rows: list[dict[str, Any]] = []
    for line in output.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 6:
            raise ValueError("df returned malformed filesystem columns")
        # POSIX df may wrap a long source path onto a preceding line. The
        # configured OctoMiner source is expected to use one-line output.
        source, size, used, available, percent, mountpoint = fields[-6:]
        try:
            size_n, used_n, available_n = int(size), int(used), int(available)
        except ValueError as exc:
            raise ValueError("df returned non-numeric capacity") from exc
        if min(size_n, used_n, available_n) < 0 or not percent.endswith("%"):
            raise ValueError("df returned invalid capacity")
        rows.append({"resource_id": f"{host_id}:filesystem:{mountpoint}", "host_id": host_id,
                     "filesystem": source, "mountpoint": mountpoint,
                     "size_bytes": size_n, "used_bytes": used_n,
                     "available_bytes": available_n, "used_percent": _number(percent[:-1]),
                     "observed_at": collected_at,
                     "evidence_source": "df over R3A-configured OpenSSH"})
    if not rows:
        raise ValueError("df returned no filesystem rows")
    return rows


def _ssh_command(config: dict[str, Any], remote_command: str = REMOTE_QUERY) -> list[str]:
    """Build an SSH invocation with all transport policy owned by R3A config."""
    if remote_command not in {REMOTE_QUERY, FILESYSTEM_QUERY, PROCESS_QUERY}:
        raise RuntimeError("r3a_ssh_command_not_allowlisted")
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("openssh_client_unavailable")
    identity = Path(_configured_value(config["identity_file"])).expanduser().resolve()
    known_hosts = Path(_configured_value(config["known_hosts_file"])).expanduser().resolve()
    if not identity.is_file() or not known_hosts.is_file():
        raise RuntimeError("r3a_ssh_credential_or_host_key_file_unavailable")
    ssh_host = _configured_value(config["ssh_host"])
    ssh_user = _configured_value(config["ssh_user"])
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", ssh_host):
        raise RuntimeError("r3a_ssh_host_invalid")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,31}", ssh_user):
        raise RuntimeError("r3a_ssh_user_invalid")
    port = config["ssh_port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise RuntimeError("r3a_ssh_port_invalid")
    timeout = config["timeout_seconds"]
    max_age = config["max_age_seconds"]
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 30
            or isinstance(max_age, bool) or not isinstance(max_age, (int, float)) or not 1 <= max_age <= 300):
        raise RuntimeError("r3a_ssh_freshness_or_timeout_config_invalid")
    return [ssh, "-F", "/dev/null", "-T", "-n", "-i", str(identity),
            "-p", str(port),
            "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", f"UserKnownHostsFile={known_hosts}",
            "-o", "GlobalKnownHostsFile=/dev/null", "-o", "ClearAllForwardings=yes",
            "-o", "PermitLocalCommand=no", "-o", "RequestTTY=no",
            f"{ssh_user}@{ssh_host}", remote_command]


def _configured_value(value: str) -> str:
    match = re.fullmatch(r"\$\{([A-Z][A-Z0-9_]*)\}", str(value))
    if match:
        resolved = os.environ.get(match.group(1))
        if not resolved:
            raise RuntimeError("r3a_ssh_config_env_unavailable")
        return resolved
    return str(value)


def _run_ssh_query(config: dict[str, Any], remote_command: str) -> str:
    completed = subprocess.run(_ssh_command(config, remote_command), capture_output=True, text=True,
                               timeout=float(config["timeout_seconds"]), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ssh_exit_{completed.returncode}")
    return completed.stdout


def _collect_source(config: dict[str, Any], *, source_kind: str, value_key: str,
                    remote_command: str, parser) -> dict[str, Any]:
    started_at = _now()
    host_id = str(config["host_id"])
    source_id = f"{source_kind}.telemetry.{host_id}"
    try:
        output = _run_ssh_query(config, remote_command)
        collected_at = _now()
        values = parser(output, host_id=host_id, collected_at=collected_at)
        content: dict[str, Any] = {"available": True, "host_id": host_id, value_key: values}
        state = "fresh"
        error = None
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        collected_at = _now()
        # Do not persist stderr or command output: either can contain host details.
        reason = str(exc) if str(exc).startswith(("ssh_exit_", "openssh_", "r3a_ssh_")) else type(exc).__name__
        content = {"available": False, "host_id": host_id, "error": reason}
        values = []
        state = "unavailable"
        error = reason
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "source_id": source_id, "source_path": f"ssh://{config.get('host_id', 'configured-host')}/{remote_command.split()[0]}",
        "content": content, "sha256": digest, "observed_at": collected_at,
        "source_timestamp": None, "source_timestamp_basis": "R3A collection time; source sample timestamp unavailable",
        "units": FIELD_UNITS, "freshness": {"state": state, "age_seconds": 0 if state == "fresh" else None,
                                            "max_age_seconds": float(config["max_age_seconds"])},
        "collection_started_at": started_at, "collection_finished_at": collected_at,
        "error": error,
    }


def read_telemetry(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect independently sourced telemetry and append a bounded local sample history."""
    samples = [
        _collect_source(config, source_kind="gpu", value_key="gpus", remote_command=REMOTE_QUERY,
                        parser=parse_nvidia_smi_csv),
        _collect_source(config, source_kind="storage", value_key="filesystems", remote_command=FILESYSTEM_QUERY,
                        parser=parse_df_posix),
        read_compute_apps(config, lambda command: _run_ssh_query(config, command)),
    ]
    samples.extend(read_model_servers(config))
    samples.extend(read_comfyui(config))
    samples.append(read_r3a_model_turns(config))
    normalized, history = apply_freshness_and_history(samples, config)
    normalized.append(history)
    return normalized


class OctoMinerTelemetryProvider:
    """Canonical capability provider binding for the existing read-only collectors."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> list[dict[str, Any]]:
        if arguments:
            raise ValueError("octominer telemetry read accepts no input fields")
        if not isinstance(context, dict):
            raise ValueError("provider invocation context must be an object")
        return read_telemetry(self.configuration)


def create_provider(configuration: dict[str, Any]) -> OctoMinerTelemetryProvider:
    """Construct a provider instance for the canonical operation registry."""
    return OctoMinerTelemetryProvider(configuration)
