# R3 CONTROLLED SOURCE
# File: runtime/host_execution.py
# Component: R3-HOST-EXECUTION
# File Revision: 1.1.0
# Created: 2026-11-02 UTC
# Purpose: Fixed local and LAN SSH command capabilities.
# Contracts: docs/r3-native-tool-contract.md
# Tests: tests/test_host_execution.py
"""Configured, fixed commands; no user-controlled shell or SSH arguments."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import subprocess


class HostConfigurationError(ValueError):
    pass


class HostExecutor:
    def __init__(self, catalog: Path):
        raw = json.loads(catalog.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("tools"), list):
            raise HostConfigurationError("Catalog must contain tools array")
        self.tools = {}
        for item in raw["tools"]:
            if not isinstance(item, dict):
                raise HostConfigurationError("Invalid tool")
            name, argv = item.get("name"), item.get("argv")
            timeout, read_only = item.get("timeout_seconds"), item.get("read_only")
            transport, host = item.get("transport", "local"), item.get("host")
            if transport not in ("local", "ssh"):
                raise HostConfigurationError("Unsupported transport")
            if transport == "ssh":
                if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", host):
                    raise HostConfigurationError("SSH host must be a fixed alias")
            elif host is not None:
                raise HostConfigurationError("Local tool cannot specify SSH host")
            if (not isinstance(name, str) or not name.startswith("r3.") or name in self.tools
                or not isinstance(argv, list) or not argv
                or any(not isinstance(a, str) or not a for a in argv)
                or not argv[0].startswith("/")
                or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                or not math.isfinite(timeout) or timeout <= 0
                or read_only is not True):
                raise HostConfigurationError("Invalid or unsupported command configuration")
            if transport == "ssh" and any(
                re.search(r"""[\s'"\\;$`|&<>]""", arg) for arg in argv
            ):
                raise HostConfigurationError("SSH arguments must be fixed simple tokens")
            self.tools[name] = {"argv": argv, "timeout": timeout, "transport": transport,
                                "host": host, "description": item.get("description", name)}

    def discover(self):
        return [{"tool": name, "read_only": True, "definition": {
            "type": "function", "function": {
                "name": name, "description": item["description"],
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            }}} for name, item in self.tools.items()]

    def invoke(self, name: str, params: dict):
        if name not in self.tools or params != {}:
            raise PermissionError("Command not authorized")
        item = self.tools[name]
        argv = item["argv"]
        if item["transport"] == "ssh":
            argv = ["/usr/bin/ssh", "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=yes",
                    "-o", "ConnectTimeout=10", "--", item["host"], *argv]
        result = subprocess.run(argv, shell=False, capture_output=True,
                                text=True, timeout=item["timeout"], check=False)
        return {"returncode": result.returncode,
                "stdout": result.stdout[:16384], "stderr": result.stderr[:16384]}
