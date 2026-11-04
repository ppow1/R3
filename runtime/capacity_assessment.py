# R3 CONTROLLED SOURCE
# File: runtime/capacity_assessment.py
# Purpose: Read-only, evidence-based GPU capacity assessment. No authority is conferred.
from __future__ import annotations

def assess_gpu_capacity(resources: list[dict], *, required_vram_bytes: int) -> dict:
    if not isinstance(required_vram_bytes, int) or isinstance(required_vram_bytes, bool) or required_vram_bytes <= 0:
        raise ValueError("Positive integer VRAM requirement needed")
    if not isinstance(resources, list):
        raise ValueError("Snapshot list required")
    evaluated = []
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("kind") != "nvidia-gpu":
            continue
        capacity = resource.get("capacity")
        free = capacity.get("vram_free_bytes") if isinstance(capacity, dict) else None
        valid = isinstance(free, int) and not isinstance(free, bool) and free >= 0
        fresh = resource.get("fresh") is True
        online = resource.get("state") == "online"
        sourced = resource.get("source") == "r3:local-nvidia-smi"
        candidate = bool(valid and fresh and online and sourced and free >= required_vram_bytes)
        reason = ("untrusted-source" if not sourced else
                  "stale-or-unknown" if not fresh else
                  "not-online" if not online else
                  "unknown-free-vram" if not valid else
                  "insufficient-free-vram" if free < required_vram_bytes else
                  "observed-fit-only")
        evaluated.append({"resource_id": resource.get("resource_id"),
                          "host": resource.get("host"),
                          "observed_free_vram_bytes": free if valid else None,
                          "candidate": candidate, "reason": reason,
                          "authorized": None, "verified_working": None})
    evaluated.sort(key=lambda entry: str(entry["resource_id"]))
    return {"required_vram_bytes": required_vram_bytes,
            "candidates": [entry for entry in evaluated if entry["candidate"]],
            "evaluated": evaluated,
            "assessment": "observational-only",
            "execution_authorized": False, "model_fit_verified": False}
