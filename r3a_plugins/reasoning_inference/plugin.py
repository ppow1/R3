"""R3 CONTROLLED SOURCE
File: r3a_plugins/reasoning_inference/plugin.py
Component: R3A-AP2-MODEL-INVOCATION-PROVIDER
File Revision: 1.0.0
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Execute a CME-authorized, configured model-role inference as a canonical capability provider.
Execution Model: CME invokes the provider only after authorization and durable activity-budget reservation.
Observability: Request/result references, digests, route identity, token usage, and timing are returned as evidence.
Dependencies: Python standard library; r3a.capability-operation.v1; configured OpenAI-compatible route context.
Authority: R3 Alpha autonomy Task B, GitHub Issues #43 and #46.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Implement canonical model inference provider.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.capability-invocation.v1.
Tests: tests/test_r3a_reasoning_provider.py; isolated live inference.
History/Predecessor: New file; initial revision recorded in Git.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ModelInferenceProvider:
    """Run one inference at the CME-selected configured model role."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = dict(configuration)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        route = context.get("model_route")
        role_id = context.get("model_role_id")
        if not isinstance(route, dict) or not isinstance(role_id, str):
            raise ValueError("CME did not supply a configured model role and route")
        endpoint, model = route.get("endpoint"), route.get("model")
        max_tokens, timeout = route.get("max_tokens"), route.get("timeout_seconds")
        messages = arguments.get("messages")
        if (not isinstance(endpoint, str) or not endpoint.startswith(("http://", "https://"))
                or not isinstance(model, str) or not model.strip()
                or not isinstance(max_tokens, int) or not isinstance(timeout, (int, float))
                or not isinstance(messages, list) or not messages):
            raise ValueError("configured model route or inference input is invalid")
        request = {"model": model, "messages": messages,
                   "max_tokens": max_tokens, "temperature": self.configuration["temperature"],
                   "stream": False}
        body = json.dumps(request, separators=(",", ":")).encode()
        request_digest = hashlib.sha256(body).hexdigest()
        request_ref = str(context["invocation_id"])
        headers = {"Content-Type": "application/json"}
        api_key_env = self.configuration.get("api_key_env")
        if api_key_env:
            import os
            api_key = os.environ.get(api_key_env)
            if not api_key:
                raise RuntimeError(f"configured inference credential is unavailable: {api_key_env}")
            headers["Authorization"] = f"Bearer {api_key}"
        http_request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(http_request, timeout=float(timeout)) as response:
                raw = response.read(1_000_000)
                payload = json.loads(raw)
        except urllib.error.HTTPError as exc:
            detail = exc.read(4000).decode("utf-8", "replace")
            raise RuntimeError(f"model provider returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"model provider transport failed: {exc}") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        choices = payload.get("choices")
        content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("model provider returned no assistant content")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        result_ref = payload.get("id") if isinstance(payload.get("id"), str) else None
        result_digest = hashlib.sha256(content.encode()).hexdigest()
        finished_at = _utcnow()
        output = {"role_id": role_id, "route_id": route.get("route_id"), "provider": route.get("provider"),
                  "model": model, "content": content.strip(), "provider_result_ref": result_ref,
                  "usage": usage, "elapsed_ms": elapsed_ms, "finished_at": finished_at}
        evidence = {"evidence_id": f"model-inference:{request_ref}", "request_ref": request_ref,
                    "request_sha256": request_digest, "result_ref": result_ref,
                    "result_sha256": result_digest, "role_id": role_id,
                    "route_id": route.get("route_id"), "provider": route.get("provider"),
                    "model": model, "usage": usage, "elapsed_ms": elapsed_ms,
                    "observed_at": finished_at}
        return CapabilityProviderResult(output, [evidence])


def create_provider(configuration: dict[str, Any]) -> ModelInferenceProvider:
    return ModelInferenceProvider(configuration)
