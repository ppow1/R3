"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_activity_handler_interop.py
Component: R3A-ACTIVITY-HANDLER-INTEROPERABILITY-TESTS
File Revision: 1.0.4
Created: 2026-11-10T02:02:46Z
Created By: Codex GPT-6
Purpose: Validate the shared v1.1 module/handler fixture and provide CME dispatch tests for Autonomy #43 to consume.
Execution Model: Contract tests run in #46; CME dispatch tests run when the #43 dispatcher is integrated.
Observability: Schema, digest, version, payload, authorization, dispatch, progress, and result assertions.
Dependencies: r3a_runtime.capability_contracts; r3a_runtime.module_extensions; CME #43 generic handler path.
Authority: AD-024; the fixture's required capabilities are not grants.
Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add shared module-manifest/handler contract and CME interoperability regressions.
Changed: 2026-11-10T02:07:18Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Avoid installing collection-time database stubs that leak across the full test suite.
Changed: 2026-11-10T03:20:00Z | R3A-AUTONOMY-BASELINE-RECONCILIATION | Codex GPT-6 | Exercise CME discovery and resident bindings from the shared v1.1 manifest projection.
Changed: 2026-11-10T04:00:00Z | R3A-CHECKPOINT-PERSISTENCE-CORRECTION | Codex GPT-6 | Assert CME commits handler progress and checkpoint in one durable ledger update.
Changed: 2026-11-11 | R3A-RESIDENT-ID-AUDIT | Codex GPT-6 | Use canonical resident principals in identity, binding and execution-profile fixtures.
Supersedes: None.
Contracts: r3a.module-manifest.v1@1.0.0 and @1.1.0; r3a.activity-handler.v1@1.0.0.
Tests: python3 -m pytest -q tests/test_r3a_activity_handler_interop.py
History/Predecessor: Immediate predecessor blob 045e1633c734cbd2dd3ec41039e9314c064c7c93; this revision retains the reconciled integration tests and corrects principal-shaped fixture values.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from r3a_runtime.capability_contracts import CapabilityContractError, validate_module_manifest
from r3a_runtime.module_extensions import (
    ModuleExtensionError,
    resolve_activity_handler,
    validate_activity_handler_payload,
)
from r3a_runtime.provider_runtime import ProviderProcessManager
from tests.r3a_activity_handler_interop_provider import create_provider


_FIXTURE = Path(__file__).parent / "fixtures/r3a_activity_handler_interop.v1.json"


def fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def validated_fixture(value: dict | None = None) -> tuple[dict, dict]:
    sample = copy.deepcopy(value if value is not None else fixture())
    module = validate_module_manifest(sample["module_manifest"], sample["operation"],
                                      sample["source_manifest"])
    registered = SimpleNamespace(
        descriptor={"provider": sample["operation"]["provider"]},
        legacy_manifest={"module_manifest": sample["module_manifest"],
                         "configuration_schema": sample["source_manifest"]["configuration_schema"]})
    projection = ProviderProcessManager._manifest(object.__new__(ProviderProcessManager), registered)
    row = {"module_id": module["module_id"], "module_version": module["module_version"],
           "lifecycle_state": "ACTIVE", "manifest": projection}
    return sample, row


def test_shared_fixture_validates_as_v11_module_and_matches_runtime_projection():
    sample, row = validated_fixture()
    artifact = Path(__file__).parent / "r3a_activity_handler_interop_provider.py"
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert sample["module_manifest"]["contract_version"] == "1.1.0"
    assert sample["module_manifest"]["artifact"]["artifact_sha256"] == digest
    assert row["manifest"]["manifest_contract"] == "r3a.module-manifest.v1@1.1.0"
    assert resolve_activity_handler([row], "billing.invoice.review")["artifact_digest"] == digest

    registered = SimpleNamespace(
        descriptor={"provider": sample["operation"]["provider"]},
        legacy_manifest={"module_manifest": sample["module_manifest"],
                         "configuration_schema": sample["source_manifest"]["configuration_schema"]})
    projection = ProviderProcessManager._manifest(object.__new__(ProviderProcessManager), registered)
    assert projection == row["manifest"]

    provider_result = create_provider({"mode": "fixture"}).invoke(
        sample["activity_request"], context={"activity_id": "fixture-activity"})
    assert provider_result == sample["expected_result"]
    for kind, payload in (("request", sample["activity_request"]),
                          ("result", provider_result),
                          ("progress", provider_result["progress"]),
                          ("checkpoint", provider_result["checkpoint"])):
        assert validate_activity_handler_payload(sample["module_manifest"]["activity_handler"],
                                                 kind, payload) == payload


