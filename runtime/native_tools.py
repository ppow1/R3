# R3 CONTROLLED SOURCE
# File: runtime/native_tools.py
# Component: R3-NATIVE-TOOLS
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: R3-owned discovery and invocation client with per-call correlation metadata.
# Contracts: docs/r3-native-tool-contract.md
# Changed: 2026-11-06T02:24:00Z | GRACE-AUTONOMY-P2 | Codex GPT-6 | Attach correlation metadata to every invocation for durable exact-grant auditing.
# Supersedes: Revision 1.0.0; read operations now receive generated correlation IDs when the caller has none.
# Tests: tests/test_native_tools.py; tests/test_native_correlation_contract.py; tests/test_proposal_submission_integration.py
"""R3-native tool client; every invocation remains subject to server-side grants."""
from __future__ import annotations

import json
import urllib.request
import uuid
from dataclasses import dataclass


class ToolContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class NativeTools:
    base_url: str
    timeout: float
    allowed_tools: tuple[str, ...]
    credential: str | None = None

    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Tool endpoint must be HTTP(S)")
        if self.timeout <= 0:
            raise ValueError("Tool timeout must be positive")

    def _request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path, data=data,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": "Bearer " + self.credential}
                   if self.credential else {}),
            }, method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def discover(self) -> list[dict]:
        data = self._request("GET", "/v1/tools")
        if not isinstance(data, list):
            raise ToolContractError("Discovery response must be a list")
        result = []
        for descriptor in data:
            if not isinstance(descriptor, dict):
                raise ToolContractError("Invalid descriptor")
            name = descriptor.get("tool")
            definition = descriptor.get("definition")
            if not isinstance(name, str) or not name or not isinstance(definition, dict):
                raise ToolContractError("Invalid tool name or definition")
            function = definition.get("function")
            if not isinstance(function, dict) or function.get("name") != name:
                raise ToolContractError("Tool definition mismatch")
            if not isinstance(descriptor.get("read_only"), bool):
                raise ToolContractError("Missing read-only classification")
            if name in self.allowed_tools:
                result.append(descriptor)
        return result

    def invoke(self, descriptor: dict, params: dict, *, correlation_id: str | None = None) -> str:
        if not isinstance(params, dict):
            raise ToolContractError("Arguments must be an object")
        name = descriptor.get("tool")
        if not isinstance(name, str) or name not in self.allowed_tools:
            raise PermissionError("Tool not authorized")
        if descriptor.get("read_only") is not True and not self.credential:
            raise PermissionError("Write tool requires resident credential")
        payload = {"tool": name, "params": params}
        if descriptor.get("read_only") is not True:
            if not isinstance(correlation_id, str) or not correlation_id:
                raise ToolContractError("Write tool requires correlation_id")
        elif correlation_id is None:
            correlation_id = "read-" + uuid.uuid4().hex
        if not isinstance(correlation_id, str) or not correlation_id:
            raise ToolContractError("Invocation correlation_id must be nonempty text")
        payload["correlation_id"] = correlation_id
        response = self._request("POST", "/v1/tools/invoke", payload)
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise ToolContractError("Invalid invocation response")
        if not response["ok"]:
            raise ToolContractError("Tool execution failed")
        return json.dumps(response.get("result"), ensure_ascii=False)
