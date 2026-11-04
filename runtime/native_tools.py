# R3 CONTROLLED SOURCE
# File: runtime/native_tools.py
# Component: R3-NATIVE-TOOLS
# File Revision: 1.0.0
# Created: 2026-11-02 UTC
# Purpose: R3-owned discovery and invocation client.
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_native_tools.py
"""R3-native tool client; read-only execution until server-side grants exist."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


class ToolContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class NativeTools:
    base_url: str
    timeout: float
    allowed_tools: tuple[str, ...]

    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Tool endpoint must be HTTP(S)")
        if self.timeout <= 0:
            raise ValueError("Tool timeout must be positive")

    def _request(self, method: str, path: str, payload: dict | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path, data=data,
            headers={"Content-Type": "application/json"}, method=method,
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

    def invoke(self, descriptor: dict, params: dict) -> str:
        if not isinstance(params, dict):
            raise ToolContractError("Arguments must be an object")
        name = descriptor.get("tool")
        if not isinstance(name, str) or name not in self.allowed_tools:
            raise PermissionError("Tool not authorized")
        if descriptor.get("read_only") is not True:
            raise PermissionError("Write tool requires server-side authorization")
        response = self._request("POST", "/v1/tools/invoke", {"tool": name, "params": params})
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise ToolContractError("Invalid invocation response")
        if not response["ok"]:
            raise ToolContractError("Tool execution failed")
        return json.dumps(response.get("result"), ensure_ascii=False)
