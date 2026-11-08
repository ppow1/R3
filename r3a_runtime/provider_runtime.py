"""
R3 CONTROLLED SOURCE
File: r3a_runtime/provider_runtime.py
Component: R3A-CAPABILITY-MODULE-RUNTIME
File Revision: 1.2.0
Created: 2026-11-07
Created By: Codex GPT-6
Purpose: Supervise generic manifest-declared capability provider processes.
Execution Model: CME-owned subprocesses using the AP0-M1 private Unix socket protocol.
Observability: Durable module lifecycle records and health handshake diagnostics.
Dependencies: r3a_runtime.protocol; r3a_runtime.capability_contracts; Store module lifecycle.
Authority: Steward directive, "Implement the Approved Modular Foundation", 2026-11-07.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Implement install, activation, invocation, deactivation, replacement, and failure handling for provider versions.
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-002 | Close admission and drain in-flight provider invocations before checkpoint and stop.
Changed: 2026-11-08 | R3A-MODULAR-RUNTIME | Restore the versioned typed output/evidence provider result after JSON transport.
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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .capability_contracts import CapabilityProviderResult, RegisteredOperation
from .protocol import PROTOCOL_MAJOR, PROTOCOL_MINOR, request


def _module_environment(operation: RegisteredOperation) -> dict[str, str]:
    """Pass only runtime basics and config references admitted by the module manifest."""
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
    declared = (operation.legacy_manifest or {}).get("module_manifest") or {}
    secret_allowlist = set((declared.get("environment") or {}).get("allowlist", []))
    for name in names:
        # Database credential references are forwarded only when a versioned
        # module manifest explicitly declares that environment variable.
        if (re.search(r"(?:^|_)(?:DB|DATABASE|POSTGRES|PSYCOPG|PG)(?:_|$)", name)
                and name not in secret_allowlist):
            continue
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
    admission_open: bool = True
    inflight: int = 0
    drained: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        self.drained.set()


class ProviderProcessManager:
    """Own one independently restartable process per provider identity/version."""

    def __init__(self, settings, store, registry):
        self.settings = settings
        self.store = store
        self.registry = registry
        self.processes: dict[tuple[str, str], ProviderProcess] = {}
        self._lock = asyncio.Lock()

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
                    "environment_allowlist": (declared.get("environment") or {}).get("allowlist", []),
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

    async def install_all(self) -> None:
        seen = set()
        restore: list[RegisteredOperation] = []
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
            previous = rows[0]["lifecycle_state"] if rows else "INSTALLED"
            diagnostic = rows[0].get("diagnostic") if rows else {}
            if not isinstance(diagnostic, dict):
                diagnostic = {}
            restore_on_start = (previous in {"ACTIVE", "ACTIVATING", "STOPPING", "REPLACING"}
                                or (previous == "STOPPED" and diagnostic.get("resume_on_start") is True))
            if previous == "INSTALLED":
                await self._state(*key, "INSTALLED", "unknown", {"source": "capability manifest"})
            elif previous in {"ACTIVE", "ACTIVATING", "STOPPING", "REPLACING"}:
                await self._state(*key, "FAILED", "stale",
                                              {"reason": "provider process did not survive CME restart",
                                               "prior_state": previous,
                                               "resume_on_start": True})
            state = "FAILED" if previous in {"ACTIVE", "ACTIVATING", "STOPPING", "REPLACING"} else previous
            self.registry.set_provider_state(*key, state, {"source": "module registry"})
            if restore_on_start:
                restore.append(operation)

        # Restores only modules whose persisted lifecycle says they had been active.
        # Explicit deactivation writes STOPPED without resume_on_start and remains off.
        for operation in restore:
            try:
                await self.activate(operation)
            except Exception:
                # A single unavailable provider must not prevent CME or other modules
                # from starting; its lifecycle/diagnostic record carries the failure.
                continue

    async def _ensure_active(self, operation: RegisteredOperation) -> ProviderProcess:
        key = self._provider(operation)
        async with self._lock:
            existing = self.processes.get(key)
            if existing and existing.process.returncode is None:
                if not existing.admission_open:
                    raise RuntimeError("provider is stopping and no longer accepting activation or invocation")
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
            binding = ProviderProcess(*key, socket, process, operation)
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
        async with self._lock:
            if self.processes.get((binding.module_id, binding.version)) is not binding or not binding.admission_open:
                raise RuntimeError("provider is closing admission for lifecycle transition")
            binding.inflight += 1
            binding.drained.clear()
        try:
            response = await request(binding.socket, binding.module_id, binding.version, "execute",
                                     {"arguments": arguments, "context": context},
                                     timeout=operation.descriptor["execution"]["timeout_seconds"])
            result = response["result"]["provider_result"]
            if isinstance(result, dict) and result.get("contract_id") == "r3a.capability-provider-result.v1":
                if set(result) != {"contract_id", "contract_version", "output", "evidence"} or \
                        result.get("contract_version") != "1.0.0":
                    raise RuntimeError("provider returned an invalid typed-result envelope")
                return CapabilityProviderResult(result["output"], result["evidence"])
            return result
        finally:
            async with self._lock:
                binding.inflight -= 1
                if binding.inflight == 0:
                    binding.drained.set()

    async def activate(self, operation: RegisteredOperation) -> dict[str, Any]:
        binding = await self._ensure_active(operation)
        return {"module_id": binding.module_id, "version": binding.version,
                "state": "ACTIVE", "pid": binding.process.pid}

    async def stop(self, module_id: str, version: str, *, restore_on_start: bool = False) -> dict[str, Any]:
        key = (module_id, version)
        async with self._lock:
            binding = self.processes.get(key)
            if binding is None or binding.process.returncode is not None:
                rows = await self.store.rows(
                    "SELECT lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s", key)
                if rows and rows[0]["lifecycle_state"] in {"ACTIVE", "ACTIVATING", "REPLACING", "STOPPING"}:
                    await self._state(*key, "FAILED", "unavailable",
                                      {"reason": "provider process exited before stop request"})
                if rows and rows[0]["lifecycle_state"] != "STOPPED":
                    await self._state(*key, "STOPPED", "stopped",
                                      {"already_stopped": True, "resume_on_start": restore_on_start})
                self.registry.set_provider_state(*key, "STOPPED", {"already_stopped": True})
                return {"module_id": module_id, "version": version, "stopped": True,
                        "already_stopped": True}
            binding.admission_open = False
            await self._state(*key, "STOPPING", "draining", {"inflight_invocations": binding.inflight})

        # Existing invocations own a durable CME request and are allowed to finish before stop.
        await binding.drained.wait()
        async with self._lock:
            if self.processes.get(key) is not binding:
                return {"module_id": module_id, "version": version, "stopped": True,
                        "already_stopped": True}
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
            await self._state(*key, "STOPPED", "stopped",
                              {"exit_code": binding.process.returncode,
                               "resume_on_start": restore_on_start})
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
                await self.stop(module_id, version, restore_on_start=True)
            except Exception:
                binding = self.processes.pop((module_id, version), None)
                if binding and binding.process.returncode is None:
                    binding.process.terminate()
                    await binding.process.wait()
                try:
                    await self._state(module_id, version, "STOPPED", "stopped",
                                      {"resume_on_start": True, "shutdown_error": True})
                except Exception:
                    pass
