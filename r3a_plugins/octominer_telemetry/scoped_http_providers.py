"""
R3 CONTROLLED SOURCE
File: r3a_plugins/octominer_telemetry/scoped_http_providers.py
Component: R3A-PLUG-OCTOMINER-SCOPED-HTTP
File Revision: 1.0.0
Created: 2026-11-11T18:01:43Z
Created By: Codex GPT-6
Purpose: Execute only selected, configured model-server and ComfyUI telemetry GETs.
Execution Model: In-process provider helper using fixed paths through existing HTTP contract utilities.
Observability: Selected source IDs and existing freshness/evidence envelopes.
Dependencies: r3a_plugins.octominer_telemetry.http_providers; configured source host metadata.
Authority: AD-024; Modular Plugins #46; read-only configured source scope.
Changed: 2026-11-11T18:01:43Z | R3A-MODULAR-PLUGINS-STEP-51 | Codex GPT-6 | Add source-selective HTTP telemetry reads.
Supersedes: None.
Contracts: r3a.capability-operation.v1 target_scope_schema.
Tests: tests/test_r3a_telemetry_target_scope.py.
History/Predecessor: New file; source contract is r3a_plugins/octominer_telemetry/http_providers.py at approved source a224a6b30f1e96b95a65fde6a50d81775f5e5039.
"""
from __future__ import annotations

from typing import Any

from .http_providers import _comfy_cuda_devices, _evidence, _get_json, _unavailable


def read_model_servers(config: dict[str, Any], selected_source_ids: set[str] | None = None
                       ) -> list[dict[str, Any]]:
    """Read only requested readiness/slot endpoints; ``None`` preserves full discovery."""
    result: list[dict[str, Any]] = []
    servers = config.get("model_servers", {})
    if not isinstance(servers, dict) or not servers:
        if selected_source_ids is None or "model-server.readiness" in selected_source_ids:
            return [_unavailable("model-server.readiness", "not-configured",
                                 "source_not_configured", 0)]
        return []
    for service_id, source in sorted(servers.items()):
        readiness_id = f"model-server.{service_id}.readiness"
        slots_id = f"model-server.{service_id}.slots"
        want_readiness = selected_source_ids is None or readiness_id in selected_source_ids
        want_slots = selected_source_ids is None or slots_id in selected_source_ids
        if not want_readiness and not want_slots:
            continue
        if not isinstance(source, dict):
            if want_readiness:
                result.append(_unavailable(readiness_id, "invalid-config",
                                           "source_configuration_invalid", 0))
            if want_slots:
                result.append(_unavailable(slots_id, "invalid-config",
                                           "source_configuration_invalid", 0))
            continue
        base = f"model-server:{service_id}"
        max_age = float(source.get("max_age_seconds", 30))
        timeout = float(source.get("timeout_seconds", 3))
        if want_readiness:
            try:
                _, observed_at, date_header = _get_json(source, "/health", timeout)
                content = {"available": True, "service_id": service_id, "ready": True,
                           "readiness_basis": "configured endpoint returned HTTP 2xx"}
                result.append(_evidence(readiness_id, base + "/health", content,
                                        observed_at, date_header, max_age))
            except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
                reason = (str(exc) if str(exc).startswith(
                    ("http_status_", "endpoint_", "configured_", "source_")) else type(exc).__name__)
                result.append(_unavailable(readiness_id, base + "/health", reason, max_age))
        if want_slots:
            try:
                slots, observed_at, date_header = _get_json(source, "/slots", timeout)
                if not isinstance(slots, list) or any(not isinstance(slot, dict) for slot in slots):
                    raise RuntimeError("slot_payload_invalid")
                if any(not isinstance(slot.get("is_processing"), bool) for slot in slots):
                    raise RuntimeError("slot_activity_field_unavailable")
                content = {"available": True, "service_id": service_id,
                           "active_slots": sum(1 for slot in slots if slot["is_processing"]),
                           "configured_slots": len(slots),
                           "slot_count_basis": "number of returned slot records",
                           "active_count_basis": "is_processing boolean per returned slot"}
                result.append(_evidence(slots_id, base + "/slots", content,
                                        observed_at, date_header, max_age))
            except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
                reason = (str(exc) if str(exc).startswith(
                    ("http_status_", "endpoint_", "configured_", "source_", "slot_"))
                          else type(exc).__name__)
                result.append(_unavailable(slots_id, base + "/slots", reason, max_age))
    return result


def read_comfyui(config: dict[str, Any], selected_source_ids: set[str] | None = None
                 ) -> list[dict[str, Any]]:
    """Read only requested ComfyUI paths, retaining count-only queue projection."""
    system_id, queue_id = "comfyui.system", "comfyui.queue"
    want_system = selected_source_ids is None or system_id in selected_source_ids
    want_queue = selected_source_ids is None or queue_id in selected_source_ids
    if not want_system and not want_queue:
        return []
    source = config.get("comfyui")
    base = "comfyui"
    if not isinstance(source, dict):
        result = []
        if want_system:
            result.append(_unavailable(system_id, "not-configured", "source_not_configured", 0))
        if want_queue:
            result.append(_unavailable(queue_id, "not-configured", "source_not_configured", 0))
        return result
    max_age = float(source.get("max_age_seconds", 30))
    timeout = float(source.get("timeout_seconds", 3))
    result: list[dict[str, Any]] = []
    if want_system:
        try:
            payload, observed_at, date_header = _get_json(source, "/system_stats", timeout)
            system = payload.get("system") if isinstance(payload, dict) else None
            devices = _comfy_cuda_devices(payload)
            content = {"available": True,
                       "version": system.get("comfyui_version") if isinstance(system, dict) else None,
                       "cuda_devices": devices}
            result.append(_evidence(system_id, base + "/system_stats", content,
                                    observed_at, date_header, max_age))
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            reason = (str(exc) if str(exc).startswith(
                ("http_status_", "endpoint_", "configured_", "source_", "comfy_"))
                      else type(exc).__name__)
            result.append(_unavailable(system_id, base + "/system_stats", reason, max_age))
    if want_queue:
        try:
            payload, observed_at, date_header = _get_json(source, "/queue", timeout)
            if (not isinstance(payload, dict)
                    or not isinstance(payload.get("queue_running"), list)
                    or not isinstance(payload.get("queue_pending"), list)):
                raise RuntimeError("comfy_queue_payload_invalid")
            content = {"available": True, "running_count": len(payload["queue_running"]),
                       "pending_count": len(payload["queue_pending"]),
                       "queue_content_projected": False}
            result.append(_evidence(queue_id, base + "/queue", content,
                                    observed_at, date_header, max_age))
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            reason = (str(exc) if str(exc).startswith(
                ("http_status_", "endpoint_", "configured_", "source_", "comfy_"))
                      else type(exc).__name__)
            result.append(_unavailable(queue_id, base + "/queue", reason, max_age))
    return result
