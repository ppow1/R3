"""Direct, read-only providers for llama.cpp-compatible servers and ComfyUI."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("endpoint_url_invalid")
    host = parsed.hostname.casefold()
    local = host in {"localhost", "localhost.localdomain"}
    try:
        local = local or ipaddress.ip_address(host).is_loopback
    except ValueError:
        pass
    if parsed.scheme != "https" and not local:
        try:
            private = ipaddress.ip_address(host).is_private
        except ValueError:
            private = False
        if not private:
            raise ValueError("endpoint_must_use_https_or_private_address")
    return base_url.rstrip("/")


def _source_base_url(source: dict[str, Any]) -> str:
    env_name = source.get("base_url_env")
    base_url = os.environ.get(env_name) if isinstance(env_name, str) else source.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        raise RuntimeError("configured_source_endpoint_unavailable")
    return _safe_base_url(base_url)


def _get_json(source: dict[str, Any], path: str, timeout: float) -> tuple[Any, str, str | None]:
    url = _source_base_url(source) + path
    headers = {"Accept": "application/json"}
    token_env = source.get("token_env")
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            raise RuntimeError("configured_source_credential_unavailable")
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"http_status_{response.status}")
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise RuntimeError("source_response_too_large")
            date = response.headers.get("Date")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"http_status_{exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("http_transport_unavailable") from None
    try:
        return json.loads(raw), _now(), date
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("source_json_invalid") from None


def _evidence(source_id: str, source_path: str, content: dict[str, Any], observed_at: str,
              date_header: str | None, max_age_seconds: float) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    available = content.get("available") is True
    return {
        "source_id": source_id, "source_path": source_path, "content": content,
        "sha256": digest, "observed_at": observed_at, "source_timestamp": None,
        "source_timestamp_basis": "R3A retrieval time; endpoint sample timestamp not supplied",
        "http_date_header": date_header,
        "freshness": {"state": "fresh" if available else "unavailable", "age_seconds": 0 if available else None,
                      "max_age_seconds": max_age_seconds},
    }


def _unavailable(source_id: str, source_path: str, reason: str, max_age_seconds: float) -> dict[str, Any]:
    return _evidence(source_id, source_path, {"available": False, "error": reason}, _now(), None,
                     max_age_seconds)


def read_model_servers(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Read health and active slots using only fixed GET routes and count-only projection."""
    result: list[dict[str, Any]] = []
    servers = config.get("model_servers", {})
    if not isinstance(servers, dict) or not servers:
        return [_unavailable("model-server.readiness", "not-configured", "source_not_configured", 0)]
    for service_id, source in sorted(servers.items()):
        if not isinstance(source, dict):
            result.append(_unavailable(f"model-server.{service_id}.readiness", "invalid-config",
                                       "source_configuration_invalid", 0))
            continue
        base = f"model-server:{service_id}"
        max_age = float(source.get("max_age_seconds", 30))
        timeout = float(source.get("timeout_seconds", 3))
        try:
            _, health_at, health_date = _get_json(source, "/health", timeout)
            health = {"available": True, "service_id": service_id, "ready": True,
                      "readiness_basis": "configured endpoint returned HTTP 2xx"}
            result.append(_evidence(f"model-server.{service_id}.readiness", base + "/health",
                                    health, health_at, health_date, max_age))
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            reason = str(exc) if str(exc).startswith(("http_status_", "endpoint_", "configured_", "source_")) else type(exc).__name__
            result.append(_unavailable(f"model-server.{service_id}.readiness", base + "/health", reason, max_age))
        try:
            slots, slots_at, slots_date = _get_json(source, "/slots", timeout)
            if not isinstance(slots, list) or any(not isinstance(slot, dict) for slot in slots):
                raise RuntimeError("slot_payload_invalid")
            if any(not isinstance(slot.get("is_processing"), bool) for slot in slots):
                raise RuntimeError("slot_activity_field_unavailable")
            active = sum(1 for slot in slots if slot["is_processing"])
            content = {"available": True, "service_id": service_id, "active_slots": active,
                       "configured_slots": len(slots), "slot_count_basis": "number of returned slot records",
                       "active_count_basis": "is_processing boolean per returned slot"}
            result.append(_evidence(f"model-server.{service_id}.slots", base + "/slots",
                                    content, slots_at, slots_date, max_age))
        except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
            reason = str(exc) if str(exc).startswith(("http_status_", "endpoint_", "configured_", "source_", "slot_")) else type(exc).__name__
            result.append(_unavailable(f"model-server.{service_id}.slots", base + "/slots", reason, max_age))
    return result


def _comfy_cuda_devices(system_stats: Any) -> list[dict[str, Any]]:
    if not isinstance(system_stats, dict):
        raise RuntimeError("comfy_system_payload_invalid")
    devices = system_stats.get("devices")
    if not isinstance(devices, list):
        raise RuntimeError("comfy_device_list_unavailable")
    output = []
    for device in devices:
        if not isinstance(device, dict):
            raise RuntimeError("comfy_device_entry_invalid")
        device_type = str(device.get("type", "")).casefold()
        if device_type in {"cuda", "cuda_malloc_async"}:
            total = device.get("vram_total")
            free = device.get("vram_free")
            total = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else None
            free = free if isinstance(free, int) and not isinstance(free, bool) and free >= 0 else None
            output.append({"name": device.get("name"), "device_type": device.get("type"),
                           "vram_total_bytes": total, "vram_free_bytes": free,
                           "vram_state": "measured" if total is not None and free is not None else "unavailable"})
    return output


def read_comfyui(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Read ComfyUI system statistics and queue counts; never return queue payloads."""
    source = config.get("comfyui")
    base = "comfyui"
    if not isinstance(source, dict):
        return [_unavailable("comfyui.system", "not-configured", "source_not_configured", 0),
                _unavailable("comfyui.queue", "not-configured", "source_not_configured", 0)]
    max_age = float(source.get("max_age_seconds", 30))
    timeout = float(source.get("timeout_seconds", 3))
    result = []
    try:
        payload, observed, date_header = _get_json(source, "/system_stats", timeout)
        system = payload.get("system") if isinstance(payload, dict) else None
        devices = _comfy_cuda_devices(payload)
        content = {"available": True, "version": system.get("comfyui_version") if isinstance(system, dict) else None,
                   "cuda_devices": devices}
        result.append(_evidence("comfyui.system", base + "/system_stats", content, observed, date_header, max_age))
    except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
        reason = str(exc) if str(exc).startswith(("http_status_", "endpoint_", "configured_", "source_", "comfy_")) else type(exc).__name__
        result.append(_unavailable("comfyui.system", base + "/system_stats", reason, max_age))
    try:
        payload, observed, date_header = _get_json(source, "/queue", timeout)
        if not isinstance(payload, dict) or not isinstance(payload.get("queue_running"), list) or not isinstance(payload.get("queue_pending"), list):
            raise RuntimeError("comfy_queue_payload_invalid")
        content = {"available": True, "running_count": len(payload["queue_running"]),
                   "pending_count": len(payload["queue_pending"]), "queue_content_projected": False}
        result.append(_evidence("comfyui.queue", base + "/queue", content, observed, date_header, max_age))
    except (KeyError, TypeError, ValueError, RuntimeError, OSError) as exc:
        reason = str(exc) if str(exc).startswith(("http_status_", "endpoint_", "configured_", "source_", "comfy_")) else type(exc).__name__
        result.append(_unavailable("comfyui.queue", base + "/queue", reason, max_age))
    return result
