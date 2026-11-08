"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_modular_autonomy.py
Component: R3A-AP1-MODULAR-AUTONOMY-REGRESSION
File Revision: 1.4.1
Created: 2026-11-06T23:19:46Z
Created By: Codex GPT-6
Purpose: Permanently verify versioned autonomy contracts, external model roles, readiness routing, deferral, and authorization-provider compatibility.
Execution Model: Python unittest with temporary configuration and in-memory provider fakes; no model inference or database connection.
Observability: Deterministic assertions for config digests, contract outcomes, route decisions, and audited grant behavior.
Dependencies: Python 3.12 standard library; r3a_runtime configuration/contracts/authorization modules.
Authority: R3A AP0/AP1 Modular Autonomy Implementation Slices 1–2; isolated development branch only.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add focused permanent regression coverage for the first modular autonomy slice.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Cover legacy configuration, durable deferral semantics, and stale readiness diagnostics.
Changed: 2026-11-08T15:02:05Z | R3A-CONTEXT-RECOVERY | Codex GPT-6 | Validate externally configured model context windows and rejection of invalid bounds.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Extend Slice 1 regressions for provider configuration, identity, stale state and recovery routing.
Changed: 2026-11-07T05:45:10Z | AP2-IMPLEMENTATION | Codex GPT-6 | Give the model deferral compatibility fixture valid required acceptance criteria.
Changed: 2026-11-07T05:59:32Z | AP2-IMPLEMENTATION | Codex GPT-6 | Assert authorization decision identity remains distinct from its audit event.
Changed: 2026-11-07T15:16:00Z | R3A-AP1-AP2-AUTONOMY | Codex GPT-6 | Verify versioned activity dependency identity and validation.
Changed: 2026-11-07 | R3A-AP2-ESCALATED-REASONING | Codex GPT-6 | Verify external escalation policy version, registered routes, authorization identity and per-activity token limits.
Changed: 2026-11-07 | AP2-ESCALATED-REASONING | Codex GPT-6 | Verify grant provider receives activity scope for external invocation authorization.
Changed: 2026-11-07 | R3A-AP1-MODEL-ROUTING | Codex GPT-6 | Verify task-class role defaults, reject autonomic reasoning, preserve vision routing, and forbid cross-class fallback.
Supersedes: None.
Contracts: AP0-003–010; R3A-019; MOD-006; r3a.contract-envelope.v1; r3a.model-role.v1; r3a.authorization-decision.v1; r3a.capability-invocation.v1; r3a.model-readiness.v2; r3a.model-readiness-provider.v1.
Tests: This test module.
History/Predecessor: Prior revision at baseline commit 9925c7a408707162e6f070a4121dcc83f5fe0e0a, blob 979644d466f21ca2dbcd49014fad832552d9bd25; earlier history includes blob ce77c005bfa4cb480b56d03ff15c0cc6e49b50ea.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from r3a_runtime.authorization import (AuthorizationDecision, AuthorizationRequest,
                                       CapabilityGrantAuthorizationProvider,
                                       create_authorization_provider, register_authorization_provider)
from r3a_runtime.config import ConfigurationError, load_settings, sanitized_config
from r3a_runtime.contracts import (ActivityDependencySet, ContractEnvelope, ContractOutcome, ContractValidationError,
                                   ReadinessObservation, resolve_role)
from r3a_runtime.cme import CME, ModelRoleUnavailable
from r3a_runtime.diagnostics import project_resource_readiness
from r3a_runtime.protocol import ModuleProtocolServer, request as module_request


ROOT = Path(__file__).resolve().parents[1]


class ActivityDependencyContractTests(unittest.TestCase):
    def test_versioned_dependency_set_normalizes_and_rejects_invalid_sets(self):
        activity_id = "A0B1C2D3-E4F5-4678-9012-123456789ABC"
        contract = ActivityDependencySet((activity_id,))
        self.assertEqual([activity_id.lower()], contract.to_dict()["activity_ids"])
        self.assertEqual(contract, ActivityDependencySet.from_value(contract.to_dict()))
        with self.assertRaises(ContractValidationError):
            ActivityDependencySet.from_value({"contract_id": "r3a.activity-dependencies",
                                              "contract_version": "2.0.0",
                                              "activity_ids": [activity_id]})
        with self.assertRaises(ContractValidationError):
            ActivityDependencySet((activity_id, activity_id.lower()))
        with self.assertRaises(ContractValidationError):
            ActivityDependencySet(("not-a-uuid",))


