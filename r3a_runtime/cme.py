"""
R3 CONTROLLED SOURCE
File: r3a_runtime/cme.py
Component: R3A-CME-AP0
File Revision: 1.7.0
Created: 2026-11-06T15:22:00Z
Created By: Codex GPT-6
Purpose: Run CME scheduling, resource leases, module lifecycle, durable recovery, registries and diagnostics.
Execution Model: Async PostgreSQL-backed process supervised by Ring 0.
Observability: Durable process/activity/module/resource/event state and local diagnostics socket.
Dependencies: PostgreSQL; psycopg 3 pool; r3a_runtime.config/db/protocol/control/diagnostics.
Authority: AP1 / R3A-019 and AP1 Slices 1–2 authorized by Steward; isolated R3A only.
Changed: 2026-11-06T15:22:00Z | R3A-AP0-M1 | Codex GPT-6 | Implement CME process, scheduler, module worker and control plane.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Reconcile orphaned module processes, record live health and correct replacement status.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Dispatch durable Grace objectives, authorize bounded evidence reads and renew long-running leases.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Route activities to configured models and persist retrieved evidence snapshots.
Changed: 2026-11-06T18:09:37Z | R3A-019 | Codex GPT-6 | Reuse the durable evidence and model-route checkpoint when recovering an activity.
Changed: 2026-11-06T18:16:39Z | R3A-019 | Codex GPT-6 | Bound module-child termination when a model request does not drain.
Changed: 2026-11-06T18:21:00Z | R3A-019 | Codex GPT-6 | Persist required knowledge citations and restore them on activity recovery.
Changed: 2026-11-06T19:05:07Z | R3A-019 | Codex GPT-6 | Exclude unrelated runtime observations from knowledge-only model context.
Changed: 2026-11-06T19:14:04Z | R3A-019 | Codex GPT-6 | Verify exhaustive transition answers before durable completion.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add versioned resident envelopes, configurable model-role readiness routing, and pluggable authorization provider use.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Enforce role configuration pinning, freshness-aware deferral, and typed outcomes.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Run configured readiness providers, validate identity, persist evidence, and recover deferred work.
Changed: 2026-11-07 | R3A-019 | Codex GPT-6 | Dispatch resident-selected read capabilities and persist model/tool continuation evidence.
Changed: 2026-11-07 | R3A-PLUG-001 | Codex GPT-6 | Discover configured capability plug-ins, register them read-only, and expose authorized tools to Grace.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Enforce structured evidence criteria and resume reasoning after rejected completion.
Changed: 2026-11-07T02:41:51Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Persist and validate a versioned acceptance envelope on objective intake.
Changed: 2026-11-07T03:59:26Z | R3A-019-SUSTAINED-OPERATION | Codex GPT-6 | Block legacy or bypassed objectives that lack explicit acceptance criteria.
Changed: 2026-11-07T05:59:32Z | AP2-IMPLEMENTATION | Codex GPT-6 | Expose authorization decision identity separately from audit-event identity.
Changed: 2026-11-07 | R3A-MODULAR-CONFORMANCE | Codex GPT-6 | Normalize typed provider output/evidence through existing CME invocation adapters.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Execute model-authored Engineering proposals through durable CME work orders, unified invocation, independent verification and guarded completion.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Return verifier identities explicitly to Grace so assessment citations match independently verified execution evidence.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Resume typed proposals from checkpoints, provide inspected artifact evidence to Grace, and advance the live work-order projection before gated completion.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Use the validated operation reference's target after proposal normalization during work-order authorization.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Accept only invocation, workspace, or actual authorization-audit references in Grace's execution assessment.
Changed: 2026-11-07T15:16:00Z | R3A-AP1-AP2-AUTONOMY | Codex GPT-6 | Expose separate capability presentation metadata and drive durable dependency resumption from the CME scheduler.
Supersedes: None.
Contracts: AP0-002–010; AP0-M1 D2–D8; R3A-019; MOD-001–MOD-010; STM-001–STM-007; r3a.resident.execution.v1; r3a.model-role.v1; r3a.authorization-decision.v1; r3a.capability-invocation.v1; r3a.model-readiness-provider.v1; r3a.model-readiness.v2.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; tests/test_r3a_octominer_plugin.py; tests/test_r3a_telemetry_providers.py; tests/test_r3a_capability_contracts.py; tests/test_r3a_engineering.py.
History/Predecessor: Modular baseline ca2d29e47336dfb3d6a0e633c20bd31e1a200978; AP2 baseline b018578ea576813fed2c973236f35d82843daf14.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings, load_settings, sanitized_config
from .authorization import AuthorizationRequest, AuthorizationProvider, create_authorization_provider
from .control import ControlServer, control_request, process_alive
from .contracts import (ContractEnvelope, ContractOutcome, ReadinessObservation, RouteDecision,
                        READINESS_REFRESH_CONTRACT_ID, READINESS_REFRESH_CONTRACT_VERSION, resolve_role,
                        )
from .readiness import (READINESS_PROVIDER_CONTRACT_ID, ReadinessCheckRequest,
                        ModelReadinessProvider, create_readiness_provider)
from .db import InvalidTransition, Store, utcnow
from .capability_contracts import (validate_invocation_request, validate_invocation_result,
                                   CapabilityContractError, validate_json, normalize_provider_result)
from .engineering import (CapabilityOperationRef, CriterionResult, EngineeringProposal,
                          EngineeringWorkOrder, EngineeringAction, VerificationResult,
                          proposal_digest, validate_completion, validate_engineering_assignment)
from .engineering_verifier import verify_workspace_artifact
from .diagnostics import make_server
from .knowledge import retrieve
from .acceptance import (AcceptanceCriteriaRequired, OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                         OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION, evidence_fingerprint,
                         validate_acceptance, validate_required_criteria)
from .protocol import PROTOCOL_MAJOR, PROTOCOL_MINOR, request as module_request


_RESIDENT_TOOLS = (
    {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
     "capability_id": "institution.knowledge.read", "name": "institution_knowledge_read",
     "description": "Search configured read-only institutional knowledge sources for facts relevant to a query. Returns source IDs, paths, content, and SHA-256 digests.",
     "arguments_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "The specific question or fact to retrieve."}},
         "required": ["query"], "additionalProperties": False}},
    {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
     "capability_id": "institution.diagnostics.read", "name": "institution_diagnostics_read",
     "description": "Read current durable R3A process, module, and database observations with freshness and timestamps.",
     "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
     "capability_id": "host.process.read", "name": "host_process_read",
     "description": "Read Ring0 and CME process identities, health, heartbeats, and liveness.",
     "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"contract_id": "r3a.resident-capability-tool", "contract_version": "1.0.0",
     "capability_id": "postgres.readiness", "name": "postgres_readiness",
     "description": "Read PostgreSQL availability, database identity, server version, and recovery state.",
     "arguments_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
)


def _requires_runtime_evidence(objective: str) -> bool:
    runtime_terms = {"healthy", "health", "runtime", "live", "current", "currently",
                     "postgres", "postgresql", "database", "ring0", "cme", "grace",
                     "module", "pid", "heartbeat", "operational"}
    objective_terms = set(re.findall(r"[a-z0-9_]+", objective.casefold()))
    return bool(runtime_terms & objective_terms)


def _knowledge_answer_issues(objective: str, evidence: list[dict[str, Any]],
                             decision: dict[str, Any]) -> list[str]:
    """Check exhaustive structured transition answers against their cited source facts."""
    query_terms = set(re.findall(r"[a-z0-9_]+", objective.casefold()))
    if not query_terms & {"all", "every", "each", "list", "enumerate", "name", "identify"}:
        return []
    if not query_terms & {"state", "states", "successor", "successors", "destination",
                          "destinations", "transition", "transitions"}:
        return []
    transition_facts = [item for item in evidence
                        if item.get("source_id", "").startswith("knowledge.")
                        and str(item.get("source_path", "")).startswith("transitions.")]
    if not transition_facts:
        return []
    if decision.get("status") == "blocked":
        return ["model returned blocked status"]
    missing = []
    assessment = str(decision.get("assessment", "")).casefold()
    for fact in transition_facts:
        content = str(fact.get("content", ""))
        if ":" not in content:
            continue
        destinations = [value.strip() for value in content.split(":", 1)[1].split(",") if value.strip()]
        missing.extend(value for value in destinations if not re.search(
            rf"(?<![a-z0-9_]){re.escape(value.casefold())}(?![a-z0-9_])", assessment))
    return sorted(set(missing))


class ModelRoleUnavailable(RuntimeError):
    def __init__(self, decision, retry_after_seconds: float):
        super().__init__(decision.reason)
        self.decision = decision
        self.retry_after_seconds = retry_after_seconds


class CME:
    def __init__(self, settings: Settings,
                 authorization_provider: AuthorizationProvider | None = None,
                 readiness_providers: dict[str, ModelReadinessProvider] | None = None):
        self.settings = settings
        self.store = Store(settings)
        self.authorization_provider = authorization_provider or create_authorization_provider(
            settings.authorization_provider.provider_id, settings.authorization_provider.options,
            settings.source_digest, self.store)
        self.readiness_providers = dict(readiness_providers or {})
        self.control: ControlServer | None = None
        self.diagnostics: ControlServer | None = None
        self.shutdown = asyncio.Event()
        self.scheduler_tick = asyncio.get_running_loop().time()
        self.heartbeat_task: asyncio.Task | None = None
        self.scheduler_task: asyncio.Task | None = None
        self.readiness_task: asyncio.Task | None = None
        self.active_activities: dict[uuid.UUID, asyncio.Task] = {}
        self.module_process: asyncio.subprocess.Process | None = None
        self.module_id = settings.module_id
        self.module_version = settings.module_version
        self.module_pid: int | None = None
        self.module_lock = asyncio.Lock()
        self.booted_at = utcnow()

    def manifest(self, version: str | None = None) -> dict[str, Any]:
        return {
            "module_id": self.settings.module_id,
            "module_version": version or self.settings.module_version,
            "contract_id": self.settings.module_contract_id,
            "protocol_major": self.settings.module_protocol_major,
            "protocol_minor": self.settings.module_protocol_minor,
            "protocol_min_minor": self.settings.module_protocol_minor,
            "protocol_max_minor": self.settings.module_protocol_minor,
            "owner": self.settings.module_owner,
            "entrypoint": self.settings.module_entrypoint,
            "dependencies": [],
            "configuration_schema": "r3a.bootstrap.v1",
            "configuration_ref": str(self.settings.source_path),
            "capability_refs": list(self.settings.module_capabilities),
            "migration_contract": "none-v1",
            "artifact_ref": str(self.settings.module_source),
            "artifact_digest": self.settings.module_digest,
            "recovery_policy": "idempotent",
            "resource_refs": ["foundation.observer", "institution.reasoning"],
            "state_namespace": self.settings.module_id,
        }

    async def start(self) -> None:
        await self.store.open()
        await self.store.migrate()
        await self.store.activate_config()
        await self.store.seed_machines()
        await self.store.begin_process("cme", os.getpid())
        await self.store.register_capability("host.process.read", "R3A-CME", "read_only",
                                             metadata={"description": "Read current Ring 0/CME process observations"})
        await self.store.register_capability("postgres.readiness", "R3A-CME", "read_only",
                                             metadata={"description": "Read PostgreSQL version and readiness"})
        await self.store.register_capability("institution.knowledge.read", "R3A-CME", "read_only",
                                             metadata={"description": "Read explicitly allowlisted institutional knowledge sources"})
        for discovery in self.settings.capability_registry.discover():
            descriptor = discovery["descriptor"]
            operation = self.settings.capability_registry.resolve(
                descriptor["operation_id"], descriptor["contract_version"])
            manifest = operation.legacy_manifest or {}
            access_mode = "read_only" if descriptor["effect_class"] == "read" else "read_write"
            await self.store.register_capability(
                descriptor["operation_id"], descriptor["provider"]["provider_id"], access_mode,
                contract_version=descriptor["contract_version"],
                metadata={"operation_contract_id": descriptor["contract_id"],
                          "operation_revision": descriptor["operation_revision"],
                          "provider_version": descriptor["provider"]["provider_version"],
                          "effect_class": descriptor["effect_class"],
                          "required_grants": descriptor["required_grants"],
                          "compatibility_manifest_id": manifest.get("contract_id"),
                          "operation_id": descriptor["operation_id"],
                          "version": descriptor["contract_version"],
                          "display_name": discovery["presentation"]["name"],
                          "description": discovery["presentation"]["description"],
                          "evidence_contract": descriptor["evidence"],
                          "provider_availability": discovery["registry_observation"]["provider_availability"]},
                health=discovery["registry_observation"]["provider_availability"])
        await self.store.register_capability("institution.diagnostics.read", "R3A-CME", "read_only",
                                             metadata={"description": "Read current durable process and database observations"})
        await self.store.register_resource("foundation.observer", self.settings.worker_concurrency,
                                           owner="R3A-CME")
        for role in self.settings.model_roles:
            configured_route = self.settings.model_route(role.route_id)
            await self.store.register_model_role(role, self.settings.source_digest,
                                                 self.settings.module_id, configured_route.model)
        await self._recover_startup()
        await self._ensure_registered_module()
        self.control = ControlServer(self.settings.control_socket, self._control_request, mode=0o600)
        self.diagnostics = make_server(self.settings, self.store)
        await self.control.start()
        await self.diagnostics.start()
        await self._activate_configured_module()
        await self.store.record_process_state("cme", os.getpid(), "RUNNING", "healthy",
                                              "CME control and scheduler ready")
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="cme-db-heartbeat")
        self.scheduler_task = asyncio.create_task(self._scheduler_loop(), name="cme-scheduler")
        self.readiness_task = asyncio.create_task(self._model_readiness_loop(), name="cme-model-readiness")

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self.shutdown.set)
            except NotImplementedError:
                pass
        await self.start()
        await self.shutdown.wait()
        await self.stop()

    async def stop(self) -> None:
        await self.store.record_process_state("cme", os.getpid(), "STOPPING", "stopping",
                                              "CME shutdown requested")
        for task in (self.scheduler_task, self.heartbeat_task, self.readiness_task):
            if task:
                task.cancel()
        if self.scheduler_task or self.heartbeat_task or self.readiness_task:
            await asyncio.gather(*(t for t in (self.scheduler_task, self.heartbeat_task,
                                                self.readiness_task) if t),
                                 return_exceptions=True)
        if self.active_activities:
            await asyncio.gather(*self.active_activities.values(), return_exceptions=True)
        await self._stop_module()
        if self.control:
            await self.control.close()
        if self.diagnostics:
            await self.diagnostics.close()
        await self.store.record_process_state("cme", os.getpid(), "STOPPED", "stopped",
                                              "CME shutdown complete")
        await self.store.close()

    async def _recover_startup(self) -> None:
        count = await self.store.recover_expired_activities()
        await self.store.requeue_blocked_activities()
        await self.store.ensure_observer_activity()
        await self.store.process_heartbeat("cme", os.getpid(), "STARTING", "recovering",
                                           {"reconciled_activities": count})

    async def _ensure_registered_module(self) -> None:
        module = self.manifest()
        exists = await self.store.rows(
            "SELECT 1 FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
            (self.module_id, self.module_version),
        )
        if exists:
            return
        await self.store.register_module(module, "INSTALLED", "unknown")
        await self.store.module_state(self.module_id, self.module_version, "INSTALLED", "unknown",
                                      {"artifact_digest": self.settings.module_digest})

    async def _reap_orphan_module(self, pid: int, module_id: str, version: str) -> None:
        """Stop only a same-user process whose argv proves it is this registered module."""
        proc = Path(f"/proc/{pid}")
        try:
            if proc.stat().st_uid != os.getuid():
                return
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            entrypoint = b"r3a_runtime.grace_module" if module_id == "resident.grace" else b"r3a_runtime.observer_module"
            expected = [b"-m", entrypoint, b"--module-id", module_id.encode(),
                        b"--module-version", version.encode()]
            if any(item not in argv for item in expected) or not process_alive(pid):
                return
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                if not process_alive(pid):
                    return
                await asyncio.sleep(0.1)
            if process_alive(pid):
                os.kill(pid, signal.SIGKILL)
        except FileNotFoundError:
            return

    async def _module_call(self, operation: str, payload: dict[str, Any] | None = None,
                           timeout: float = 5.0) -> dict[str, Any]:
        payload = dict(payload or {})
        if operation == "execute" and payload.get("activity_type") == "grace.objective":
            payload["contract_envelope"] = ContractEnvelope(
                "r3a.resident.execution", "1.0.0", str(uuid.uuid4()),
                str(payload["activity_id"]), str(payload["attempt_id"]),
                str(payload.get("correlation_id") or payload["activity_id"]),
                self.module_id, str(payload["config_revision"]), utcnow().isoformat(),
                {"operation": "execute", "continuation_ref": payload.get("continuation_ref")}).to_dict()
        return await module_request(self.settings.module_socket, self.module_id, self.module_version,
                                    operation, payload, timeout=timeout)

    async def _authorization_decision(self, capability_id: str, *, activity_id: str | None = None,
                                    attempt_id: str | None = None,
                                    request_id: str | None = None,
                                    context: dict[str, Any] | None = None,
                                    resident_id: str | None = None,
                                    correlation_id: str | None = None):
        request_id = request_id or str(uuid.uuid4())
        request = AuthorizationRequest(
            contract_id="r3a.authorization-decision", contract_version="1.0.0",
            request_id=request_id, correlation_id=correlation_id or request_id,
            resident_id=resident_id or self.module_id,
            capability_id=capability_id, activity_id=activity_id, attempt_id=attempt_id,
            config_revision=self.settings.source_digest, created_at=utcnow().isoformat(),
            context=context or {})
        decision = await self.authorization_provider.authorize(request)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        return decision

    async def _authorize_capability(self, capability_id: str, *, activity_id: str | None = None,
                                    attempt_id: str | None = None,
                                    request_id: str | None = None,
                                    context: dict[str, Any] | None = None,
                                    resident_id: str | None = None) -> dict[str, Any]:
        decision = await self._authorization_decision(
            capability_id, activity_id=activity_id, attempt_id=attempt_id,
            request_id=request_id, context=context, resident_id=resident_id)
        return {"provider_id": decision.provider_id,
                "contract_id": decision.contract_id,
                "contract_version": decision.contract_version,
                "decision_id": decision.decision_id,
                "policy_revision": decision.policy_revision,
                "config_revision": decision.config_revision,
                "observed_at": decision.observed_at,
                "audit_event_id": decision.audit_event_id}

    async def _activate_configured_module(self) -> None:
        await self._activate_module(self.module_id, self.module_version)

    async def _activate_module(self, module_id: str, version: str) -> dict[str, Any]:
        async with self.module_lock:
            row = await self.store.rows(
                "SELECT manifest,lifecycle_state,diagnostic FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                (module_id, version),
            )
            if not row:
                raise KeyError(f"Module is not installed: {module_id}@{version}")
            manifest = row[0]["manifest"]
            if manifest["protocol_major"] != PROTOCOL_MAJOR or not (
                    manifest["protocol_min_minor"] <= PROTOCOL_MINOR <= manifest["protocol_max_minor"]):
                await self.store.module_state(module_id, version, "INCOMPATIBLE", "unavailable",
                                              {"reason": "host contract version outside supported range"})
                raise RuntimeError("Module contract is incompatible with this CME")
            if self.module_process and self.module_process.returncode is None:
                if module_id == self.module_id and version == self.module_version:
                    health = await self._module_call("health")
                    if health["result"].get("state") == "ACTIVE":
                        return {"module_id": module_id, "version": version,
                                "state": "ACTIVE", "pid": self.module_process.pid}
                else:
                    await self._stop_module()
            elif isinstance(row[0].get("diagnostic"), dict) and isinstance(row[0]["diagnostic"].get("pid"), int):
                await self._reap_orphan_module(row[0]["diagnostic"]["pid"], module_id, version)
            prior = await self.store.rows(
                "SELECT state FROM r3a.runtime_entities WHERE entity_type='module' AND entity_id=%s",
                (f"{module_id}@{version}",),
            )
            if prior and prior[0]["state"] in {"ACTIVE", "STOPPING", "REPLACING"}:
                await self.store.module_state(module_id, version, "FAILED", "stale",
                                              {"reason": "CME restarted during module lifecycle; reconcile process before activation",
                                               "prior_state": prior[0]["state"]})
            await self.store.module_state(module_id, version, "ACTIVATING", "starting")
            socket = self.settings.module_socket
            socket.unlink(missing_ok=True)
            command = [sys.executable, "-m", manifest["entrypoint"], "--socket", str(socket),
                       "--module-id", module_id, "--module-version", version]
            if manifest["entrypoint"] == "r3a_runtime.grace_module":
                command.extend(["--config", str(self.settings.source_path)])
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=Path(__file__).resolve().parent.parent,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            self.module_process = process
            self.module_id = module_id
            self.module_version = version
            self.module_pid = process.pid
            try:
                deadline = asyncio.get_running_loop().time() + 8.0
                hello = None
                while asyncio.get_running_loop().time() < deadline:
                    if process.returncode is not None:
                        error = (await process.stderr.read()).decode("utf-8", "replace")[-1500:]
                        raise RuntimeError(f"Module process exited during startup: {error}")
                    try:
                        hello = await self._module_call("hello")
                        break
                    except (OSError, ConnectionError, asyncio.TimeoutError, RuntimeError):
                        await asyncio.sleep(0.1)
                if hello is None:
                    raise TimeoutError("Module did not expose its local socket before startup deadline")
                protocol = hello["result"].get("supported_protocol", {})
                if protocol.get("major") != manifest["protocol_major"] or not (
                        protocol.get("min_minor", 999) <= PROTOCOL_MINOR <= protocol.get("max_minor", -1)):
                    await self.store.module_state(module_id, version, "INCOMPATIBLE", "unavailable",
                                                  {"reason": "module handshake protocol incompatible", "hello": hello["result"]})
                    raise RuntimeError("Module hello handshake is incompatible")
                await self._module_call("prepare")
                await self._module_call("activate")
                health = await self._module_call("health")
                if health["result"].get("state") != "ACTIVE" or health["result"].get("health") != "healthy":
                    raise RuntimeError("Module readiness observation did not report healthy/active")
                await self.store.module_state(module_id, version, "ACTIVE", "healthy",
                                              {"pid": process.pid, "protocol": protocol,
                                               "artifact_digest": manifest["artifact_digest"]})
                return {"module_id": module_id, "version": version, "state": "ACTIVE", "pid": process.pid}
            except Exception as exc:
                await self.store.module_state(module_id, version, "FAILED", "unavailable",
                                              {"reason": f"{type(exc).__name__}: {exc}"})
                if process.returncode is None:
                    process.terminate()
                    await process.wait()
                raise

    async def _stop_module(self) -> dict[str, Any]:
        process = self.module_process
        if process is None or process.returncode is not None:
            return {"stopped": True, "already_stopped": True}
        module_id, version = self.module_id, self.module_version
        await self.store.module_state(module_id, version, "STOPPING", "stopping")
        try:
            await self._module_call("stop")
        except (OSError, RuntimeError, asyncio.TimeoutError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=self.settings.heartbeat_stale_after_seconds)
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=self.settings.heartbeat_stale_after_seconds)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        self.module_process = None
        self.module_pid = None
        await self.store.module_state(module_id, version, "STOPPED", "stopped",
                                      {"exit_code": process.returncode})
        return {"stopped": True, "module_id": module_id, "version": version,
                "exit_code": process.returncode}

    async def _replace_module(self, version: str) -> dict[str, Any]:
        parts = version.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError("version must be semantic major.minor.patch numbers")
        old_id, old_version = self.module_id, self.module_version
        old_process_pid = os.getpid()
        if version == old_version:
            return await self._activate_module(old_id, old_version)
        if self.module_process and self.module_process.returncode is None:
            await self._stop_module()
        manifest = self.manifest(version)
        await self.store.register_module(manifest, "INSTALLED", "unknown")
        result = await self._activate_module(old_id, version)
        await self.store.record_module_replacement(old_id, old_version, version)
        result["cme_pid_unchanged"] = old_process_pid == os.getpid()
        result["prior_version"] = old_version
        return result

    async def _control_request(self, operation: str, payload: dict[str, Any],
                               idempotency_key: str) -> dict[str, Any]:
        if operation == "health":
            return {"component": "cme", "pid": os.getpid(), "state": "RUNNING",
                    "health": "healthy", "scheduler_tick_age_seconds": max(
                        0.0, asyncio.get_running_loop().time() - self.scheduler_tick),
                    "module_pid": self.module_pid, "module_id": self.module_id,
                    "module_version": self.module_version,
                    "config_revision": self.settings.source_digest}
        if operation == "stop":
            self.shutdown.set()
            return {"stopping": True}
        if operation == "module.install":
            version = str(payload.get("version", self.settings.module_version))
            manifest = self.manifest(version)
            existing = await self.store.rows(
                "SELECT artifact_digest,lifecycle_state FROM r3a.module_registry "
                "WHERE module_id=%s AND module_version=%s",
                (self.module_id, version),
            )
            if existing:
                if existing[0]["artifact_digest"].strip() != manifest["artifact_digest"]:
                    raise RuntimeError("Installed module version is immutable; use a new version")
                return {"installed": True, "already_registered": True,
                        "module_id": self.module_id, "version": version,
                        "artifact_digest": manifest["artifact_digest"],
                        "lifecycle_state": existing[0]["lifecycle_state"]}
            await self.store.register_module(manifest, "INSTALLED", "unknown")
            await self.store.module_state(self.module_id, version, "INSTALLED", "unknown",
                                          {"artifact_digest": self.settings.module_digest,
                                           "idempotency_key": idempotency_key})
            return {"installed": True, "module_id": self.module_id, "version": version,
                    "artifact_digest": self.settings.module_digest}
        if operation == "module.activate":
            module_id = str(payload.get("module_id", self.settings.module_id))
            version = str(payload.get("version", self.settings.module_version))
            return await self._activate_module(module_id, version)
        if operation == "module.stop":
            return await self._stop_module()
        if operation == "module.replace":
            return await self._replace_module(str(payload["version"]))
        if operation == "capability.grant":
            module_id = str(payload["module_id"])
            capability_id = str(payload["capability_id"])
            reason = str(payload["reason"])
            grant_id = await self.store.grant_capability(module_id, capability_id, reason)
            await self.store.requeue_blocked_activities()
            return {"grant_id": str(grant_id), "module_id": module_id,
                    "capability_id": capability_id, "granted_by": f"uid:{os.getuid()}"}
        if operation == "capability.check":
            module_id, capability_id = str(payload["module_id"]), str(payload["capability_id"])
            try:
                provider = await self._authorize_capability(
                    capability_id, request_id=idempotency_key,
                    context={"request_idempotency_key": idempotency_key}, resident_id=module_id)
                allowed = True
            except PermissionError as exc:
                provider = {"provider_id": self.authorization_provider.provider_id,
                            "contract_id": "r3a.authorization-decision", "contract_version": "1.0.0"}
                allowed = False
                reason = str(exc)
            return {"module_id": module_id, "capability_id": capability_id,
                    "authorized": allowed, "reason": None if allowed else reason,
                    "authorization": provider,
                    "effect": "none; discovery/check is read-only"}
        if operation == "model.readiness.refresh":
            role_id = str(payload["role_id"])
            role = next((entry for entry in self.settings.model_roles if entry.role_id == role_id), None)
            if role is None:
                raise ValueError("model readiness references an unconfigured role")
            observation, queued = await self._observe_model_role(role)
            return {"role_id": role.role_id, "status": observation.status,
                    "provider_id": observation.provider_id,
                    "config_revision": observation.config_revision,
                    "observation_id": observation.observation_id,
                    "deferred_activities_requeued": queued,
                    "contract_outcome": ContractOutcome(
                        READINESS_REFRESH_CONTRACT_ID, READINESS_REFRESH_CONTRACT_VERSION, idempotency_key,
                        observation.observation_id, self.module_id,
                        self.settings.source_digest, utcnow().isoformat(), "succeeded", False,
                        result={"role_id": role.role_id, "status": observation.status,
                                "provider_id": observation.provider_id,
                                "deferred_activities_requeued": queued}).to_dict()}
        if operation == "grace.objective.submit":
            if self.settings.module_id != "resident.grace":
                raise RuntimeError("The configured module is not the AP1 Grace resident")
            return await self.store.submit_grace_objective(
                str(payload.get("objective", "")), idempotency_key,
                str(payload.get("event_kind", "objective")),
                str(payload["route_id"]) if payload.get("route_id") is not None else None,
                str(payload["role_id"]) if payload.get("role_id") is not None else None,
                tuple(payload.get("required_capabilities", ())),
                tuple(payload.get("required_modalities", ())),
                payload.get("acceptance_criteria", []), payload.get("engineering_assignment"),
                payload.get("depends_on_activity_ids"), payload.get("activity_id"))
        if operation == "config.reload":
            if any(not task.done() for task in self.active_activities.values()):
                raise RuntimeError("Config reload waits for in-flight activity to reach a safe boundary")
            new_settings = load_settings(self.settings.source_path)
            immutable = (new_settings.instance_id, new_settings.database, new_settings.database_user,
                         new_settings.database_socket_dir, new_settings.database_port,
                         new_settings.control_socket, new_settings.diagnostics_socket,
                         new_settings.module_socket)
            current = (self.settings.instance_id, self.settings.database, self.settings.database_user,
                       self.settings.database_socket_dir, self.settings.database_port,
                       self.settings.control_socket, self.settings.diagnostics_socket,
                       self.settings.module_socket)
            if immutable != current:
                raise RuntimeError("Bootstrap identity/socket/database changes require process restart")
            new_provider = create_authorization_provider(
                new_settings.authorization_provider.provider_id,
                new_settings.authorization_provider.options, new_settings.source_digest, self.store)
            self.settings = new_settings
            self.store.settings = new_settings
            self.authorization_provider = new_provider
            revision = await self.store.activate_config()
            await self.store.register_resource("foundation.observer", new_settings.worker_concurrency,
                                               owner="R3A-CME")
            for role in new_settings.model_roles:
                configured_route = new_settings.model_route(role.route_id)
                await self.store.register_model_role(role, new_settings.source_digest,
                                                     new_settings.module_id, configured_route.model)
            return {"activated": True, "config_revision": revision,
                    "source_digest": new_settings.source_digest}
        raise ValueError(f"Unsupported CME control operation: {operation}")

    async def _requeue_ready_model_activities(self, causation_id: str | None = None) -> int:
        roles = self.settings.model_roles
        if not roles:
            return 0
        observations = await self._model_readiness_observations()
        requeued = 0
        for activity in await self.store.waiting_model_activities():
            event_input = activity["input"] or {}
            requested_role = event_input.get("role_id")
            if not requested_role:
                continue
            if event_input.get("role_config_revision") != self.settings.source_digest:
                await self.store.block_waiting_model_activity(
                    activity["activity_id"], "role_configuration_revision_changed",
                    {"role_id": requested_role,
                     "activity_config_revision": event_input.get("role_config_revision"),
                     "current_config_revision": self.settings.source_digest})
                continue
            decision = resolve_role(
                roles, requested_role, set(event_input.get("required_capabilities", [])),
                observations, config_revision=self.settings.source_digest,
                required_modalities=set(event_input.get("required_modalities", [])))
            if decision.action == "route" and decision.selected_role_id:
                if await self.store.requeue_model_activity(
                        activity["activity_id"], requested_role,
                        decision.selected_role_id, causation_id):
                    requeued += 1
        return requeued

    async def _model_readiness_observations(self) -> dict[str, dict[str, Any]]:
        roles = self.settings.model_roles
        observations = await self.store.model_role_observations(tuple(role.role_id for role in roles))
        for role in roles:
            observation = observations.get(role.role_id, {"status": "unknown"})
            route = self.settings.model_route(role.route_id)
            expected_provider = role.readiness.provider_id if role.readiness else None
            if (observation.get("model_id") != route.model
                    or observation.get("config_revision") != self.settings.source_digest
                    or not expected_provider
                    or observation.get("provider_id") != expected_provider
                    or observation.get("source") not in {"provider_model", "model_protocol"}):
                observations[role.role_id] = {"status": "unknown"}
        return observations

    async def _observe_model_role(self, role) -> tuple[ReadinessObservation, int]:
        policy = role.readiness
        if policy is None:
            raise ValueError(f"No readiness provider is configured for role {role.role_id}")
        route = self.settings.model_route(role.route_id)
        observation_id = str(uuid.uuid4())
        try:
            provider = self.readiness_providers.get(policy.provider_id)
            if provider is None:
                provider = create_readiness_provider(policy.provider_id)
                self.readiness_providers[policy.provider_id] = provider
            request = ReadinessCheckRequest(
                READINESS_PROVIDER_CONTRACT_ID, policy.contract_version, self.module_id,
                role, route, policy, self.settings.source_digest, observation_id)
            if (provider.provider_id != policy.provider_id
                    or provider.contract_id != READINESS_PROVIDER_CONTRACT_ID
                    or provider.contract_version.split(".")[0] != "1"):
                raise ValueError("readiness provider contract is incompatible with configured v1 policy")
            observed = await provider.observe(request)
            if (observed.role_id != role.role_id or observed.resident_id != self.module_id
                    or observed.model_id != route.model
                    or observed.config_revision != self.settings.source_digest
                    or observed.provider_id != policy.provider_id
                    or observed.observation_id != observation_id
                    or observed.source not in {"provider_model", "model_protocol"}):
                raise ValueError("readiness provider returned mismatched identity or configuration provenance")
            observation = observed
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            observation = ReadinessObservation(
                resident_id=self.module_id, role_id=role.role_id, model_id=route.model,
                status="unknown", source="model_protocol", observed_at=utcnow().isoformat(),
                config_revision=self.settings.source_digest, observation_id=observation_id,
                reason="readiness_provider_contract_or_execution_error",
                evidence_ref=f"provider-error:{policy.provider_id}:{observation_id}",
                provider_id=policy.provider_id,
                evidence={"error_type": type(exc).__name__, "error": "provider observation was rejected"})
        await self.store.observe_model_role(observation)
        queued = await self._requeue_ready_model_activities(observation.observation_id)
        return observation, queued

    async def _model_readiness_loop(self) -> None:
        due_by_revision: dict[tuple[str, str], float] = {}
        loop = asyncio.get_running_loop()
        while not self.shutdown.is_set():
            now = loop.time()
            roles = self.settings.model_roles
            active_keys = {(role.role_id, self.settings.source_digest)
                           for role in roles if role.readiness is not None}
            due_by_revision = {key: when for key, when in due_by_revision.items()
                               if key in active_keys}
            for role in roles:
                policy = role.readiness
                if policy is None:
                    continue
                key = (role.role_id, self.settings.source_digest)
                if due_by_revision.get(key, 0.0) > loop.time():
                    continue
                due_by_revision[key] = loop.time() + policy.poll_interval_seconds
                try:
                    await self._observe_model_role(role)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # A failed persistence/probe cycle never creates a ready observation.
                    continue
            if not active_keys:
                await asyncio.sleep(self.settings.scheduler_interval_seconds)
            else:
                now = loop.time()
                delay = min((due - now for due in due_by_revision.values()), default=1.0)
                await asyncio.sleep(max(0.05, delay))

    async def _observer_context(self, activity: dict[str, Any]) -> dict[str, Any]:
        for capability_id in self.settings.module_capabilities:
            await self._authorize_capability(capability_id, activity_id=str(activity["activity_id"]),
                                              attempt_id=str(activity["attempt_id"]))
        processes = await self.store.rows(
            "SELECT component_id,pid,state,health,heartbeat_at FROM r3a.process_observations "
            "WHERE component_id IN ('ring0','cme') ORDER BY component_id"
        )
        now = datetime.now(timezone.utc)
        process_evidence = []
        for row in processes:
            age = (now - row["heartbeat_at"]).total_seconds()
            process_evidence.append({
                "component_id": row["component_id"], "pid": row["pid"],
                "process_exists": process_alive(row["pid"]), "state": row["state"],
                "health": row["health"] if age <= self.settings.heartbeat_stale_after_seconds else "stale",
                "heartbeat_at": row["heartbeat_at"].isoformat(), "heartbeat_age_seconds": age,
            })
        db_evidence = await self.store.rows(
            "SELECT current_setting('server_version') AS server_version,clock_timestamp() AS observed_at,"
            "pg_is_in_recovery() AS in_recovery, current_database() AS database"
        )
        return {"activity_type": activity["activity_type"],
                "activity_id": str(activity["activity_id"]), "attempt_id": str(activity["attempt_id"]),
                "processes": process_evidence,
                "postgres": {**db_evidence[0], "ready": True,
                             "observed_at": db_evidence[0]["observed_at"].isoformat()},
                "config_revision": self.settings.source_digest}

    async def _objective_context(self, activity: dict[str, Any]) -> dict[str, Any]:
        event_input = activity["input"]
        engineering_assignment = event_input.get("engineering_assignment")
        acceptance_contract = event_input.get("acceptance_contract") or {
            "contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
            "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION, "criteria": []}
        if (acceptance_contract.get("contract_id") != OBJECTIVE_ACCEPTANCE_CONTRACT_ID
                or acceptance_contract.get("contract_version") != OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION):
            raise ValueError("objective acceptance contract identity or version is unsupported")
        acceptance_criteria = (validate_required_criteria(acceptance_contract.get("criteria"))
                               if engineering_assignment is None else [])
        if engineering_assignment is not None:
            engineering_assignment = validate_engineering_assignment(engineering_assignment)
        for capability_id in self.settings.module_capabilities:
            await self._authorize_capability(capability_id, activity_id=str(activity["activity_id"]),
                                              attempt_id=str(activity["attempt_id"]))
        saved = activity.get("checkpoint") or {}
        route_id = event_input.get("route_id")
        selected_role_id = event_input.get("role_id")
        if selected_role_id:
            roles = self.settings.model_roles
            if event_input.get("role_config_revision") != self.settings.source_digest:
                raise ModelRoleUnavailable(
                    RouteDecision("block", selected_role_id, None, None,
                                  "role_configuration_revision_changed", False,
                                  self.settings.source_digest,
                                  request_id=str(uuid.uuid4()),
                                  activity_id=str(activity["activity_id"]),
                                  attempt_id=str(activity["attempt_id"]),
                                  correlation_id=str(activity["activity_id"]),
                                  resident_id=self.module_id,
                                  evaluated_at=utcnow().isoformat()), 0)
            observations = await self._model_readiness_observations()
            decision_role_id = saved.get("selected_role_id") or event_input["role_id"]
            decision = resolve_role(
                roles, decision_role_id, set(event_input.get("required_capabilities", [])),
                observations, config_revision=self.settings.source_digest,
                permit_fallback=not bool(saved.get("selected_role_id")),
                request_id=str(uuid.uuid4()), activity_id=str(activity["activity_id"]),
                attempt_id=str(activity["attempt_id"]),
                correlation_id=str(activity["activity_id"]), resident_id=self.module_id,
                required_modalities=set(event_input.get("required_modalities", [])))
            if decision.action != "route":
                raise ModelRoleUnavailable(decision, next(
                    role.deferral_seconds for role in roles if role.role_id == decision_role_id))
            selected_role_id = decision.selected_role_id
            route_id = decision.route_id
            if saved.get("selected_role_id") and saved["selected_role_id"] != selected_role_id:
                raise ModelRoleUnavailable(
                    RouteDecision("defer", event_input["role_id"], None, None,
                                  "continuation_role_changed", True, self.settings.source_digest,
                                  request_id=decision.request_id,
                                  activity_id=decision.activity_id,
                                  attempt_id=decision.attempt_id,
                                  correlation_id=decision.correlation_id,
                                  resident_id=decision.resident_id,
                                  evaluated_at=utcnow().isoformat()),
                    next(role.deferral_seconds for role in roles if role.role_id == event_input["role_id"]))
        route = self.settings.model_route(route_id)
        effective_route = {"route_id": route.route_id, "provider": route.provider,
                           "model": route.model, "endpoint": route.endpoint,
                           "timeout_seconds": route.timeout_seconds, "max_tokens": route.max_tokens}
        saved_route = saved.get("model_route")
        if saved_route is not None and saved_route != effective_route:
            raise RuntimeError("Configured model route changed during durable activity continuation")
        reasoning_state = saved.get("reasoning_state") or {}
        if not isinstance(reasoning_state, dict):
            raise RuntimeError("Persisted Grace reasoning continuation is malformed")
        available_tools = [tool for tool in self._resident_tools()
                           if tool["capability_id"] in self.settings.module_capabilities]
        available_engineering_operations = []
        if engineering_assignment is not None and self.settings.capability_registry is not None:
            available_engineering_operations = [
                {**discovery["descriptor"], "presentation": discovery["presentation"],
                 "registry_observation": discovery["registry_observation"]}
                for discovery in self.settings.capability_registry.discover()
                if discovery["descriptor"].get("effect_class") == "isolated_write"]
        evidence = saved.get("evidence", [])
        if not isinstance(evidence, list):
            raise RuntimeError("Persisted resident evidence is malformed")
        return {"activity_type": "grace.objective", "activity_id": str(activity["activity_id"]),
                "attempt_id": str(activity["attempt_id"]),
                "objective": event_input["objective"], "event_kind": event_input.get("event_kind", "objective"),
                "acceptance_contract": {"contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                                        "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION,
                                        "criteria": acceptance_criteria},
                "acceptance_criteria": acceptance_criteria,
                "route_id": route.route_id,
                "model_route": effective_route,
                "evidence_format": "r3a.knowledge-evidence.v1",
                "required_evidence_refs": saved.get("required_evidence_refs", []),
                "selected_role_id": selected_role_id,
                "route_decision": decision.__dict__ if selected_role_id else None,
                "evidence": evidence,
                "dependency_context": await self.store.activity_dependency_context(event_input.get("dependencies")),
                "available_tools": available_tools,
                "engineering_assignment": engineering_assignment,
                "available_engineering_operations": available_engineering_operations,
                "conversation": reasoning_state.get("conversation", []),
                "reasoning_state": reasoning_state,
                "pending_final": reasoning_state.get("pending_final"),
                "request_ref": str(uuid.uuid4()), "config_revision": self.settings.source_digest}

    async def _invoke_resident_capability(self, activity: dict[str, Any],
                                          request: dict[str, Any]) -> dict[str, Any]:
        capability_id = request.get("capability_id")
        arguments = request.get("arguments")
        tool = next((entry for entry in self._resident_tools()
                     if entry["capability_id"] == capability_id), None)
        if tool is None:
            raise PermissionError("resident requested a capability without an execution adapter")
        if capability_id not in self.settings.module_capabilities:
            raise PermissionError("resident requested a capability absent from its configured manifest")
        if (request.get("contract_id") != tool["contract_id"]
                or request.get("contract_version") != tool["contract_version"]):
            raise ValueError("resident capability request contract does not match the registered tool")
        if not isinstance(arguments, dict):
            raise ValueError("resident capability arguments must be an object")
        if capability_id == "institution.knowledge.read":
            if set(arguments) != {"query"}:
                raise ValueError("institution.knowledge.read requires exactly one query argument")
            query = arguments["query"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("institution.knowledge.read query must be nonempty text")
        registry = getattr(self.settings, "capability_registry", None)
        try:
            registered_operation = registry.resolve(capability_id) if registry is not None else None
        except KeyError:
            registered_operation = None
        if capability_id != "institution.knowledge.read" and registered_operation is None and arguments:
            raise ValueError(f"{capability_id} accepts no arguments")
        if registered_operation is not None:
            if registered_operation.descriptor["effect_class"] != "read":
                raise PermissionError("effectful operation requires the canonical AP2 invocation dispatcher")
            from .capability_contracts import validate_json
            validate_json(arguments, registered_operation.descriptor["input_schema"], path="$.input")
        authorization = await self._authorize_capability(
            capability_id, activity_id=str(activity["activity_id"]),
            attempt_id=str(activity["attempt_id"]),
            context={"invocation_source": "resident_selected_action",
                     "tool_contract_id": tool["contract_id"],
                     "operation_contract_id": registered_operation.descriptor["contract_id"]
                     if registered_operation is not None else tool["contract_id"],
                     "effect_class": registered_operation.descriptor["effect_class"]
                     if registered_operation is not None else "read",
                     "query_sha256": hashlib.sha256(query.encode()).hexdigest()
                     if capability_id == "institution.knowledge.read" else None})
        evidence = []
        if capability_id == "institution.knowledge.read":
            for index, path in enumerate(self.settings.knowledge_sources):
                evidence.extend(retrieve(path, f"knowledge.{index+1}", query))
        elif registered_operation is not None:
            provider = registered_operation.load_provider()
            provided = await asyncio.to_thread(provider.invoke, arguments,
                                                context={"activity_id": str(activity["activity_id"]),
                                                         "attempt_id": str(activity["attempt_id"]),
                                                         "correlation_id": str(activity.get("correlation_id")
                                                                               or activity["activity_id"]),
                                                         "operation_id": capability_id})
            _, provider_evidence = normalize_provider_result(
                provided, registered_operation.descriptor)
            evidence.extend(provider_evidence if isinstance(provider_evidence, list)
                            else [provider_evidence])
        else:
            evidence.extend(await self._read_runtime_capability(capability_id))
        return {"contract_id": tool["contract_id"],
                "contract_version": tool["contract_version"],
                "capability_id": capability_id, "outcome": "succeeded",
                "arguments": arguments, "evidence": evidence,
                "authorization": authorization, "observed_at": utcnow().isoformat()}

    async def invoke_capability(self, request: dict[str, Any], *,
                                work_order: EngineeringWorkOrder) -> dict[str, Any]:
        """CME-only canonical dispatcher for AP2 operations, including isolated writes."""
        if not isinstance(work_order, EngineeringWorkOrder):
            raise TypeError("canonical Engineering invocation requires a validated work order")
        if request.get("contract_id") != "r3a.capability-invocation.v1":
            raise CapabilityContractError("CME requires r3a.capability-invocation.v1")
        operation = self.settings.capability_registry.resolve(
            request.get("operation_id", ""), request.get("operation_contract_version", ""))
        descriptor = operation.descriptor
        checked = validate_invocation_request(request, descriptor)
        order = work_order.to_dict()
        if (checked["work_order"] != {"work_order_id": work_order.work_order_id,
                                     "version": work_order.work_order_version}
                or checked["activity_id"] != work_order.activity_id
                or checked["attempt_id"] != work_order.attempt_id
                or checked["correlation_id"] != work_order.correlation_id
                or checked["caller"]["resident_id"] != work_order.resident_id
                or checked["config_revision"] != work_order.config_revision):
            raise PermissionError("invocation lineage does not match its immutable Engineering work order")
        if not any(ref.to_dict()["operation_id"] == descriptor["operation_id"]
                   and ref.contract_version == descriptor["contract_version"]
                   and ref.effect_class == descriptor["effect_class"]
                   and ref.target == checked["target"] and ref.inputs == checked["input"]
                   for ref in work_order.operation_refs):
            raise PermissionError("operation, inputs, target, or effect are outside the authorized work order")
        stored = await self.store.get_engineering_work_order(work_order.work_order_id)
        if (stored is None or stored.get("state") != "EXECUTING"
                or stored.get("details", {}).get("work_order") != order):
            raise PermissionError("invocation requires the matching durable EXECUTING work order")
        if descriptor["effect_class"] == "external_write":
            raise PermissionError("this isolated Engineering dispatcher does not execute external_write")
        started_at = utcnow().isoformat()
        authorization = await self._authorize_capability(
            descriptor["operation_id"], activity_id=work_order.activity_id,
            attempt_id=work_order.attempt_id, request_id=checked["invocation_id"],
            resident_id=work_order.resident_id,
            context={"dispatcher": "CME", "invocation_id": checked["invocation_id"],
                     "idempotency_key": checked["idempotency_key"],
                     "effect_class": descriptor["effect_class"],
                     "required_grants": descriptor["required_grants"],
                     "target": checked["target"], "work_order_id": work_order.work_order_id,
                     "work_order_version": work_order.work_order_version,
                     "config_revision": work_order.config_revision})
        auth_ref = {"provider_id": authorization["provider_id"], "allowed": True,
                    "decision_id": authorization["decision_id"],
                    "audit_event_id": authorization["audit_event_id"],
                    "policy_revision": authorization["policy_revision"],
                    "config_revision": authorization["config_revision"]}
        canonical_digest = hashlib.sha256(json.dumps(checked, sort_keys=True,
                                                    separators=(",", ":")).encode()).hexdigest()
        existing = await self.store.begin_capability_invocation(checked, canonical_digest, auth_ref)
        if existing["state"] == "SUCCEEDED" and existing.get("result") is not None:
            return existing["result"]
        if existing["state"] != "STARTED":
            raise RuntimeError(f"invocation requires reconciliation from durable state {existing['state']}")
        if not descriptor["recovery"]["replay_safe"]:
            raise RuntimeError("interrupted invocation is not replay safe; reconciliation is required")
        provider = operation.load_provider()
        try:
            output = await asyncio.to_thread(provider.invoke, checked["input"], context={
                "invocation_id": checked["invocation_id"], "idempotency_key": checked["idempotency_key"],
                "activity_id": checked["activity_id"], "attempt_id": checked["attempt_id"],
                "correlation_id": checked["correlation_id"], "target": checked["target"],
                "work_order": order, "effect_class": descriptor["effect_class"]})
        except Exception as exc:
            finished = utcnow().isoformat()
            result = {"contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                      "invocation_id": checked["invocation_id"], "operation_id": descriptor["operation_id"],
                      "operation_contract_version": descriptor["contract_version"],
                      "activity_id": checked["activity_id"], "attempt_id": checked["attempt_id"],
                      "correlation_id": checked["correlation_id"],
                      "provider": {k: descriptor["provider"][k] for k in
                                   ("provider_id", "provider_version", "artifact_sha256")},
                      "outcome": "FAILED", "started_at": started_at, "finished_at": finished,
                      "authorization": auth_ref, "effect_disposition": "UNKNOWN", "output": None,
                      "error": {"type": type(exc).__name__, "message": str(exc)}, "evidence": [],
                      "retryable": descriptor["recovery"]["replay_safe"],
                      "reconciliation_ref": checked["idempotency_key"]}
            await self.store.finish_capability_invocation(checked["idempotency_key"], canonical_digest, result)
            raise
        output, provider_evidence = normalize_provider_result(output, descriptor)
        finished_at = utcnow().isoformat()
        result = {"contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                  "invocation_id": checked["invocation_id"], "operation_id": descriptor["operation_id"],
                  "operation_contract_version": descriptor["contract_version"],
                  "activity_id": checked["activity_id"], "attempt_id": checked["attempt_id"],
                  "correlation_id": checked["correlation_id"],
                  "provider": {k: descriptor["provider"][k] for k in
                               ("provider_id", "provider_version", "artifact_sha256")},
                  "outcome": "SUCCEEDED", "started_at": started_at, "finished_at": finished_at,
                  "authorization": auth_ref,
                  "effect_disposition": "NOT_STARTED" if descriptor["effect_class"] == "read" else "COMMITTED",
                  "output": output, "error": None,
                  "evidence": provider_evidence if isinstance(provider_evidence, list) else [provider_evidence],
                  "retryable": False, "reconciliation_ref": None}
        validate_invocation_result(result, descriptor)
        await self.store.finish_capability_invocation(checked["idempotency_key"], canonical_digest, result)
        return result

    async def complete_engineering_work_order(self, work_order: EngineeringWorkOrder,
                                              verification: VerificationResult) -> bool:
        """Let CME advance an Engineering order only after the independent PASS gate validates."""
        if not isinstance(work_order, EngineeringWorkOrder) or not isinstance(verification, VerificationResult):
            raise TypeError("CME completion requires typed work-order and verification contracts")
        validate_completion(work_order, verification)
        stored = await self.store.get_engineering_work_order(work_order.work_order_id)
        if (stored is None or stored.get("state") != "VERIFYING"
                or stored.get("details", {}).get("work_order") != work_order.to_dict()):
            raise PermissionError("CME completion requires the matching durable VERIFYING work order")
        return await self.store.transition_engineering_work_order(
            work_order.work_order_id, "COMPLETED", work_order.activity_id, work_order.attempt_id,
            work_order.correlation_id, "CME accepted independent verification PASS",
            {"verification_id": verification.verification_id,
             "verifier_id": verification.verifier_id,
             "artifact_digests": list(verification.artifact_digests)},
            work_order=work_order, verification=verification)

    def _resident_tools(self) -> tuple[dict[str, Any], ...]:
        tools = list(_RESIDENT_TOOLS)
        # This is the temporary resident-capability-tool compatibility projection.
        # AP2's canonical dispatcher consumes all registered effect classes.
        registry = getattr(self.settings, "capability_registry", None)
        if registry is None:
            return tuple(tools)
        for discovery in registry.discover():
            operation = registry.resolve(
                discovery["descriptor"]["operation_id"], discovery["descriptor"]["contract_version"])
            if operation.descriptor["effect_class"] == "read":
                tools.append(operation.resident_tool_projection())
        return tuple(tools)

    async def _read_runtime_capability(self, capability_id: str) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        if capability_id in {"host.process.read", "institution.diagnostics.read"}:
            rows = await self.store.rows(
                "SELECT component_id,pid,state,health,heartbeat_at FROM r3a.process_observations "
                "WHERE component_id IN ('ring0','cme') ORDER BY component_id")
            now = datetime.now(timezone.utc)
            processes = [{"component_id": row["component_id"], "pid": row["pid"],
                          "process_exists": process_alive(row["pid"]), "state": row["state"],
                          "health": row["health"] if (now-row["heartbeat_at"]).total_seconds()
                          <= self.settings.heartbeat_stale_after_seconds else "stale",
                          "heartbeat_at": row["heartbeat_at"].isoformat(),
                          "heartbeat_age_seconds": (now-row["heartbeat_at"]).total_seconds()}
                         for row in rows]
            evidence.append(self._runtime_evidence("runtime.processes", processes))
        if capability_id in {"postgres.readiness", "institution.diagnostics.read"}:
            rows = await self.store.rows(
                "SELECT current_setting('server_version') AS server_version,clock_timestamp() AS observed_at,"
                "pg_is_in_recovery() AS in_recovery,current_database() AS database")
            postgres = {**rows[0], "ready": True,
                        "observed_at": rows[0]["observed_at"].isoformat()}
            evidence.append(self._runtime_evidence("runtime.postgres", postgres))
        if capability_id == "institution.diagnostics.read":
            modules = await self.store.rows(
                "SELECT module_id,module_version,lifecycle_state,health,observed_at,diagnostic "
                "FROM r3a.module_registry ORDER BY module_id,module_version")
            module_content = [{"module_id": row["module_id"], "module_version": row["module_version"],
                               "lifecycle_state": row["lifecycle_state"], "health": row["health"],
                               "pid": row["diagnostic"].get("pid") if isinstance(row["diagnostic"], dict) else None,
                               "observed_at": row["observed_at"].isoformat() if row["observed_at"] else None}
                              for row in modules]
            evidence.append(self._runtime_evidence("runtime.modules", module_content))
        return evidence

    @staticmethod
    def _runtime_evidence(source_id: str, content: Any) -> dict[str, Any]:
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
        return {"source_id": source_id, "source_path": source_id, "content": content,
                "sha256": digest}

    async def _lease_heartbeat(self, activity: dict[str, Any]) -> None:
        interval = max(1.0, self.settings.lease_seconds / 3.0)
        while True:
            await asyncio.sleep(interval)
            await self.store.renew_activity_lease(activity)

    async def _run_engineering_activity(self, activity: dict[str, Any], context: dict[str, Any]) -> None:
        """Run Grace proposal -> CME authorization/dispatch -> separate verifier -> CME completion."""
        assignment = validate_engineering_assignment(context["engineering_assignment"])
        if not context["available_engineering_operations"]:
            raise PermissionError("no enabled isolated_write operation is available for this assignment")
        prior = activity.get("checkpoint") or {}
        state = dict(prior.get("engineering_state") or {})
        conversation = list(state.get("conversation") or [])
        model_turns = list(state.get("model_turns") or [])
        base_checkpoint = {"activity_input": activity["input"], "model_route": context["model_route"],
                           "config_revision": context["config_revision"],
                           "selected_role_id": context.get("selected_role_id"),
                           "route_decision": context.get("route_decision")}

        async def checkpoint(phase: str, **items: Any) -> None:
            state.update(items)
            snapshot = {**base_checkpoint, "engineering_state": state}
            await self.store.record_progress(activity,
                {"phase": phase, "at": utcnow().isoformat(), **items}, snapshot)

        proposal_value = state.get("proposal")
        typed_proposal = None
        if isinstance(proposal_value, dict) and proposal_value.get("contract_id") == "r3a.engineering-proposal":
            typed_proposal = EngineeringProposal.from_dict(proposal_value)
            if len(typed_proposal.proposed_operations) != 1:
                raise ValueError("this isolated AP2 execution slice requires one bounded proposed operation")
            saved_ref = typed_proposal.proposed_operations[0]
            proposal_value = {"operation_id": saved_ref.operation_id,
                              "contract_version": saved_ref.contract_version,
                              "target": saved_ref.target, "inputs": saved_ref.inputs,
                              "verification_plan": typed_proposal.verification_plan}
        if proposal_value is None:
            context["conversation"] = conversation
            context["request_ref"] = str(uuid.uuid4())
            await checkpoint("engineering.proposal.requested", request_ref=context["request_ref"])
            response = (await self._module_call("execute", context,
                         timeout=context["model_route"]["timeout_seconds"] + 15))["result"]
            if response.get("action") != "propose_engineering" or not isinstance(response.get("engineering_proposal"), dict):
                raise ValueError("Grace did not return a typed Engineering proposal action")
            model_record = response.get("model") or {}
            model_turns.append({"action": "propose_engineering", "request_ref": model_record.get("request_ref"),
                                "result_ref": model_record.get("result_ref"),
                                "request_sha256": model_record.get("request_sha256"),
                                "result_sha256": model_record.get("result_sha256"),
                                "usage": model_record.get("usage"), "content": response.get("model_content"),
                                "observed_at": utcnow().isoformat()})
            conversation.append({"role": "assistant", "content": response["model_content"]})
            proposal_value = response["engineering_proposal"]
            await checkpoint("engineering.proposal.received", proposal=proposal_value,
                             model_turns=model_turns, conversation=conversation,
                             proposal_rationale=response.get("rationale"),
                             proposal_model=model_record)

        descriptor = next((entry for entry in context["available_engineering_operations"]
                           if entry.get("operation_id") == proposal_value.get("operation_id")
                           and entry.get("contract_version") == proposal_value.get("contract_version")), None)
        if descriptor is None or descriptor.get("effect_class") != "isolated_write":
            raise PermissionError("Grace proposal does not resolve to a discovered enabled isolated_write operation")
        operation = self.settings.capability_registry.resolve(
            descriptor["operation_id"], descriptor["contract_version"])
        validate_json(proposal_value["target"], descriptor["target_scope_schema"], path="$.target")
        validate_json(proposal_value["inputs"], descriptor["input_schema"], path="$.input")
        target_workspace = proposal_value["target"].get("workspace_id")
        if target_workspace != assignment["workspace_id"]:
            raise PermissionError("Grace proposal target is outside the institution-assigned workspace")
        artifact_path = proposal_value["inputs"].get("path")
        if not isinstance(artifact_path, str) or not any(
                artifact_path == allowed or (allowed.endswith("**") and artifact_path.startswith(allowed[:-2]))
                for allowed in assignment["allowed_paths"]):
            raise PermissionError("Grace proposal output path is outside the institution-assigned allowlist")
        operation_ref = CapabilityOperationRef(descriptor["operation_id"], descriptor["contract_version"],
                                               descriptor["effect_class"], proposal_value["target"],
                                               proposal_value["inputs"])
        proposal = typed_proposal
        if proposal is None:
            model_ref = state.get("proposal_model") or {}
            proposal = EngineeringProposal(
                proposal_id=str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                           "grace-engineering-proposal-v1")),
                proposal_revision=1, activity_id=str(activity["activity_id"]),
                attempt_id=str(activity["attempt_id"]),
                correlation_id=str(activity["input"]["correlation_id"]),
                resident_id=self.module_id, config_revision=self.settings.source_digest,
                created_at=utcnow().isoformat(), objective=activity["input"]["objective"],
                criteria=tuple(assignment["criteria"]), repository=assignment["repository"],
                baseline_ref=assignment["baseline_ref"], scope=assignment,
                proposed_operations=(operation_ref,),
                verification_plan=proposal_value["verification_plan"],
                reasoning_provenance={"route_id": context["route_id"],
                                      "provider": model_ref.get("provider"),
                                      "model": model_ref.get("name"),
                                      "request_ref": model_ref.get("request_ref"),
                                      "result_ref": model_ref.get("result_ref"),
                                      "result_sha256": model_ref.get("result_sha256")})
            proposal_value = proposal.to_dict()
            await self.store.record_engineering_proposal(activity, proposal)
            await checkpoint("engineering.proposal.validated", proposal=proposal_value,
                             proposal_digest=proposal_digest(proposal))

        proposal = typed_proposal or EngineeringProposal.from_dict(proposal_value)
        order_id = str(uuid.uuid5(uuid.UUID(proposal.proposal_id), f"work-order:{proposal.proposal_revision}"))
        durable_order = await self.store.get_engineering_work_order(order_id)
        if durable_order is None:
            request_id = str(uuid.uuid5(uuid.UUID(order_id), "authorization"))
            decision = await self._authorization_decision(
                descriptor["required_grants"][0], request_id=request_id,
                activity_id=proposal.activity_id, attempt_id=proposal.attempt_id,
                correlation_id=proposal.correlation_id,
                context={"dispatcher": "CME", "purpose": "engineering_work_order_issue",
                         "operation_id": descriptor["operation_id"], "target": operation_ref.target,
                         "allowed_paths": assignment["allowed_paths"],
                         "proposal_id": proposal.proposal_id,
                         "proposal_digest": proposal_digest(proposal)})
            if not decision.audit_event_id or not decision.decision_id:
                raise PermissionError("authorization provider did not return durable audit and decision references")
            work_order = EngineeringWorkOrder(
                work_order_id=order_id, work_order_version=1, activity_id=proposal.activity_id,
                attempt_id=proposal.attempt_id, correlation_id=proposal.correlation_id,
                proposal_id=proposal.proposal_id, proposal_revision=proposal.proposal_revision,
                proposal_digest=proposal_digest(proposal), resident_id=self.module_id,
                config_revision=self.settings.source_digest, repository=assignment["repository"],
                baseline_ref=assignment["baseline_ref"], workspace_id=assignment["workspace_id"],
                allowed_paths=tuple(assignment["allowed_paths"]),
                command_profiles=tuple(assignment["command_profiles"]),
                operation_refs=(operation_ref,), authorization_decision_id=decision.decision_id,
                authorization_audit_event_id=decision.audit_event_id,
                authorization_provider_id=decision.provider_id, policy_revision=decision.policy_revision,
                authorization_expires_at=None, criteria=tuple(assignment["criteria"]), issued_at=utcnow().isoformat())
            await self.store.create_engineering_work_order(work_order.to_dict(), decision)
            await checkpoint("engineering.work_order.authorized", work_order=work_order.to_dict(),
                             work_order_id=order_id, authorization_audit_event_id=decision.audit_event_id)
            durable_order = await self.store.get_engineering_work_order(order_id)
        work_order = EngineeringWorkOrder.from_dict(durable_order["details"]["work_order"])
        if durable_order["state"] == "AUTHORIZED":
            await self.store.transition_engineering_work_order(
                order_id, "EXECUTING", work_order.activity_id, str(activity["attempt_id"]),
                work_order.correlation_id, "CME dispatched the authorized proposal", {
                    "proposal_digest": work_order.proposal_digest, "execution_owner": "CME"})
            durable_order["state"] = "EXECUTING"
        elif durable_order["state"] not in {"EXECUTING", "VERIFYING", "COMPLETED"}:
            raise RuntimeError(f"Engineering work order cannot resume from {durable_order['state']}")

        invocation = None
        if durable_order["state"] not in {"VERIFYING", "COMPLETED"}:
            action_id = str(uuid.uuid5(uuid.UUID(order_id), "canonical-invocation-v1"))
            action = EngineeringAction(
                action_id=action_id, idempotency_key=f"{order_id}:{descriptor['operation_id']}:v1",
                work_order_id=order_id, work_order_version=work_order.work_order_version,
                activity_id=work_order.activity_id, attempt_id=work_order.attempt_id,
                correlation_id=work_order.correlation_id, operation=operation_ref,
                caller_id=self.module_id, requested_at=utcnow().isoformat(),
                config_revision=self.settings.source_digest,
                evidence_purpose="produce the bounded, independently verifiable Engineering artifact")
            invocation = await self.invoke_capability(action.to_invocation_request(), work_order=work_order)
            if invocation.get("outcome") != "SUCCEEDED":
                raise RuntimeError("canonical Engineering capability did not succeed")
            await checkpoint("engineering.execution.succeeded", invocation=invocation,
                             invocation_id=action_id)

        invocation = invocation or state.get("invocation")
        if not isinstance(invocation, dict) or invocation.get("outcome") != "SUCCEEDED":
            raise RuntimeError("durable successful invocation evidence is unavailable")
        evidence_refs = [f"invocation:{invocation['invocation_id']}"]
        evidence_refs.append(str(invocation["invocation_id"]))
        authorization = invocation.get("authorization") or {}
        if authorization.get("audit_event_id"):
            evidence_refs.append(str(authorization["audit_event_id"]))
        operation_for_verifier = {**descriptor, "configuration": operation.configuration}
        verification = verify_workspace_artifact(
            work_order, operation_for_verifier, operation.configuration["workspace_root"],
            verifier_id=assignment["verifier_id"], verifier_version=assignment["verifier_version"],
            policy_revision=assignment["policy_revision"])
        artifact_path = operation_ref.inputs["path"]
        artifact_file = (Path(operation.configuration["workspace_root"]) / artifact_path).resolve()
        artifact_observation = {"path": artifact_path, "evidence_ref": f"workspace:{artifact_path}",
                                "sha256": verification.artifact_digests[0]
                                if verification.artifact_digests else None,
                                "exists": artifact_file.is_file()}
        if artifact_file.is_file() and artifact_file.stat().st_size <= 65536:
            artifact_observation["content"] = artifact_file.read_text(encoding="utf-8")
        execution_evidence = {"invocation": invocation,
                              "artifact": artifact_observation,
                              "independent_verification": verification.to_dict()}
        evidence_refs.append(f"workspace:{artifact_path}")
        if verification.verification_id:
            evidence_refs.append("independent_verification")
            evidence_refs.append(str(verification.verification_id))
        await checkpoint("engineering.artifact.inspected", invocation=invocation,
                         invocation_id=invocation["invocation_id"],
                         execution_evidence=execution_evidence,
                         verification_preview=verification.to_dict())
        if state.get("grace_assessment") is None:
            context["conversation"] = conversation + [
                {"role": "user", "content": json.dumps({"engineering_execution_result": execution_evidence,
                                                          "available_evidence_refs": evidence_refs,
                                                          "instruction": "Assess the actual execution output against the assignment. State whether it is ready for independent verification or blocked; do not claim acceptance."}, separators=(",", ":"))}]
            context["request_ref"] = str(uuid.uuid4())
            response = (await self._module_call("execute", context,
                         timeout=context["model_route"]["timeout_seconds"] + 15))["result"]
            if response.get("action") != "engineering_assess":
                raise ValueError("Grace did not return its required post-execution assessment")
            assessment = response.get("engineering_assessment") or {}
            model_ref = response.get("model") or {}
            model_turns.append({"action": "engineering_assess", "request_ref": model_ref.get("request_ref"),
                                "result_ref": model_ref.get("result_ref"),
                                "request_sha256": model_ref.get("request_sha256"),
                                "result_sha256": model_ref.get("result_sha256"),
                                "usage": model_ref.get("usage"), "content": response.get("model_content"),
                                "observed_at": utcnow().isoformat()})
            await checkpoint("engineering.resident_assessed", grace_assessment=assessment,
                             model_turns=model_turns, execution_evidence=execution_evidence,
                             assessment_model=model_ref)
        assessment = state["grace_assessment"]
        if assessment.get("status") != "ready_for_verification":
            if durable_order["state"] in {"EXECUTING", "AUTHORIZED"}:
                await self.store.transition_engineering_work_order(
                    order_id, "BLOCKED", work_order.activity_id, str(activity["attempt_id"]),
                    work_order.correlation_id, "Grace assessed execution as blocked",
                    {"grace_assessment": assessment, "invocation_id": invocation["invocation_id"]})
            await self.store.block_activity(activity, "Grace reported Engineering execution blocked",
                                            {"engineering_assessment": assessment,
                                             "work_order_id": order_id,
                                             "model_turns": model_turns,
                                             "invocation": invocation})
            return
        if not set(assessment.get("evidence_refs", [])).issubset(set(evidence_refs)):
            raise PermissionError("Grace assessment references execution evidence not returned by CME")
        if durable_order["state"] == "COMPLETED":
            result = {"work_order_id": order_id, "state": "COMPLETED",
                      "verification": durable_order["details"].get("verification_result"),
                      "grace_assessment": assessment, "model_turns": model_turns,
                      "invocation": invocation}
            await self.store.finish_activity(activity, result)
            return
        await checkpoint("engineering.verification.completed", verification=verification.to_dict(),
                         verification_outcome=verification.outcome)
        if durable_order["state"] == "EXECUTING":
            await self.store.transition_engineering_work_order(
                order_id, "VERIFYING", work_order.activity_id, str(activity["attempt_id"]),
                work_order.correlation_id, "CME submitted artifact to independent verifier",
                {"verification_id": verification.verification_id,
                 "verification_outcome": verification.outcome,
                 "artifact_digests": list(verification.artifact_digests)})
        if verification.outcome != "PASS":
            await self.store.transition_engineering_work_order(
                order_id, "BLOCKED", work_order.activity_id, str(activity["attempt_id"]),
                work_order.correlation_id, "Independent verification did not PASS",
                {"verification_result": verification.to_dict()})
            await self.store.block_activity(activity, "Independent Engineering verification did not pass",
                                            {"work_order_id": order_id,
                                             "verification": verification.to_dict(),
                                             "grace_assessment": assessment,
                                             "model_turns": model_turns, "invocation": invocation})
            return
        await self.complete_engineering_work_order(work_order, verification)
        await self.store.finish_activity(activity, {
            "work_order_id": order_id, "work_order_state": "COMPLETED",
            "proposal": proposal.to_dict(), "grace_rationale": state.get("proposal_rationale"),
            "grace_assessment": assessment, "model_turns": model_turns,
            "invocation": invocation, "verification": verification.to_dict()})

    async def _run_activity(self, activity: dict[str, Any]) -> None:
        lease_task: asyncio.Task | None = None
        try:
            if self.module_process is None or self.module_process.returncode is not None:
                raise RuntimeError("registered module process is not running")
            context = (await self._objective_context(activity) if activity["activity_type"] == "grace.objective"
                       else await self._observer_context(activity))
            if activity["activity_type"] == "grace.objective":
                if context.get("engineering_assignment") is not None:
                    lease_task = asyncio.create_task(self._lease_heartbeat(activity),
                                                     name=f"lease-heartbeat:{activity['activity_id']}")
                    await self._run_engineering_activity(activity, context)
                    return
                model_route = context["model_route"]
                reasoning_state = dict(context.get("reasoning_state") or {})
                conversation = list(context.get("conversation") or [])
                turns = list(reasoning_state.get("model_turns") or [])
                invocations = list(reasoning_state.get("capability_invocations") or [])
                evidence = list(context.get("evidence") or [])
                required_evidence_refs = list(context.get("required_evidence_refs") or [])
                acceptance_rejections = list(reasoning_state.get("acceptance_rejections") or [])
                last_rejected_fingerprint = reasoning_state.get("last_rejected_evidence_fingerprint")

                def durable_checkpoint() -> dict[str, Any]:
                    return {"activity_input": activity["input"], "model_route": model_route,
                            "evidence_format": context["evidence_format"],
                            "required_evidence_refs": required_evidence_refs,
                            "config_revision": context["config_revision"],
                            "selected_role_id": context.get("selected_role_id"),
                            "route_decision": context.get("route_decision"),
                            "evidence": evidence,
                            "evidence_refs": [{"source_id": item["source_id"],
                                               "source_path": item.get("source_path"),
                                               "sha256": item["sha256"],
                                               "source_sha256": item.get("source_sha256")}
                                              for item in evidence],
                            "reasoning_state": {"conversation": conversation,
                                                "model_turns": turns,
                                                "capability_invocations": invocations,
                                                "acceptance_rejections": acceptance_rejections,
                                                "last_rejected_evidence_fingerprint": last_rejected_fingerprint,
                                                "pending_final": context.get("pending_final")}}

                lease_task = asyncio.create_task(self._lease_heartbeat(activity),
                                                 name=f"lease-heartbeat:{activity['activity_id']}")
                observations = context.get("pending_final")
                while observations is None:
                    context["conversation"] = conversation
                    context["evidence"] = evidence
                    context["required_evidence_refs"] = required_evidence_refs
                    context["request_ref"] = str(uuid.uuid4())
                    await self.store.record_progress(
                        activity,
                        {"phase": "resident.inference.requested", "at": utcnow().isoformat(),
                         "route_id": model_route["route_id"], "provider": model_route["provider"],
                         "model": model_route["model"], "request_ref": context["request_ref"],
                         "turn": len(turns) + 1,
                         "objective_sha256": hashlib.sha256(
                             activity["input"]["objective"].encode()).hexdigest()},
                        durable_checkpoint())
                    result = await self._module_call("execute", context,
                        timeout=context["model_route"]["timeout_seconds"] + 15)
                    observations = result["result"]
                    turn_model = observations.get("model", {})
                    turn_record = {"turn": len(turns) + 1, "request_ref": turn_model.get("request_ref"),
                                   "request_sha256": turn_model.get("request_sha256"),
                                   "result_ref": turn_model.get("result_ref"),
                                   "result_sha256": turn_model.get("result_sha256"),
                                   "usage": turn_model.get("usage"),
                                   "action": observations.get("action"),
                                   "observed_at": utcnow().isoformat()}
                    turns.append(turn_record)
                    model_content = observations.get("model_content")
                    if not isinstance(model_content, str):
                        raise RuntimeError("Grace omitted the recorded model action content")
                    conversation.append({"role": "assistant", "content": model_content})
                    if observations.get("action") == "invoke_capability":
                        capability_request = observations.get("capability_request")
                        if not isinstance(capability_request, dict):
                            raise RuntimeError("Grace returned an incomplete capability request")
                        capability_result = await self._invoke_resident_capability(activity,
                                                                                   capability_request)
                        invocations.append({"capability_request": capability_request,
                                            "result": capability_result})
                        evidence.extend(capability_result["evidence"])
                        required_evidence_refs = sorted(set(required_evidence_refs) |
                                                        {item["source_id"] for item in
                                                         capability_result["evidence"]})
                        conversation.append({"role": "user", "content": json.dumps(
                            {"capability_result": capability_result}, separators=(",", ":"))})
                        await self.store.record_progress(
                            activity,
                            {"phase": "resident.capability.completed", "at": utcnow().isoformat(),
                             "turn": len(turns), "capability_id": capability_request["capability_id"],
                             "authorization_audit_event_id": capability_result["authorization"].get(
                                 "audit_event_id"),
                             "evidence_count": len(capability_result["evidence"])},
                            durable_checkpoint())
                        observations = None
                        continue
                    if observations.get("action") != "final":
                        raise RuntimeError("Grace returned an unsupported resident action")
                    candidate_decision = observations.get("decision") or {}
                    if candidate_decision.get("status") == "healthy":
                        final_issues = self._final_evidence_issues(context, evidence, candidate_decision)
                        if final_issues:
                            fingerprint = evidence_fingerprint(evidence)
                            if fingerprint == last_rejected_fingerprint:
                                await self.store.block_activity(
                                    activity, "Grace repeated an unsupported completion without new evidence",
                                    {"validation": "r3a.objective-acceptance.v1",
                                     "criteria_gaps": final_issues,
                                     "decision": candidate_decision,
                                     "model": observations.get("model"),
                                     "reasoning_trace": {"model_turns": turns,
                                                          "capability_invocations": invocations,
                                                          "acceptance_rejections": acceptance_rejections,
                                                          "evidence": evidence}})
                                return
                            last_rejected_fingerprint = fingerprint
                            rejection = {"turn": len(turns), "observed_at": utcnow().isoformat(),
                                         "criteria_gaps": final_issues,
                                         "evidence_fingerprint": fingerprint,
                                         "result_ref": (observations.get("model") or {}).get("result_ref")}
                            acceptance_rejections.append(rejection)
                            conversation.append({"role": "user", "content": json.dumps(
                                {"institutional_acceptance": "rejected",
                                 "message": "The proposed COMPLETED result does not yet satisfy the "
                                            "objective's evidence criteria. Reassess the original objective "
                                            "against all evidence collected. Continue with any relevant "
                                            "authorized read capability you judge necessary, or return a "
                                            "truthful blocked final if the evidence cannot be obtained.",
                                 "gaps": final_issues}, separators=(",", ":"))})
                            context["pending_final"] = None
                            await self.store.record_progress(
                                activity,
                                {"phase": "resident.completion.rejected", "at": utcnow().isoformat(),
                                 "turn": len(turns), "criteria_gaps": final_issues,
                                 "evidence_fingerprint": fingerprint},
                                durable_checkpoint())
                            observations = None
                            continue
                    context["pending_final"] = observations
                    await self.store.record_progress(
                        activity,
                        {"phase": "resident.decision.ready", "at": utcnow().isoformat(),
                         "turn": len(turns), "status": (observations.get("decision") or {}).get("status"),
                         "result_ref": (observations.get("model") or {}).get("result_ref")},
                        durable_checkpoint())
                    break
            else:
                await self.store.record_progress(activity,
                    {"phase": "capabilities_read", "at": utcnow().isoformat()},
                                             {"capability_observations": context})
                result = await self._module_call("execute", context, timeout=5.0)
                observations = result["result"]
            decision = observations.get("decision", {}) if isinstance(observations, dict) else {}
            answer_issues = (_knowledge_answer_issues(context["objective"], context["evidence"], decision)
                             if activity["activity_type"] == "grace.objective" else [])
            if activity["activity_type"] != "grace.objective":
                await self.store.finish_activity(activity, observations)
            elif decision.get("status") != "healthy":
                await self.store.block_activity(activity,
                    "Grace did not conclude the objective with a fully supported answer",
                    {"decision": decision, "model": observations.get("model"),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "evidence": evidence}})
            elif not decision.get("evidence_refs"):
                await self.store.block_activity(activity,
                    "Grace final response did not cite any returned evidence",
                    {"validation": "r3a.resident-evidence-citation.v1", "decision": decision,
                     "model": observations.get("model"),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "evidence": evidence}})
            elif (not set(decision.get("evidence_refs", [])).issubset(
                        {item.get("source_id") for item in evidence})
                  or not set(context.get("required_evidence_refs", [])).issubset(
                        decision.get("evidence_refs", []))):
                await self.store.block_activity(activity,
                    "Grace final response cited missing or incomplete source evidence",
                    {"validation": "r3a.resident-evidence-citation.v1", "decision": decision,
                     "known_source_ids": sorted({item.get("source_id") for item in evidence}),
                     "required_evidence_refs": context.get("required_evidence_refs", []),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "evidence": evidence}})
            elif answer_issues:
                await self.store.block_activity(
                    activity, "Grace response did not satisfy the evidence-backed transition request",
                    {"validation": "r3a.transition-answer.v1", "missing_destinations": answer_issues,
                     "decision": decision, "model": observations.get("model"),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "evidence": evidence},
                     "request_ref": (observations.get("model") or {}).get("request_ref")})
            else:
                observations["reasoning_trace"] = {"model_turns": turns,
                                                    "capability_invocations": invocations,
                                                    "acceptance_rejections": acceptance_rejections,
                                                    "evidence": [{"source_id": item["source_id"],
                                                                  "source_path": item.get("source_path"),
                                                                  "sha256": item["sha256"],
                                                                  "source_sha256": item.get("source_sha256")}
                                                                 for item in evidence]}
                await self.store.finish_activity(activity, observations)
        except AcceptanceCriteriaRequired as exc:
            await self.store.block_activity(
                activity, "objective acceptance criteria are required",
                {"validation": "r3a.objective-acceptance.v1",
                 "criteria_gaps": [{"criterion_id": "acceptance_criteria",
                                    "code": "acceptance_criteria_missing", "message": str(exc)}]})
        except PermissionError as exc:
            await self.store.block_activity(activity, "capability grant required", {"error": str(exc)})
        except ModelRoleUnavailable as exc:
            details = {"role_id": exc.decision.requested_role_id,
                       "decision": exc.decision.__dict__,
                       "config_revision": self.settings.source_digest}
            if exc.decision.action == "defer":
                details["contract_outcome"] = ContractOutcome(
                    "r3a.model-route-decision", "1.0.0",
                    exc.decision.request_id or str(uuid.uuid4()),
                    exc.decision.correlation_id or str(activity["activity_id"]),
                    self.module_id, self.settings.source_digest, utcnow().isoformat(),
                    "deferred", True, reason_code=exc.decision.reason,
                    retry_after_seconds=exc.retry_after_seconds,
                    activity_id=str(activity["activity_id"]),
                    attempt_id=str(activity["attempt_id"])).to_dict()
                await self.store.defer_activity(activity, exc.decision.reason,
                                                exc.retry_after_seconds, details)
            else:
                details["contract_outcome"] = ContractOutcome(
                    "r3a.model-route-decision", "1.0.0",
                    exc.decision.request_id or str(uuid.uuid4()),
                    exc.decision.correlation_id or str(activity["activity_id"]),
                    self.module_id, self.settings.source_digest, utcnow().isoformat(),
                    "blocked", False, reason_code=exc.decision.reason,
                    error={"code": exc.decision.reason},
                    activity_id=str(activity["activity_id"]),
                    attempt_id=str(activity["attempt_id"])).to_dict()
                await self.store.block_activity(activity, exc.decision.reason, details)
        except asyncio.CancelledError:
            await self.store.fail_activity(activity, RuntimeError("CME shutdown interrupted idempotent observer"), 0)
            raise
        except Exception as exc:
            retry = min(self.settings.restart_initial_seconds * (2 ** min(activity["attempt_count"], 16)),
                        self.settings.restart_max_seconds)
            await self.store.fail_activity(activity, exc, retry)
        finally:
            if lease_task:
                lease_task.cancel()
                await asyncio.gather(lease_task, return_exceptions=True)
            self.active_activities.pop(activity["activity_id"], None)

    def _final_evidence_issues(self, context: dict[str, Any], evidence: list[dict[str, Any]],
                               decision: dict[str, Any]) -> list[dict[str, Any]]:
        """Check citations and objective acceptance against independently returned evidence."""
        known_sources = {item.get("source_id") for item in evidence}
        citations = decision.get("evidence_refs")
        if not isinstance(citations, list) or not citations:
            return [{"code": "evidence_citations_missing",
                     "message": "Cite the returned source IDs that support the deliverable."}]
        if (not set(citations).issubset(known_sources)
                or not set(context.get("required_evidence_refs", [])).issubset(citations)):
            return [{"code": "evidence_citations_incomplete",
                     "known_source_ids": sorted(str(item) for item in known_sources if item),
                     "required_source_ids": context.get("required_evidence_refs", []),
                     "message": "Citations do not cover the required returned evidence sources."}]
        answer_issues = _knowledge_answer_issues(context["objective"], evidence, decision)
        if answer_issues:
            return [{"code": "knowledge_answer_incomplete", "missing_facts": answer_issues,
                     "message": "The deliverable omits facts required by the cited knowledge evidence."}]
        trusted_digests: dict[str, set[str]] = {}
        for path in self.settings.knowledge_sources:
            try:
                source_path = Path(path)
                trusted_digests.setdefault(source_path.name, set()).add(
                    hashlib.sha256(source_path.read_bytes()).hexdigest())
            except OSError:
                continue
        try:
            criteria = validate_required_criteria(context.get("acceptance_criteria", []))
        except AcceptanceCriteriaRequired as exc:
            return [{"criterion_id": "acceptance_criteria", "code": "acceptance_criteria_missing",
                     "message": str(exc)}]
        return validate_acceptance(criteria, evidence, decision, trusted_digests)

    async def _scheduler_loop(self) -> None:
        while not self.shutdown.is_set():
            self.scheduler_tick = asyncio.get_running_loop().time()
            await self.store.ensure_observer_activity()
            await self.store.recover_expired_activities()
            await self._requeue_ready_model_activities()
            for waiting in await self.store.waiting_dependency_activities():
                await self.store.requeue_dependency_activity(waiting["activity_id"])
            while len(self.active_activities) < self.settings.worker_concurrency:
                activity = await self.store.claim_activity(f"cme:{os.getpid()}", self.settings.lease_seconds)
                if activity is None:
                    break
                task = asyncio.create_task(self._run_activity(activity),
                                           name=f"activity:{activity['activity_id']}")
                self.active_activities[activity["activity_id"]] = task
            await asyncio.sleep(self.settings.scheduler_interval_seconds)

    async def _heartbeat_loop(self) -> None:
        while not self.shutdown.is_set():
            module_health = "degraded"
            if self.module_process and self.module_process.returncode is None:
                try:
                    observation = await asyncio.wait_for(self._module_call("health"), timeout=3.0)
                    result = observation.get("result", {})
                    module_health = ("healthy" if result.get("state") == "ACTIVE"
                                     and result.get("health") == "healthy" else "degraded")
                    await self.store.observe_module(self.module_id, self.module_version, module_health,
                                                    {"pid": self.module_pid,
                                                     "module_state": result.get("state"),
                                                     "last_activity": result.get("last_activity")})
                except Exception as exc:
                    await self.store.observe_module(self.module_id, self.module_version, "unavailable",
                                                    {"pid": self.module_pid,
                                                     "probe_error": f"{type(exc).__name__}: {exc}"})
            await self.store.process_heartbeat("cme", os.getpid(), "RUNNING", module_health,
                                               {"module_id": self.module_id, "module_version": self.module_version,
                                                "module_pid": self.module_pid,
                                                "scheduler_tick_age_seconds": max(0.0, asyncio.get_running_loop().time() - self.scheduler_tick)})
            await asyncio.sleep(self.settings.heartbeat_interval_seconds)


async def run(config_path: str) -> None:
    settings = load_settings(config_path)
    cme = CME(settings)
    await cme.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="R3A AP0 CME process")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.config))


if __name__ == "__main__":
    main()
