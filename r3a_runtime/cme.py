"""
R3 CONTROLLED SOURCE
File: r3a_runtime/cme.py
Component: R3A-CME-AP0
File Revision: 1.12.0
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
Changed: 2026-11-08 | R3A-AP2-VERIFICATION-FEEDBACK | Codex GPT-6 | Persist generic verifier results and ask Grace for a scoped corrective decision before blocking.
Changed: 2026-11-08 | R3A-MODULAR-RUNTIME | Codex GPT-6 | Omit CME-only durable reasoning checkpoint internals from resident protocol frames.
Changed: 2026-11-08 | R3A-MODULAR-RUNTIME | Codex GPT-6 | Keep full capability evidence once in context and compact its conversation receipt.
Changed: 2026-11-08 | R3A-MODULAR-RUNTIME | Codex GPT-6 | Compact legacy durable capability receipts when resuming activities.
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
Changed: 2026-11-07 | R3A-MODULAR-FOUNDATION-001 | Codex GPT-6 | Bind manifest-declared capability provider versions through the generic CME module lifecycle while preserving CME authorization and invocation persistence.
Supersedes: None.
Contracts: AP0-002–010; AP0-M1 D2–D8; R3A-019; MOD-001–MOD-010; STM-001–STM-007; module.lifecycle v2; r3a.resident.execution.v1; r3a.model-role.v1; r3a.authorization-decision.v1; r3a.capability-invocation.v1; r3a.model-readiness-provider.v1; r3a.model-readiness.v2.
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
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import ConfigurationError, Settings, load_settings, sanitized_config
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
from .notifications import INSTITUTION_EVENT_SOURCE, validate_notification_envelope
from .acceptance import (AcceptanceCriteriaRequired, OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                         OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION, evidence_fingerprint,
                         validate_acceptance, validate_required_criteria)
from .protocol import PROTOCOL_MAJOR, PROTOCOL_MINOR, request as module_request
from .provider_runtime import ProviderProcessManager
from .grace_module import validate_resident_profile


@dataclass
class ResidentProcessBinding:
    resident_id: str
    version: str
    socket: Path
    process: asyncio.subprocess.Process


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
    def __getattr__(self, name: str):
        # Keep lightweight test/diagnostic instances compatible with the configured
        # primary identity when they are constructed without calling __init__.
        if name == "module_id":
            return getattr(self.settings, "module_id", "resident.grace")
        raise AttributeError(name)

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
        self.resident_processes: dict[str, ResidentProcessBinding] = {}
        self.provider_runtime = ProviderProcessManager(settings, self.store, settings.capability_registry)
        self.booted_at = utcnow()

    def _primary_resident_id(self) -> str:
        return getattr(self, "module_id", getattr(self.settings, "module_id", "resident.grace"))

    def manifest(self, version: str | None = None) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
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
            "state_namespace": self.module_id,
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
        if any(source.enabled for source in getattr(self.settings, "notification_sources", ())):
            await self.store.register_capability(
                "notification.source.read", "R3A-CME", "read_only",
                metadata={"description": "Read one identified event from the configured durable institution-event source",
                          "source_id": INSTITUTION_EVENT_SOURCE})
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
        await self.provider_runtime.install_all()
        escalation_policy = self.settings.reasoning_escalation
        if escalation_policy and escalation_policy.enabled:
            escalation_operation = self.settings.capability_registry.resolve(
                escalation_policy.authorization_capability_id)
            if escalation_operation.descriptor["effect_class"] != "external_write":
                raise RuntimeError("reasoning escalation must resolve to a registered external_write operation")
        await self.store.register_capability("institution.diagnostics.read", "R3A-CME", "read_only",
                                             metadata={"description": "Read current durable process and database observations"})
        await self.store.register_capability(
            "resident.delegate", "R3A-CME", "read_only",
            metadata={"contract_id": "r3a.resident.handoff", "contract_version": "1.0.0",
                      "description": "Create one CME-authorized durable handoff to a directory-bound resident"})
        await self.store.register_capability(
            "resident.objective.execute", "R3A-CME", "read_only",
            metadata={"contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
                      "description": "Run one durable reasoning activity for the authorized target resident"})
        await self.store.register_resource("foundation.observer", self.settings.worker_concurrency,
                                           owner="R3A-CME")
        for role in self.settings.model_roles:
            configured_route = self.settings.model_route(role.route_id)
            await self.store.register_model_role(role, self.settings.source_digest,
                                                 self.module_id, configured_route.model)
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
        await self._stop_resident_modules()
        await self.provider_runtime.close()
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

    async def _reap_orphan_module(self, pid: int, module_id: str, version: str,
                                  entrypoint: str | None = None) -> None:
        """Stop only a same-user process whose argv proves it is this registered module."""
        proc = Path(f"/proc/{pid}")
        try:
            if proc.stat().st_uid != os.getuid():
                return
            argv = (proc / "cmdline").read_bytes().split(b"\0")
            expected_entrypoint = (entrypoint or ("r3a_runtime.grace_module"
                                                  if module_id == self.module_id
                                                  else "r3a_runtime.observer_module")).encode()
            expected = [b"-m", expected_entrypoint, b"--module-id", module_id.encode(),
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
        profile = payload.get("resident_profile")
        resident_id = (profile.get("resident_id") if isinstance(profile, dict)
                       else payload.get("resident_id")) or self.module_id
        version = getattr(self.settings, "module_version", self.module_version)
        socket = getattr(self.settings, "module_socket", None)
        if resident_id != self.module_id:
            if not isinstance(profile, dict):
                raise PermissionError("non-primary resident execution requires a verified profile")
            binding = await self._ensure_resident_module(profile)
            version, socket = binding.version, binding.socket
        if operation == "execute" and payload.get("activity_type") == "grace.objective":
            # CME has already extracted these durable internals into its own state. The
            # resident receives the conversation and evidence, not a duplicate copy of
            # invocation history and retry bookkeeping that can exceed the module frame.
            payload.pop("reasoning_state", None)
            payload["contract_envelope"] = ContractEnvelope(
                "r3a.resident.execution", "1.0.0", str(uuid.uuid4()),
                str(payload["activity_id"]), str(payload["attempt_id"]),
                str(payload.get("correlation_id") or payload["activity_id"]),
                resident_id, str(payload["config_revision"]), utcnow().isoformat(),
                {"operation": "execute", "continuation_ref": payload.get("continuation_ref")}).to_dict()
        return await module_request(socket, resident_id, version,
                                    operation, payload, timeout=timeout)

    async def _ensure_resident_module(self, value: dict[str, Any]) -> ResidentProcessBinding:
        profile = validate_resident_profile(value, resident_id=str(value.get("resident_id", "")),
                                            config_revision=self.settings.source_digest)
        role = self.settings.model_role_for_office(profile["office_role"])
        if self.settings.model_route(role.route_id).route_id != profile["model_route_id"]:
            raise PermissionError("directory office role profile conflicts with configured model route")
        resident_id = profile["resident_id"]
        existing = self.resident_processes.get(resident_id)
        if existing is not None and existing.process.returncode is None:
            return existing
        version = self.settings.module_version
        socket_dir = self.settings.data_dir / "modules"
        socket_dir.mkdir(parents=True, exist_ok=True)
        socket = socket_dir / f"resident-{hashlib.sha256(resident_id.encode()).hexdigest()[:24]}.sock"
        module = self.manifest(version)
        module.update({"module_id": resident_id, "owner": profile["office_role"],
                       "state_namespace": resident_id,
                       "resident_execution_profile": profile})
        await self.store.register_module(module, "INSTALLED", "unknown")
        rows = await self.store.rows(
            "SELECT lifecycle_state,diagnostic,manifest FROM r3a.module_registry "
            "WHERE module_id=%s AND module_version=%s", (resident_id, version))
        if rows and isinstance(rows[0].get("diagnostic"), dict):
            pid = rows[0]["diagnostic"].get("pid")
            if isinstance(pid, int):
                await self._reap_orphan_module(pid, resident_id, version,
                                               rows[0]["manifest"].get("entrypoint"))
        await self.store.module_state(resident_id, version, "ACTIVATING", "starting",
                                      {"resident_profile": profile})
        socket.unlink(missing_ok=True)
        command = [sys.executable, "-m", "r3a_runtime.grace_module", "--socket", str(socket),
                   "--module-id", resident_id, "--module-version", version,
                   "--config", str(self.settings.source_path)]
        process = await asyncio.create_subprocess_exec(
            *command, cwd=Path(__file__).resolve().parent.parent,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
            start_new_session=True)
        try:
            deadline = asyncio.get_running_loop().time() + 8.0
            hello = None
            while asyncio.get_running_loop().time() < deadline:
                if process.returncode is not None:
                    error = (await process.stderr.read()).decode("utf-8", "replace")[-1500:]
                    raise RuntimeError(f"Resident process exited during startup: {error}")
                try:
                    hello = await module_request(socket, resident_id, version, "hello", timeout=1.0)
                    break
                except (OSError, ConnectionError, asyncio.TimeoutError, RuntimeError):
                    await asyncio.sleep(0.1)
            if hello is None:
                raise TimeoutError("Resident did not expose its local socket before startup deadline")
            protocol = hello["result"].get("supported_protocol", {})
            if protocol.get("major") != module["protocol_major"] or not (
                    protocol.get("min_minor", 999) <= PROTOCOL_MINOR <= protocol.get("max_minor", -1)):
                raise RuntimeError("Resident handshake protocol is incompatible")
            await module_request(socket, resident_id, version, "prepare")
            await module_request(socket, resident_id, version, "activate")
            health = await module_request(socket, resident_id, version, "health")
            if health["result"].get("state") != "ACTIVE" or health["result"].get("health") != "healthy":
                raise RuntimeError("Resident process did not report healthy/active")
            await self.store.module_state(resident_id, version, "ACTIVE", "healthy",
                                          {"pid": process.pid, "protocol": protocol,
                                           "artifact_digest": module["artifact_digest"],
                                           "resident_profile": profile})
            binding = ResidentProcessBinding(resident_id, version, socket, process)
            self.resident_processes[resident_id] = binding
            return binding
        except Exception as exc:
            await self.store.module_state(resident_id, version, "FAILED", "unavailable",
                                          {"reason": f"{type(exc).__name__}: {exc}",
                                           "resident_profile": profile})
            if process.returncode is None:
                process.terminate()
                await process.wait()
            raise

    async def _stop_resident_modules(self) -> None:
        for resident_id, binding in list(self.resident_processes.items()):
            if binding.process.returncode is None:
                try:
                    await self.store.module_state(resident_id, binding.version, "STOPPING", "stopping")
                    await module_request(binding.socket, resident_id, binding.version, "stop")
                except Exception:
                    binding.process.terminate()
                try:
                    await asyncio.wait_for(binding.process.wait(),
                                           timeout=self.settings.heartbeat_stale_after_seconds)
                except asyncio.TimeoutError:
                    binding.process.kill()
                    await binding.process.wait()
            await self.store.module_state(resident_id, binding.version, "STOPPED", "stopped",
                                          {"exit_code": binding.process.returncode,
                                           "resume_on_start": True})
            self.resident_processes.pop(resident_id, None)

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

    async def _resolve_resident_execution_profile(self, resident_id: str, *,
                                                  activity_id: str,
                                                  idempotency_key: str) -> tuple[dict[str, Any], Any]:
        """Resolve a target identity from a measured directory snapshot, then bind its configured role route."""
        operation = self.settings.capability_registry.resolve("institutional.directory.discover")
        invocation_id = str(uuid.uuid5(uuid.NAMESPACE_URL,
                                       f"r3a.resident.directory-profile:{idempotency_key}"))
        attempt_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{invocation_id}:directory-read"))
        request = {
            "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
            "invocation_id": invocation_id,
            "operation_id": operation.descriptor["operation_id"],
            "operation_contract_version": operation.descriptor["contract_version"],
            "caller": {"principal_id": self.module_id,
                       "resident_id": self.module_id, "service_id": None},
            "target": {}, "input": {"resident_id": resident_id, "limit": 250},
            "activity_id": activity_id, "attempt_id": attempt_id,
            "correlation_id": activity_id, "work_order": None,
            "evidence_purpose": "Resolve an explicitly requested resident execution target",
            "idempotency_key": f"resident-directory:{invocation_id}",
            "deadline": (datetime.now(timezone.utc)
                         + timedelta(seconds=operation.descriptor["execution"]["timeout_seconds"])).isoformat(),
            "config_revision": self.settings.source_digest,
        }
        validate_json(request["input"], operation.descriptor["input_schema"], path="$.input")
        result = await self.invoke_capability(request)
        if result["outcome"] != "SUCCEEDED":
            raise RuntimeError("authoritative resident directory invocation did not succeed")
        output = result.get("output")
        if not isinstance(output, dict) or output.get("schema_id") != "r3a.institutional-directory.v1":
            raise ValueError("authoritative resident directory returned an unsupported snapshot")
        source = output.get("source")
        if (not isinstance(source, dict) or source.get("freshness") != "fresh"
                or source.get("availability") != "measured"
                or not isinstance(source.get("snapshot_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", source["snapshot_sha256"]) is None):
            raise PermissionError("authoritative resident directory snapshot is not measured and fresh")
        matches = [entry for entry in output.get("residents", [])
                   if isinstance(entry, dict) and entry.get("resident_id") == resident_id]
        if len(matches) != 1:
            raise LookupError("target resident is absent or ambiguous in the authoritative directory")
        resident = matches[0]
        role = self.settings.model_role_for_office(str(resident.get("office_role", "")))
        profile = {
            "contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
            "resident_id": resident_id, "display_name": resident.get("display_name"),
            "office_id": resident["office_id"], "office_role": resident["office_role"],
            "directory_evidence": {"source_id": source["source_id"],
                                   "snapshot_sha256": source["snapshot_sha256"],
                                   "observed_at": source["observed_at"]},
            "model_route_id": role.route_id, "config_revision": self.settings.source_digest,
        }
        profile = validate_resident_profile(profile, resident_id=resident_id,
                                            config_revision=self.settings.source_digest)
        return profile, role

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
                await self._reap_orphan_module(row[0]["diagnostic"]["pid"], module_id, version,
                                               manifest.get("entrypoint"))
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
            module_id = str(payload.get("module_id", self.module_id))
            version = str(payload.get("version", self.settings.module_version))
            return await self._activate_module(module_id, version)
        if operation == "module.stop":
            return await self._stop_module()
        if operation == "module.replace":
            return await self._replace_module(str(payload["version"]))
        if operation in {"capability.module.install", "capability.module.activate",
                         "capability.module.deactivate", "capability.module.status"}:
            operation_id = payload.get("operation_id")
            contract_version = payload.get("contract_version", "1.0.0")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError(f"{operation} requires operation_id")
            provider_version = payload.get("provider_version")
            if provider_version is not None and not isinstance(provider_version, str):
                raise ValueError("provider_version must be text")
            registered = (self.settings.capability_registry.resolve_provider(operation_id, provider_version)
                          if provider_version else self.settings.capability_registry.resolve(
                              operation_id, contract_version, include_stopped=True))
            provider = registered.descriptor["provider"]
            if operation == "capability.module.status":
                modules = await self.store.rows(
                    "SELECT lifecycle_state,health,observed_at,diagnostic FROM r3a.module_registry "
                    "WHERE module_id=%s AND module_version=%s", (provider["provider_id"], provider["provider_version"]))
                return {"operation_id": operation_id, "provider_id": provider["provider_id"],
                        "provider_version": provider["provider_version"],
                        "module": modules[0] if modules else None}
            if operation == "capability.module.install":
                manifest = self.provider_runtime._manifest(registered)
                installed = await self.store.rows(
                    "SELECT artifact_digest,lifecycle_state FROM r3a.module_registry "
                    "WHERE module_id=%s AND module_version=%s", (provider["provider_id"], provider["provider_version"]))
                if installed:
                    if installed[0]["artifact_digest"].strip() != manifest["artifact_digest"]:
                        raise RuntimeError("installed provider version is immutable; use a new provider version")
                    return {"installed": True, "already_registered": True,
                            "module_id": provider["provider_id"], "version": provider["provider_version"],
                            "lifecycle_state": installed[0]["lifecycle_state"]}
                await self.store.register_module(manifest, "INSTALLED", "unknown")
                await self.store.module_state(provider["provider_id"], provider["provider_version"],
                                              "INSTALLED", "unknown", {"source": "control.install",
                                                                        "idempotency_key": idempotency_key},
                                              machine_version=2)
                self.settings.capability_registry.set_provider_state(provider["provider_id"],
                                                                     provider["provider_version"],
                                                                     "INSTALLED", {})
                return {"installed": True, "module_id": provider["provider_id"],
                        "version": provider["provider_version"], "artifact_digest": provider["artifact_sha256"]}
            if operation == "capability.module.activate":
                result = await self.provider_runtime.activate(registered)
                self.settings.capability_registry.activate_provider(operation_id, provider["provider_version"])
                return result
            stopped = await self.provider_runtime.stop(provider["provider_id"], provider["provider_version"])
            return stopped
        if operation == "capability.module.replace":
            new_id = payload.get("operation_id")
            old_module_id, old_version = payload.get("old_module_id"), payload.get("old_version")
            new_version = payload.get("new_provider_version")
            if not all(isinstance(x, str) and x for x in (new_id, old_module_id, old_version, new_version)):
                raise ValueError("capability.module.replace requires operation_id, old_module_id, old_version, and new_provider_version")
            old_operation = self.settings.capability_registry.resolve_provider(new_id, old_version)
            new_operation = self.settings.capability_registry.resolve_provider(new_id, new_version)
            if old_operation.descriptor["provider"]["provider_id"] != old_module_id:
                raise ValueError("old_module_id does not match the registered prior provider version")
            await self.provider_runtime.activate(old_operation)
            await self.provider_runtime.begin_replacement(old_module_id, old_version)
            try:
                result = await self.provider_runtime.activate(new_operation)
            except Exception:
                await self.provider_runtime.cancel_replacement(old_module_id, old_version)
                raise
            self.settings.capability_registry.activate_provider(new_id, new_version)
            await self.provider_runtime.stop(old_module_id, old_version)
            await self.store.record_module_replacement(old_module_id, old_version, new_version,
                                                      machine_version=2)
            result.update({"replaced": True, "prior_version": old_version})
            return result
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
        if operation == "notification.ingest":
            source_id = str(payload.get("source_id", ""))
            source_event_id = str(payload.get("source_event_id", ""))
            source = next((item for item in getattr(self.settings, "notification_sources", ())
                           if item.source_id == source_id and item.enabled
                           and item.adapter == "institution_events.v1"), None)
            if source is None:
                raise PermissionError("notification source is not enabled by bootstrap configuration")
            stable_key = f"notification:{source_id}:{source_event_id}"
            if idempotency_key != stable_key:
                raise ValueError("notification intake requires a source-bound idempotency key")
            authorization = await self._authorize_capability(
                "notification.source.read", request_id=idempotency_key,
                context={"source_id": source_id, "source_event_id": source_event_id},
                resident_id=self.module_id)
            try:
                result = await self.store.ingest_institution_event_notification(
                    source_id, source_event_id, idempotency_key)
            except Exception as exc:
                try:
                    await self.store.record_notification_intake_failure(
                        source_id, source_event_id, idempotency_key, exc)
                except Exception:
                    # If the database is unavailable, the control response remains the truthful failure.
                    pass
                raise
            result["source_authorization"] = authorization
            return result
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
            if self.module_id != "resident.grace":
                raise RuntimeError("The configured module is not the AP1 Grace resident")
            modalities = tuple(payload.get("required_modalities", ()))
            task_class = payload.get("task_class")
            if task_class is None:
                task_class = "vision" if "image" in modalities else "objective_reasoning"
            if task_class not in {"objective_reasoning", "vision"}:
                raise ValueError("Grace objective intake cannot use autonomic-only model roles")
            requested_role_id = payload.get("role_id")
            requested_route = payload.get("route_id")
            target_resident_id = payload.get("target_resident_id")
            resident_profile = None
            requested_activity_id = payload.get("requested_activity_id", payload.get("activity_id"))
            if target_resident_id is not None:
                if (not isinstance(target_resident_id, str) or not target_resident_id.strip()
                        or target_resident_id == self.module_id):
                    raise ValueError("target_resident_id must be a distinct canonical resident identity")
                activity_id = str(requested_activity_id or uuid.uuid5(
                    uuid.NAMESPACE_URL, f"r3a.resident.objective:{idempotency_key}"))
                delegation_auth = await self._authorize_capability(
                    "resident.delegate", activity_id=activity_id,
                    request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"resident.delegate:{idempotency_key}")),
                    context={"target_resident_id": target_resident_id,
                             "intake": "grace.objective.submit"},
                    resident_id=self.module_id)
                resident_profile, selected_role = await self._resolve_resident_execution_profile(
                    target_resident_id, activity_id=activity_id,
                    idempotency_key=idempotency_key)
                target_auth = await self._authorize_capability(
                    "resident.objective.execute", activity_id=activity_id,
                    request_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                                              f"resident.execute:{idempotency_key}")),
                    context={"resident_profile": resident_profile,
                             "delegation_audit_event_id": delegation_auth["audit_event_id"]},
                    resident_id=target_resident_id)
                if target_auth.get("allowed") is False:
                    raise PermissionError("target resident is not authorized for objective execution")
                if requested_role_id is not None and requested_role_id != selected_role.role_id:
                    raise PermissionError("requested model role conflicts with directory office route")
                if requested_route is not None and requested_route != selected_role.route_id:
                    raise PermissionError("requested model route conflicts with directory office route")
                if payload.get("engineering_assignment") is not None:
                    raise PermissionError("resident objective routing does not bypass CME Engineering work-order handlers")
            else:
                activity_id = requested_activity_id
            roles = self.settings.model_roles
            if target_resident_id is not None:
                pass
            elif requested_role_id is not None:
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
                activity_id, task_class, resident_id=target_resident_id or self.module_id,
                resident_profile=resident_profile)
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
            if any(source.enabled for source in new_settings.notification_sources):
                await self.store.register_capability(
                    "notification.source.read", "R3A-CME", "read_only",
                    metadata={"description": "Read one identified event from the configured durable institution-event source",
                              "source_id": INSTITUTION_EVENT_SOURCE})
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
        resident_id = event_input.get("resident_id") or self.module_id
        resident_profile = event_input.get("resident_profile")
        if resident_id == self.module_id:
            if resident_profile is not None:
                raise ValueError("primary resident activity cannot carry a delegated profile")
        else:
            resident_profile = validate_resident_profile(
                resident_profile, resident_id=resident_id,
                config_revision=self.settings.source_digest)
            configured_role = self.settings.model_role_for_office(resident_profile["office_role"])
            if (configured_role.role_id != event_input.get("role_id")
                    or configured_role.route_id != resident_profile["model_route_id"]):
                raise PermissionError("durable resident profile does not match configured route binding")
        engineering_assignment = event_input.get("engineering_assignment")
        acceptance_contract = event_input.get("acceptance_contract") or {
            "contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
            "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION, "criteria": []}
        if (acceptance_contract.get("contract_id") != OBJECTIVE_ACCEPTANCE_CONTRACT_ID
                or acceptance_contract.get("contract_version") != OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION):
            raise ValueError("objective acceptance contract identity or version is unsupported")
        notification = event_input.get("notification")
        if notification is not None:
            notification = validate_notification_envelope(notification)
        acceptance_criteria = (validate_required_criteria(acceptance_contract.get("criteria"))
                               if engineering_assignment is None and notification is None else [])
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
                              resident_id=resident_id, evaluated_at=utcnow().isoformat()), 0)
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
                                  resident_id=resident_id,
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
                                  resident_id=resident_id, evaluated_at=utcnow().isoformat()), 0)
            decision = resolve_role(
                roles, decision_role_id, set(event_input.get("required_capabilities", [])),
                observations, config_revision=self.settings.source_digest,
                permit_fallback=not bool(saved.get("selected_role_id")),
                request_id=str(uuid.uuid4()), activity_id=str(activity["activity_id"]),
                attempt_id=str(activity["attempt_id"]),
                correlation_id=str(activity["activity_id"]), resident_id=resident_id,
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
        if resident_id != self.module_id:
            authorized_tools = []
            for tool in available_tools:
                try:
                    await self.store.require_capability(resident_id, tool["capability_id"])
                except PermissionError:
                    continue
                authorized_tools.append(tool)
            available_tools = authorized_tools
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
        available_residents = []
        # Residents are offered to Grace only when the configured directory adapter
        # returned a measured snapshot during this activity and the target has an
        # explicit execution route and effective CME execution grant.
        for invocation in reasoning_state.get("capability_invocations", []):
            request = invocation.get("capability_request", {})
            result = invocation.get("result", {})
            if request.get("capability_id") != "institutional.directory.discover":
                continue
            output = result.get("output", {})
            source = output.get("source", {}) if isinstance(output, dict) else {}
            if (not isinstance(source, dict) or source.get("availability") != "measured"
                    or source.get("freshness") != "fresh"):
                continue
            for directory_resident in output.get("residents", []):
                target_id = directory_resident.get("resident_id")
                office_role = directory_resident.get("office_role")
                if not isinstance(target_id, str) or target_id == resident_id:
                    continue
                try:
                    role_binding = self.settings.model_role_for_office(str(office_role))
                    await self.store.require_capability(target_id, "resident.objective.execute")
                except (KeyError, PermissionError, ConfigurationError):
                    continue
                available_residents.append({
                    "resident_id": target_id,
                    "office_id": directory_resident.get("office_id"),
                    "office_role": office_role,
                    "model_role_id": role_binding.role_id,
                    "model_route_id": role_binding.route_id,
                    "directory_evidence": {
                        "source_id": source.get("source_id"),
                        "snapshot_sha256": source.get("snapshot_sha256"),
                        "observed_at": source.get("observed_at"),
                    },
                })
        # De-duplicate by canonical principal in case the directory adapter produced
        # repeated source rows. Ambiguous identities are never offered to the model.
        resident_counts: dict[str, int] = {}
        for entry in available_residents:
            resident_counts[entry["resident_id"]] = resident_counts.get(entry["resident_id"], 0) + 1
        available_residents = [entry for entry in available_residents
                               if resident_counts[entry["resident_id"]] == 1]
        required_evidence_refs = list(saved.get("required_evidence_refs", []))
        if notification is not None:
            notification_source = f"notification:{notification['source_id']}:{notification['source_event_id']}"
            source_content = json.dumps(notification, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=False)
            if not any(item.get("source_id") == notification_source for item in evidence):
                evidence.append({"source_id": notification_source,
                                 "source_path": notification["payload_ref"],
                                 "content": source_content,
                                 "sha256": hashlib.sha256(source_content.encode("utf-8")).hexdigest(),
                                 "source": notification["provenance"]["store"]})
            required_evidence_refs = sorted(set(required_evidence_refs + [notification_source]))
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
                "resident_id": resident_id, "resident_profile": resident_profile,
                "objective": event_input["objective"], "event_kind": event_input.get("event_kind", "objective"),
                "task_class": task_class,
                "notification": notification,
                "acceptance_contract": {"contract_id": OBJECTIVE_ACCEPTANCE_CONTRACT_ID,
                                        "contract_version": OBJECTIVE_ACCEPTANCE_CONTRACT_VERSION,
                                        "criteria": acceptance_criteria},
                "acceptance_criteria": acceptance_criteria,
                "route_id": route.route_id,
                "model_route": effective_route,
                "evidence_format": "r3a.knowledge-evidence.v1",
                "required_evidence_refs": required_evidence_refs,
                "selected_role_id": selected_role_id,
                "route_decision": decision.__dict__ if selected_role_id else None,
                "evidence": evidence,
                "dependency_context": await self.store.activity_dependency_context(event_input.get("dependencies")),
                "available_tools": available_tools,
                "available_residents": available_residents,
                "engineering_assignment": engineering_assignment,
                "available_engineering_operations": available_engineering_operations,
                "reasoning_escalation": escalation_offer,
                "conversation": reasoning_state.get("conversation", []),
                "reasoning_state": reasoning_state,
                "pending_final": reasoning_state.get("pending_final"),
                "request_ref": str(uuid.uuid4()), "config_revision": self.settings.source_digest}

    async def _invoke_resident_capability(self, activity: dict[str, Any],
                                          request: dict[str, Any]) -> dict[str, Any]:
        resident_id = activity.get("input", {}).get("resident_id") or self.module_id
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
        registry = getattr(self.settings, "capability_registry", None)
        try:
            registered_operation = registry.resolve(capability_id) if registry is not None else None
        except KeyError:
            registered_operation = None
        if capability_id == "institution.knowledge.read" and registered_operation is None:
            if set(arguments) != {"query"}:
                raise ValueError("institution.knowledge.read requires exactly one query argument")
            query = arguments["query"]
            if not isinstance(query, str) or not query.strip():
                raise ValueError("institution.knowledge.read query must be nonempty text")
        if capability_id != "institution.knowledge.read" and registered_operation is None and arguments:
            raise ValueError(f"{capability_id} accepts no arguments")
        if registered_operation is not None:
            if registered_operation.descriptor["effect_class"] != "read":
                raise PermissionError("effectful operation requires the canonical AP2 invocation dispatcher")
            from .capability_contracts import validate_json
            validate_json(arguments, registered_operation.descriptor["input_schema"], path="$.input")
        authorization = None
        if registered_operation is None:
            authorization = await self._authorize_capability(
                capability_id, activity_id=str(activity["activity_id"]),
                attempt_id=str(activity["attempt_id"]),
                resident_id=resident_id,
                context={"invocation_source": "resident_selected_action",
                         "tool_contract_id": tool["contract_id"], "effect_class": "read",
                         "query_sha256": hashlib.sha256(arguments.get("query", "").encode()).hexdigest()
                         if capability_id == "institution.knowledge.read" else None})
        evidence = []
        capability_output: Any = None
        if capability_id == "institution.knowledge.read" and registered_operation is None:
            for index, path in enumerate(self.settings.knowledge_sources):
                evidence.extend(retrieve(path, f"knowledge.{index+1}", query))
            capability_output = evidence
        elif registered_operation is not None:
            descriptor = registered_operation.descriptor
            invocation_id = str(uuid.uuid4())
            invocation = {
                "contract_id": "r3a.capability-invocation.v1", "contract_version": "1.0.0",
                "invocation_id": invocation_id,
                "operation_id": descriptor["operation_id"],
                "operation_contract_version": descriptor["contract_version"],
                "caller": {"principal_id": resident_id, "resident_id": resident_id,
                           "service_id": None},
                "target": {}, "input": arguments,
                "activity_id": str(activity["activity_id"]),
                "attempt_id": str(activity["attempt_id"]),
                "correlation_id": str(activity.get("input", {}).get("correlation_id")
                                       or activity.get("correlation_id") or activity["activity_id"]),
                "work_order": None, "evidence_purpose": request.get("rationale"),
                "idempotency_key": f"resident-capability:{invocation_id}",
                "deadline": (datetime.now(timezone.utc)
                             + timedelta(seconds=descriptor["execution"]["timeout_seconds"])).isoformat(),
                "config_revision": self.settings.source_digest,
            }
            canonical_result = await self.invoke_capability(invocation)
            if canonical_result["outcome"] != "SUCCEEDED":
                raise RuntimeError("CME capability invocation did not succeed")
            capability_output = canonical_result["output"]
            evidence.extend(canonical_result["evidence"])
            authorization = canonical_result["authorization"]
            invocation_summary = {key: canonical_result[key] for key in
                                  ("invocation_id", "operation_id", "operation_contract_version",
                                   "provider", "outcome", "started_at", "finished_at")}
        else:
            evidence.extend(await self._read_runtime_capability(capability_id))
            capability_output = evidence
        result = {"contract_id": tool["contract_id"],
                "contract_version": tool["contract_version"],
                "capability_id": capability_id, "outcome": "succeeded",
                "arguments": arguments, "output": capability_output, "evidence": evidence,
                "authorization": authorization, "observed_at": utcnow().isoformat()}
        if registered_operation is not None:
            result["invocation"] = invocation_summary
        return result

    async def _await_resident_handoff(self, activity: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
        """Wait on a durable child activity; the child's deterministic ID makes recovery idempotent."""
        child_id = handoff["child_activity_id"]
        while True:
            rows = await self.store.rows(
                "SELECT state,result,exception FROM r3a.activities WHERE activity_id=%s",
                (uuid.UUID(child_id),))
            if not rows:
                raise RuntimeError("durable resident handoff activity disappeared")
            row = rows[0]
            if row["state"] in {"COMPLETED", "BLOCKED", "FAILED", "CANCELLED"}:
                return {"activity_id": child_id, "resident_id": handoff["target_resident_id"],
                        "state": row["state"], "result": row.get("result"),
                        "exception": row.get("exception"),
                        "directory_snapshot_sha256": handoff["directory_snapshot_sha256"]}
            await asyncio.sleep(max(0.25, min(1.0, self.settings.scheduler_interval_seconds)))

    async def _create_resident_handoff(self, activity: dict[str, Any], request: dict[str, Any],
                                       turn: int) -> dict[str, Any]:
        """Authorize, resolve and enqueue one resident handoff through canonical CME intake."""
        target_id = request.get("target_resident_id")
        objective = request.get("objective")
        rationale = request.get("rationale")
        criteria = request.get("acceptance_criteria")
        if (not isinstance(target_id, str) or not isinstance(objective, str)
                or not isinstance(rationale, str) or not isinstance(criteria, list)):
            raise ValueError("resident delegation request is incomplete")
        parent_id = str(activity["activity_id"])
        idempotency = f"resident-handoff:{parent_id}:{turn}"
        child_id = str(uuid.uuid5(uuid.NAMESPACE_URL, idempotency))
        profile, role = await self._resolve_resident_execution_profile(
            target_id, activity_id=parent_id, idempotency_key=idempotency)
        delegation_auth = await self._authorize_capability(
            "resident.delegate", activity_id=parent_id,
            request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{idempotency}:authorize")),
            context={"target_resident_id": target_id, "child_activity_id": child_id,
                     "rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest()},
            resident_id=activity.get("input", {}).get("resident_id", self.module_id))
        execution_auth = await self._authorize_capability(
            "resident.objective.execute", activity_id=child_id,
            request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{idempotency}:target-authorize")),
            context={"resident_profile": profile,
                     "delegation_audit_event_id": delegation_auth["audit_event_id"]},
            resident_id=target_id)
        if execution_auth.get("allowed") is False:
            raise PermissionError("target resident is not authorized for delegated execution")
        child = await self.store.submit_grace_objective(
            objective, idempotency, role_id=role.role_id, requested_activity_id=child_id,
            resident_id=target_id, resident_profile=profile, acceptance_criteria=criteria)
        return {"child_activity_id": str(child["activity_id"]),
                "target_resident_id": target_id,
                "directory_snapshot_sha256": profile["directory_evidence"]["snapshot_sha256"],
                "office_id": profile["office_id"], "office_role": profile["office_role"],
                "model_role_id": role.role_id, "model_route_id": role.route_id,
                "directory_authorization_audit_event_id": delegation_auth.get("audit_event_id"),
                "execution_authorization_audit_event_id": execution_auth.get("audit_event_id"),
                "rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest()}

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
        try:
            provider_context = {
                "invocation_id": checked["invocation_id"], "idempotency_key": persistence_key,
                "activity_id": checked["activity_id"], "attempt_id": checked["attempt_id"],
                "correlation_id": checked["correlation_id"], "target": checked["target"],
                "work_order": order, "effect_class": descriptor["effect_class"],
                "config_revision": self.settings.source_digest,
                **(_provider_context or {}),
                "capability_catalog": list(self.settings.capability_registry.discover())}
            runtime = getattr(self, "provider_runtime", None)
            if runtime is None:  # Narrow compatibility for isolated CME contract fixtures.
                provider = operation.load_provider()
                output = await asyncio.to_thread(provider.invoke, checked["input"], context=provider_context)
            else:
                output = await runtime.invoke(operation, checked["input"], context=provider_context)
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
        discoveries = registry.discover()
        overridden = {item["descriptor"]["operation_id"] for item in discoveries
                      if item["descriptor"]["effect_class"] == "read"}
        tools = [tool for tool in tools if tool["capability_id"] not in overridden]
        for discovery in discoveries:
            operation = registry.resolve(
                discovery["descriptor"]["operation_id"], discovery["descriptor"]["contract_version"])
            if operation.descriptor["effect_class"] == "read":
                tools.append(operation.resident_tool_projection())
        return tuple(tools)

    @staticmethod
    def _resident_capability_summary(result: dict[str, Any]) -> dict[str, Any]:
        """Give Grace a durable invocation receipt without duplicating evidence content."""
        invocation = result.get("invocation") or {}
        return {"capability_result": {
            "capability_id": result.get("capability_id"),
            "outcome": result.get("outcome"),
            "invocation": {key: invocation[key] for key in
                           ("invocation_id", "operation_id", "provider", "outcome")
                           if key in invocation},
            "evidence": [{"source_id": item.get("source_id"), "sha256": item.get("sha256")}
                         for item in result.get("evidence", []) if isinstance(item, dict)],
        }}

    @classmethod
    def _compact_resident_conversation(cls, conversation: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize older checkpoints that embedded full provider evidence in the transcript."""
        compacted = []
        for message in conversation:
            item = dict(message)
            if item.get("role") == "user" and isinstance(item.get("content"), str):
                try:
                    value = json.loads(item["content"])
                except (TypeError, json.JSONDecodeError):
                    value = None
                if isinstance(value, dict) and isinstance(value.get("capability_result"), dict):
                    item["content"] = json.dumps(
                        cls._resident_capability_summary(value["capability_result"]),
                        separators=(",", ":"))
            compacted.append(item)
        return compacted

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

    def _resident_result_from_verification(self, activity: dict[str, Any],
                                           verification: VerificationResult) -> dict[str, Any]:
        verification_value = verification.to_dict()
        evidence_ref = f"verification:{verification.verification_id}"
        failure_reasons = [
            {"code": "criterion_failed" if result.status == "FAIL" else "criterion_inconclusive",
             "message": result.rationale,
             "evidence_refs": list(result.evidence_refs) or [evidence_ref]}
            for result in verification.results if result.status != "PASS"
        ]
        if verification.outcome != "PASS" and not failure_reasons:
            failure_reasons = [{"code": "verification_non_pass",
                                "message": "Independent verification did not pass.",
                                "evidence_refs": [evidence_ref]}]
        return {
            "contract_id": "r3a.resident.result", "contract_version": "1.0.0",
            "activity_id": str(activity["activity_id"]),
            "attempt_id": str(activity["attempt_id"]),
            "correlation_id": str(activity["input"]["correlation_id"]),
            "resident_id": self.module_id,
            "config_revision": self.settings.source_digest,
            "issued_at": verification.verified_at,
            "issuer": {"component_id": "independent-verifier", "decision_ref": evidence_ref},
            "outcome": verification.outcome,
            "evidence": [{"evidence_ref": evidence_ref,
                          "kind": "independent_verification", "content": verification_value}],
            "failure_reasons": failure_reasons,
            "completion_authority": False,
        }

    async def _resident_verification_decision(self, activity: dict[str, Any],
                                              context: dict[str, Any],
                                              resident_result: dict[str, Any],
                                              conversation: list[dict[str, Any]]) -> dict[str, Any]:
        """Ask Grace to choose a scoped correction or blocked disposition from durable feedback."""
        decision_context = dict(context)
        decision_context["resident_result"] = resident_result
        decision_context["available_tools"] = []
        decision_context["reasoning_escalation"] = {"enabled": False, "available_roles": []}
        decision_context["conversation"] = list(conversation) + [{
            "role": "user",
            "content": json.dumps({"instruction": (
                "This is the post-verification continuation decision for the same Engineering activity. "
                "Inspect the supplied resident_result and its failure evidence. If one currently listed "
                "Engineering operation can correct the failed criteria within this assignment, propose "
                "one bounded correction. Otherwise return an engineering_assess decision with status "
                "blocked. Do not assert completion or verification; CME and the independent verifier "
                "retain those authorities."), "resident_result": resident_result}, separators=(",", ":")),
        }]
        decision_context["request_ref"] = str(uuid.uuid4())
        return (await self._module_call("execute", decision_context,
                                        timeout=context["model_route"]["timeout_seconds"] + 15))["result"]

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
            proposal_revision = int(state.get("proposal_revision", 1))
            proposal = EngineeringProposal(
                proposal_id=str(uuid.uuid5(uuid.UUID(str(activity["activity_id"])),
                                           f"grace-engineering-proposal-v{proposal_revision}")),
                proposal_revision=proposal_revision, activity_id=str(activity["activity_id"]),
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
            resident_result = self._resident_result_from_verification(activity, verification)
            await checkpoint("engineering.verification_feedback.requested",
                             resident_result=resident_result)
            correction_count = int(state.get("verification_correction_count", 0))
            if correction_count >= 1:
                correction_response = {
                    "action": "engineering_assess",
                    "engineering_assessment": {
                        "status": "blocked",
                        "assessment": "The single bounded correction did not pass independent verification.",
                        "evidence_refs": [resident_result["issuer"]["decision_ref"]]},
                    "model": {},
                    "model_content": "",
                }
            else:
                correction_response = await self._resident_verification_decision(
                    activity, context, resident_result, conversation)
            correction_model = correction_response.get("model") or {}
            model_turns.append({"action": correction_response.get("action"),
                                "request_ref": correction_model.get("request_ref"),
                                "result_ref": correction_model.get("result_ref"),
                                "request_sha256": correction_model.get("request_sha256"),
                                "result_sha256": correction_model.get("result_sha256"),
                                "usage": correction_model.get("usage"),
                                "content": correction_response.get("model_content"),
                                "observed_at": utcnow().isoformat(),
                                "resident_result_ref": resident_result["issuer"]["decision_ref"]})
            correction_conversation = conversation + [
                {"role": "user", "content": json.dumps({"resident_result": resident_result,
                                                          "instruction": "Choose one scoped correction or block."},
                                                         separators=(",", ":"))},
                {"role": "assistant", "content": correction_response.get("model_content", "")},
            ]
            if correction_response.get("action") == "propose_engineering":
                correction_proposal = correction_response.get("engineering_proposal")
                if not isinstance(correction_proposal, dict):
                    raise ValueError("Grace corrective action omitted its Engineering proposal")
                descriptor = next((entry for entry in context["available_engineering_operations"]
                                   if entry.get("operation_id") == correction_proposal.get("operation_id")
                                   and entry.get("contract_version") == correction_proposal.get("contract_version")), None)
                if descriptor is None or descriptor.get("effect_class") != "isolated_write":
                    raise PermissionError("Grace corrective proposal is not a currently offered isolated_write operation")
                operation = self.settings.capability_registry.resolve(
                    descriptor["operation_id"], descriptor["contract_version"])
                validate_json(correction_proposal["target"], descriptor["target_scope_schema"], path="$.target")
                validate_json(correction_proposal["inputs"], descriptor["input_schema"], path="$.input")
                if correction_proposal["target"].get("workspace_id") != assignment["workspace_id"]:
                    raise PermissionError("Grace corrective target is outside the institution-assigned workspace")
                correction_path = correction_proposal["inputs"].get("path")
                if not isinstance(correction_path, str) or not any(
                        correction_path == allowed or (allowed.endswith("**")
                                                       and correction_path.startswith(allowed[:-2]))
                        for allowed in assignment["allowed_paths"]):
                    raise PermissionError("Grace corrective output is outside the institution-assigned allowlist")
                proposal_revision = max(int(state.get("proposal_revision", 1)),
                                        int((state.get("proposal") or {}).get("proposal_revision", 1))) + 1
                state.update({"proposal": correction_proposal, "proposal_revision": proposal_revision,
                              "proposal_rationale": correction_response.get("rationale"),
                              "proposal_model": correction_model,
                              "verification_correction_count": int(state.get("verification_correction_count", 0)) + 1,
                              "resident_result": resident_result, "model_turns": model_turns,
                              "conversation": correction_conversation})
                for prior_key in ("grace_assessment", "execution_evidence", "verification_preview",
                                  "verification_outcome", "invocation", "invocation_id"):
                    state.pop(prior_key, None)
                await checkpoint("engineering.corrective_proposal.selected",
                                 resident_result=resident_result,
                                 corrective_proposal=correction_proposal,
                                 proposal_revision=proposal_revision,
                                 model_turns=model_turns, conversation=correction_conversation,
                                 correction_model=correction_model)
                await self.store.transition_engineering_work_order(
                    order_id, "BLOCKED", work_order.activity_id, str(activity["attempt_id"]),
                    work_order.correlation_id, "Independent verification did not PASS; Grace proposed a new revision",
                    {"verification_result": verification.to_dict(),
                     "resident_result": resident_result,
                     "corrective_proposal_revision": proposal_revision})
                await self.store.fail_activity(
                    activity, "Grace selected a scoped corrective proposal after failed verification", 0)
                return
            decision = correction_response.get("engineering_assessment")
            if not isinstance(decision, dict) or decision.get("status") != "blocked":
                decision = {"status": "blocked",
                            "assessment": "Grace did not return a bounded corrective proposal; completion remains blocked.",
                            "evidence_refs": [resident_result["issuer"]["decision_ref"]]}
            await checkpoint("engineering.verification_feedback.decided",
                             resident_result=resident_result,
                             verification_feedback_decision=decision,
                             model_turns=model_turns, conversation=correction_conversation,
                             correction_model=correction_model)
            await self.store.transition_engineering_work_order(
                order_id, "BLOCKED", work_order.activity_id, str(activity["attempt_id"]),
                work_order.correlation_id, "Independent verification did not PASS",
                {"verification_result": verification.to_dict(),
                 "resident_result": resident_result,
                 "verification_feedback_decision": decision})
            await self.store.block_activity(activity, "Independent Engineering verification did not pass",
                                            {"work_order_id": order_id,
                                             "verification": verification.to_dict(),
                                             "resident_result": resident_result,
                                             "verification_feedback_decision": decision,
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
        resident_id = activity.get("input", {}).get("resident_id") or self.module_id
        try:
            if (resident_id == self.module_id
                    and (self.module_process is None or self.module_process.returncode is not None)):
                raise RuntimeError("registered module process is not running")
            context = (await self._objective_context(activity) if activity["activity_type"] == "grace.objective"
                       else await self._observer_context(activity))
            if activity["activity_type"] == "grace.objective":
                if resident_id != self.module_id:
                    execution_authorization = await self._authorize_capability(
                        "resident.objective.execute", activity_id=str(activity["activity_id"]),
                        attempt_id=str(activity["attempt_id"]),
                        request_id=str(uuid.uuid5(uuid.NAMESPACE_URL,
                                                  f"resident.execute:{activity['activity_id']}:{activity['attempt_id']}")),
                        context={"resident_profile": context["resident_profile"]},
                        resident_id=resident_id)
                    context["resident_execution_authorization"] = execution_authorization
                    await self.store.record_progress(
                        activity, {"phase": "resident.execution.authorized", "at": utcnow().isoformat(),
                                   "resident_id": resident_id,
                                   "authorization_audit_event_id": execution_authorization["audit_event_id"],
                                   "directory_snapshot_sha256": context["resident_profile"][
                                       "directory_evidence"]["snapshot_sha256"]})
                if context.get("engineering_assignment") is not None:
                    if resident_id != self.module_id:
                        raise PermissionError("Engineering work-order execution is not yet a delegated resident handler")
                    lease_task = asyncio.create_task(self._lease_heartbeat(activity),
                                                     name=f"lease-heartbeat:{activity['activity_id']}")
                    await self._run_engineering_activity(activity, context)
                    return
                model_route = context["model_route"]
                reasoning_state = dict(context.get("reasoning_state") or {})
                conversation = self._compact_resident_conversation(
                    list(context.get("conversation") or []))
                turns = list(reasoning_state.get("model_turns") or [])
                invocations = list(reasoning_state.get("capability_invocations") or [])
                evidence = list(context.get("evidence") or [])
                required_evidence_refs = list(context.get("required_evidence_refs") or [])
                acceptance_rejections = list(reasoning_state.get("acceptance_rejections") or [])
                last_rejected_fingerprint = reasoning_state.get("last_rejected_evidence_fingerprint")
                pending_handoff = reasoning_state.get("pending_handoff")
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
                                                "pending_handoff": pending_handoff,
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
                if pending_handoff is not None:
                    handoff_result = await self._await_resident_handoff(activity, pending_handoff)
                    conversation.append({"role": "user", "content": json.dumps(
                        {"resident_handoff_response": handoff_result,
                         "instruction": "Evaluate this resident's independently produced result and decide the next action for the original objective."},
                        separators=(",", ":"), ensure_ascii=False)})
                    pending_handoff = None
                    await self.store.record_progress(
                        activity, {"phase": "resident.handoff.response", "at": utcnow().isoformat(),
                                   "child_activity_id": handoff_result["activity_id"],
                                   "child_state": handoff_result["state"],
                                   "target_resident_id": handoff_result["resident_id"]},
                        durable_checkpoint())
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
                        if context.get("notification") is not None:
                            await self.store.acknowledge_notification(activity)
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
                            self._resident_capability_summary(capability_result),
                            separators=(",", ":"))})
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
                    if observations.get("action") == "delegate_to_resident":
                        handoff_request = observations.get("delegation_request")
                        if not isinstance(handoff_request, dict):
                            raise RuntimeError("Grace returned an incomplete resident handoff request")
                        handoff_turn = len(turns)
                        pending_handoff = await self._create_resident_handoff(
                            activity, handoff_request, handoff_turn)
                        pending_handoff["status"] = "SCHEDULED"
                        await self.store.record_progress(
                            activity, {"phase": "resident.handoff.scheduled", "at": utcnow().isoformat(),
                                       "child_activity_id": pending_handoff["child_activity_id"],
                                       "target_resident_id": pending_handoff["target_resident_id"],
                                       "model_role_id": pending_handoff["model_role_id"],
                                       "model_route_id": pending_handoff["model_route_id"],
                                       "authorization_audit_event_ids": [
                                           pending_handoff.get("directory_authorization_audit_event_id"),
                                           pending_handoff.get("execution_authorization_audit_event_id")]},
                            durable_checkpoint())
                        handoff_result = await self._await_resident_handoff(activity, pending_handoff)
                        conversation.append({"role": "user", "content": json.dumps(
                            {"resident_handoff_response": handoff_result,
                             "instruction": "Evaluate this resident's independently produced result and decide the next action for the original objective."},
                            separators=(",", ":"), ensure_ascii=False)})
                        pending_handoff = None
                        await self.store.record_progress(
                            activity, {"phase": "resident.handoff.response", "at": utcnow().isoformat(),
                                       "child_activity_id": handoff_result["activity_id"],
                                       "child_state": handoff_result["state"],
                                       "target_resident_id": handoff_result["resident_id"]},
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
        if context.get("notification") is not None:
            if not isinstance(decision.get("assessment"), str) or not decision["assessment"].strip():
                return [{"code": "notification_disposition_missing",
                         "message": "Provide an evidence-grounded notification disposition."}]
            return []
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