def make_config(directory: Path, *, primary_model: str = "reasoner-a",
                vision_model: str = "vision-a") -> Path:
    data = directory / "state"
    sockets = data / "run"
    source = ROOT / "r3a_runtime" / "grace_module.py"
    routes = [
        {"route_id": "autonomic-route", "provider": "openai-compatible",
         "endpoint": "http://127.0.0.1:18001/v1/chat/completions", "model": "small-reasoner",
         "timeout_seconds": 15, "max_tokens": 128},
        {"route_id": "primary-route", "provider": "openai-compatible",
         "endpoint": "https://models.example.invalid/v1/chat/completions", "model": primary_model,
         "timeout_seconds": 90, "max_tokens": 256},
        {"route_id": "vision-route", "provider": "openai-compatible",
         "endpoint": "https://vision.example.invalid/v1/chat/completions", "model": vision_model,
         "timeout_seconds": 60, "max_tokens": 192},
    ]
    roles = [
        {"role_id": "resident.autonomic", "route_id": "autonomic-route",
         "capabilities": ["monitor.health"], "modalities": ["text"],
         "task_classes": ["autonomic"], "fallback_roles": [],
         "readiness_max_age_seconds": 30, "unavailable_action": "defer",
         "deferral_seconds": 10, "concurrency": 1,
         "readiness": {"provider_id": "openai-compatible.models", "contract_version": "1.0.0",
                       "endpoint": "http://127.0.0.1:18001/v1/models", "timeout_seconds": 2,
                       "max_attempts": 2, "retry_delay_seconds": 0.01,
                       "poll_interval_seconds": 15}},
        {"role_id": "resident.primary", "route_id": "primary-route",
         "capabilities": ["reason.text", "plan"], "modalities": ["text"],
         "task_classes": ["objective_reasoning"], "fallback_roles": [], "readiness_max_age_seconds": 45,
         "unavailable_action": "defer", "deferral_seconds": 12, "concurrency": 2,
         "readiness": {"provider_id": "openai-compatible.models", "contract_version": "1.0.0",
                       "endpoint": "https://models.example.invalid/v1/models", "timeout_seconds": 3,
                       "max_attempts": 2, "retry_delay_seconds": 0.01,
                       "poll_interval_seconds": 20}},
        {"role_id": "resident.vision", "route_id": "vision-route",
         "capabilities": ["reason.text", "vision.interpret"], "modalities": ["text", "image"],
         "task_classes": ["vision"],
         "fallback_roles": [], "readiness_max_age_seconds": 45,
         "unavailable_action": "block", "deferral_seconds": 12, "concurrency": 1,
         "readiness": {"provider_id": "openai-compatible.models", "contract_version": "1.0.0",
                       "endpoint": "https://vision.example.invalid/v1/models", "timeout_seconds": 3,
                       "max_attempts": 2, "retry_delay_seconds": 0.01,
                       "poll_interval_seconds": 20}},
    ]
    value = {
        "schema_version": 1,
        "instance_id": "r3a_contract_test",
        "paths": {"data_dir": str(data), "postgres_socket_dir": str(sockets),
                  "control_socket": str(sockets / "control.sock"),
                  "diagnostics_socket": str(sockets / "diagnostics.sock"),
                  "module_socket": str(sockets / "module.sock"),
                  "machine_catalog_dir": str(ROOT / "r3a_runtime" / "state_machines")},
        "postgres": {"database": "r3a_contract_test", "user": "r3a_runtime",
                     "socket_dir": str(sockets), "port": 55432},
        "module": {"module_id": "resident.grace", "version": "1.0.0",
                   "contract_id": "r3a.module", "protocol_major": 1, "protocol_minor": 0,
                   "capabilities": ["institution.knowledge.read", "institution.diagnostics.read"],
                   "owner": "Steward", "entrypoint": "r3a_runtime.grace_module",
                   "source": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
        "timing": {"observer_interval_seconds": 60, "scheduler_interval_seconds": 1,
                   "lease_seconds": 30, "heartbeat_interval_seconds": 2,
                   "heartbeat_stale_after_seconds": 10, "diagnostic_stale_after_seconds": 10,
                   "restart_initial_seconds": 1, "restart_max_seconds": 8,
                   "worker_concurrency": 2},
        "grace": {"routes": routes, "default_route": "primary-route",
                  "knowledge_sources": [str(ROOT / "r3a_runtime" / "state_machines" / "process.json")],
                  "role_registry": {"schema_version": 1, "default_role": "resident.primary",
                                    "task_defaults": {"autonomic": "resident.autonomic",
                                                      "objective_reasoning": "resident.primary",
                                                      "vision": "resident.vision"},
                                    "roles": roles}},
        "authorization": {"provider_id": "capability_grants", "contract_version": "1.0.0",
                          "options": {}},
    }
    path = directory / "config.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class ReasoningEscalationConfigTests(unittest.TestCase):
    def test_escalation_policy_is_versioned_configured_and_sanitized(self):
        with TemporaryDirectory() as temporary:
            path = make_config(Path(temporary))
            value = json.loads(path.read_text(encoding="utf-8"))
            value["module"]["capabilities"].append("reasoning.escalation.request")
            value["grace"]["reasoning_escalation"] = {
                "contract_id": "r3a.reasoning-escalation-policy", "contract_version": "1.0.0",
                "enabled": True, "authorization_capability_id": "reasoning.escalation.request",
                "allowed_role_ids": ["resident.primary"], "max_requests_per_activity": 2,
                "max_completion_tokens_per_activity": 512}
            path.write_text(json.dumps(value), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings.reasoning_escalation.allowed_role_ids, ("resident.primary",))
            self.assertEqual(settings.reasoning_escalation.max_completion_tokens_per_activity, 512)
            self.assertEqual(sanitized_config(settings)["grace"]["reasoning_escalation"][
                "authorization_capability_id"], "reasoning.escalation.request")

    def test_escalation_policy_rejects_unregistered_roles_and_bad_budget(self):
        for field, invalid, message in (
                ("allowed_role_ids", ["resident.missing"], "unconfigured role"),
                ("max_completion_tokens_per_activity", 0, "token budget")):
            with self.subTest(field=field), TemporaryDirectory() as temporary:
                path = make_config(Path(temporary))
                value = json.loads(path.read_text(encoding="utf-8"))
                value["module"]["capabilities"].append("reasoning.escalation.request")
                value["grace"]["reasoning_escalation"] = {
                    "contract_id": "r3a.reasoning-escalation-policy", "contract_version": "1.0.0",
                    "enabled": True, "authorization_capability_id": "reasoning.escalation.request",
                    "allowed_role_ids": ["resident.primary"], "max_requests_per_activity": 1,
                    "max_completion_tokens_per_activity": 256}
                value["grace"]["reasoning_escalation"][field] = invalid
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(ConfigurationError, message):
                    load_settings(path)


class VersionedEnvelopeTests(unittest.TestCase):
    def test_contract_envelope_round_trip_and_rejects_incompatible_major(self):
        envelope = ContractEnvelope("r3a.resident.execution", "1.0.0", "request-1", "activity-1",
                                    "attempt-1", "correlation-1", "resident.grace", "config-1",
                                    "2026-11-06T23:00:00Z", {"operation": "execute"})
        self.assertEqual(ContractEnvelope.from_dict(envelope.to_dict()).activity_id, "activity-1")
        incompatible = {**envelope.to_dict(), "contract_version": "2.0.0"}
        with self.assertRaises(ContractValidationError):
            ContractEnvelope.from_dict(incompatible)

    def test_outcome_contract_requires_typed_defer_and_failure_reasons(self):
        outcome = ContractOutcome("r3a.model-route-decision", "1.0.0", "request-2", "correlation-2",
                                  "resident.grace", "config-1", "2026-11-06T23:00:00Z",
                                  "deferred", True, reason_code="role_not_ready",
                                  retry_after_seconds=10, activity_id="activity-1", attempt_id="attempt-1")
        self.assertEqual(outcome.to_dict()["outcome"], "deferred")
        with self.assertRaises(ContractValidationError):
            ContractOutcome("r3a.model-route-decision", "1.0.0", "request-2", "correlation-2",
                            "resident.grace", "config-1", "2026-11-06T23:00:00Z",
                            "deferred", False, reason_code="role_not_ready")


class ModelRoleConfigAndRoutingTests(unittest.TestCase):
    def test_model_route_context_window_is_externally_configurable_and_bounded(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            route = value["grace"]["routes"][1]
            route["context_window_tokens"] = 16384
            path.write_text(json.dumps(value), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings.model_route("primary-route").context_window_tokens, 16384)
            self.assertEqual(sanitized_config(settings)["grace"]["routes"][1]["context_window_tokens"], 16384)

            for invalid in (True, 1023, 1000001, route["max_tokens"]):
                route["context_window_tokens"] = invalid
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ConfigurationError):
                    load_settings(path)

    def test_roles_are_external_and_model_assignment_change_changes_revision(self):
        with TemporaryDirectory() as first_dir, TemporaryDirectory() as second_dir:
            first = load_settings(make_config(Path(first_dir)))
            second = load_settings(make_config(Path(second_dir), primary_model="reasoner-b"))
            self.assertEqual(first.default_model_role, "resident.primary")
            self.assertEqual(len(first.model_roles), 3)
            self.assertEqual(first.model_role_for_task("objective_reasoning").route_id, "primary-route")
            self.assertEqual(first.model_role_for_task("autonomic").route_id, "autonomic-route")
            self.assertEqual(first.model_role_for_task("vision").route_id, "vision-route")
            self.assertEqual(first.model_route("primary-route").model, "reasoner-a")
            self.assertEqual(second.model_route("primary-route").model, "reasoner-b")
            self.assertNotEqual(first.source_digest, second.source_digest)
            durable = sanitized_config(first)
            self.assertEqual(durable["grace"]["role_registry"]["schema_version"], 1)
            self.assertEqual(durable["grace"]["role_registry"]["task_defaults"]["objective_reasoning"],
                             "resident.primary")
            self.assertEqual(durable["authorization"]["provider_id"], "capability_grants")

    def test_legacy_route_configuration_remains_supported(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            value["grace"].pop("role_registry")
            value.pop("authorization")
            path.write_text(json.dumps(value), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings.model_roles, ())
            self.assertIsNone(settings.default_model_role)
            self.assertEqual(settings.authorization_provider.provider_id, "capability_grants")

    def test_objective_intake_defaults_to_primary_and_rejects_autonomic_role(self):
        async def scenario():
            with TemporaryDirectory() as directory:
                settings = load_settings(make_config(Path(directory)))
                cme = CME.__new__(CME)
                cme.settings = settings
                cme.store = type("Store", (), {"submit_grace_objective": AsyncMock(
                    return_value={"activity_id": "activity-primary", "state": "QUEUED"})})()
                result = await cme._control_request("grace.objective.submit", {
                    "objective": "Inspect the configured process definition.",
                    "acceptance_criteria": []}, "objective-primary")
                self.assertEqual(result["activity_id"], "activity-primary")
                args = cme.store.submit_grace_objective.await_args.args
                self.assertEqual(args[3], "primary-route")
                self.assertEqual(args[4], "resident.primary")
                self.assertEqual(args[-1], "objective_reasoning")
                with self.assertRaisesRegex(ValueError, "not authorized for objective_reasoning"):
                    await cme._control_request("grace.objective.submit", {
                        "objective": "Use the autonomic route for reasoning.",
                        "acceptance_criteria": [], "role_id": "resident.autonomic"},
                        "objective-autonomic")
                self.assertEqual(cme.store.submit_grace_objective.await_count, 1)
                await cme._control_request("grace.objective.submit", {
                    "objective": "Interpret this submitted visual evidence.",
                    "acceptance_criteria": [], "required_modalities": ["image"]},
                    "objective-vision")
                vision_args = cme.store.submit_grace_objective.await_args.args
                self.assertEqual(vision_args[3], "vision-route")
                self.assertEqual(vision_args[4], "resident.vision")
                self.assertEqual(vision_args[-1], "vision")
        asyncio.run(scenario())

    def test_cme_rejects_autonomic_role_before_objective_inference(self):
        async def scenario():
            with TemporaryDirectory() as directory:
                settings = load_settings(make_config(Path(directory)))
                cme = CME.__new__(CME)
                cme.settings = settings
                cme.module_id = "resident.grace"
                activity = {"activity_id": "activity-autonomic", "attempt_id": "attempt-1",
                            "input": {"objective": "Reason about an institutional assignment.",
                                      "task_class": "autonomic", "role_id": "resident.autonomic",
                                      "role_config_revision": settings.source_digest,
                                      "acceptance_contract": {"contract_id": "r3a.objective-acceptance",
                                                              "contract_version": "1.0.0",
                                                              "criteria": [{"criterion_id": "state-route",
                                                                            "type": "transition_path",
                                                                            "from_state": "RUNNING",
                                                                            "to_state": "STOPPED"}]}},
                            "checkpoint": {}}
                with self.assertRaises(ModelRoleUnavailable) as raised:
                    await cme._objective_context(activity)
                self.assertEqual(raised.exception.decision.action, "block")
                self.assertEqual(raised.exception.decision.reason,
                                 "objective_activity_cannot_use_autonomic_role")
        asyncio.run(scenario())

    def test_durable_continuation_keeps_pinned_primary_role(self):
        async def scenario():
            with TemporaryDirectory() as directory:
                settings = load_settings(make_config(Path(directory)))
                role = next(entry for entry in settings.model_roles
                            if entry.role_id == "resident.primary")
                route = settings.model_route(role.route_id)

                class StoreFake:
                    async def activity_dependency_context(self, _dependencies):
                        return None

                    async def model_role_observations(self, _role_ids):
                        return {role.role_id: {"status": "ready", "observed_at": datetime.now(timezone.utc).isoformat(),
                            "config_revision": settings.source_digest, "model_id": route.model,
                            "provider_id": role.readiness.provider_id, "source": "provider_model",
                            "evidence_ref": "sha256:provider-evidence", "evidence": {"model_match": True}}}

                cme = CME.__new__(CME)
                cme.settings = settings
                cme.store = StoreFake()
                cme.module_id = "resident.grace"
                cme._resident_tools = lambda: []
                expected_route = {"route_id": route.route_id, "provider": route.provider,
                                  "model": route.model, "endpoint": route.endpoint,
                                  "timeout_seconds": route.timeout_seconds, "max_tokens": route.max_tokens}
                activity = {"activity_id": "activity-resume", "attempt_id": "attempt-2",
                    "input": {"objective": "Continue the durable reasoning assignment.",
                        "role_id": role.role_id, "route_id": role.route_id,
                        "task_class": "objective_reasoning", "role_config_revision": settings.source_digest,
                        "required_capabilities": ["plan"], "required_modalities": [],
                        "acceptance_contract": {"contract_id": "r3a.objective-acceptance",
                            "contract_version": "1.0.0", "criteria": [{"criterion_id": "state-route",
                                "type": "transition_path", "from_state": "RUNNING", "to_state": "STOPPED"}]}},
                    "checkpoint": {"selected_role_id": role.role_id, "model_route": expected_route,
                                   "evidence": [], "reasoning_state": {}}}
                context = await cme._objective_context(activity)
                self.assertEqual(context["selected_role_id"], "resident.primary")
                self.assertEqual(context["route_id"], "primary-route")
        asyncio.run(scenario())

    def test_private_network_http_model_endpoint_is_externally_configurable(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            route = value["grace"]["routes"][1]
            route["endpoint"] = "http://10.20.30.40:8080/v1/chat/completions"
            role = value["grace"]["role_registry"]["roles"][1]
            role["readiness"]["endpoint"] = "http://10.20.30.40:8080/v1/models"
            path.write_text(json.dumps(value), encoding="utf-8")
            settings = load_settings(path)
            self.assertEqual(settings.model_route("primary-route").endpoint, route["endpoint"])
            self.assertEqual(settings.model_roles[1].readiness.endpoint, role["readiness"]["endpoint"])

    def test_role_without_provider_policy_remains_unknown_and_cannot_route(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            role_data = value["grace"]["role_registry"]["roles"][1]
            role_data.pop("readiness")
            path.write_text(json.dumps(value), encoding="utf-8")
            settings = load_settings(path)
            role = settings.model_roles[1]
            self.assertIsNone(role.readiness)
            decision = resolve_role((role,), role.role_id, {"plan"},
                                    {role.role_id: {"status": "ready",
                                                    "observed_at": datetime.now(timezone.utc).isoformat(),
                                                    "config_revision": settings.source_digest,
                                                    "provider_id": "forged-provider",
                                                    "evidence_ref": "forged",
                                                    "evidence": {"model_match": True}}},
                                    config_revision=settings.source_digest)
            self.assertNotEqual(decision.action, "route")

    def test_readiness_endpoint_must_identify_the_configured_model_provider(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            value["grace"]["role_registry"]["roles"][1]["readiness"]["endpoint"] = (
                "https://other.example.invalid/v1/models")
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_settings(path)

    def test_bad_role_route_fallback_and_contract_versions_fail_closed(self):
        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            value["grace"]["role_registry"]["roles"][1]["route_id"] = "missing"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_settings(path)

        with TemporaryDirectory() as directory:
            path = make_config(Path(directory))
            value = json.loads(path.read_text(encoding="utf-8"))
            value["grace"]["role_registry"]["roles"][1]["fallback_roles"] = ["resident.autonomic"]
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "preserve task-class authorization"):
                load_settings(path)

    def test_capability_selection_fallback_deferral_staleness_and_unsupported(self):
        with TemporaryDirectory() as directory:
            settings = load_settings(make_config(Path(directory)))
            now = datetime.now(timezone.utc)
            def observation(role_id, status, observed_at):
                role = next(item for item in settings.model_roles if item.role_id == role_id)
                route = settings.model_route(role.route_id)
                return {"status": status, "observed_at": observed_at,
                        "config_revision": settings.source_digest, "model_id": route.model,
                        "provider_id": role.readiness.provider_id, "evidence_ref": "sha256:provider",
                        "evidence": {"model_match": status == "ready"}}
            observations = {
                "resident.primary": observation("resident.primary", "unavailable", now.isoformat()),
                "resident.vision": observation("resident.vision", "ready", now.isoformat()),
            }
            primary_cannot_be_replaced_by_vision = resolve_role(
                settings.model_roles, "resident.primary", {"vision.interpret"},
                observations, config_revision=settings.source_digest, now=now)
            self.assertEqual((primary_cannot_be_replaced_by_vision.action,
                              primary_cannot_be_replaced_by_vision.reason),
                             ("block", "unsupported_capability"))
            vision = resolve_role(settings.model_roles, "resident.vision", {"vision.interpret"},
                                  observations, config_revision=settings.source_digest, now=now)
            self.assertEqual((vision.action, vision.selected_role_id, vision.route_id),
                             ("route", "resident.vision", "vision-route"))
            unavailable = resolve_role(settings.model_roles, "resident.primary", {"plan"},
                                       observations, config_revision=settings.source_digest, now=now)
            self.assertEqual(unavailable.action, "defer")
            self.assertIsNone(unavailable.selected_role_id)
            self.assertNotEqual(unavailable.route_id, "autonomic-route")
            stale = {"resident.primary": observation(
                "resident.primary", "ready", (now - timedelta(minutes=2)).isoformat())}
            self.assertEqual(resolve_role(settings.model_roles, "resident.primary", {"plan"}, stale,
                                          config_revision=settings.source_digest, now=now).action, "defer")
            unsupported = resolve_role(settings.model_roles, "resident.primary", {"image.generate"},
                                       observations, config_revision=settings.source_digest, now=now)
            self.assertEqual((unsupported.action, unsupported.reason), ("block", "unsupported_capability"))
            no_vision = resolve_role(settings.model_roles, "resident.primary", set(), observations,
                                     config_revision=settings.source_digest, now=now,
                                     required_modalities={"audio"})
            self.assertEqual((no_vision.action, no_vision.reason), ("block", "unsupported_modality"))

    def test_host_reachability_cannot_be_submitted_as_model_readiness(self):
        with self.assertRaises(ContractValidationError):
            ReadinessObservation(resident_id="resident.grace", role_id="resident.primary",
                                 model_id="reasoner-a", status="ready", source="tcp",
                                 observed_at="2026-11-06T23:00:00Z", config_revision="revision",
                                 observation_id="00000000-0000-0000-0000-000000000001",
                                 evidence_ref="tcp:ok", provider_id="fake-provider",
                                 evidence={"connected": True})

    def test_stale_model_readiness_is_not_projected_as_ready(self):
        now = datetime.now(timezone.utc)
        row = {"resource_id": "model-role:reasoner", "health": "ready",
               "metadata": {"registry_contract": "r3a.model-role.v1",
                            "config_revision": "revision", "readiness_max_age_seconds": 10,
                            "readiness_provider_id": "provider-a", "configured_model_id": "model-x",
                            "readiness": {"status": "ready", "source": "provider_model",
                                          "model_id": "model-x", "evidence_ref": "probe:abc",
                                          "provider_id": "provider-a", "evidence": {"model_match": True},
                                          "config_revision": "revision",
                                          "observed_at": (now - timedelta(seconds=20)).isoformat()}}}
        projected = project_resource_readiness(row, now, "revision")
        self.assertEqual(projected["readiness_freshness"], "stale")
        self.assertEqual(projected["readiness_status"], "stale")
        self.assertEqual(projected["health"], "stale")
        wrong_model = {**row, "metadata": {**row["metadata"],
                                             "readiness": {**row["metadata"]["readiness"],
                                                           "observed_at": now.isoformat(),
                                                           "model_id": "unconfigured-model"}}}
        mismatch = project_resource_readiness(wrong_model, now, "revision")
        self.assertEqual(mismatch["readiness_status"], "unknown")
        self.assertEqual(mismatch["health"], "unknown")


class GrantAuthorizationCompatibilityTests(unittest.TestCase):
    class StoreFake:
        def __init__(self, allowed: bool):
            self.allowed = allowed
            self.calls = []

        async def require_capability(self, resident_id: str, capability_id: str,
                                    activity_id: str | None = None):
            self.calls.append(("require", resident_id, capability_id, activity_id))
            if not self.allowed:
                raise PermissionError("no active grant")

        async def audit_capability_invocation(self, resident_id: str, capability_id: str,
                                              result: str, details: dict):
            self.calls.append(("audit", resident_id, capability_id, result, details))

    def make_request(self):
        return AuthorizationRequest("r3a.authorization-decision", "1.0.0", "request-1", "correlation-1",
                                    "resident.grace", "institution.knowledge.read", "activity-1",
                                    "attempt-1", "config-1", "2026-11-06T23:00:00Z", {})

    def test_existing_grant_check_and_audit_are_preserved_for_allow_and_deny(self):
        for allowed in (True, False):
            store = self.StoreFake(allowed)
            provider = CapabilityGrantAuthorizationProvider(store, "config-1")
            decision = asyncio.run(provider.authorize(self.make_request()))
            self.assertEqual(decision.allowed, allowed)
            self.assertEqual(store.calls[0],
                             ("require", "resident.grace", "institution.knowledge.read", "activity-1"))
            self.assertEqual(store.calls[1][0:4],
                             ("audit", "resident.grace", "institution.knowledge.read",
                              "allowed" if allowed else "denied"))
            self.assertEqual(store.calls[1][4]["authorization_provider"], "capability_grants")
            self.assertEqual(decision.config_revision, "config-1")
            self.assertIsNone(decision.policy_revision)
            self.assertEqual(decision.decision_id, "request-1")
            self.assertNotEqual(decision.decision_id, decision.audit_event_id)

    def test_grant_provider_passes_activity_identity_for_scoped_grant_evaluation(self):
        store = self.StoreFake(True)
        decision = asyncio.run(CapabilityGrantAuthorizationProvider(
            store, "config-1").authorize(self.make_request()))
        self.assertTrue(decision.allowed)
        self.assertEqual(store.calls[0],
                         ("require", "resident.grace", "institution.knowledge.read", "activity-1"))

    def test_grant_provider_does_not_treat_scope_or_delegation_as_an_existing_grant(self):
        store = self.StoreFake(True)
        request = self.make_request()
        scoped = AuthorizationRequest(**{**request.__dict__, "resource_scope": {"path": "source"},
                                         "delegation_ref": "delegation-1"})
        decision = asyncio.run(CapabilityGrantAuthorizationProvider(store, "config-1").authorize(scoped))
        self.assertFalse(decision.allowed)
        self.assertEqual(store.calls[-1][3], "denied")

    def test_alternative_provider_can_be_registered_without_cme_changes(self):
        class Alternative:
            provider_id = "test.alternative"
            contract_version = "1.0.0"

            async def authorize(self, request):
                return None

        register_authorization_provider("test.alternative", lambda *_: Alternative())
        provider = create_authorization_provider("test.alternative", {}, "config-1", object())
        self.assertEqual(provider.provider_id, "test.alternative")


class NoDeploymentPolicyConstantsTests(unittest.TestCase):
    def test_core_and_resident_sources_do_not_embed_assigned_host_or_model_identities(self):
        sources = [(ROOT / "r3a_runtime" / name).read_text(encoding="utf-8")
                   for name in ("cme.py", "grace_module.py", "readiness.py", "config.py")]
        for source in sources:
            for forbidden in ("192.168.1.155", "192.168.1.160", "192.168.1.162",
                              "OctoMiner1", "OctoMiner2", "Camrui"):
                self.assertNotIn(forbidden, source)


class ExistingModuleRpcCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_v1_module_health_rpc_remains_compatible(self):
        async def handler(operation, payload):
            self.assertEqual(operation, "health")
            return {"state": "ACTIVE", "health": "healthy"}

        with TemporaryDirectory() as directory:
            socket_path = Path(directory) / "module.sock"
            server = ModuleProtocolServer(socket_path, "resident.test", "1.0.0", handler)
            await server.start()
            try:
                response = await module_request(socket_path, "resident.test", "1.0.0", "health", {})
                self.assertEqual(response["protocol_version"], {"major": 1, "minor": 0})
                self.assertEqual(response["result"]["state"], "ACTIVE")
            finally:
                await server.close()

    async def test_cme_adds_execution_contract_without_changing_rpc_signature(self):
        class Provider:
            provider_id = "test.provider"
            contract_version = "1.0.0"

            async def authorize(self, _request):
                raise AssertionError("no authorization call expected")

        with TemporaryDirectory() as directory:
            settings = load_settings(make_config(Path(directory)))
            cme = CME(settings, authorization_provider=Provider())
            captured = {}

            async def fake_request(socket, module_id, version, operation, payload, timeout):
                captured.update(socket=socket, module_id=module_id, version=version,
                                operation=operation, payload=payload, timeout=timeout)
                return {"ok": True, "result": {}}

            payload = {"activity_type": "grace.objective", "activity_id": "activity-1",
                       "attempt_id": "attempt-1", "config_revision": settings.source_digest}
            with patch("r3a_runtime.cme.module_request", fake_request):
                await cme._module_call("execute", payload, timeout=30)
            self.assertEqual(captured["operation"], "execute")
            self.assertEqual(captured["module_id"], "resident.grace")
            envelope = ContractEnvelope.from_dict(
                captured["payload"]["contract_envelope"], expected_contract="r3a.resident.execution")
            self.assertEqual(envelope.activity_id, "activity-1")
            self.assertEqual(envelope.attempt_id, "attempt-1")

    async def test_unready_requested_role_is_durably_deferred_not_completed(self):
        class Provider:
            provider_id = "test.provider"
            contract_version = "1.0.0"

            async def authorize(self, request):
                return AuthorizationDecision("r3a.authorization-decision", "1.0.0",
                                             self.provider_id, True, "allowed", False,
                                             None, request.config_revision,
                                             "2026-11-06T23:00:00Z", request.correlation_id,
                                             request.activity_id, request.attempt_id)

        class StoreFake:
            def __init__(self):
                self.deferred = []
                self.completed = False

            async def model_role_observations(self, _role_ids):
                return {}

            async def defer_activity(self, activity, reason, retry_after, details):
                self.deferred.append((activity["activity_id"], reason, retry_after, details))

            async def block_activity(self, *_args):
                raise AssertionError("freshly deferrable role should not block")

            async def finish_activity(self, *_args):
                self.completed = True
                raise AssertionError("unready role must never complete")


        with TemporaryDirectory() as directory:
            settings = load_settings(make_config(Path(directory)))
            cme = CME(settings, authorization_provider=Provider())
            store = StoreFake()
            cme.store = store
            cme.module_process = type("Process", (), {"returncode": None})()
            activity = {"activity_type": "grace.objective", "activity_id": "activity-1",
                        "attempt_id": "attempt-1", "attempt_count": 0,
                        "input": {"objective": "Determine whether RUNNING can reach COMPLETED in process.lifecycle.",
                                  "event_kind": "objective", "route_id": None,
                                  "role_id": "resident.primary",
                                  "required_capabilities": ["plan"], "required_modalities": [],
                                  "role_config_revision": settings.source_digest,
                                  "acceptance_contract": {"contract_id": "r3a.objective-acceptance",
                                                          "contract_version": "1.0.0",
                                                          "criteria": [{"criterion_id": "running_to_completed",
                                                                        "type": "transition_path",
                                                                        "from_state": "RUNNING",
                                                                        "to_state": "COMPLETED"}]}},
                        "checkpoint": {}}
            await cme._run_activity(activity)
            self.assertEqual(len(store.deferred), 1)
            self.assertTrue(store.deferred[0][1].startswith("resident.primary:unknown"))
            self.assertGreater(store.deferred[0][2], 0)
            self.assertFalse(store.completed)


if __name__ == "__main__":
    unittest.main()