@pytest.mark.parametrize("contract_version", ["1.0.1", "1.2.0", "2.0.0", "garbage"])
def test_shared_fixture_rejects_unknown_manifest_contract_versions(contract_version):
    sample = fixture()
    sample["module_manifest"]["contract_version"] = contract_version
    with pytest.raises(CapabilityContractError, match="contract version is unsupported"):
        validate_module_manifest(sample["module_manifest"], sample["operation"], sample["source_manifest"])


def test_v10_manifest_cannot_smuggle_v11_role_fields():
    sample = fixture()
    sample["module_manifest"]["contract_version"] = "1.0.0"
    with pytest.raises(CapabilityContractError, match="unknown fields"):
        validate_module_manifest(sample["module_manifest"], sample["operation"], sample["source_manifest"])


@pytest.mark.parametrize("mutate", [
    lambda sample: sample["module_manifest"]["artifact"].update(artifact_sha256="0" * 64),
    lambda sample: sample["operation"]["provider"].update(artifact_sha256="0" * 64),
    lambda sample: sample["source_manifest"].update(artifact_sha256="0" * 64),
])
def test_shared_fixture_rejects_digest_mismatch(mutate):
    sample = fixture()
    mutate(sample)
    with pytest.raises(CapabilityContractError, match="artifact digest"):
        validate_module_manifest(sample["module_manifest"], sample["operation"], sample["source_manifest"])


@pytest.mark.parametrize("mutate", [
    lambda sample: sample["module_manifest"]["activity_handler"].update(contract_version="2.0.0"),
    lambda sample: sample["module_manifest"]["activity_handler"]["handler_contract_range"].update(major=2),
    lambda sample: sample["module_manifest"]["activity_handler"].update(activity_types=[]),
])
def test_shared_fixture_rejects_invalid_handler_contract_versions_and_fields(mutate):
    sample = fixture()
    mutate(sample)
    with pytest.raises(CapabilityContractError):
        validate_module_manifest(sample["module_manifest"], sample["operation"], sample["source_manifest"])


def test_shared_fixture_rejects_invalid_request_result_progress_and_checkpoint_payloads():
    sample = fixture()
    handler = sample["module_manifest"]["activity_handler"]
    for kind, payload in (("request", {"invoice_id": ""}),
                          ("result", {**sample["expected_result"], "status": "approved"}),
                          ("progress", {"phase": "completed", "completed": "one"}),
                          ("checkpoint", {"cursor": True})):
        with pytest.raises(ModuleExtensionError, match="payload is invalid"):
            validate_activity_handler_payload(handler, kind, payload)


def _cme_activity(sample: dict) -> dict:
    return {
        "activity_id": "00000000-0000-4000-8000-000000000101",
        "attempt_id": "00000000-0000-4000-8000-000000000102",
        "idempotency_key": "billing-invoice-review-001",
        "activity_type": "billing.invoice.review",
        "input": {"correlation_id": "00000000-0000-4000-8000-000000000103",
                  "activity_input": copy.deepcopy(sample["activity_request"]),
                  "resident_id": "resident:fixture"},
        "checkpoint": {"cursor": 0},
    }


_CME_DISPATCH_AVAILABLE = False
if (importlib.util.find_spec("psycopg") is not None
        and importlib.util.find_spec("psycopg_pool") is not None):
    _CME_DISPATCH_AVAILABLE = hasattr(
        __import__("r3a_runtime.cme", fromlist=["CME"]).CME,
        "_run_registered_activity")


@pytest.mark.skipif(not _CME_DISPATCH_AVAILABLE,
                    reason="shared CME dispatch acceptance runs when Autonomy #43 integrates the handler contract")
