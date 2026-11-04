# R3 CONTROLLED SOURCE
# File: runtime/native_tools.py
# Component: R3-NATIVE-TOOLS
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: R3-owned discovery and invocation client with explicitly supplied resident credential.
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_native_tools.py
# Changed: 2026-11-04 UTC | R3-GRACE-AUTH-003 | Authenticated governed read/write contract with fail-closed legacy behavior.
# History/Predecessor: Git blob ad06a78b6ea847a7bc1d07d4604c131344cc084b
"""R3-native tool client; server grants alone authorize governed execution."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable


class ToolContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class NativeTools:
    base_url: str
    timeout: float
    allowed_tools: tuple[str, ...]
    credential_provider: Callable[[], str] | None = None

    def __post_init__(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Tool endpoint must be HTTP(S)")
        if self.timeout <= 0:
            raise ValueError("Tool timeout must be positive")

    def _request(self, method: str, path: str, payload: dict | None = None,
                 *, headers: dict[str, str] | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path, data=data,
            headers={"Content-Type": "application/json", **(headers or {})}, method=method,
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

    def invoke(self, descriptor: dict, params: dict, *,
               correlation_id: str | None = None) -> str:
        if not isinstance(params, dict) or not isinstance(descriptor, dict):
            raise ToolContractError("Arguments and descriptor must be objects")
        name = descriptor.get("tool")
        definition = descriptor.get("definition")
        if (not isinstance(name, str) or name not in self.allowed_tools
                or not isinstance(definition, dict)
                or definition.get("function", {}).get("name") != name):
            raise PermissionError("Tool not allowlisted or definition mismatch")

        governed = "resource_id" in descriptor or "operation" in descriptor
        payload = {"tool": name, "params": params}
        headers = None
        if governed:
            operation, resource = descriptor.get("operation"), descriptor.get("resource_id")
            if (operation not in ("read", "write") or not isinstance(resource, str)
                    or not resource or descriptor.get("read_only") is not (operation == "read")):
                raise ToolContractError("Invalid governed descriptor")
            if self.credential_provider is None:
                raise PermissionError("Independent R3 resident credential unavailable")
            if not isinstance(correlation_id, str) or not correlation_id:
                raise PermissionError("Governed invocation needs durable correlation")
            if not isinstance(params.get("scope_ref"), str) or not params["scope_ref"]:
                raise PermissionError("Governed invocation needs exact scope")
            token = self.credential_provider()
            if not isinstance(token, str) or not token or token != token.strip():
                raise PermissionError("Resident credential unavailable")
            headers = {"Authorization": "Bearer " + token}
            payload["correlation_id"] = correlation_id
        elif descriptor.get("read_only") is not True:
            # An ungoverned legacy tool never gets write permission by client flag.
            raise PermissionError("Write tool has no R3 governed server contract")

        if headers is None:
            response = self._request("POST", "/v1/tools/invoke", payload)
        else:
            response = self._request("POST", "/v1/tools/invoke", payload, headers=headers)
        if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
            raise ToolContractError("Invalid invocation response")
        if not response["ok"]:
            raise ToolContractError("Tool execution failed; uncertain writes must not be replayed")

        result = response.get("result")
        if governed:
            if not isinstance(result, dict):
                raise ToolContractError("Governed response lacks server evidence")
            evidence = result.get("authorization")
            if (not isinstance(evidence, dict)
                    or not isinstance(evidence.get("principal_id"), str)
                    or not evidence["principal_id"].startswith("resident:")
                    or not isinstance(evidence.get("grant_id"), str)
                    or not evidence["grant_id"]
                    or evidence.get("resource_id") != resource
                    or evidence.get("operation") != operation
                    or result.get("correlation_id") != correlation_id):
                raise ToolContractError("Governed server authorization evidence mismatch")
        return json.dumps(result, ensure_ascii=False)
