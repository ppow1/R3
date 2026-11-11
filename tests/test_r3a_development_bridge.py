"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_development_bridge.py
Component: TEST-R3A-DEVELOPMENT-BRIDGE
File Revision: 1.0.0
Created: 2026-11-11T14:22:00Z
Created By: Codex GPT-6
Purpose: Verify the Bridge v3 provider against canonical manifest/activity contracts and exercise mocked transport routing, receipts, crash recovery, and deduplication
Execution Model: Isolated unit/contract tests; temporary SQLite cache and mocked host transport only
Observability: Route decision states, transport invocation count, receipt identity, cache recovery, and manifest/lifecycle contract assertions
Dependencies: r3a_plugins.development_bridge; R3A module/capability/activity contracts
Authority: Step 11 dispatch 6798229653; no live host, grant, or service authority
Changed: 2026-11-11T14:22:00Z | R3-BRIDGE-V3-STEP11 | Codex GPT-6 | Add canonical module and transport regression tests
Supersedes: None
Contracts: r3a.module-manifest.v1@1.2.0; r3a.capability-operation.v1; r3a.activity-handler.v1.1; module.lifecycle v2; activity.generic v1
Tests: python3 -m pytest -q tests/test_r3a_development_bridge.py
History/Predecessor: None; new file
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio

import pytest

from r3a_plugins.development_bridge.provider import (
    DeliveryReceipt,
    TransportAttemptCache,
    create_provider,
    deliver_ready,
    route_batch,
)
from r3a_runtime.capability_contracts import CapabilityRegistry, operation_from_manifest
from r3a_runtime.capability_worker import CapabilityWorker
from r3a_runtime.config import load_settings
from r3a_runtime.module_extensions import resolve_activity_handler, validate_activity_handler_payload
from r3a_runtime.provider_runtime import ProviderProcessManager
from tests.test_r3a_module_extensions import bootstrap_config


PACKAGE = Path(__file__).parents[1] / "r3a_plugins" / "development_bridge"


def _manifest() -> dict:
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256((PACKAGE / "provider.py").read_bytes()).hexdigest()
    assert manifest["artifact_sha256"] == digest
    assert manifest["provider"]["artifact_sha256"] == digest
    assert manifest["module_manifest"]["artifact"]["artifact_sha256"] == digest
    return manifest


def _dispatch(comment_id: int = 100, *, target: str = "Live Modular", mode: str = "QUEUE") -> dict:
    return {"repository": "ppow1/R3", "issue_number": 61, "comment_id": comment_id,
            "target": target, "mode": mode, "summary": f"planned task {comment_id}"}


class MockTransport:
    def __init__(self, *, safe_steer: bool = False, outcomes=()):
        self.supports_safe_steer = safe_steer
        self.outcomes = list(outcomes)
        self.deliveries = []

    def deliver(self, target, dispatch, *, idempotency_key):
        self.deliveries.append((target, dispatch.source_key, idempotency_key))
        return self.outcomes.pop(0) if self.outcomes else DeliveryReceipt("confirmed", "mock:receipt-1")


