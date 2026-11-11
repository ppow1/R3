"""Direct NVIDIA process-to-GPU observations and explicit model mapping."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from typing import Any, Callable


PROCESS_QUERY = (
    "nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory "
    "--format=csv,noheader,nounits"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_compute_apps(output: str, *, host_id: str, observed_at: str,
                       model_process_names: dict[str, str] | None = None) -> list[dict[str, Any]]:
    mappings = model_process_names or {}
    rows = []
    for fields in csv.reader(io.StringIO(output)):
        if len(fields) != 4:
            raise ValueError("nvidia-smi process query returned malformed columns")
        gpu_uuid, pid_text, process_name, memory_text = (field.strip() for field in fields)
        if not gpu_uuid or not pid_text.isdigit() or not process_name:
            raise ValueError("nvidia-smi process query omitted identity")
        memory = None if memory_text.upper() in {"N/A", "[NOT SUPPORTED]"} else float(memory_text)
        if memory is not None and (not math.isfinite(memory) or memory < 0):
            raise ValueError("nvidia-smi process query returned invalid GPU memory")
        model_id = mappings.get(process_name)
        rows.append({
            "resource_id": f"{host_id}:nvidia:{gpu_uuid}:pid:{pid_text}", "host_id": host_id,
            "nvidia_uuid": gpu_uuid, "pid": int(pid_text), "process_name": process_name,
            "gpu_memory_mib": memory, "model_id": model_id,
            "model_mapping_state": "configured" if model_id else "unmapped",
            "process_gpu_provenance": "nvidia-smi --query-compute-apps direct host observation",
            "model_mapping_provenance": "R3A model_process_names configuration" if model_id else None,
            "observed_at": observed_at,
        })
    return rows


def read_compute_apps(config: dict[str, Any], run_query: Callable[[str], str]) -> dict[str, Any]:
    observed_at = _now()
    source_id = f"gpu.processes.{config['host_id']}"
    try:
        output = run_query(PROCESS_QUERY)
        processes = parse_compute_apps(output, host_id=str(config["host_id"]),
                                       observed_at=observed_at,
                                       model_process_names=config.get("model_process_names", {}))
        content = {"available": True, "host_id": str(config["host_id"]),
                   "processes": processes, "mapping_config_sha256": hashlib.sha256(
                       json.dumps(config.get("model_process_names", {}), sort_keys=True,
                                  separators=(",", ":")).encode()).hexdigest()}
        error = None
        state = "fresh"
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
        reason = str(exc) if str(exc).startswith(("ssh_exit_", "openssh_", "r3a_ssh_")) else type(exc).__name__
        content = {"available": False, "host_id": str(config["host_id"]), "error": reason}
        error = reason
        state = "unavailable"
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"source_id": source_id, "source_path": "nvidia-smi --query-compute-apps over configured R3A SSH",
            "content": content, "sha256": digest, "observed_at": observed_at,
            "source_timestamp": None,
            "source_timestamp_basis": "R3A collection time; NVIDIA process sample timestamp unavailable",
            "units": {"gpu_memory_mib": "MiB"},
            "freshness": {"state": state, "age_seconds": 0 if state == "fresh" else None,
                          "max_age_seconds": config["max_age_seconds"]}, "error": error}
