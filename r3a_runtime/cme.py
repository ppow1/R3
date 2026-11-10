"""
R3 CONTROLLED SOURCE
File: r3a_runtime/cme.py
Component: R3A-CME-AP0
File Revision: 2.0.4
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
Changed: 2026-11-07 | R3A-AP2-ESCALATED-REASONING | Codex GPT-6 | Enforce Grace-requested reasoning escalation through existing authorization, readiness, durable checkpoint and per-activity token-budget paths.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Dispatch escalation inference through the unified capability invocation and durable budget-reservation path.
Changed: 2026-11-07 | R3A-AP1-MODEL-ROUTING | Codex GPT-6 | Resolve routes by configured task class and reject autonomic objective inference before model execution.
Changed: 2026-11-10T00:49:41Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Add registry-bound generic handler dispatch while preserving Grace and provider paths.
Changed: 2026-11-10T01:00:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Route bound residents through registry-selected executors and validate their manifest protocol range.
Changed: 2026-11-10T01:05:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Preserve test and compatibility contexts that omit the optional primary resident identifier.
Changed: 2026-11-10T01:10:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Block invalid registry bindings immediately and authorize handler capabilities as the registered handler module.
Changed: 2026-11-10T01:15:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Require handler capability declarations to be present in the registered module manifest.
Supersedes: None.
Contracts: AP0-002–010; AP0-M1 D2–D8; R3A-019; MOD-001–MOD-010; STM-001–STM-007; r3a.resident.execution.v1; r3a.model-role.v1; r3a.authorization-decision.v1; r3a.capability-invocation.v1; r3a.model-readiness-provider.v1; r3a.model-readiness.v2.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; tests/test_r3a_octominer_plugin.py; tests/test_r3a_telemetry_providers.py; tests/test_r3a_capability_contracts.py; tests/test_r3a_engineering.py.
History/Predecessor: Prior revision preserved at pre-change HEAD db9ba0e96eb02049a44729d982cc8522a0066937.
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
from datetime import datetime, timedelta, timezone
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
from .modular_dispatch import (DispatchContractError, build_resident_execution_profile,
                               resolve_activity_handler, resolve_resident_binding,
                               validate_activity_handler)


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

ACTIVITY_INTAKE_SCHEMA = json.loads(
    (Path(__file__).parent / "schemas" / "activity-intake.v1.schema.json").read_text(encoding="utf-8"))


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
        self.module_workers: dict[tuple[str, str, str], tuple[asyncio.subprocess.Process, Path]] = {}
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
        escalation_policy = self.settings.reasoning_escalation
        if escalation_policy and escalation_policy.enabled:
            escalation_operation = self.settings.capability_registry.resolve(
                escalation_policy.authorization_capability_id)
            if escalation_operation.descriptor["effect_class"] != "external_write":
                raise RuntimeError("reasoning escalation must resolve to a registered external_write operation")
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
        for key, (process, socket_path) in list(self.module_workers.items()):
            try:
                await module_request(socket_path, key[0], key[1], "stop", {}, timeout=2.0)
            except Exception:
                pass
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            socket_path.unlink(missing_ok=True)
        self.module_workers.clear()
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
            rows = await self.store.rows(
                "SELECT manifest FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                (module_id, version))
            if len(rows) != 1 or not isinstance(rows[0]["manifest"], dict):
                return
            entrypoint = rows[0]["manifest"].get("entrypoint")
            if not isinstance(entrypoint, str):
                return
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            expected = [b"-m", entrypoint.encode(), b"--module-id", module_id.encode(),
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

    async def _registered_module_call(self, module_id: str, module_version: str, operation: str,
                                      payload: dict[str, Any], timeout: float = 30.0,
                                      configuration_ref: str | None = None,
                                      binding_revision: str | None = None) -> dict[str, Any]:
        """Call an active registered module in its own CME-supervised worker process."""
        if (module_id, module_version) == (self.module_id, self.module_version):
            return await self._module_call(operation, payload, timeout)
        scope = binding_revision or "module-default"
        key = (module_id, module_version, scope)
        worker = self.module_workers.get(key)
        if worker is None or worker[0].returncode is not None:
            rows = await self.store.rows(
                "SELECT manifest,lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                key[:2])
            if len(rows) != 1 or rows[0]["lifecycle_state"] != "ACTIVE":
                raise PermissionError("registered module is missing or not active")
            manifest = rows[0]["manifest"]
            entrypoint = manifest.get("entrypoint") if isinstance(manifest, dict) else None
            if not isinstance(entrypoint, str) or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", entrypoint):
                raise ValueError("registered module entrypoint is invalid")
            artifact_ref = manifest.get("artifact_ref")
            digest = manifest.get("artifact_digest")
            artifact = Path(artifact_ref) if isinstance(artifact_ref, str) else None
            if (artifact is None or not artifact.is_absolute() or not artifact.is_file()
                    or not isinstance(digest, str) or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest):
                raise PermissionError("registered module artifact is unavailable or its immutable digest changed")
            socket_path = self.settings.module_socket.parent / "modules" / hashlib.sha256(
                f"{module_id}@{module_version}@{scope}".encode()).hexdigest() / "module.sock"
            socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            socket_path.unlink(missing_ok=True)
            command = [sys.executable, "-m", entrypoint, "--socket", str(socket_path),
                       "--module-id", module_id, "--module-version", module_version]
            config_ref = configuration_ref or manifest.get("configuration_ref")
            if isinstance(config_ref, str) and Path(config_ref).is_absolute() and Path(config_ref).is_file():
                command.extend(["--config", config_ref])
            process = await asyncio.create_subprocess_exec(
                *command, cwd=Path(__file__).resolve().parent.parent,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
                start_new_session=True)
            self.module_workers[key] = (process, socket_path)
            deadline = asyncio.get_running_loop().time() + 8.0
            while asyncio.get_running_loop().time() < deadline:
                if process.returncode is not None:
                    message = (await process.stderr.read()).decode("utf-8", "replace")[-1500:]
                    self.module_workers.pop(key, None)
                    raise RuntimeError(f"registered module failed to start: {message}")
                try:
                    hello = await module_request(socket_path, module_id, module_version, "hello", {}, timeout=1.0)
                    supported = hello.get("result", {}).get("supported_protocol", {})
                    if (supported.get("major") != PROTOCOL_MAJOR
                            or supported.get("min_minor", 999) > PROTOCOL_MINOR
                            or supported.get("max_minor", -1) < PROTOCOL_MINOR):
                        raise PermissionError("registered module protocol is incompatible")
                    break
                except (OSError, ConnectionError, asyncio.TimeoutError, RuntimeError):
                    await asyncio.sleep(0.1)
            else:
                process.terminate()
                await process.wait()
                self.module_workers.pop(key, None)
                raise TimeoutError("registered module did not expose its private socket")
            worker = (process, socket_path)
        return await module_request(worker[1], module_id, module_version, operation, payload, timeout)

    async def _registered_handler(self, activity_type: str) -> dict[str, Any]:
        if not hasattr(self.store, "rows"):
            return {}
        rows = await self.store.rows(
            "SELECT module_id,module_version,manifest,lifecycle_state FROM r3a.module_registry "
            "ORDER BY module_id,module_version")
        declared = any(isinstance(row.get("manifest"), dict)
                       and isinstance(row["manifest"].get("activity_handler"), dict)
                       and activity_type in row["manifest"]["activity_handler"].get("activity_types", [])
                       for row in rows)
        active = [row for row in rows if row.get("lifecycle_state") == "ACTIVE"]
        if not declared:
            # Activities with no handler declaration may still resolve through a resident binding.
            return {}
        resolved = resolve_activity_handler(active, activity_type)
        declared_capabilities = set(resolved["module"]["manifest"].get("capability_refs", []))
        if not set(resolved["handler"]["required_capabilities"]).issubset(declared_capabilities):
            raise DispatchContractError("activity handler requires capabilities absent from its registered module manifest")
        return resolved

    async def _resolve_resident_executor(self, activity: dict[str, Any]) -> dict[str, Any] | None:
        event_input = activity.get("input") or {}
        resident_id = event_input.get("resident_id")
        if not isinstance(resident_id, str) or not resident_id:
            return None
        bindings = [binding for binding in getattr(self.settings, "resident_module_bindings", ())
                    if binding.get("resident_id") == resident_id]
        if not bindings:
            if resident_id == self.module_id:
                return None
            raise DispatchContractError("no effective resident module binding is configured")
        if len(bindings) != 1:
            raise DispatchContractError("resident module binding is ambiguous")
        binding = bindings[0]
        activity_id = str(activity["activity_id"])
        attempt_id = str(activity["attempt_id"])
        decision = await self._authorization_decision(
            "resident.executor.execute", activity_id=activity_id, attempt_id=attempt_id,
            request_id=str(uuid.uuid5(uuid.UUID(activity_id), f"resident-execution:{resident_id}:{attempt_id}")),
            context={"dispatcher": "CME", "resident_id": resident_id,
                     "module_id": binding["module_id"], "module_version": binding["module_version"],
                     "binding_revision": binding["binding_revision"]}, resident_id=resident_id)
        try:
            directory_operation = self.settings.capability_registry.resolve("institutional.directory.discover")
        except KeyError as exc:
            raise DispatchContractError("authoritative resident directory capability is unavailable") from exc
        descriptor = directory_operation.descriptor
        request_id = str(uuid.uuid5(uuid.UUID(activity_id), f"resident-directory:{resident_id}:{attempt_id}"))
        invocation = {
            "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
            "invocation_id": request_id, "operation_id": descriptor["operation_id"],
            "operation_contract_version": descriptor["contract_version"],
            "caller": {"principal_id": resident_id, "resident_id": resident_id, "service_id": None},
            "target": {}, "input": {"resident_id": resident_id},
            "activity_id": activity_id, "attempt_id": attempt_id, "correlation_id": activity_id,
            "work_order": None, "evidence_purpose": "Verify current authoritative resident/office association",
            "idempotency_key": request_id,
            "deadline": (datetime.now(timezone.utc)
                         + timedelta(seconds=descriptor["execution"]["timeout_seconds"])).isoformat(),
            "config_revision": self.settings.source_digest,
        }
        directory_result = await self.invoke_capability(invocation)
        if directory_result.get("outcome") != "SUCCEEDED" or not isinstance(directory_result.get("output"), dict):
            raise DispatchContractError("authoritative directory lookup did not succeed")
        module_rows = await self.store.rows(
            "SELECT module_id,module_version,manifest,lifecycle_state FROM r3a.module_registry "
            "ORDER BY module_id,module_version")
        resolved = resolve_resident_binding(bindings, resident_id,
                                            binding["identity_association"], module_rows)
        config_path = Path(binding["configuration_ref"])
        profile = build_resident_execution_profile(binding, directory_result["output"], config_path)
        resolved["execution_profile"] = profile
        resolved["configuration_path"] = str(config_path)
        resolved["execution_authorization"] = {"decision_id": decision.decision_id,
                                                "audit_event_id": decision.audit_event_id,
                                                "policy_revision": decision.policy_revision}
        return resolved

    async def _run_registered_activity(self, activity: dict[str, Any], resolved: dict[str, Any]) -> None:
        handler = validate_activity_handler(resolved["handler"])
        module = resolved["module"]
        event_input = activity.get("input") or {}
        payload = {"contract_id": "r3a.activity-handler.request", "contract_version": "1.0.0",
                   "activity_id": str(activity["activity_id"]), "attempt_id": str(activity["attempt_id"]),
                   "correlation_id": str(event_input.get("correlation_id") or activity["activity_id"]),
                   "activity_type": activity["activity_type"], "idempotency_key": activity["idempotency_key"],
                   "input": event_input.get("activity_input", event_input),
                   "evidence": event_input.get("activity_evidence", []),
                   "checkpoint": activity.get("checkpoint") or {},
                   "handler": {"handler_id": handler["handler_id"],
                               "handler_version": handler["handler_version"],
                               "module_id": resolved["module_id"],
                               "module_version": resolved["module_version"],
                               "artifact_digest": resolved["artifact_digest"]}}
        validate_json(payload["input"], handler["request_schema"], path="$.input")
        handler_decision = await self._authorization_decision(
            "activity.handler.execute", activity_id=str(activity["activity_id"]),
            attempt_id=str(activity["attempt_id"]),
            request_id=str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                      f"handler-execute:{resolved['module_id']}:{activity['attempt_id']}")),
            context={"dispatcher": "CME", "handler_id": handler["handler_id"],
                     "module_id": resolved["module_id"], "activity_type": activity["activity_type"]},
            resident_id=event_input.get("resident_id") or resolved["module_id"])
        decisions = [{"capability_id": "activity.handler.execute",
                      "decision_id": handler_decision.decision_id,
                      "audit_event_id": handler_decision.audit_event_id,
                      "policy_revision": handler_decision.policy_revision}]
        for index, capability_id in enumerate(handler["required_capabilities"]):
            decision = await self._authorization_decision(
                capability_id, activity_id=str(activity["activity_id"]),
                attempt_id=str(activity["attempt_id"]),
                request_id=str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                          f"handler-grant:{capability_id}:{activity['attempt_id']}")),
                context={"dispatcher": "CME", "handler_id": handler["handler_id"],
                         "module_id": resolved["module_id"], "activity_type": activity["activity_type"]},
                resident_id=resolved["module_id"])
            decisions.append({"capability_id": capability_id, "decision_id": decision.decision_id,
                              "audit_event_id": decision.audit_event_id,
                              "policy_revision": decision.policy_revision})
        payload["authorized_capabilities"] = decisions
        await self.store.record_progress(activity,
            {"phase": "handler.dispatched", "handler_id": handler["handler_id"],
             "module_id": resolved["module_id"], "module_version": resolved["module_version"],
             "at": utcnow().isoformat()},
            {"handler": payload["handler"], "request": payload})
        response = await self._registered_module_call(
            resolved["module_id"], resolved["module_version"], "execute", payload, timeout=60.0)
        result = response.get("result")
        if not isinstance(result, dict):
            raise ValueError("activity handler returned a non-object result")
        validate_json(result, handler["result_schema"], path="$.result")
        progress = result.get("progress")
        if progress is not None:
            validate_json(progress, handler["progress_schema"], path="$.progress")
        checkpoint = result.get("checkpoint")
        if checkpoint is not None:
            validate_json(checkpoint, handler["checkpoint_schema"], path="$.checkpoint")
            await self.store.record_progress(activity,
                {"phase": "handler.checkpointed", "at": utcnow().isoformat(),
                 "handler_id": handler["handler_id"]},
                {"handler": payload["handler"], "handler_checkpoint": checkpoint})
        outcome = result.get("outcome")
        if outcome == "completed":
            await self.store.finish_activity(activity,
                {"contract_id": "r3a.activity-handler.result", "contract_version": "1.0.0",
                 "handler": payload["handler"], "authorization": decisions, "result": result})
        elif outcome == "blocked":
            await self.store.block_activity(activity, str(result.get("reason") or "activity handler blocked"),
                {"handler": payload["handler"], "authorization": decisions, "result": result})
        else:
            raise ValueError("activity handler result outcome must be completed or blocked")

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
            if (module_id, version) != (self.module_id, self.module_version):
                worker_key = (module_id, version, "module-default")
                running = self.module_workers.get(worker_key)
                if running is not None and running[0].returncode is None:
                    health = await self._registered_module_call(module_id, version, "health", {})
                    if health.get("result", {}).get("state") == "ACTIVE":
                        return {"module_id": module_id, "version": version,
                                "state": "ACTIVE", "pid": running[0].pid}
                await self.store.module_state(module_id, version, "ACTIVATING", "starting")
                try:
                    await self._registered_module_call(module_id, version, "hello", {},
                                                       allow_activation=True)
                    await self._registered_module_call(module_id, version, "prepare", {})
                    await self._registered_module_call(module_id, version, "activate", {})
                    health = await self._registered_module_call(module_id, version, "health", {})
                    if (health.get("result", {}).get("state") != "ACTIVE"
                            or health.get("result", {}).get("health") != "healthy"):
                        raise RuntimeError("registered module readiness observation did not report healthy/active")
                    worker = self.module_workers[worker_key]
                    await self.store.module_state(module_id, version, "ACTIVE", "healthy",
                                                  {"pid": worker[0].pid,
                                                   "artifact_digest": manifest["artifact_digest"]})
                    return {"module_id": module_id, "version": version,
                            "state": "ACTIVE", "pid": worker[0].pid}
                except Exception as exc:
                    await self.store.module_state(module_id, version, "FAILED", "unavailable",
                                                  {"reason": f"{type(exc).__name__}: {exc}"})
                    worker = self.module_workers.pop(worker_key, None)
                    if worker and worker[0].returncode is None:
                        worker[0].terminate()
                        await worker[0].wait()
                    raise
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

    async def _stop_registered_module(self, module_id: str, version: str) -> dict[str, Any]:
        matching = [(key, worker) for key, worker in self.module_workers.items()
                    if key[0] == module_id and key[1] == version]
        if not matching:
            await self.store.module_state(module_id, version, "STOPPED", "stopped",
                                          {"reason": "module worker was not running"})
            return {"stopped": True, "already_stopped": True, "module_id": module_id,
                    "version": version}
        await self.store.module_state(module_id, version, "STOPPING", "stopping")
        exit_codes = []
        for key, (process, socket_path) in matching:
            try:
                await module_request(socket_path, module_id, version, "stop", {}, timeout=2.0)
            except Exception:
                pass
            if process.returncode is None:
                try:
                    await asyncio.wait_for(process.wait(), self.settings.heartbeat_stale_after_seconds)
                except asyncio.TimeoutError:
                    process.terminate()
                    try:
                        await asyncio.wait_for(process.wait(), self.settings.heartbeat_stale_after_seconds)
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.wait()
            socket_path.unlink(missing_ok=True)
            self.module_workers.pop(key, None)
            exit_codes.append(process.returncode)
        await self.store.module_state(module_id, version, "STOPPED", "stopped",
                                      {"exit_codes": exit_codes})
        return {"stopped": True, "module_id": module_id, "version": version,
                "exit_codes": exit_codes}

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
            registered_manifest = payload.get("manifest")
            if registered_manifest is not None:
                if not isinstance(registered_manifest, dict):
                    raise ValueError("module.install manifest must be an object")
                required = {"module_id", "module_version", "contract_id", "protocol_major", "protocol_minor",
                            "entrypoint", "artifact_ref", "artifact_digest"}
                if not required.issubset(registered_manifest):
                    raise ValueError("module.install manifest is missing required registry fields")
                module_id = registered_manifest["module_id"]
                version = registered_manifest["module_version"]
                artifact_ref = registered_manifest["artifact_ref"]
                digest = registered_manifest["artifact_digest"]
                registered_manifest.setdefault("protocol_min_minor", registered_manifest["protocol_minor"])
                registered_manifest.setdefault("protocol_max_minor", registered_manifest["protocol_minor"])
                if (not isinstance(module_id, str)
                        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}", module_id)
                        or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version)
                        or not isinstance(registered_manifest["contract_id"], str)
                        or registered_manifest["protocol_major"] != PROTOCOL_MAJOR
                        or isinstance(registered_manifest["protocol_minor"], bool)
                        or not isinstance(registered_manifest["protocol_minor"], int)
                        or any(isinstance(registered_manifest[key], bool)
                               or not isinstance(registered_manifest[key], int)
                               for key in ("protocol_min_minor", "protocol_max_minor"))
                        or registered_manifest["protocol_min_minor"] < 0
                        or registered_manifest["protocol_max_minor"] < registered_manifest["protocol_min_minor"]
                        or not registered_manifest["protocol_min_minor"] <= PROTOCOL_MINOR
                           <= registered_manifest["protocol_max_minor"]
                        or not isinstance(registered_manifest["entrypoint"], str)
                        or not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", registered_manifest["entrypoint"])):
                    raise ValueError("module.install identity or protocol declaration is invalid")
                artifact = Path(artifact_ref) if isinstance(artifact_ref, str) else None
                if (artifact is None or not artifact.is_absolute() or not artifact.is_file()
                        or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                        or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest):
                    raise PermissionError("module.install artifact is unavailable or digest does not match")
                handler = (validate_activity_handler(registered_manifest["activity_handler"])
                           if registered_manifest.get("activity_handler") is not None else None)
                caps = registered_manifest.get("capability_refs", [])
                if (not isinstance(caps, list)
                        or any(not isinstance(cap, str) or not cap.strip() for cap in caps)
                        or len(set(caps)) != len(caps)):
                    raise ValueError("module.install capability_refs must be unique capability identifiers")
                if handler is not None and not set(handler["required_capabilities"]).issubset(set(caps)):
                    raise ValueError("module.install handler capabilities must be declared in capability_refs")
                await self.store.register_module(registered_manifest, "INSTALLED", "unknown",
                                                 {"idempotency_key": idempotency_key})
                await self.store.module_state(module_id, version, "INSTALLED", "unknown",
                                              {"artifact_digest": digest, "idempotency_key": idempotency_key})
                return {"installed": True, "module_id": module_id, "version": version,
                        "artifact_digest": digest, "lifecycle_state": "INSTALLED"}
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
            module_id = str(payload.get("module_id", self.module_id))
            version = str(payload.get("version", self.module_version))
            if (module_id, version) == (self.module_id, self.module_version):
                return await self._stop_module()
            return await self._stop_registered_module(module_id, version)
        if operation == "module.replace":
            module_id = str(payload.get("module_id", self.module_id))
            old_version = str(payload.get("old_version", self.module_version))
            new_version = str(payload.get("new_version", payload.get("version", "")))
            if module_id != self.module_id:
                if any(not task.done() for task in self.active_activities.values()):
                    raise RuntimeError("registered module replacement waits for active activities to reach a safe boundary")
                new_manifest = payload.get("manifest")
                if new_manifest is not None:
                    installed = await self._control_request(
                        "module.install", {"manifest": new_manifest}, f"{idempotency_key}:install")
                    if installed["module_id"] != module_id or installed["version"] != new_version:
                        raise ValueError("replacement manifest identity does not match module_id/new_version")
                if not new_version or new_version == old_version:
                    raise ValueError("replacement requires a distinct semantic module version")
                await self._stop_registered_module(module_id, old_version)
                try:
                    activated = await self._activate_module(module_id, new_version)
                except Exception:
                    await self._activate_module(module_id, old_version)
                    raise
                await self.store.record_module_replacement(module_id, old_version, new_version)
                return {**activated, "prior_version": old_version, "replacement_completed": True,
                        "cme_pid_unchanged": True}
            return await self._replace_module(str(payload["version"]))
        if operation == "capability.grant":
            module_id = str(payload["module_id"])
            capability_id = str(payload["capability_id"])
            reason = str(payload["reason"])
            grant_id = await self.store.grant_capability(
                module_id, capability_id, reason, payload.get("activity_id"))
            await self.store.requeue_blocked_activities()
            return {"grant_id": str(grant_id), "module_id": module_id,
                    "capability_id": capability_id, "activity_id": payload.get("activity_id"),
                    "granted_by": f"uid:{os.getuid()}"}
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
        if operation == "capability.discover":
            registry = self.settings.capability_registry
            operation_id = payload.get("operation_id")
            if operation_id is not None:
                if not isinstance(operation_id, str) or not operation_id:
                    raise ValueError("capability.discover operation_id must be nonempty text")
                contract_version = payload.get("contract_version", "1.0.0")
                if not isinstance(contract_version, str):
                    raise ValueError("capability.discover contract_version must be text")
                registry.resolve(operation_id, contract_version)
                operations = [entry for entry in registry.discover()
                              if entry["descriptor"]["operation_id"] == operation_id]
            else:
                operations = list(registry.discover())
            return {"operations": operations, "authorization_evaluated": False,
                    "effect": "none; discovery does not authorize invocation"}
        if operation == "capability.invoke":
            request = payload.get("request")
            if not isinstance(request, dict):
                raise ValueError("capability.invoke requires one canonical invocation request")
            if request.get("work_order") is not None:
                raise ValueError("work-order invocations must be submitted by the AP2 Engineering adapter")
            return await self.invoke_capability(request)
        if operation == "activity.intake.submit":
            operation_id = payload.get("operation_id")
            contract_version = payload.get("contract_version", "1.0.0")
            arguments = payload.get("arguments")
            if not isinstance(operation_id, str) or not operation_id or not isinstance(arguments, dict):
                raise ValueError("activity.intake.submit requires an operation_id and object arguments")
            provider_operation = self.settings.capability_registry.resolve(operation_id, contract_version)
            descriptor = provider_operation.descriptor
            if (descriptor["effect_class"] != "read"
                    or descriptor["output_schema"].get("$id") != "r3a.activity-intake.v1"):
                raise PermissionError("activity intake requires a read-only registered provider with the activity-intake output contract")
            validate_json(arguments, descriptor["input_schema"], path="$.arguments")
            invocation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"r3a.activity-intake:{idempotency_key}"))
            source_activity_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                                f"r3a.source-activity:{idempotency_key}"))
            source_attempt_id = str(uuid.uuid5(uuid.UUID(invocation_id), "source-intake"))
            invocation = {
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": invocation_id, "operation_id": operation_id,
                "operation_contract_version": contract_version,
                "caller": {"principal_id": self.module_id, "resident_id": self.module_id,
                           "service_id": None},
                "target": {}, "input": arguments, "activity_id": source_activity_id,
                "attempt_id": source_attempt_id,
                "correlation_id": invocation_id, "work_order": None,
                "evidence_purpose": "Read an authorized source and submit one durable activity intake",
                "idempotency_key": idempotency_key,
                "deadline": (datetime.now(timezone.utc)
                             + timedelta(seconds=descriptor["execution"]["timeout_seconds"])).isoformat(),
                "config_revision": self.settings.source_digest,
            }
            invocation_result = await self.invoke_capability(invocation)
            if invocation_result.get("outcome") != "SUCCEEDED":
                raise RuntimeError("registered activity-intake source did not return a successful result")
            intake = invocation_result.get("output")
            validate_json(intake, ACTIVITY_INTAKE_SCHEMA, path="$.activity_intake")
            provider = descriptor["provider"]
            provenance = intake["provenance"]
            if (provenance["module_id"] != provider["provider_id"]
                    or provenance["module_version"] != provider["provider_version"]
                    or provenance["artifact_sha256"] != provider["artifact_sha256"]
                    or provenance["configuration_revision"] != self.settings.source_digest
                    or intake["source"]["idempotency_key"] != idempotency_key):
                raise CapabilityContractError("activity-intake provenance or idempotency key does not match its authorized source")
            accepted = await self.store.submit_activity_intake(intake, invocation_result)
            return {**accepted, "source_invocation_id": invocation_id,
                    "source_authorization": invocation_result["authorization"],
                    "source_provider": invocation_result["provider"]}
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
            modalities = tuple(payload.get("required_modalities", ()))
            task_class = payload.get("task_class")
            if task_class is None:
                task_class = "vision" if "image" in modalities else "objective_reasoning"
            if task_class not in {"objective_reasoning", "vision"}:
                raise ValueError("Grace objective intake cannot use autonomic-only model roles")
            requested_role_id = payload.get("role_id")
            requested_route = payload.get("route_id")
            roles = self.settings.model_roles
            if requested_role_id is not None:
                selected_role = next((role for role in roles if role.role_id == requested_role_id), None)
                if selected_role is None:
                    raise ValueError("requested model role is not configured")
            elif requested_route is not None:
                matching = [role for role in roles if role.route_id == requested_route]
                if len(matching) != 1:
                    raise ValueError("requested route must resolve to exactly one configured model role")
                selected_role = matching[0]
            else:
                selected_role = self.settings.model_role_for_task(task_class)
            if task_class not in selected_role.task_classes:
                raise ValueError(f"model role {selected_role.role_id} is not authorized for {task_class}")
            return await self.store.submit_grace_objective(
                str(payload.get("objective", "")), idempotency_key,
                str(payload.get("event_kind", "objective")),
                str(selected_role.route_id), str(selected_role.role_id),
                tuple(payload.get("required_capabilities", ())),
                modalities,
                payload.get("acceptance_criteria", []), payload.get("engineering_assignment"),
                payload.get("depends_on_activity_ids"),
                payload.get("requested_activity_id", payload.get("activity_id")), task_class)
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
        saved = activity.get("checkpoint") or {}
        route_id = event_input.get("route_id")
        selected_role_id = event_input.get("role_id")
        task_class = event_input.get("task_class", "objective_reasoning")
        if task_class not in {"objective_reasoning", "vision"}:
            raise ModelRoleUnavailable(
                RouteDecision("block", selected_role_id or "", None, None,
                              "objective_activity_cannot_use_autonomic_role", False,
                              self.settings.source_digest,
                              request_id=str(uuid.uuid4()), activity_id=str(activity["activity_id"]),
                              attempt_id=str(activity["attempt_id"]), correlation_id=str(activity["activity_id"]),
                              resident_id=self.module_id, evaluated_at=utcnow().isoformat()), 0)
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
            role_contract = next((role for role in roles if role.role_id == decision_role_id), None)
            if role_contract is None or task_class not in role_contract.task_classes:
                raise ModelRoleUnavailable(
                    RouteDecision("block", decision_role_id, None, None,
                                  "role_not_authorized_for_task_class", False,
                                  self.settings.source_digest,
                                  request_id=str(uuid.uuid4()), activity_id=str(activity["activity_id"]),
                                  attempt_id=str(activity["attempt_id"]), correlation_id=str(activity["activity_id"]),
                                  resident_id=self.module_id, evaluated_at=utcnow().isoformat()), 0)
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
        escalation_offer = {"enabled": False}
        policy = event_input.get("reasoning_escalation")
        if policy and policy.get("enabled") is True:
            if (policy.get("contract_id") != "r3a.reasoning-escalation-policy"
                    or not str(policy.get("contract_version", "")).startswith("1.")
                    or policy.get("config_revision") != self.settings.source_digest):
                raise RuntimeError("Persisted reasoning escalation policy is incompatible with this activity")
            observations = await self._model_readiness_observations()
            escalation_state = reasoning_state.get("escalation") or {"requests": []}
            charged = sum(int(item.get("charged_completion_tokens", 0))
                          for item in escalation_state.get("requests", []))
            allowed_ids = set(policy.get("allowed_role_ids", []))
            role_offers = []
            for role in self.settings.model_roles:
                if (role.role_id not in allowed_ids or role.role_id == selected_role_id
                        or "objective_reasoning" not in role.task_classes):
                    continue
                readiness = resolve_role(
                    self.settings.model_roles, role.role_id, set(), observations,
                    config_revision=self.settings.source_digest, permit_fallback=False)
                role_offers.append({"role_id": role.role_id, "route_id": role.route_id,
                                    "capabilities": list(role.capabilities),
                                    "readiness": "ready" if readiness.action == "route" else "unavailable",
                                    "readiness_reason": readiness.reason,
                                    "readiness_observed_at": readiness.readiness_observed_at})
            escalation_offer = {
                "enabled": True,
                "contract_id": policy["contract_id"],
                "contract_version": policy["contract_version"],
                "authorization_capability_id": policy["authorization_capability_id"],
                "max_requests_per_activity": policy["max_requests_per_activity"],
                "max_completion_tokens_per_activity": policy["max_completion_tokens_per_activity"],
                "charged_completion_tokens": charged,
                "available_roles": role_offers,
            }
        return {"activity_type": "grace.objective", "activity_id": str(activity["activity_id"]),
                "attempt_id": str(activity["attempt_id"]),
                "objective": event_input["objective"], "event_kind": event_input.get("event_kind", "objective"),
                "task_class": task_class,
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
                "reasoning_escalation": escalation_offer,
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
        executor_module_id = activity.get("input", {}).get("executor_module_id")
        if executor_module_id:
            executor_version = activity.get("input", {}).get("executor_module_version")
            rows = await self.store.rows(
                "SELECT manifest,lifecycle_state FROM r3a.module_registry WHERE module_id=%s AND module_version=%s",
                (executor_module_id, executor_version))
            if (len(rows) != 1 or rows[0].get("lifecycle_state") != "ACTIVE"
                    or capability_id not in (rows[0].get("manifest") or {}).get("capability_refs", [])):
                raise PermissionError("resident capability is absent from its active executor manifest")
        elif capability_id not in self.settings.module_capabilities:
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
                     if capability_id == "institution.knowledge.read" else None},
            resident_id=activity.get("input", {}).get("resident_id"))
        evidence = []
        capability_output: Any = None
        if capability_id == "institution.knowledge.read":
            for index, path in enumerate(self.settings.knowledge_sources):
                evidence.extend(retrieve(path, f"knowledge.{index+1}", query))
            capability_output = evidence
        elif registered_operation is not None:
            provider = registered_operation.load_provider()
            provided = await asyncio.to_thread(provider.invoke, arguments,
                                                context={"activity_id": str(activity["activity_id"]),
                                                         "attempt_id": str(activity["attempt_id"]),
                                                         "correlation_id": str(activity.get("correlation_id")
                                                                               or activity["activity_id"]),
                                                         "operation_id": capability_id,
                                                         "config_revision": self.settings.source_digest,
                                                         "capability_catalog": list(registry.discover())})
            capability_output, provider_evidence = normalize_provider_result(
                provided, registered_operation.descriptor)
            evidence.extend(provider_evidence if isinstance(provider_evidence, list)
                            else [provider_evidence])
        else:
            evidence.extend(await self._read_runtime_capability(capability_id))
            capability_output = evidence
        return {"contract_id": tool["contract_id"],
                "contract_version": tool["contract_version"],
                "capability_id": capability_id, "outcome": "succeeded",
                "arguments": arguments, "output": capability_output, "evidence": evidence,
                "authorization": authorization, "observed_at": utcnow().isoformat()}

    async def invoke_capability(self, request: dict[str, Any], *,
                                work_order: EngineeringWorkOrder | None = None,
                                _approved_budget_reservation: dict[str, Any] | None = None,
                                _provider_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Single canonical CME dispatcher; read operations may omit Engineering work orders."""
        if request.get("contract_id") != "r3a.capability-invocation.v1":
            raise CapabilityContractError("CME requires r3a.capability-invocation.v1")
        operation = self.settings.capability_registry.resolve(
            request.get("operation_id", ""), request.get("operation_contract_version", ""))
        descriptor = operation.descriptor
        checked = validate_invocation_request(request, descriptor)
        order = None
        if work_order is None:
            if checked["work_order"] is not None:
                raise PermissionError("effectful invocation requires its validated Engineering work order")
            if descriptor["effect_class"] == "read":
                if checked.get("budget_reservation") is not None:
                    raise PermissionError("read invocation cannot reserve an external effect budget")
            elif descriptor["effect_class"] == "external_write":
                reservation = checked.get("budget_reservation")
                if (reservation is None or _approved_budget_reservation != reservation
                        or reservation["activity_id"] != checked["activity_id"]):
                    raise PermissionError(
                        "external invocation without a work order requires CME-approved activity budget reservation")
            else:
                raise PermissionError("isolated writes require their validated Engineering work order")
        else:
            if not isinstance(work_order, EngineeringWorkOrder):
                raise TypeError("work_order must be a validated EngineeringWorkOrder")
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
        if descriptor["effect_class"] == "external_write" and (
                work_order is not None or checked.get("budget_reservation") is None
                or _provider_context is None):
            raise PermissionError(
                "external_write requires a CME-approved activity budget and internal configured provider context")
        started_at = utcnow().isoformat()
        caller_resident = checked["caller"]["resident_id"] or checked["caller"]["principal_id"]
        authorization = await self._authorize_capability(
            descriptor["operation_id"], activity_id=work_order.activity_id if work_order else checked["activity_id"],
            attempt_id=work_order.attempt_id if work_order else checked["attempt_id"],
            request_id=checked["invocation_id"], resident_id=caller_resident,
            context={"dispatcher": "CME", "invocation_id": checked["invocation_id"],
                     "idempotency_key": checked["idempotency_key"],
                     "effect_class": descriptor["effect_class"],
                     "required_grants": descriptor["required_grants"],
                     "target": checked["target"],
                     "work_order_id": work_order.work_order_id if work_order else None,
                     "work_order_version": work_order.work_order_version if work_order else None,
                     "config_revision": checked["config_revision"]})
        auth_ref = {"provider_id": authorization["provider_id"], "allowed": True,
                    "decision_id": authorization["decision_id"],
                    "audit_event_id": authorization["audit_event_id"],
                    "policy_revision": authorization["policy_revision"],
                    "config_revision": authorization["config_revision"]}
        canonical_digest = hashlib.sha256(json.dumps(checked, sort_keys=True,
                                                    separators=(",", ":")).encode()).hexdigest()
        persistence_key = checked["idempotency_key"] or f"invocation:{checked['invocation_id']}"
        durable_request = {**checked, "idempotency_key": persistence_key}
        existing = await self.store.begin_capability_invocation(durable_request, canonical_digest, auth_ref)
        if existing["state"] == "SUCCEEDED" and existing.get("result") is not None:
            return existing["result"]
        if existing["state"] != "STARTED":
            raise RuntimeError(f"invocation requires reconciliation from durable state {existing['state']}")
        if not existing.get("created", False) and not descriptor["recovery"]["replay_safe"]:
            raise RuntimeError("interrupted invocation is not replay safe; reconciliation is required")
        provider = operation.load_provider()
        try:
            output = await asyncio.to_thread(provider.invoke, checked["input"], context={
                "invocation_id": checked["invocation_id"], "idempotency_key": persistence_key,
                "activity_id": checked["activity_id"], "attempt_id": checked["attempt_id"],
                "correlation_id": checked["correlation_id"], "target": checked["target"],
                "work_order": order, "effect_class": descriptor["effect_class"],
                "config_revision": self.settings.source_digest,
                **(_provider_context or {}),
                "capability_catalog": list(self.settings.capability_registry.discover())})
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
                      "reconciliation_ref": persistence_key}
            await self.store.finish_capability_invocation(persistence_key, canonical_digest, result)
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
        await self.store.finish_capability_invocation(persistence_key, canonical_digest, result)
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

    async def _run_bound_resident_activity(self, activity: dict[str, Any],
                                           resolved: dict[str, Any]) -> None:
        """Dispatch through the binding selected from external configuration and the module registry."""
        profile = resolved["execution_profile"]
        module = resolved["module"]
        resident_id = profile["resident_id"]
        event_input = activity.get("input") or {}
        module_capabilities = set(module["manifest"].get("capability_refs", []))
        tools = [tool for tool in self._resident_tools()
                 if tool.get("capability_id") in module_capabilities]
        resident_input = event_input.get("activity_input", event_input)
        conversation = list((activity.get("checkpoint") or {}).get("resident_conversation", []))
        evidence = list((activity.get("checkpoint") or {}).get("resident_evidence", []))
        correlation_id = str(event_input.get("correlation_id") or activity["activity_id"])
        request_ref = str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                     f"resident:{resolved['binding_revision']}:{activity['attempt_id']}"))
        execution = {"activity_id": str(activity["activity_id"]),
                    "attempt_id": str(activity["attempt_id"]),
                    "correlation_id": correlation_id, "resident_id": resident_id,
                    "executor_module_id": resolved["module_id"],
                    "executor_module_version": resolved["module_version"],
                    "binding_revision": resolved["binding_revision"],
                    "configuration_revision": profile["config_revision"],
                    "profile": profile, "conversation": conversation, "evidence": evidence,
                    "request_ref": request_ref}
        await self.store.record_progress(activity,
            {"phase": "resident.executor.dispatched", "at": utcnow().isoformat(),
             "resident_id": resident_id, "module_id": resolved["module_id"],
             "module_version": resolved["module_version"],
             "binding_revision": resolved["binding_revision"]},
            {"resident_execution": execution})
        execution_request_id = request_ref
        bound_activity = {**activity, "input": {**event_input, "resident_id": resident_id,
                                                  "executor_module_id": resolved["module_id"],
                                                  "executor_module_version": resolved["module_version"]}}
        while True:
            envelope = ContractEnvelope(
                "r3a.resident.execution", "1.0.0", execution_request_id,
                str(activity["activity_id"]), str(activity["attempt_id"]), correlation_id,
                resident_id, profile["config_revision"], utcnow().isoformat(),
                {"operation": "execute", "continuation_ref": str(activity["activity_id"])}).to_dict()
            payload = {"contract_envelope": envelope,
                       "activity_type": activity["activity_type"],
                       "activity_id": str(activity["activity_id"]),
                       "attempt_id": str(activity["attempt_id"]), "correlation_id": correlation_id,
                       "resident_id": resident_id, "config_revision": profile["config_revision"],
                       "resident_profile": profile, "objective": event_input.get("objective", ""),
                       "activity_input": resident_input, "evidence": evidence,
                       "conversation": conversation, "available_tools": tools,
                       "request_ref": execution_request_id}
            if "resident_result" in execution:
                payload["resident_result"] = execution["resident_result"]
            response = await self._registered_module_call(
                resolved["module_id"], resolved["module_version"], "execute", payload,
                timeout=120.0, configuration_ref=resolved["configuration_path"],
                binding_revision=resolved["binding_revision"])
            result = response.get("result")
            if not isinstance(result, dict):
                raise ValueError("resident executor returned a non-object result")
            if result.get("action") == "invoke_capability":
                request = result.get("capability_request")
                if not isinstance(request, dict):
                    raise ValueError("resident executor returned an incomplete capability request")
                try:
                    capability_result = await self._invoke_resident_capability(bound_activity, request)
                    feedback_outcome, feedback_reasons = "PASS", []
                except PermissionError as exc:
                    capability_result = {"outcome": "denied", "error": str(exc), "evidence": []}
                    feedback_outcome = "REJECTED"
                    feedback_reasons = [{"code": "capability_denied", "message": str(exc),
                                         "evidence_refs": []}]
                returned = capability_result.get("evidence", [])
                feedback_evidence = [{"evidence_ref": str(item.get("source_id") or
                                                              f"capability:{request.get('capability_id')}:{index}"),
                                      "kind": "capability_result", "content": item}
                                     for index, item in enumerate(returned) if isinstance(item, dict)]
                auth = capability_result.get("authorization") or {}
                feedback = {"contract_id": "r3a.resident.result", "contract_version": "1.0.0",
                            "activity_id": str(activity["activity_id"]),
                            "attempt_id": str(activity["attempt_id"]), "correlation_id": correlation_id,
                            "resident_id": resident_id, "config_revision": profile["config_revision"],
                            "issued_at": utcnow().isoformat(),
                            "issuer": {"component_id": "cme",
                                       "decision_ref": str(auth.get("audit_event_id") or execution_request_id)},
                            "outcome": feedback_outcome, "evidence": feedback_evidence,
                            "failure_reasons": feedback_reasons, "completion_authority": False}
                conversation.extend([
                    {"role": "assistant", "content": json.dumps({"capability_request": request}, separators=(",", ":"))},
                    {"role": "user", "content": json.dumps({"resident_result": feedback,
                                                               "capability_result": capability_result},
                                                              separators=(",", ":"))}])
                evidence.extend(feedback_evidence)
                execution["resident_result"] = feedback
                execution["conversation"] = conversation
                execution["evidence"] = evidence
                execution_request_id = str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                                      f"resident-continuation:{activity['attempt_id']}:{len(conversation)}"))
                execution["request_ref"] = execution_request_id
                await self.store.record_progress(activity,
                    {"phase": "resident.capability.completed" if feedback_outcome == "PASS"
                     else "resident.capability.denied", "at": utcnow().isoformat(),
                     "resident_id": resident_id, "capability_id": request.get("capability_id")},
                    {"resident_execution": execution})
                continue
            if result.get("action") != "final" or not isinstance(result.get("decision"), dict):
                raise ValueError("resident executor returned no typed final decision")
            decision = result["decision"]
            if decision.get("status") == "blocked":
                await self.store.block_activity(activity, "resident executor returned a blocked decision",
                    {"resident_id": resident_id, "module_id": resolved["module_id"],
                     "module_version": resolved["module_version"],
                     "binding_revision": resolved["binding_revision"], "decision": decision,
                     "model": result.get("model")})
            elif decision.get("status") in {"healthy", "degraded"}:
                await self.store.finish_activity(activity,
                    {"contract_id": "r3a.resident.execution-result", "contract_version": "1.0.0",
                     "resident_id": resident_id, "module_id": resolved["module_id"],
                     "module_version": resolved["module_version"],
                     "artifact_digest": resolved["artifact_digest"],
                     "binding_revision": resolved["binding_revision"],
                     "configuration_revision": profile["config_revision"],
                     "decision": decision, "model": result.get("model"),
                     "conversation": conversation, "evidence": evidence})
            else:
                raise ValueError("resident executor decision status is invalid")
            return

    async def _run_activity(self, activity: dict[str, Any]) -> None:
        lease_task: asyncio.Task | None = None
        try:
            handler = await self._registered_handler(activity["activity_type"])
            if handler:
                lease_task = asyncio.create_task(self._lease_heartbeat(activity),
                                                 name=f"lease-heartbeat:{activity['activity_id']}")
                await self._run_registered_activity(activity, handler)
                return
            event_input = activity.get("input") or {}
            target_resident = event_input.get("resident_id")
            if target_resident is None and activity["activity_type"] == "grace.objective":
                target_resident = getattr(self, "module_id", None)
            if target_resident is not None:
                bound = await self._resolve_resident_executor(
                    {**activity, "input": {**event_input, "resident_id": target_resident}})
                if bound:
                    lease_task = asyncio.create_task(self._lease_heartbeat(activity),
                                                     name=f"lease-heartbeat:{activity['activity_id']}")
                    await self._run_bound_resident_activity(activity, bound)
                    return
            if activity["activity_type"] != "grace.objective":
                raise DispatchContractError("no registered handler or resident binding accepts this activity type")
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
                escalation_state = dict(reasoning_state.get("escalation") or {"requests": []})
                escalation_requests = list(escalation_state.get("requests") or [])

                recovered_request = next((item for item in reversed(escalation_requests)
                                          if item.get("status") == "REQUESTED"
                                          and item.get("request_attempt_id") != str(activity["attempt_id"])), None)
                if recovered_request is not None:
                    # A provider call may have completed just before process loss. Charge its full
                    # reserved completion budget and resume on the prior route; do not replay it.
                    recovered_request["status"] = "UNKNOWN"
                    recovered_request["unknown_at"] = utcnow().isoformat()
                    previous_role = next((item for item in self.settings.model_roles
                                          if item.role_id == recovered_request.get("previous_role_id")), None)
                    if previous_role is None:
                        raise RuntimeError("Cannot recover escalation because its previous configured role is missing")
                    previous_route = self.settings.model_route(previous_role.route_id)
                    model_route = {"route_id": previous_route.route_id, "provider": previous_route.provider,
                                   "model": previous_route.model, "endpoint": previous_route.endpoint,
                                   "timeout_seconds": previous_route.timeout_seconds,
                                   "max_tokens": previous_route.max_tokens}
                    context.update({"model_route": model_route, "route_id": previous_route.route_id,
                                    "selected_role_id": previous_role.role_id,
                                    "route_decision": {"action": "resume_previous_route_after_unknown_escalation",
                                                       "target_role_id": recovered_request["target_role_id"]}})
                    conversation.append({"role": "user", "content": json.dumps(
                        {"reasoning_escalation": "outcome_unknown_after_interruption",
                         "request_id": recovered_request["request_id"],
                         "target_role_id": recovered_request["target_role_id"],
                         "charged_completion_tokens": recovered_request["charged_completion_tokens"],
                         "instruction": "The prior provider result was not durably observed. It was not replayed; its full reserved budget remains charged. Continue the original objective or request a new authorized escalation only within remaining budget."},
                        separators=(",", ":"))})
                    policy = activity["input"].get("reasoning_escalation") or {}
                    readiness = await self._model_readiness_observations()
                    charged = sum(int(item.get("charged_completion_tokens", 0))
                                  for item in escalation_requests)
                    allowed_ids = set(policy.get("allowed_role_ids", []))
                    role_offers = []
                    for role in self.settings.model_roles:
                        if role.role_id not in allowed_ids or role.role_id == previous_role.role_id:
                            continue
                        decision = resolve_role(
                            self.settings.model_roles, role.role_id, set(), readiness,
                            config_revision=self.settings.source_digest, permit_fallback=False)
                        role_offers.append({"role_id": role.role_id, "route_id": role.route_id,
                                            "capabilities": list(role.capabilities),
                                            "readiness": "ready" if decision.action == "route" else "unavailable",
                                            "readiness_reason": decision.reason,
                                            "readiness_observed_at": decision.readiness_observed_at})
                    context["reasoning_escalation"] = {
                        **context.get("reasoning_escalation", {}),
                        "charged_completion_tokens": charged,
                        "available_roles": role_offers,
                    }
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
                                                "escalation": {"requests": escalation_requests},
                                                "last_rejected_evidence_fingerprint": last_rejected_fingerprint,
                                                "pending_final": context.get("pending_final")}}

                if recovered_request is not None:
                    await self.store.record_progress(
                        activity, {"phase": "resident.reasoning_escalation.recovered_unknown",
                                   "at": utcnow().isoformat(), "request_id": recovered_request["request_id"],
                                   "charged_completion_tokens": recovered_request["charged_completion_tokens"],
                                   "resumed_route_id": model_route["route_id"]}, durable_checkpoint())

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
                    try:
                        result = await self._module_call("execute", context,
                            timeout=context["model_route"]["timeout_seconds"] + 15)
                    except Exception as exc:
                        pending = next((item for item in reversed(escalation_requests)
                                        if item.get("status") == "REQUESTED"
                                        and item.get("target_role_id") == context.get("selected_role_id")), None)
                        if pending is None:
                            raise
                        # An inference transport failure can occur after the provider accepted the
                        # request. Retain the full reservation, avoid replay, and let Grace continue
                        # on the prior configured route with the same durable conversation.
                        pending.update({"status": "UNKNOWN", "unknown_at": utcnow().isoformat(),
                                        "failure_type": type(exc).__name__,
                                        "failure_ref": str(uuid.uuid4())})
                        previous_role = next((item for item in self.settings.model_roles
                                              if item.role_id == pending.get("previous_role_id")), None)
                        if previous_role is None:
                            raise RuntimeError("cannot recover failed escalation without its prior role") from exc
                        previous_route = self.settings.model_route(previous_role.route_id)
                        model_route = {"route_id": previous_route.route_id, "provider": previous_route.provider,
                                       "model": previous_route.model, "endpoint": previous_route.endpoint,
                                       "timeout_seconds": previous_route.timeout_seconds,
                                       "max_tokens": previous_route.max_tokens}
                        context.update({"model_route": model_route, "route_id": previous_route.route_id,
                                        "selected_role_id": previous_role.role_id,
                                        "route_decision": {"action": "resume_previous_route_after_provider_failure",
                                                           "target_role_id": pending["target_role_id"]}})
                        conversation.append({"role": "user", "content": json.dumps(
                            {"reasoning_escalation": "provider_failure_outcome_unknown",
                             "request_id": pending["request_id"],
                             "role_id": pending["target_role_id"],
                             "charged_completion_tokens": pending["charged_completion_tokens"],
                             "error_type": type(exc).__name__,
                             "instruction": "The provider outcome is unknown. The request was not replayed and its full reserved token budget remains charged. Continue the original objective on the prior route or return a truthful blocked result."},
                            separators=(",", ":"))})
                        await self.store.record_progress(
                            activity, {"phase": "resident.reasoning_escalation.provider_failure",
                                       "at": utcnow().isoformat(), "request_id": pending["request_id"],
                                       "failure_type": type(exc).__name__,
                                       "resumed_route_id": previous_route.route_id}, durable_checkpoint())
                        observations = None
                        continue
                    observations = result["result"]
                    turn_model = observations.get("model", {})
                    turn_record = {"turn": len(turns) + 1, "request_ref": turn_model.get("request_ref"),
                                   "route_id": turn_model.get("route_id", model_route["route_id"]),
                                   "provider": turn_model.get("provider", model_route["provider"]),
                                   "model": turn_model.get("name", model_route["model"]),
                                   "request_sha256": turn_model.get("request_sha256"),
                                   "result_ref": turn_model.get("result_ref"),
                                   "result_sha256": turn_model.get("result_sha256"),
                                   "usage": turn_model.get("usage"),
                                   "action": observations.get("action"),
                                   "observed_at": utcnow().isoformat()}
                    turns.append(turn_record)
                    pending_escalation = next((item for item in reversed(escalation_requests)
                                               if item.get("status") == "REQUESTED"
                                               and item.get("target_role_id") == context.get("selected_role_id")), None)
                    if pending_escalation is not None:
                        usage = turn_model.get("usage") or {}
                        reported = usage.get("completion_tokens", usage.get("output_tokens"))
                        charged = (reported if isinstance(reported, int) and not isinstance(reported, bool)
                                   and reported >= 0 else pending_escalation["reserved_completion_tokens"])
                        if charged > pending_escalation["reserved_completion_tokens"]:
                            await self.store.block_activity(
                                activity, "reasoning provider usage exceeded the reserved activity budget",
                                {"validation": "r3a.reasoning-escalation-policy.v1",
                                 "request_id": pending_escalation["request_id"],
                                 "reserved_completion_tokens": pending_escalation["reserved_completion_tokens"],
                                 "reported_completion_tokens": charged,
                                 "reasoning_trace": {"model_turns": turns,
                                                      "escalation_requests": escalation_requests}})
                            return
                        pending_escalation.update({"status": "SUCCEEDED", "charged_completion_tokens": charged,
                                                   "model_request_ref": turn_model.get("request_ref"),
                                                   "model_result_ref": turn_model.get("result_ref"),
                                                   "model_result_sha256": turn_model.get("result_sha256"),
                                                   "completed_at": utcnow().isoformat()})
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
                    if observations.get("action") == "escalate_reasoning":
                        request = observations.get("reasoning_escalation_request")
                        if not isinstance(request, dict):
                            raise RuntimeError("Grace returned an incomplete reasoning escalation request")
                        policy = activity["input"].get("reasoning_escalation") or {}
                        target_role = next((item for item in self.settings.model_roles
                                            if item.role_id == request.get("target_role_id")), None)
                        reason = request.get("rationale")
                        failure = None
                        if (policy.get("enabled") is not True
                                or request.get("target_role_id") not in policy.get("allowed_role_ids", [])):
                            failure = "target_role_not_allowed_by_activity_policy"
                        elif not isinstance(reason, str) or not reason.strip():
                            failure = "reasoning_escalation_rationale_missing"
                        elif (target_role is None or target_role.role_id == context.get("selected_role_id")
                              or "objective_reasoning" not in target_role.task_classes):
                            failure = "target_role_unavailable_or_not_stronger"
                        elif target_role.route_id == model_route["route_id"]:
                            failure = "target_role_does_not_change_configured_route"
                        elif len(escalation_requests) >= int(policy.get("max_requests_per_activity", 0)):
                            failure = "activity_escalation_request_budget_exhausted"
                        elif (sum(int(item.get("charged_completion_tokens", 0)) for item in escalation_requests)
                              + self.settings.model_route(target_role.route_id).max_tokens
                              > int(policy.get("max_completion_tokens_per_activity", 0))):
                            failure = "activity_escalation_token_budget_exhausted"
                        operation = None
                        if failure is None:
                            try:
                                operation = self.settings.capability_registry.resolve(
                                    policy["authorization_capability_id"])
                            except (KeyError, AttributeError):
                                failure = "reasoning_escalation_operation_unregistered"
                            if (operation is not None
                                    and (operation.descriptor["operation_id"] != policy["authorization_capability_id"]
                                         or operation.descriptor["effect_class"] != "external_write")):
                                failure = "reasoning_escalation_operation_contract_mismatch"
                        readiness = await self._model_readiness_observations() if target_role else {}
                        if failure is None:
                            decision = resolve_role(
                                self.settings.model_roles, target_role.role_id, set(), readiness,
                                config_revision=self.settings.source_digest, permit_fallback=False,
                                request_id=str(uuid.uuid4()), activity_id=str(activity["activity_id"]),
                                attempt_id=str(activity["attempt_id"]),
                                correlation_id=str(activity.get("input", {}).get("correlation_id")
                                                   or activity["activity_id"]), resident_id=self.module_id)
                            if decision.action != "route":
                                failure = "target_model_role_not_ready"
                        ordinal = len(escalation_requests) + 1
                        request_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                                    f"r3a.reasoning-escalation:{activity['activity_id']}:{ordinal}"))
                        auth_record = None
                        invocation_result = None
                        reservation = None
                        target_route = self.settings.model_route(target_role.route_id) if target_role else None
                        if failure is None:
                            reservation = {
                                "contract_id": "r3a.activity-budget-reservation.v1",
                                "contract_version": "1.0.0", "reservation_id": request_id,
                                "activity_id": str(activity["activity_id"]),
                                "resource": "completion_tokens", "units": target_route.max_tokens,
                                "limit": int(policy["max_completion_tokens_per_activity"]),
                                "policy_revision": str(policy["config_revision"]),
                            }
                            escalation_messages = [{"role": "system", "content":
                                "You provide bounded advisory reasoning to Grace, Director of Operations. "
                                "Analyze the stated uncertainty and supplied evidence. Do not claim to execute "
                                "capabilities or make institutional state changes. Identify remaining uncertainty."}]
                            escalation_messages.extend(context.get("conversation", []))
                            escalation_messages.append({"role": "user", "content": json.dumps({
                                "objective": activity["input"].get("objective"),
                                "grace_rationale": reason,
                                "evidence": evidence,
                                "instruction": "Return analysis for Grace to evaluate in the same activity."},
                                separators=(",", ":"), ensure_ascii=False)})
                            invocation = {
                                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                                "invocation_id": request_id,
                                "operation_id": operation.descriptor["operation_id"],
                                "operation_contract_version": operation.descriptor["contract_version"],
                                "caller": {"principal_id": self.module_id, "resident_id": self.module_id,
                                           "service_id": None},
                                "target": {"role_id": target_role.role_id},
                                "input": {"messages": escalation_messages},
                                "activity_id": str(activity["activity_id"]),
                                "attempt_id": str(activity["attempt_id"]),
                                "correlation_id": str(activity["input"].get("correlation_id")
                                                       or activity["activity_id"]),
                                "work_order": None, "budget_reservation": reservation,
                                "evidence_purpose": "Grace-requested reasoning escalation",
                                "idempotency_key": f"reasoning-escalation:{activity['activity_id']}:{ordinal}",
                                "deadline": (datetime.now(timezone.utc)
                                             + timedelta(seconds=target_route.timeout_seconds)).isoformat(),
                                "config_revision": self.settings.source_digest,
                            }
                            try:
                                invocation_result = await self.invoke_capability(
                                    invocation, _approved_budget_reservation=reservation,
                                    _provider_context={"model_role_id": target_role.role_id,
                                                       "model_route": {"route_id": target_route.route_id,
                                                                       "provider": target_route.provider,
                                                                       "endpoint": target_route.endpoint,
                                                                       "model": target_route.model,
                                                                       "timeout_seconds": target_route.timeout_seconds,
                                                                       "max_tokens": target_route.max_tokens}})
                                auth_record = invocation_result["authorization"]
                                if invocation_result["outcome"] != "SUCCEEDED":
                                    failure = f"reasoning_escalation_provider_{invocation_result['outcome'].lower()}"
                            except PermissionError:
                                failure = "reasoning_escalation_authorization_denied"
                            except Exception as exc:
                                failure = f"reasoning_escalation_invocation_failed:{type(exc).__name__}"
                                existing = None
                                if hasattr(self.store, "get_capability_invocation"):
                                    existing = await self.store.get_capability_invocation(
                                        invocation["idempotency_key"])
                                if existing is not None:
                                    invocation_result = existing.get("result") or {
                                        "invocation_id": request_id, "outcome": "UNKNOWN",
                                        "durable_state": existing.get("state")}
                                    if existing.get("state") == "STARTED":
                                        failure = "reasoning_escalation_outcome_unknown_no_replay"
                                    elif existing.get("state") == "SUCCEEDED":
                                        invocation_result = existing["result"]
                                        failure = None
                        if failure is not None:
                            charged = reservation["units"] if reservation and invocation_result is not None else 0
                            escalation_requests.append({"request_id": request_id,
                                                        "target_role_id": request.get("target_role_id"),
                                                        "rationale": reason, "authorization": auth_record,
                                                        "status": "REFUSED", "reason": failure,
                                                        "budget_reservation": reservation,
                                                        "charged_completion_tokens": charged,
                                                        "invocation_id": invocation_result.get("invocation_id")
                                                        if invocation_result else None,
                                                        "observed_at": utcnow().isoformat()})
                            conversation.append({"role": "user", "content": json.dumps(
                                {"reasoning_escalation": "refused", "reason": failure,
                                 "instruction": "Continue the same objective using the available route or return a justified blocked result."},
                                separators=(",", ":"))})
                            await self.store.record_progress(
                                activity, {"phase": "resident.reasoning_escalation.refused",
                                           "at": utcnow().isoformat(), "request_id": request_id,
                                           "invocation_id": invocation_result.get("invocation_id")
                                           if invocation_result else None,
                                           "reason": failure}, durable_checkpoint())
                            observations = None
                            continue
                        auth_record = invocation_result["authorization"]
                        provider_output = invocation_result["output"]
                        escalation_requests.append({"request_id": request_id,
                                                    "target_role_id": target_role.role_id,
                                                    "previous_role_id": context.get("selected_role_id"),
                                                    "previous_route_id": model_route["route_id"],
                                                    "route_id": target_route.route_id,
                                                    "provider": target_route.provider,
                                                    "model": target_route.model,
                                                    "rationale": reason,
                                                    "authorization": auth_record,
                                                    "status": "COMPLETED",
                                                    "invocation_id": invocation_result["invocation_id"],
                                                    "budget_reservation": reservation,
                                                    "reserved_completion_tokens": target_route.max_tokens,
                                                    "charged_completion_tokens": target_route.max_tokens,
                                                    "actual_usage": provider_output.get("usage", {}),
                                                    "provider_evidence": invocation_result["evidence"],
                                                    "request_attempt_id": str(activity["attempt_id"]),
                                                    "requested_at": utcnow().isoformat()})
                        conversation.append({"role": "user", "content": json.dumps(
                            {"reasoning_escalation": "completed", "request_id": request_id,
                             "invocation_id": invocation_result["invocation_id"],
                             "role_id": target_role.role_id, "route_id": target_route.route_id,
                             "rationale": reason, "analysis": provider_output["content"],
                             "evidence": invocation_result["evidence"],
                             "instruction": "Evaluate this additional analysis against the supplied evidence and continue the original objective."},
                            separators=(",", ":"), ensure_ascii=False)})
                        await self.store.record_progress(
                            activity, {"phase": "resident.reasoning_escalation.completed",
                                       "at": utcnow().isoformat(), "request_id": request_id,
                                       "invocation_id": invocation_result["invocation_id"],
                                       "target_role_id": target_role.role_id,
                                       "route_id": target_route.route_id,
                                       "authorization_audit_event_id": auth_record.get("audit_event_id"),
                                       "reserved_completion_tokens": target_route.max_tokens,
                                       "usage": provider_output.get("usage", {})},
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
                                                          "escalation_requests": escalation_requests,
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
                                          "escalation_requests": escalation_requests,
                                          "evidence": evidence}})
            elif not decision.get("evidence_refs"):
                await self.store.block_activity(activity,
                    "Grace final response did not cite any returned evidence",
                    {"validation": "r3a.resident-evidence-citation.v1", "decision": decision,
                     "model": observations.get("model"),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "escalation_requests": escalation_requests,
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
                                          "escalation_requests": escalation_requests,
                                          "evidence": evidence}})
            elif answer_issues:
                await self.store.block_activity(
                    activity, "Grace response did not satisfy the evidence-backed transition request",
                    {"validation": "r3a.transition-answer.v1", "missing_destinations": answer_issues,
                     "decision": decision, "model": observations.get("model"),
                     "reasoning_trace": {"model_turns": turns,
                                          "capability_invocations": invocations,
                                          "escalation_requests": escalation_requests,
                                          "evidence": evidence},
                     "request_ref": (observations.get("model") or {}).get("request_ref")})
            else:
                observations["reasoning_trace"] = {"model_turns": turns,
                                                    "capability_invocations": invocations,
                                                    "escalation_requests": escalation_requests,
                                                    "acceptance_rejections": acceptance_rejections,
                                                    "evidence": [{"source_id": item["source_id"],
                                                                  "source_path": item.get("source_path"),
                                                                  "sha256": item["sha256"],
                                                                  "source_sha256": item.get("source_sha256")}
                                                                 for item in evidence]}
                await self.store.finish_activity(activity, observations)
        except DispatchContractError as exc:
            await self.store.block_activity(activity, "registered dispatch contract denied activity",
                                            {"contract": "r3a.modular-dispatch.v1", "error": str(exc)})
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
