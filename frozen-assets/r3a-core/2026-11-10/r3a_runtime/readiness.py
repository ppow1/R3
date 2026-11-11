"""
R3 CONTROLLED SOURCE
File: r3a_runtime/readiness.py
Component: R3A-MODEL-READINESS-PROVIDERS
File Revision: 1.0.0
Created: 2026-11-07 UTC (exact time not captured)
Created By: Codex GPT-6
Purpose: Provide versioned, provider-backed model readiness observations without inference.
Execution Model: Async provider interface with bounded HTTP protocol probes.
Observability: Provider/model identity, response digest, status, latency, attempts, timestamp and config revision.
Dependencies: Python 3.12 standard library; r3a_runtime.contracts and configuration policy types.
Authority: R3A AP1 Modular Autonomy Implementation Slice 2; isolated development only.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Add the v1 provider interface and bounded model-catalog readiness probe without inference.
Supersedes: None.
Contracts: r3a.model-readiness-provider.v1; r3a.model-readiness.v1; R3A-019.
Tests: tests/test_r3a_readiness.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from .config import ModelReadinessPolicy, ModelRoute, ModelRole
from .contracts import ReadinessObservation


READINESS_PROVIDER_CONTRACT_ID = "r3a.model-readiness-provider"
READINESS_PROVIDER_CONTRACT_VERSION = "1.0.0"
OPENAI_MODELS_PROVIDER_ID = "openai-compatible.models"


@dataclass(frozen=True)
class ReadinessCheckRequest:
    contract_id: str
    contract_version: str
    resident_id: str
    role: ModelRole
    route: ModelRoute
    policy: ModelReadinessPolicy
    config_revision: str
    observation_id: str

    def __post_init__(self) -> None:
        if self.contract_id != READINESS_PROVIDER_CONTRACT_ID:
            raise ValueError("readiness provider contract identity mismatch")
        parts = self.contract_version.split(".")
        if len(parts) != 3 or not all(item.isdigit() for item in parts) or parts[0] != "1":
            raise ValueError("unsupported readiness provider contract version")


class ModelReadinessProvider(Protocol):
    provider_id: str
    contract_id: str
    contract_version: str

    async def observe(self, request: ReadinessCheckRequest) -> ReadinessObservation:
        """Return a typed provider-backed observation; this method must not infer."""


def _http_get(endpoint: str, timeout: float, api_key: str | None) -> tuple[int, bytes]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, headers=headers, method="GET")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return int(response.status), response.read(1_048_577)
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read(1_048_577)


class OpenAICompatibleModelsReadinessProvider:
    """Checks GET /models and requires the configured model ID in the provider response."""

    provider_id = OPENAI_MODELS_PROVIDER_ID
    contract_id = READINESS_PROVIDER_CONTRACT_ID
    contract_version = READINESS_PROVIDER_CONTRACT_VERSION

    def __init__(self, *, transport: Callable[[str, float, str | None], tuple[int, bytes]] = _http_get,
                 sleep: Callable[[float], Any] = asyncio.sleep):
        self._transport = transport
        self._sleep = sleep

    async def observe(self, request: ReadinessCheckRequest) -> ReadinessObservation:
        if request.policy.provider_id != self.provider_id:
            raise ValueError("readiness provider identity mismatch")
        started = time.monotonic()
        attempts = 0
        status_code: int | None = None
        response_digest: str | None = None
        model_ids: list[str] = []
        error_code: str | None = None
        status = "unknown"
        reason = "provider_response_unclassified"
        env_name = request.policy.api_key_env
        api_key = os.environ.get(env_name) if env_name else None
        for attempt in range(1, request.policy.max_attempts + 1):
            attempts = attempt
            try:
                status_code, body = await asyncio.wait_for(
                    asyncio.to_thread(self._transport, request.policy.endpoint,
                                      request.policy.timeout_seconds, api_key),
                    timeout=request.policy.timeout_seconds + 0.25)
                response_digest = hashlib.sha256(body).hexdigest()
                if status_code == 200:
                    try:
                        payload = json.loads(body)
                        data = payload.get("data") if isinstance(payload, dict) else None
                        if not isinstance(data, list):
                            raise ValueError("models response lacks a data list")
                        model_ids = [item["id"] for item in data
                                     if isinstance(item, dict) and isinstance(item.get("id"), str)]
                    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
                        status = "unknown"
                        reason = "invalid_models_response"
                        error_code = "invalid_provider_response"
                        break
                    if request.route.model in model_ids:
                        status, reason = "ready", "configured_model_present_in_provider_catalog"
                    else:
                        status, reason = "unavailable", "configured_model_absent_from_provider_catalog"
                    break
                if 400 <= status_code < 500 and status_code not in {408, 429}:
                    status = "unavailable"
                    reason = "provider_rejected_readiness_request"
                    error_code = f"http_{status_code}"
                    break
                error_code = f"http_{status_code}"
                reason = ("provider_rate_limited" if status_code == 429 else
                          "provider_request_timeout" if status_code == 408 else
                          "provider_server_error")
                status = "unavailable"
            except (TimeoutError, asyncio.TimeoutError):
                status = "unavailable"
                error_code, reason = "timeout", "provider_readiness_timeout"
            except (urllib.error.URLError, OSError, ConnectionError) as exc:
                status = "unavailable"
                error_code = type(exc).__name__
                reason = "provider_unreachable"
            except Exception as exc:
                error_code = type(exc).__name__
                reason = "provider_probe_error"
            if attempt < request.policy.max_attempts:
                await self._sleep(request.policy.retry_delay_seconds)
        elapsed_ms = round((time.monotonic() - started) * 1000, 3)
        evidence = {"provider_id": self.provider_id,
                    "provider_contract": f"{self.contract_id}@{self.contract_version}",
                    "protocol": "GET models catalog; no inference",
                    "http_status": status_code,
                    "configured_model_present": request.route.model in model_ids,
                    "returned_model_count": len(model_ids),
                    "response_sha256": response_digest,
                    "attempts": attempts, "latency_ms": elapsed_ms,
                    "error_code": error_code}
        evidence_ref = (f"sha256:{response_digest}" if response_digest else
                        f"probe:{self.provider_id}:{request.observation_id}")
        return ReadinessObservation(
            resident_id=request.resident_id, role_id=request.role.role_id,
            model_id=request.route.model, status=status, source="model_protocol",
            observed_at=datetime.now(timezone.utc).isoformat(),
            config_revision=request.config_revision, observation_id=request.observation_id,
            reason=reason, evidence_ref=evidence_ref, provider_id=self.provider_id,
            evidence=evidence)


_PROVIDERS: dict[str, Callable[[], ModelReadinessProvider]] = {}


def register_readiness_provider(provider_id: str,
                                factory: Callable[[], ModelReadinessProvider]) -> None:
    if not provider_id or provider_id in _PROVIDERS:
        raise ValueError(f"readiness provider already registered or invalid: {provider_id}")
    provider = factory()
    version = provider.contract_version.split(".")
    if (provider.provider_id != provider_id
            or provider.contract_id != READINESS_PROVIDER_CONTRACT_ID
            or len(version) != 3 or not all(item.isdigit() for item in version)
            or version[0] != "1"):
        raise ValueError("readiness provider does not implement the supported v1 contract")
    _PROVIDERS[provider_id] = factory


def create_readiness_provider(provider_id: str) -> ModelReadinessProvider:
    try:
        return _PROVIDERS[provider_id]()
    except KeyError as exc:
        raise ValueError(f"No readiness provider registered for {provider_id}") from exc


register_readiness_provider(OPENAI_MODELS_PROVIDER_ID, OpenAICompatibleModelsReadinessProvider)
