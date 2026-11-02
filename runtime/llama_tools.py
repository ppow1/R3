# R3 CONTROLLED SOURCE
# File: runtime/llama_tools.py
# Component: R3-LLAMA-TOOLS-ADAPTER
# File Revision: 1.0.0
# Created: 2026-11-02 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Adapt the existing llama.cpp /tools HTTP contract for R3 residents.
# Execution Model: Synchronous HTTP adapter, invoked by async callers via asyncio.to_thread.
# Observability: Explicit exceptions on HTTP, schema, and tool errors.
# Dependencies: Python 3.12 stdlib; llama.cpp tools API (README-dev.md).
# Authority: R3 charter and engineering-test-policy; no automatic write grants.
# Changed: 2026-11-02 UTC | R3-GRACE-003 | Initial isolated tools API adapter.
# Supersedes: None
# Contracts: llama.cpp GET /tools and POST /tools; MCP exposed by llama.cpp.
# Tests: Permanent contract coverage pending; not deployed.
# History/Predecessor: New file.
"""Adapter for llama.cpp's existing /tools endpoint (not an MCP implementation).

The /tools API is experimental; keep its schema confined to this module.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass


class ToolContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class LlamaTools:
    base_url: str
    timeout: float = 120.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Tool endpoint must be HTTP(S)")

    def _request(self, method: str, payload: dict | None = None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/tools",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def discover(self) -> list[dict]:
        tools = self._request("GET")
        if not isinstance(tools, list):
            raise ToolContractError("GET /tools did not return a list")
        for tool in tools:
            if not isinstance(tool, dict) or not isinstance(tool.get("tool"), str):
                raise ToolContractError("Invalid tool descriptor")
            if not isinstance(tool.get("definition"), dict):
                raise ToolContractError("Missing OpenAI-compatible tool definition")
        return tools

    def invoke(self, descriptor: dict, params: dict, *, allow_write: bool = False) -> str:
        if not isinstance(params, dict):
            raise ToolContractError("Tool arguments must be an object")
        permissions = descriptor.get("permissions", {})
        if not isinstance(permissions, dict):
            raise ToolContractError("Invalid tool permissions")
        if permissions.get("write") and not allow_write:
            raise PermissionError("Tool requires explicit write authorization")
        if any(key != "write" and value for key, value in permissions.items()):
            raise PermissionError("Tool requests an unsupported permission")
        result = self._request("POST", {"tool": descriptor["tool"], "params": params})
        if not isinstance(result, dict):
            raise ToolContractError("Unexpected POST /tools response")
        if "error" in result:
            raise ToolContractError(str(result["error"]))
        if "plain_text_response" in result:
            return str(result["plain_text_response"])
        return json.dumps(result, ensure_ascii=False)