def test_manifest_discovers_disabled_provider_and_reuses_cme_module_activity_contracts(monkeypatch):
    manifest = _manifest()
    assert manifest["module_manifest"]["contract_version"] == "1.1.0"
    assert manifest["operation"]["lifecycle"]["desired_state"] == "disabled"
    assert manifest["module_manifest"]["binding"]["contract_id"] == "r3a.capability-provider.v1"
    assert manifest["module_manifest"]["activity_handler"]["contract_version"] == "1.0.0"
    descriptor = operation_from_manifest(manifest)
    config = json.loads((PACKAGE / "config.example.json").read_text(encoding="utf-8"))

    with TemporaryDirectory() as temporary:
        cache_path = str(Path(temporary) / "transport-attempts.sqlite3")
        monkeypatch.setenv("R3A_BRIDGE_TRANSPORT_STATE_PATH", cache_path)
        registry = CapabilityRegistry()
        registered = registry.register(descriptor, config, legacy_manifest=manifest)
        discovered = registry.discover(include_disabled=True)
        assert len(discovered) == 1
        assert discovered[0]["descriptor"]["lifecycle"]["desired_state"] == "disabled"
        assert "authorized" not in discovered[0]["registry_observation"]
        assert isinstance(registered.load_provider(), type(create_provider(config)))

        provider_manifest = ProviderProcessManager._manifest(
            object.__new__(ProviderProcessManager), registered)
        assert provider_manifest["manifest_contract"] == "r3a.module-manifest.v1@1.1.0"
        handler = resolve_activity_handler([{
            "module_id": provider_manifest["module_id"],
            "module_version": provider_manifest["module_version"],
            "artifact_digest": provider_manifest["artifact_digest"],
            "manifest": provider_manifest,
            "lifecycle_state": "ACTIVE",
        }], "bridge.dispatch.plan")["handler"]
        request = {"dispatches": [_dispatch()], "sessions": [{"target": "Live Modular", "state": "AVAILABLE"}]}
        handler_result = create_provider(config).invoke({
            "input": request,
            "request": {"operation": "execute", "payload": {
                "contract_id": "r3a.activity-handler.request", "input": request,
                "activity_id": "activity-fixture", "attempt_id": "attempt-fixture"}},
        }, context={"dispatcher": "CME"}).output
        validate_activity_handler_payload(handler, "result", handler_result)
        validate_activity_handler_payload(handler, "progress", handler_result["progress"])
        validate_activity_handler_payload(handler, "checkpoint", handler_result["checkpoint"])
        assert handler_result["outcome"] == "completed"
        assert handler_result["decisions"][0]["state"] == "READY"


def test_digest_pinned_provider_obeys_existing_cme_worker_lifecycle_and_activity_call(monkeypatch):
    manifest = _manifest()
    config = json.loads((PACKAGE / "config.example.json").read_text(encoding="utf-8"))

    async def exercise_worker():
        worker = CapabilityWorker(
            manifest["provider"]["provider_id"], manifest["provider"]["provider_version"],
            manifest["provider"]["entrypoint"], PACKAGE / "provider.py", manifest["artifact_sha256"])
        hello = await worker.handle("hello", {})
        assert hello["contract_id"] == "r3a.capability-provider.v1"
        await worker.handle("prepare", {"configuration": config, "pinned_artifacts": {}})
        await worker.handle("activate", {})
        health = await worker.handle("health", {})
        assert health == {"state": "ACTIVE", "health": "healthy"}
        payload = {"dispatches": [_dispatch(120)],
                   "sessions": [{"target": "Live Modular", "state": "AVAILABLE"}]}
        response = await worker.handle("execute", {
            "arguments": {"input": payload}, "context": {"dispatcher": "CME"}})
        assert response["provider_result"]["output"]["decisions"][0]["state"] == "READY"
        checkpoint = await worker.handle("checkpoint", {})
        assert checkpoint["checkpointed"] is True
        assert (await worker.handle("stop", {}))["stopped"] is True

    with TemporaryDirectory() as temporary:
        monkeypatch.setenv("R3A_BRIDGE_TRANSPORT_STATE_PATH", str(Path(temporary) / "attempts.sqlite3"))
        asyncio.run(exercise_worker())


def test_external_capability_operations_loader_discovers_bridge_without_core_changes(tmp_path):
    bootstrap = bootstrap_config(tmp_path, include_binding=False)
    bridge_package = tmp_path / "development_bridge"
    shutil.copytree(PACKAGE, bridge_package)
    value = json.loads(bootstrap.read_text(encoding="utf-8"))
    value["module"]["capabilities"].append("development.bridge.dispatch.plan")
    value["capability_operations"].append({
        "manifest": str(bridge_package / "manifest.json"),
        "configuration": str(bridge_package / "config.example.json"),
    })
    bootstrap.write_text(json.dumps(value), encoding="utf-8")

    settings = load_settings(bootstrap)
    discovered = settings.capability_registry.discover(include_disabled=True, include_versions=True)
    operation = next(item["descriptor"] for item in discovered
                     if item["descriptor"]["operation_id"] == "development.bridge.dispatch.plan")
    assert operation["provider"]["provider_id"] == "r3a.development-bridge"
    assert operation["contract_version"] == "1.0.0"
    assert operation["lifecycle"]["desired_state"] == "disabled"


