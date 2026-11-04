# R3 CONTROLLED SOURCE
# File: runtime/mcp_tools.py
# Component: R3-MCP-TOOLS-ADAPTER
# File Revision: 1.0.0
# Purpose: Optional native MCP transport for existing R3 resident tool loop.
# Authority: R3 charter; hints/engineering-test-policy.md.
# Changed: 2026-11-02 UTC | R3-MCP-001 | Add native MCP adapter without changing llama.cpp adapter.
"""MCP adapter matching the existing LlamaTools discover/invoke interface.

Requires the existing official Python MCP SDK. Credentials are read from the
runtime environment and are never printed, persisted or included in tool logs.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class McpTools:
    url: str
    bearer_token: str | None = None

    def __post_init__(self) -> None:
        if not self.url.startswith(("https://", "http://")):
            raise ValueError("MCP URL must use HTTP(S)")

    async def _session_call(self, name: str | None = None, params: dict | None = None) -> Any:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        headers = {"Authorization": f"Bearer {self.bearer_token}"} if self.bearer_token else None
        async with streamablehttp_client(self.url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if name is None:
                    return await session.list_tools()
                return await session.call_tool(name, arguments=params or {})

    def discover(self) -> list[dict]:
        response = asyncio.run(self._session_call())
        result = []
        for tool in response.tools:
            schema = tool.inputSchema or {"type": "object", "properties": {}}
            result.append({
                "tool": tool.name,
                "definition": {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": schema,
                    },
                },
                "permissions": {},
            })
        return result

    def invoke(self, descriptor: dict, params: dict, *, allow_write: bool = False) -> str:
        if not isinstance(params, dict):
            raise ValueError("MCP tool arguments must be an object")
        response = asyncio.run(self._session_call(descriptor["tool"], params))
        if response.isError:
            raise RuntimeError("MCP tool returned an error: " + json.dumps(
                [part.model_dump(mode="json") for part in response.content], ensure_ascii=False
            ))
        if response.structuredContent is not None:
            return json.dumps(response.structuredContent, ensure_ascii=False)
        return json.dumps([part.model_dump(mode="json") for part in response.content], ensure_ascii=False)