def test_cme_dispatches_shared_fixture_and_records_authorized_result():
    async def run():
        from r3a_runtime.cme import CME

        sample, row = validated_fixture()
        registry_row = {
            "module_id": row["module_id"], "module_version": row["module_version"],
            "manifest": row["manifest"], "lifecycle_state": "ACTIVE"}
        cme = object.__new__(CME)
        cme.store = SimpleNamespace(rows=AsyncMock(side_effect=[[registry_row], [registry_row]]),
                                    record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        resolved = await cme._registered_handler("billing.invoice.review")
        decision = SimpleNamespace(decision_id="decision-1", audit_event_id="audit-1", policy_revision="policy-1")
        operation_descriptor = {"operation_id": sample["operation"]["operation_id"],
                                "provider": sample["operation"]["provider"],
                                "lifecycle": {"desired_state": "enabled"}}
        provider_operation = SimpleNamespace(descriptor=operation_descriptor)
        cme.settings = SimpleNamespace(
            lease_seconds=30,
            capability_registry=SimpleNamespace(
                discover=Mock(return_value=[{"descriptor": operation_descriptor}]),
                resolve_provider=Mock(return_value=provider_operation)))
        cme.module_id = "resident.fixture"
        cme.module_version = "0.0.0"
        cme._authorization_decision = AsyncMock(return_value=decision)
        async def provider_invoke(_operation, arguments, *, context):
            provider = create_provider({"mode": "fixture"})
            return provider.invoke(arguments, context=context)
        cme.provider_runtime = SimpleNamespace(invoke=AsyncMock(side_effect=provider_invoke))

        await cme._run_registered_activity(_cme_activity(sample), resolved)

        cme._authorization_decision.assert_awaited()
        dispatched = cme.provider_runtime.invoke.await_args
        assert dispatched.args[0] is provider_operation
        assert dispatched.args[1]["input"] == sample["activity_request"]
        assert dispatched.args[1]["request"]["operation"] == "execute"
        assert dispatched.args[1]["request"]["payload"]["checkpoint"] == {"cursor": 0}
        assert dispatched.kwargs["context"]["handler"]["handler_id"] == resolved["handler"]["handler_id"]
        cme.store.record_progress.assert_awaited()
        writes = cme.store.record_progress.await_args_list
        assert len(writes) == 2
        assert writes[-1].args[1]["progress"] == sample["expected_result"]["progress"]
        assert writes[-1].args[2]["handler_checkpoint"] == sample["expected_result"]["checkpoint"]
        cme.store.finish_activity.assert_awaited_once()
        final = cme.store.finish_activity.await_args.args[1]
        assert final["handler"]["artifact_digest"] == sample["module_manifest"]["artifact"]["artifact_sha256"]
        assert final["authorization"][0]["audit_event_id"] == "audit-1"

    asyncio.run(run())


@pytest.mark.skipif(not _CME_DISPATCH_AVAILABLE,
                    reason="shared CME dispatch acceptance runs when Autonomy #43 integrates the handler contract")
def test_cme_authorization_denial_precedes_shared_fixture_dispatch():
    async def run():
        from r3a_runtime.cme import CME

        sample, row = validated_fixture()
        cme = object.__new__(CME)
        cme.store = SimpleNamespace(rows=AsyncMock(return_value=[{
            "module_id": row["module_id"], "module_version": row["module_version"],
            "manifest": row["manifest"], "lifecycle_state": "ACTIVE"}]))
        resolved = await cme._registered_handler("billing.invoice.review")
        cme.store = SimpleNamespace(record_progress=AsyncMock(), finish_activity=AsyncMock(), block_activity=AsyncMock())
        cme.settings = SimpleNamespace(lease_seconds=30)
        cme.module_id = "resident.fixture"
        cme._authorization_decision = AsyncMock(side_effect=PermissionError("billing.invoice.read grant missing"))
        cme._registered_module_call = AsyncMock()
        with pytest.raises(PermissionError, match="grant missing"):
            await cme._run_registered_activity(_cme_activity(sample), resolved)
        cme._registered_module_call.assert_not_awaited()
        cme.store.finish_activity.assert_not_awaited()

    asyncio.run(run())


def test_cme_rejects_invalid_handler_checkpoint_before_persisting_it():
    async def run():
        from r3a_runtime.cme import CME

        sample, row = validated_fixture()
        registry_row = {"module_id": row["module_id"], "module_version": row["module_version"],
                        "manifest": row["manifest"], "lifecycle_state": "ACTIVE"}
        operation_descriptor = {"operation_id": sample["operation"]["operation_id"],
                                "provider": sample["operation"]["provider"],
                                "lifecycle": {"desired_state": "enabled"}}
        provider_operation = SimpleNamespace(descriptor=operation_descriptor)
        cme = object.__new__(CME)
        cme.store = SimpleNamespace(rows=AsyncMock(side_effect=[[registry_row], [registry_row]]),
                                    record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        resolved = await cme._registered_handler("billing.invoice.review")
        cme.settings = SimpleNamespace(
            lease_seconds=30,
            capability_registry=SimpleNamespace(
                discover=Mock(return_value=[{"descriptor": operation_descriptor}]),
                resolve_provider=Mock(return_value=provider_operation)))
        cme.module_id = "resident.fixture"
        cme.module_version = "0.0.0"
        cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
            decision_id="decision", audit_event_id="audit", policy_revision="policy"))
        invalid_result = dict(sample["expected_result"], checkpoint={"cursor": True})
        cme.provider_runtime = SimpleNamespace(invoke=AsyncMock(return_value=invalid_result))

        with pytest.raises(ModuleExtensionError, match="result payload is invalid"):
            await cme._run_registered_activity(_cme_activity(sample), resolved)
        # The first write records dispatch metadata. The invalid returned checkpoint
        # is rejected before any result progress/checkpoint update is written.
        assert cme.store.record_progress.await_count == 1
        cme.store.finish_activity.assert_not_awaited()

    asyncio.run(run())


