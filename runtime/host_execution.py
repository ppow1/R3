# R3 CONTROLLED SOURCE
# File: runtime/host_execution.py
# Component: R3-HOST-EXECUTION
# File Revision: 1.2.0
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
    def __init__(self, catalog: Path, hosts: Path | None = None):
        self.hosts = self._load_hosts(hosts) if hosts is not None else None
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
                if self.hosts is not None and host not in self.hosts:
                    raise HostConfigurationError("SSH host not registered")
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

    @staticmethod
    def _load_hosts(path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("hosts"), dict):
            raise HostConfigurationError("Host registry must contain hosts object")
        result = {}
        for alias, entry in raw["hosts"].items():
            if not isinstance(alias, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", alias):
                raise HostConfigurationError("Invalid host identifier")
            if not isinstance(entry, dict):
                raise HostConfigurationError("Invalid host profile")
            hostname, user = entry.get("hostname"), entry.get("user")
            port = entry.get("port", 22)
            identity = entry.get("identity_file")
            known_hosts = entry.get("known_hosts_file")
            if (not isinstance(hostname, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]+", hostname)
                or not isinstance(user, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", user)
                or not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535
                or not isinstance(identity, str) or not identity.startswith("/")
                or not isinstance(known_hosts, str) or not known_hosts.startswith("/")):
                raise HostConfigurationError("Invalid host connection settings")
            result[alias] = {"hostname": hostname, "user": user, "port": port,
                             "identity": identity, "known_hosts": known_hosts}
        return result

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
            options = ["/usr/bin/ssh", "-o", "BatchMode=yes",
                       "-o", "StrictHostKeyChecking=yes",
                       "-o", "ConnectTimeout=10"]
            target = item["host"]
            if self.hosts is not None:
                profile = self.hosts[target]
                options += ["-o", "IdentitiesOnly=yes",
                            "-o", "UserKnownHostsFile=" + profile["known_hosts"],
                            "-i", profile["identity"], "-p", str(profile["port"])]
                target = profile["user"] + "@" + profile["hostname"]
            argv = [*options, "--", target, *argv]
        result = subprocess.run(argv, shell=False, capture_output=True,
                                text=True, timeout=item["timeout"], check=False)
        return {"returncode": result.returncode,
                "stdout": result.stdout[:16384], "stderr": result.stderr[:16384]}
