"""R3 CONTROLLED SOURCE
File: r3a_plugins/reasoning_inference/plugin.py
Component: R3A-AP2-MODEL-INVOCATION-PROVIDER
File Revision: 1.1.0
Created: 2026-11-07 UTC
Created By: Codex GPT-6
Purpose: Execute a CME-authorized, configured model-role inference as a canonical capability provider.
Execution Model: CME invokes the provider only after authorization and durable activity-budget reservation.
Observability: Request/result references, digests, route identity, token usage, and timing are returned as evidence.
Dependencies: Python standard library; r3a.capability-operation.v1; configured OpenAI-compatible route context.
Authority: R3 Alpha autonomy Task B, GitHub Issues #43 and #46.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Implement canonical model inference provider.
Changed: 2026-11-07T21:59:02Z | R3A-AP3-M2-CONSUMER | Codex GPT-6 | Resolve configured secret references inside authorized inference calls and redact/close leases.
Supersedes: None.
Contracts: r3a.capability-operation.v1; r3a.capability-invocation.v1; r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: tests/test_r3a_reasoning_provider.py; tests/test_r3a_bitwarden_consumer_integration.py.
History/Predecessor: Revision 1.0.0 at commit d07bade6dfa6e6ef498f454d82866aa592b899ba, blob b1452ee197a37b1a66ce8160bd9e3c2a1022e769.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult
from r3a_runtime.secrets import (SECRET_PROVIDER_CONTRACT_ID, SECRET_PROVIDER_CONTRACT_VERSION,
                                 SecretProviderError, SecretReference)

from r3a_plugins.bitwarden_secrets.provider import load_configured_provider


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ModelInferenceProvider:
    """Run one inference at the CME-selected configured model role."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = dict(configuration)
        self.secret_reference_configuration = self.configuration.get("secret_reference")
        self.secret_provider = None

    @staticmethod
    def _validate_secret_reference_configuration(value: Any) -> None:
        required = {"provider_id", "provider_version", "secret_id", "manifest_path",
                    "configuration_path"}
        if (not isinstance(value, dict) or set(value) != required
                or any(not isinstance(value[key], str) or not value[key].strip() for key in required)):
            raise ValueError("configured model secret reference is invalid")
        if value["provider_id"] != "r3a.bitwarden-secrets" or value["provider_version"] != "1.1.0":
            raise ValueError("configured model secret provider identity or version is unsupported")
        if not value["manifest_path"].startswith("/") or not value["configuration_path"].startswith("/"):
            raise ValueError("model secret provider files must use absolute external paths")

    def _resolve_api_key(self, correlation_id: str):
        """Return an env credential or a private lease for this authorized provider call."""
        if self.secret_reference_configuration is not None:
            if self.secret_provider is None:
                try:
                    self.secret_provider = load_configured_provider(
                        self.secret_reference_configuration["manifest_path"],
                        self.secret_reference_configuration["configuration_path"])
                except Exception:
                    raise RuntimeError(
                        "configured model secret provider outcome: FAILED (provider_configuration_invalid)") from None
            reference = self.secret_reference_configuration
            secret_ref = SecretReference(
                provider_id=reference["provider_id"], provider_version=reference["provider_version"],
                secret_id=reference["secret_id"], contract_id=SECRET_PROVIDER_CONTRACT_ID,
                contract_version=SECRET_PROVIDER_CONTRACT_VERSION)
            try:
                return self.secret_provider.resolve(secret_ref, correlation_id=correlation_id)
            except SecretProviderError as exc:
                raise RuntimeError(
                    f"configured model secret provider outcome: {exc.outcome} ({exc.reason_code})") from None
        api_key_env = self.configuration.get("api_key_env")
        if api_key_env:
            api_key = os.environ.get(api_key_env)
            if not api_key:
                raise RuntimeError("configured inference credential is unavailable")
            return api_key
        return None

    @staticmethod
    def _redact(value: Any, secret: str) -> Any:
        """Remove any exact credential echo before provider data can become durable output."""
        if not secret:
            return value
        if isinstance(value, str):
            return value.replace(secret, "[REDACTED]")
        if isinstance(value, list):
            return [ModelInferenceProvider._redact(item, secret) for item in value]
        if isinstance(value, dict):
            return {(key.replace(secret, "[REDACTED]") if isinstance(key, str) else key):
                    ModelInferenceProvider._redact(item, secret) for key, item in value.items()}
        return value

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        if self.secret_reference_configuration is not None:
            if self.configuration.get("api_key_env"):
                raise ValueError("model inference must use either api_key_env or secret_reference, not both")
            self._validate_secret_reference_configuration(self.secret_reference_configuration)
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
        started = time.perf_counter()
        lease = self._resolve_api_key(str(context.get("correlation_id") or request_ref))
        api_key = None
        credential_source = None
        try:
            api_key = lease.reveal() if lease is not None and hasattr(lease, "reveal") else lease
            principal = getattr(lease, "machine_principal", None)
            if principal is not None:
                credential_source = {
                    "contract_id": SECRET_PROVIDER_CONTRACT_ID,
                    "contract_version": SECRET_PROVIDER_CONTRACT_VERSION,
                    "provider_id": lease.provider_id,
                    "provider_version": lease.provider_version,
                    "secret_id": lease.secret_id,
                    "remote_revision": lease.remote_revision,
                    "fetched_at": lease.fetched_at,
                    "machine_principal": {
                        "contract_id": principal.contract_id,
                        "contract_version": principal.contract_version,
                        "issuer": principal.issuer,
                        "principal_id": principal.principal_id,
                        "authenticated_at": principal.authenticated_at,
                        "correlation_id": principal.correlation_id,
                    },
                }
            if isinstance(api_key, str) and api_key.encode() in body:
                raise RuntimeError("inference request body contains configured credential material")
            if api_key is not None:
                headers["Authorization"] = f"Bearer {api_key}"
            http_request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(http_request, timeout=float(timeout)) as response:
                raw = response.read(1_000_000)
            payload = json.loads(raw)
            raw = b""
            if isinstance(api_key, str):
                payload = self._redact(payload, api_key)
        except urllib.error.HTTPError as exc:
            try:
                exc.close()
            except OSError:
                pass
            raise RuntimeError(f"model provider returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            raise RuntimeError("model provider transport failed") from None
        finally:
            if lease is not None and hasattr(lease, "close"):
                lease.close()
            api_key = None
            headers.clear()
            http_request = None
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        choices = payload.get("choices")
        content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices else None
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("model provider returned no assistant content")
        content = content.strip()
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
        if credential_source is not None:
            evidence["credential_source"] = credential_source
        return CapabilityProviderResult(output, [evidence])


def create_provider(configuration: dict[str, Any]) -> ModelInferenceProvider:
    return ModelInferenceProvider(configuration)