def test_cme_resolves_two_authoritative_resident_bindings_to_one_registered_executor():
    async def run():
        from r3a_runtime.cme import CME

        sample = fixture()
        sample["module_manifest"]["resident_executor"] = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                         "min_minor": 0, "max_minor": 0}}
        module = validate_module_manifest(sample["module_manifest"], sample["operation"],
                                          sample["source_manifest"])
        registered = SimpleNamespace(
            descriptor={"provider": sample["operation"]["provider"]},
            legacy_manifest={"module_manifest": sample["module_manifest"],
                             "configuration_schema": sample["source_manifest"]["configuration_schema"]})
        projection = ProviderProcessManager._manifest(object.__new__(ProviderProcessManager), registered)
        registry_row = {"module_id": module["module_id"], "module_version": module["module_version"],
                        "lifecycle_state": "ACTIVE", "manifest": projection}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "bootstrap.json"
            config_path.write_text("{}", encoding="utf-8")
            bindings = []
            associations = {}
            for resident_id in ("resident:alpha", "resident:beta"):
                executor_config = root / f"{resident_id}.json"
                executor_config.write_text('{"resident_model_route_id":"route.alpha"}', encoding="utf-8")
                association = {"authority": "hr.directory", "record_id": resident_id,
                               "record_revision": f"directory-{resident_id}"}
                associations[resident_id] = association
                bindings.append({
                    "contract_id": "r3a.resident.module-binding", "contract_version": "1.0.0",
                    "resident_id": resident_id, "module_id": module["module_id"],
                    "module_version": module["module_version"],
                    "artifact_digest": module["artifact"]["artifact_sha256"],
                    "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                                 "min_minor": 0, "max_minor": 0},
                    "binding_revision": f"binding-{resident_id}",
                    "configuration_ref": executor_config.name,
                    "configuration_revision": hashlib.sha256(executor_config.read_bytes()).hexdigest(),
                    "identity_association": association})
            profiles = {}
            for resident_id in associations:
                profiles[resident_id] = ({
                    "contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
                    "resident_id": resident_id, "display_name": resident_id,
                    "office_id": f"office-{resident_id}", "office_role": "reviewer",
                    "directory_evidence": {"source_id": "hr.directory", "snapshot_sha256": "a" * 64,
                                            "observed_at": datetime.now(timezone.utc).isoformat()},
                    "model_route_id": "route.alpha", "config_revision": "c" * 64},
                    SimpleNamespace(route_id="route.alpha"), associations[resident_id])

            cme = object.__new__(CME)
            cme.settings = SimpleNamespace(
                resident_module_bindings=tuple(bindings), source_path=config_path,
                source_digest="c" * 64,
                capability_registry=SimpleNamespace(
                    discover=Mock(side_effect=lambda **kwargs:
                        [{"descriptor": {**sample["operation"],
                                         "lifecycle": {"desired_state": "enabled"}}}]
                        if kwargs.get("include_versions") else []),
                    resolve_provider=Mock(return_value=SimpleNamespace(
                        descriptor={"operation_id": sample["operation"]["operation_id"],
                                    "provider": sample["operation"]["provider"]}))))
            cme.store = SimpleNamespace(rows=AsyncMock(return_value=[registry_row]),
                                        record_progress=AsyncMock(), finish_activity=AsyncMock())
            cme.module_id = "resident.grace"
            cme.module_version = "0.0.0"
            cme._resolve_resident_execution_profile = AsyncMock(
                side_effect=lambda resident_id, **_kwargs: profiles[resident_id])
            cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
                decision_id="decision", audit_event_id="audit", policy_revision="policy"))
            cme.provider_runtime = SimpleNamespace(invoke=AsyncMock(return_value={
                "action": "final", "decision": {"status": "healthy"}}))
            resolved = []
            for index, resident_id in enumerate(associations, start=1):
                activity = {"activity_id": f"00000000-0000-4000-8000-00000000010{index}",
                            "attempt_id": f"00000000-0000-4000-8000-00000000020{index}",
                            "idempotency_key": f"resident:{resident_id}",
                            "activity_type": "resident.review",
                            "input": {"resident_id": resident_id,
                                      "objective": "Inspect the assigned request.",
                                      "correlation_id": f"correlation:{resident_id}"}}
                resolved.append(await cme._resolve_resident_executor(activity))
                await cme._run_bound_resident_activity(activity, resolved[-1])
            assert [item["execution_profile"]["resident_id"] for item in resolved] == [
                "resident:alpha", "resident:beta"]
            assert [item["binding_revision"] for item in resolved] == [
                "binding-resident:alpha", "binding-resident:beta"]
            assert [item["module_id"] for item in resolved] == [module["module_id"]] * 2
            calls = cme.provider_runtime.invoke.await_args_list
            assert len(calls) == 2
            assert {call.args[1]["request"]["payload"]["resident_id"] for call in calls} == {
                "resident:alpha", "resident:beta"}
            assert cme.store.finish_activity.await_count == 2
            assert cme._authorization_decision.await_count == 2

            cme._authorization_decision.side_effect = PermissionError("resident execution grant missing")
            with pytest.raises(PermissionError, match="resident execution grant missing"):
                await cme._resolve_resident_executor({
                    "activity_id": "00000000-0000-4000-8000-000000000111",
                    "attempt_id": "00000000-0000-4000-8000-000000000211",
                    "idempotency_key": "review:resident:alpha",
                    "input": {"resident_id": "resident:alpha"}})
            assert cme.provider_runtime.invoke.await_count == 2

    asyncio.run(run())