def test_batch_routes_all_targets_and_fails_closed_for_unknown_or_ambiguous_target():
    decisions = route_batch(
        [_dispatch(100), _dispatch(101, target="Coordinator"), _dispatch(102, target="Missing")],
        [{"target": "Live Modular", "state": "AVAILABLE"},
         {"target": "Coordinator", "state": "BUSY"}],
    )
    assert [item.state for item in decisions] == ["READY", "QUEUED", "REJECTED"]
    assert decisions[2].reason == "target is not uniquely registered"
    ambiguous = route_batch([_dispatch()], [{"target": "Live Modular", "state": "AVAILABLE"},
                                          {"target": "Live Modular", "state": "BUSY"}])
    assert ambiguous[0].state == "REJECTED"


def test_same_poll_duplicate_and_priority_are_not_delivered():
    duplicate_batch = route_batch([_dispatch(105), _dispatch(105),
                                   _dispatch(106, mode="PRIORITY")],
                                  [{"target": "Live Modular", "state": "AVAILABLE"}])
    assert [item.state for item in duplicate_batch] == ["READY", "DUPLICATE", "REVIEW_REQUIRED"]
    with TemporaryDirectory() as temporary:
        transport = MockTransport()
        delivered = deliver_ready(duplicate_batch, transport,
                                  TransportAttemptCache(Path(temporary) / "attempts.sqlite3"))
    assert [item.state for item in delivered] == ["DELIVERED", "DUPLICATE", "REVIEW_REQUIRED"]
    assert len(transport.deliveries) == 1


def test_receipt_and_deduplication_survive_provider_cache_reopen():
    with TemporaryDirectory() as temporary:
        cache_path = Path(temporary) / "attempts.sqlite3"
        transport = MockTransport(outcomes=[DeliveryReceipt("confirmed", "github:receipt-abc")])
        decision = route_batch([_dispatch(110)], [{"target": "Live Modular", "state": "AVAILABLE"}])[0]
        first = deliver_ready([decision], transport, TransportAttemptCache(cache_path))[0]
        replay = deliver_ready([decision], transport, TransportAttemptCache(cache_path))[0]
        assert first.state == "DELIVERED"
        assert first.receipt_ref == "github:receipt-abc"
        assert replay.state == "DELIVERED"
        assert replay.receipt_ref == "github:receipt-abc"
        assert "duplicate suppressed" in replay.reason
        assert len(transport.deliveries) == 1
        assert cache_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("changes", [
    {"target": "Coordinator"},
    {"mode": "STEER"},
    {"summary": "different immutable payload"},
])
def test_replay_with_changed_target_mode_or_payload_fails_closed_without_receipt(changes):
    with TemporaryDirectory() as temporary:
        cache = TransportAttemptCache(Path(temporary) / "attempts.sqlite3")
        transport = MockTransport(safe_steer=True,
                                  outcomes=[DeliveryReceipt("confirmed", "receipt:Live-Modular")])
        original = _dispatch(130)
        first_decision = route_batch([original], [{"target": "Live Modular", "state": "AVAILABLE"}])[0]
        first = deliver_ready([first_decision], transport, cache)[0]
        assert first.state == "DELIVERED"
        assert first.receipt_ref == "receipt:Live-Modular"

        replay_payload = {**original, **changes}
        replay_target = replay_payload["target"]
        replay_session_state = "BUSY" if replay_payload["mode"] == "STEER" else "AVAILABLE"
        replay_decision = route_batch([replay_payload], [
            {"target": replay_target, "state": replay_session_state}
        ], safe_steer_available=replay_payload["mode"] == "STEER")[0]
        replay = deliver_ready([replay_decision], transport, cache)[0]

        assert replay.state == "IDEMPOTENCY_CONFLICT"
        assert replay.receipt_ref is None
        assert len(transport.deliveries) == 1
        assert transport.deliveries[0][0] == "Live Modular"


