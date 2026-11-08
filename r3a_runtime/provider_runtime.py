"""
R3 CONTROLLED SOURCE
File: r3a_runtime/provider_runtime.py
Component: R3A-CAPABILITY-MODULE-RUNTIME
File Revision: 1.0.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Supervise generic manifest-declared capability provider processes.
Execution Model: CME-owned subprocesses using the AP0-M1 private Unix socket protocol.
Observability: Durable module lifecycle records and health handshake diagnostics.
Dependencies: r3a_runtime.protocol; r3a_runtime.capability_contracts; Store module lifecycle.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Implement install, activation, invocation, deactivation, replacement, and failure handling for provider versions.
Supersedes: None.
Contracts: MOD-001–MOD-010; module.lifecycle v2; r3a.capability-provider.v1.
Tests: tests/test_r3a_capability_integration_demo.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import signal
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .capability_contracts import CapabilityProviderResult, RegisteredOperation
from .protocol import PROTOCOL_MAJOR, PROTOCOL_MINOR, request


def _module_environment(operation: RegisteredOperation) -> dict[str, str]:
    """Pass only runtime basics and environment variables explicitly named by config."""
    allowed = {name: value for name in ("PATH", "HOME", "LANG", "LC_ALL")
               if (value := os.environ.get(name)) is not None}
    names: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.endswith("_env") and isinstance(child, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", child):
                    names.add(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            names.update(re.findall(r"\$\{([A-Z][A-Z0-9_]*)\}", value))

    visit(operation.configuration)
    for name in names:
        if name in os.environ:
            allowed[name] = os.environ[name]
    return allowed


@dataclass
class ProviderProcess:
    module_id: str
    version: str
    socket: Path
    process: asyncio.subprocess.Process
    operation: RegisteredOperation
    inflight: int = 0
    drained: asyncio.Event | None = None


class ProviderProcessManager:
    """Own one independently restartable process per provider identity/version."""

    def __init__(self, settings, store, registry):
        self.settings = settings
        self.store = store
        self.registry = registry
        self.processes: dict[tuple[str, str], ProviderProcess] = {}
        self._lock = asyncio.Lock()
        self._draining: set[tuple[str, str]] = set()

    async def _state(self, module_id: str, version: str, lifecycle: str, health: str,
                     diagnostic: dict[str, Any] | None = None) -> None:
        await self.store.module_state(module_id, version, lifecycle, health, diagnostic,
                                      machine_version=2)

    @staticmethod
    def _provider(operation: RegisteredOperation) -> tuple[str, str]:
        provider = operation.descriptor["provider"]
        return provider["provider_id"], provider["provider_version"]

    def _manifest(self, operation: RegisteredOperation) -> dict[str, Any]:
        provider = operation.descriptor["provider"]
        legacy = operation.legacy_manifest or {}
        declared = legacy.get("module_manifest")
        if declared is not None:
            binding = declared["binding"]
            artifact = declared["artifact"]
            return {"module_id": declared["module_id"], "module_version": declared["module_version"],
                    "contract_id": binding["contract_id"], "protocol_major": binding["protocol_major"],
                    "protocol_minor": PROTOCOL_MINOR, "protocol_min_minor": binding["protocol_min_minor"],
                    "protocol_max_minor": binding["protocol_max_minor"], "owner": declared["owner"],
                    "entrypoint": binding["entrypoint"], "dependencies": declared["dependencies"],
                    "configuration_schema": legacy["configuration_schema"],
                    "configuration_ref": declared["configuration"]["configuration_ref"],
                    "capability_refs": declared["capability_refs"],
                    "migration_contract": declared["migration_contract"],
                    "artifact_ref": artifact["artifact_ref"], "artifact_digest": artifact["artifact_sha256"],
                    "recovery_policy": declared["recovery_policy"],
                    "resource_refs": declared["resource_refs"],
                    "state_namespace": declared["state_namespace"]}
        return {"module_id": provider["provider_id"], "module_version": provider["provider_version"],
                "contract_id": "r3a.capability-provider.v1", "protocol_major": PROTOCOL_MAJOR,
                "protocol_minor": PROTOCOL_MINOR, "protocol_min_minor": 0, "protocol_max_minor": 0,
                "owner": "manifest", "entrypoint": provider["entrypoint"], "dependencies": [],
                "configuration_schema": legacy.get("configuration_schema", {}),
                "configuration_ref": "external-config", "capability_refs": [operation.descriptor["operation_id"]],
                "migration_contract": "provider-stateless.v1", "artifact_ref": legacy.get(
                    "artifact_ref", provider["entrypoint"]), "artifact_digest": provider["artifact_sha256"],
                "recovery_policy": "replay-per-operation-contract", "resource_refs": [],
                "state_namespace": provider["provider_id"]}

    @staticmethod
    def _version_matches(version: str, expression: str) -> bool:
        candidate = tuple(map(int, version.split(".")))
        for clause in expression.split(","):
            clause = clause.strip()
            range_match = re.fullmatch(r"([~^])([0-9]+\.[0-9]+\.[0-9]+)", clause)
            if range_match:
                kind, raw_lower = range_match.groups()
                lower = tuple(map(int, raw_lower.split(".")))
                if kind == "~":
                    upper = (lower[0], lower[1] + 1, 0)
                elif lower[0] > 0:
                    upper = (lower[0] + 1, 0, 0)
                elif lower[1] > 0:
                    upper = (0, lower[1] + 1, 0)
                else:
                    upper = (0, 0, lower[2] + 1)
                if candidate < lower or candidate >= upper:
                    return False
                continue
            match = re.fullmatch(r"(>=|<=|>|<|==)?([0-9]+\.[0-9]+\.[0-9]+)", clause)
            if match is None:
                raise RuntimeError(f"unsupported module dependency version range: {expression}")
            bound = tuple(map(int, match.group(2).split(".")))
            operator = match.group(1) or "=="
            if not {">=": candidate >= bound, "<=": candidate <= bound, ">": candidate > bound,
                    "<": candidate < bound, "==": candidate == bound}[operator]:
                return False
        return True

    async def _activate_dependencies(self, operation: RegisteredOperation,
                                     ancestry: tuple[tuple[str, str], ...]) -> None:
        module_key = self._provider(operation)
        if module_key in ancestry:
            raise RuntimeError("module dependency cycle reached during activation")
        legacy = operation.legacy_manifest or {}
        module_manifest = legacy.get("module_manifest") or {}
        configured = [item["descriptor"] for item in self.registry.discover(
            include_disabled=True, include_versions=True)]
        for dependency in module_manifest.get("dependencies", []):
            candidates = [item for item in configured
                          if item["lifecycle"]["desired_state"] == "enabled"
                          and item["provider"]["provider_id"] == dependency["module_id"]
                          and self._version_matches(item["provider"]["provider_version"],
                                                    dependency["version_range"])]
            if not candidates:
                raise RuntimeError(
                    f"module dependency is not configured: {dependency['module_id']}@{dependency['version_range']}")
            selected = max(candidates, key=lambda item: tuple(map(int, item["provider"]["provider_version"].split("."))))
            required = self.registry.resolve_provider(selected["operation_id"],
                                                      selected["provider"]["provider_version"])
            await self._activate_dependencies(required, (*ancestry, module_key))
            await self._ensure_active(required, ancestry=(*ancestry, module_key))

    async def install_all(self) -> None:
        seen = set()
        prior_active: list[tuple[str, str, RegisteredOperation]] = []
        for item in self.registry.discover(include_disabled=True, include_versions=True):
            descriptor = item["descriptor"]
            if descriptor["lifecycle"]["desired_state"] != "enabled":
                continue
            provider = descriptor["provider"]
            key = provider["provider_id"], provider["provider_version"]
            if key in seen:
                continue
            seen.add(key)
            operation = self.registry.resolve_provider(descriptor["operation_id"],
                                                       provider["provider_version"])
            manifest = self._manifest(operation)
            if (manifest["protocol_major"] != PROTOCOL_MAJOR
                    or not manifest["protocol_min_minor"] <= PROTOCOL_MINOR <= manifest["protocol_max_minor"]):
                await self.store.register_module(manifest, "INCOMPATIBLE", "unavailable",
                                                 {"reason": "module manifest protocol range excludes host"})
                await self._state(*key, "INCOMPATIBLE", "unavailable",
                                  {"reason": "module manifest protocol range excludes host"})
                self.registry.set_provider_state(*key, "INCOMPATIBLE",
                                                 {"reason": "module manifest protocol range excludes host"})
                continue
            await self.store.register_module(manifest, "INSTALLED", "unknown")
            rows = await self.store.rows(
                "SELECT lifecycle_state,diagnostic FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                key)
            prior_state = rows[0]["lifecycle_state"] if rows else "INSTALLED"
            existing_process = self.processes.get(key)
            if existing_process and existing_process.process.returncode is None:
                self.registry.set_provider_state(*key, "ACTIVE", {"pid": existing_process.process.pid,
                                                                      "source": "retained process"})
                prior_active.append((*key, operation))
                continue
            if prior_state == "INSTALLED":
                await self._state(*key, "INSTALLED", "unknown", {"source": "capability manifest"})
            elif prior_state in {"ACTIVE", "ACTIVATING", "STOPPING", "REPLACING"}:
                diagnostic = rows[0].get("diagnostic") or {}
                pid = diagnostic.get("pid") if isinstance(diagnostic, dict) else None
                if isinstance(pid, int):
                    await self._reap_orphan_module(pid, *key)
                await self._state(*key, "FAILED", "stale",
                                              {"reason": "provider process did not survive CME restart",
                                               "prior_state": prior_state})
                # A previously active configured module is restored only after its
                # pinned artifact passes the normal activation handshake below.
                active_operation = self.registry.resolve_provider(descriptor["operation_id"],
                                                                   provider["provider_version"])
                prior_active.append((*key, active_operation))
                prior_state = "FAILED"
            state = prior_state
            self.registry.set_provider_state(*key, state, {"source": "module registry"})
        for module_id, version, operation in prior_active:
            await self.activate(operation)
            self.registry.activate_provider(operation.descriptor["operation_id"], version)

    @staticmethod
    async def _reap_orphan_module(pid: int, module_id: str, version: str) -> None:
        """Stop only a same-user provider process whose command line proves its identity."""
        proc = Path(f"/proc/{pid}")
        try:
            if proc.stat().st_uid != os.getuid():
                return
            command = (proc / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return
        if not ("r3a_runtime.capability_worker" in command
                and "--module-id" in command and module_id in command
                and "--module-version" in command and version in command):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        for _ in range(100):
            await asyncio.sleep(0.02)
            if not proc.exists():
                return
        # Revalidate identity before the bounded hard-stop in case the PID was reused.
        try:
            command = (proc / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
            if proc.stat().st_uid == os.getuid() and "r3a_runtime.capability_worker" in command \
                    and "--module-id" in command and module_id in command \
                    and "--module-version" in command and version in command:
                os.kill(pid, signal.SIGKILL)
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            return

    async def _ensure_active(self, operation: RegisteredOperation, *,
                             ancestry: tuple[tuple[str, str], ...] = ()) -> ProviderProcess:
        key = self._provider(operation)
        if key in ancestry:
            raise RuntimeError("module dependency cycle reached during activation")
        await self._activate_dependencies(operation, ancestry)
        async with self._lock:
            existing = self.processes.get(key)
            if existing and existing.process.returncode is None:
                return existing
            manifest = self._manifest(operation)
            rows = await self.store.rows(
                "SELECT artifact_digest,lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                key)
            if (manifest["protocol_major"] != PROTOCOL_MAJOR
                    or not manifest["protocol_min_minor"] <= PROTOCOL_MINOR <= manifest["protocol_max_minor"]):
                if not rows:
                    await self.store.register_module(manifest, "INSTALLED", "unknown")
                await self._state(*key, "INCOMPATIBLE", "unavailable",
                                  {"reason": "module manifest protocol range excludes host"})
                self.registry.set_provider_state(*key, "INCOMPATIBLE",
                                                 {"reason": "module manifest protocol range excludes host"})
                raise RuntimeError("module manifest protocol range excludes host")
            if not rows:
                await self.store.register_module(manifest, "INSTALLED", "unknown")
                await self._state(*key, "INSTALLED", "unknown", {"source": "capability manifest"})
            elif rows[0]["artifact_digest"].strip() != manifest["artifact_digest"]:
                raise RuntimeError("provider artifact changed under an installed version")
            state = rows[0]["lifecycle_state"] if rows else "INSTALLED"
            if state in {"ACTIVE", "ACTIVATING", "STOPPING", "REPLACING"}:
                await self._state(*key, "FAILED", "stale",
                                              {"reason": "provider process was not observed after CME restart",
                                               "prior_state": state})
                state = "FAILED"
            if state in {"STOPPED", "FAILED", "INCOMPATIBLE"}:
                await self._state(*key, "ACTIVATING", "starting",
                                              {"recovery_from": state})
            else:
                await self._state(*key, "ACTIVATING", "starting")
            module_name = manifest["entrypoint"].split(":", 1)[0]
            legacy = operation.legacy_manifest or {}
            artifact = legacy.get("_provider_artifact_path")
            if not artifact:
                spec = importlib.util.find_spec(manifest["entrypoint"].split(":", 1)[0])
                artifact = spec.origin if spec else None
            if not artifact:
                raise RuntimeError("provider manifest has no resolved pinned artifact path")
            artifact_path = Path(artifact).resolve(strict=True)
            if hashlib.sha256(artifact_path.read_bytes()).hexdigest() != manifest["artifact_digest"]:
                await self._state(*key, "INCOMPATIBLE", "unavailable",
                                              {"reason": "provider artifact digest mismatch"})
                raise RuntimeError("provider artifact digest mismatch")
            socket_key = hashlib.sha256(f"{key[0]}@{key[1]}".encode()).hexdigest()[:24]
            socket = self.settings.data_dir / "modules" / f"{socket_key}.sock"
            socket.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            socket.parent.chmod(0o700)
            socket.unlink(missing_ok=True)
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "r3a_runtime.capability_worker", "--socket", str(socket),
                "--module-id", key[0], "--module-version", key[1], "--entrypoint", manifest["entrypoint"],
                "--artifact", str(artifact_path), "--artifact-sha256", manifest["artifact_digest"],
                cwd=Path(__file__).resolve().parent.parent,
                env=_module_environment(operation),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE, start_new_session=True)
            binding = ProviderProcess(*key, socket, process, operation, drained=asyncio.Event())
            binding.drained.set()
            self.processes[key] = binding
            try:
                handshake_attempts = max(50, int(getattr(self.settings,
                                                          "heartbeat_stale_after_seconds", 10) / 0.02))
                for _ in range(handshake_attempts):
                    if process.returncode is not None:
                        error = (await process.stderr.read()).decode("utf-8", "replace")[-1000:]
                        raise RuntimeError(f"provider process exited before handshake: {error}")
                    try:
                        hello = await request(socket, *key, "hello", timeout=0.2)
                        break
                    except (OSError, asyncio.TimeoutError):
                        await asyncio.sleep(0.02)
                else:
                    raise RuntimeError("provider module handshake timed out")
                remote = hello["result"].get("supported_protocol", {})
                if (hello["result"].get("contract_id") != "r3a.capability-provider.v1"
                        or remote.get("major") != PROTOCOL_MAJOR
                        or not remote.get("min_minor", 1) <= PROTOCOL_MINOR <= remote.get("max_minor", -1)):
                    await self._state(*key, "INCOMPATIBLE", "unavailable",
                                                  {"reason": "provider protocol contract is incompatible"})
                    raise RuntimeError("provider protocol contract is incompatible")
                await request(socket, *key, "prepare", {
                    "configuration": operation.configuration,
                    "pinned_artifacts": legacy.get("_pinned_artifact_paths", {})})
                await request(socket, *key, "activate")
                health = await request(socket, *key, "health")
                if health["result"].get("state") != "ACTIVE":
                    raise RuntimeError("provider readiness handshake did not report ACTIVE")
                await self._state(*key, "ACTIVE", "healthy", {"pid": process.pid,
                                                                            "observed_contract": hello["result"]})
                self.registry.set_provider_state(*key, "ACTIVE", {"pid": process.pid})
                return binding
            except Exception as exc:
                if process.returncode is None:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), timeout=2)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
                self.processes.pop(key, None)
                try:
                    await self._state(*key, "FAILED", "unavailable",
                                                  {"error_type": type(exc).__name__})
                except Exception:
                    pass
                status = "INCOMPATIBLE" if "incompatible" in str(exc).casefold() else "FAILED"
                self.registry.set_provider_state(*key, status, {"error_type": type(exc).__name__})
                raise

    async def invoke(self, operation: RegisteredOperation, arguments: dict[str, Any],
                     context: dict[str, Any]) -> Any:
        binding = await self._ensure_active(operation)
        key = (binding.module_id, binding.version)
        async with self._lock:
            if key in self._draining or binding.process.returncode is not None:
                raise RuntimeError("provider is draining and no longer accepts invocations")
            binding.inflight += 1
            assert binding.drained is not None
            binding.drained.clear()
        try:
            response = await request(binding.socket, binding.module_id, binding.version, "execute",
                                     {"arguments": arguments, "context": context},
                                     timeout=operation.descriptor["execution"]["timeout_seconds"])
            result = response["result"]["provider_result"]
            if isinstance(result, dict) and result.get("contract_id") == "r3a.capability-provider-result.v1":
                if (set(result) != {"contract_id", "contract_version", "output", "evidence"}
                        or result.get("contract_version") != "1.0.0"):
                    raise RuntimeError("provider returned an invalid typed-result envelope")
                return CapabilityProviderResult(result["output"], result["evidence"])
            return result
        finally:
            async with self._lock:
                binding.inflight -= 1
                if binding.inflight == 0 and binding.drained is not None:
                    binding.drained.set()

    async def activate(self, operation: RegisteredOperation) -> dict[str, Any]:
        binding = await self._ensure_active(operation)
        return {"module_id": binding.module_id, "version": binding.version,
                "state": "ACTIVE", "pid": binding.process.pid}

    async def stop(self, module_id: str, version: str) -> dict[str, Any]:
        key = (module_id, version)
        async with self._lock:
            binding = self.processes.get(key)
            if binding is None or binding.process.returncode is not None:
                rows = await self.store.rows(
                    "SELECT lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s", key)
                if rows and rows[0]["lifecycle_state"] != "STOPPED":
                    await self._state(*key, "STOPPED", "stopped", {"already_stopped": True})
                self.registry.set_provider_state(*key, "STOPPED", {"already_stopped": True})
                return {"module_id": module_id, "version": version, "stopped": True,
                        "already_stopped": True}
            self._draining.add(key)
            await self._state(*key, "STOPPING", "stopping")
        # Stop accepting new calls, then let all provider calls finish before
        # requesting the worker checkpoint and shutdown.
        timeout = max(3.0, binding.operation.descriptor["execution"]["timeout_seconds"] + 2.0)
        try:
            assert binding.drained is not None
            await asyncio.wait_for(binding.drained.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"provider {module_id}@{version} did not drain in {timeout:.1f}s") from exc
        async with self._lock:
            try:
                await request(binding.socket, *key, "checkpoint")
                await request(binding.socket, *key, "stop")
                await asyncio.wait_for(binding.process.wait(), timeout=3)
            except (OSError, RuntimeError, asyncio.TimeoutError):
                binding.process.terminate()
                try:
                    await asyncio.wait_for(binding.process.wait(), timeout=2)
                except asyncio.TimeoutError:
                    binding.process.kill()
                    await binding.process.wait()
            self.processes.pop(key, None)
            self._draining.discard(key)
            await self._state(*key, "STOPPED", "stopped", {"exit_code": binding.process.returncode})
            self.registry.set_provider_state(*key, "STOPPED", {})
            return {"module_id": module_id, "version": version, "stopped": True}

    async def begin_replacement(self, module_id: str, version: str) -> None:
        rows = await self.store.rows(
            "SELECT lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
            (module_id, version))
        if not rows or rows[0]["lifecycle_state"] != "ACTIVE":
            raise RuntimeError("replacement source provider is not active")
        await self._state(module_id, version, "REPLACING", "transitioning",
                          {"replacement_started": True})

    async def cancel_replacement(self, module_id: str, version: str) -> None:
        await self._state(module_id, version, "ACTIVE", "healthy",
                          {"replacement_candidate_failed": True})

    async def close(self) -> None:
        for module_id, version in list(self.processes):
            try:
                await self.stop(module_id, version)
            except Exception:
                binding = self.processes.pop((module_id, version), None)
                if binding and binding.process.returncode is None:
                    binding.process.terminate()
                    await binding.process.wait()

    async def check_health(self) -> None:
        """Refresh provider process health without allowing failures to stop CME."""
        for key, binding in list(self.processes.items()):
            if key in self._draining:
                continue
            if binding.process.returncode is not None:
                try:
                    await self._state(*key, "FAILED", "unavailable",
                                      {"reason": "provider process exited", "exit_code": binding.process.returncode})
                except Exception:
                    pass
                self.registry.set_provider_state(*key, "FAILED", {"exit_code": binding.process.returncode})
                continue
            try:
                response = await request(binding.socket, *key, "health", timeout=2.0)
                health = response["result"]
                healthy = health.get("state") == "ACTIVE" and health.get("health") == "healthy"
                await self.store.observe_module(
                    *key, "healthy" if healthy else "degraded",
                    {"pid": binding.process.pid, "module_state": health.get("state"),
                     "checked_at": datetime.now(timezone.utc).isoformat()})
                if not healthy:
                    self.registry.set_provider_state(*key, "degraded", {"health": health})
            except Exception as exc:
                await self.store.observe_module(*key, "unavailable",
                                                {"pid": binding.process.pid,
                                                 "health_error": type(exc).__name__})