def test_cme_rejects_stale_directory_association_before_authorization():
    async def run():
        from r3a_runtime.cme import CME

        sample = fixture()
        sample["module_manifest"]["resident_executor"] = {
            "contract_id": "r3a.resident.executor", "contract_version": "1.0.0",
            "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                         "min_minor": 0, "max_minor": 0}}
        module = validate_module_manifest(sample["module_manifest"], sample["operation"],
                                          sample["source_manifest"])
        registered = SimpleNamespace(
            descriptor={"provider": sample["operation"]["provider"]},
            legacy_manifest={"module_manifest": sample["module_manifest"],
                             "configuration_schema": sample["source_manifest"]["configuration_schema"]})
        projection = ProviderProcessManager._manifest(object.__new__(ProviderProcessManager), registered)
        association = {"authority": "hr.directory", "record_id": "resident:alpha",
                       "record_revision": "directory-current"}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_path = root / "bootstrap.json"
            config_path.write_text("{}", encoding="utf-8")
            executor_config = root / "executor.json"
            executor_config.write_text("{}", encoding="utf-8")
            binding = {"contract_id": "r3a.resident.module-binding", "contract_version": "1.0.0",
                       "resident_id": "resident:alpha", "module_id": module["module_id"],
                       "module_version": module["module_version"],
                       "artifact_digest": module["artifact"]["artifact_sha256"],
                       "execution_contract_range": {"contract_id": "r3a.resident.execution", "major": 1,
                                                    "min_minor": 0, "max_minor": 0},
                       "binding_revision": "binding-alpha", "configuration_ref": "executor.json",
                       "configuration_revision": hashlib.sha256(executor_config.read_bytes()).hexdigest(),
                       "identity_association": {**association, "record_revision": "directory-stale"}}
            profile = ({"contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
                        "resident_id": "resident:alpha", "display_name": "Alpha", "office_id": "office-a",
                        "office_role": "reviewer", "directory_evidence": {
                            "source_id": "hr.directory", "snapshot_sha256": "a" * 64,
                            "observed_at": datetime.now(timezone.utc).isoformat()},
                        "model_route_id": "route.alpha", "config_revision": "c" * 64},
                       SimpleNamespace(route_id="route.alpha"), association)
            cme = object.__new__(CME)
            cme.settings = SimpleNamespace(resident_module_bindings=(binding,), source_path=config_path,
                                           source_digest="c" * 64)
            cme.store = SimpleNamespace(rows=AsyncMock(return_value=[{
                "module_id": module["module_id"], "module_version": module["module_version"],
                "manifest": projection, "lifecycle_state": "ACTIVE"}]))
            cme.module_id = "resident.grace"
            cme._resolve_resident_execution_profile = AsyncMock(return_value=profile)
            cme._authorization_decision = AsyncMock()
            activity = {"activity_id": "00000000-0000-4000-8000-000000000301",
                        "attempt_id": "00000000-0000-4000-8000-000000000302",
                        "idempotency_key": "resident:alpha", "input": {"resident_id": "resident:alpha"}}
            with pytest.raises(ModuleExtensionError, match="identity/HR association"):
                await cme._resolve_resident_executor(activity)
            cme._authorization_decision.assert_not_awaited()

    asyncio.run(run())