def test_legacy_cache_rows_without_fingerprint_fail_closed_after_schema_upgrade():
    with TemporaryDirectory() as temporary:
        cache_path = Path(temporary) / "attempts.sqlite3"
        decision = route_batch([_dispatch(131)], [
            {"target": "Live Modular", "state": "AVAILABLE"}
        ])[0]
        connection = sqlite3.connect(cache_path)
        connection.execute("""CREATE TABLE transport_attempts (
            idempotency_key TEXT PRIMARY KEY,
            target TEXT NOT NULL,
            mode TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('ATTEMPTING','DELIVERED','UNCERTAIN','FAILED')),
            receipt_ref TEXT,
            reason TEXT,
            updated_at TEXT NOT NULL
        )""")
        connection.execute("PRAGMA user_version=1")
        connection.execute(
            "INSERT INTO transport_attempts VALUES (?,?,?,?,?,?,?)",
            (decision.idempotency_key, "Live Modular", "QUEUE", "DELIVERED",
             "legacy:receipt-for-unknown-payload", "legacy fixture", "2026-11-11T00:00:00+00:00"))
        connection.commit()
        connection.close()

        cache = TransportAttemptCache(cache_path)
        transport = MockTransport()
        replay = deliver_ready([decision], transport, cache)[0]

        assert replay.state == "IDEMPOTENCY_CONFLICT"
        assert replay.receipt_ref is None
        assert not transport.deliveries
        connection = sqlite3.connect(cache_path)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT dispatch_fingerprint FROM transport_attempts WHERE idempotency_key=?",
            (decision.idempotency_key,)).fetchone()[0] is None
        connection.close()


def test_cache_stores_dispatch_fingerprint_not_payload_text():
    with TemporaryDirectory() as temporary:
        cache_path = Path(temporary) / "attempts.sqlite3"
        dispatch = _dispatch(132)
        decision = route_batch([dispatch], [
            {"target": "Live Modular", "state": "AVAILABLE"}
        ])[0]
        delivered = deliver_ready([decision], MockTransport(), TransportAttemptCache(cache_path))[0]
        assert delivered.state == "DELIVERED"

        connection = sqlite3.connect(cache_path)
        fingerprint, target, mode = connection.execute(
            "SELECT dispatch_fingerprint,target,mode FROM transport_attempts WHERE idempotency_key=?",
            (decision.idempotency_key,)).fetchone()
        connection.close()

        canonical = json.dumps({
            "repository": dispatch["repository"],
            "issue_number": dispatch["issue_number"],
            "comment_id": dispatch["comment_id"],
            "target": dispatch["target"],
            "mode": dispatch["mode"],
            "summary": dispatch["summary"],
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        assert fingerprint == hashlib.sha256(canonical).hexdigest()
        assert target == dispatch["target"]
        assert mode == dispatch["mode"]
        assert dispatch["summary"] not in fingerprint


def test_crash_during_attempt_becomes_uncertain_and_requires_explicit_reconciliation():
    with TemporaryDirectory() as temporary:
        cache_path = Path(temporary) / "attempts.sqlite3"
        decision = route_batch([_dispatch(111)], [{"target": "Live Modular", "state": "AVAILABLE"}])[0]
        first_cache = TransportAttemptCache(cache_path)
        claimed, _ = first_cache.begin(decision)
        assert claimed

        restarted_cache = TransportAttemptCache(cache_path)
        transport = MockTransport()
        replay = deliver_ready([decision], transport, restarted_cache)[0]
        assert replay.state == "UNCERTAIN"
        assert not transport.deliveries
        reconciled = restarted_cache.reconcile(
            decision.idempotency_key, DeliveryReceipt("confirmed", "operator:evidence-1"))
        assert reconciled["state"] == "DELIVERED"
        suppressed = deliver_ready([decision], transport, restarted_cache)[0]
        assert suppressed.state == "DELIVERED"
        assert len(transport.deliveries) == 0


def test_steer_requires_explicit_safe_transport_and_adapter_exceptions_are_uncertain():
    busy = [{"target": "Live Modular", "state": "BUSY"}]
    steer = _dispatch(112, mode="STEER")
    blocked = route_batch([steer], busy)[0]
    assert blocked.state == "STEER_PENDING"
    safe = route_batch([steer], busy, safe_steer_available=True)[0]
    assert safe.state == "READY"

    class BrokenTransport:
        supports_safe_steer = True

        def deliver(self, *_args, **_kwargs):
            raise TimeoutError("receipt outcome is unknown")

    with TemporaryDirectory() as temporary:
        result = deliver_ready([safe], BrokenTransport(),
                               TransportAttemptCache(Path(temporary) / "attempts.sqlite3"))[0]
        assert result.state == "UNCERTAIN"
        assert "reconcile before retry" in result.reason
