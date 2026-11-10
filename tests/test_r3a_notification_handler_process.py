"""
R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_notification_handler_process.py
Component: R3A-NOTIFICATION-HANDLER-PROCESS-REGRESSION
File Revision: 1.1.0
Created: 2026-11-10
Created By: Codex GPT-6
Purpose: Exercise the registered notification handler through CME dispatch and a real provider child process.
Execution Model: Isolated local provider process over the existing module protocol; no source database access.
Observability: Assert source provenance/idempotency, handler evidence/checkpoint, and blocked lifecycle semantics.
Dependencies: r3a_runtime.cme; r3a_runtime.capability_worker; notification activity-intake manifest.
Authority: Issue #48; generic module lifecycle and activity-handler contracts.
Changed: 2026-11-10T20:10:03Z | R3A-GENERIC-OBJECTIVE-CONTINUATION | R3A Coordinator | Exercise the notification objective action and durable disposition continuation in the provider child process.
Supersedes: None.
Contracts: r3a.activity-handler@1.1.0; r3a.activity-handler.objective-submission@1.0.0; r3a.module-manifest.v1@1.2.0; AP0-M1.
Tests: pytest -q tests/test_r3a_notification_handler_process.py.
History/Predecessor: New process-level regression for Issue #48 handler execute defect.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import multiprocessing
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_runtime.cme import CME
from r3a_runtime.module_extensions import resolve_activity_handler, validate_activity_handler_payload
from r3a_runtime.capability_worker import CapabilityWorker


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins" / "notification_source"


def _provider_child(connection, module_id: str, module_version: str, artifact: str, digest: str,
                    entrypoint: str, configuration: dict):
    """Run the real provider lifecycle in an isolated operating-system process."""
    worker = CapabilityWorker(module_id, module_version, entrypoint, Path(artifact), digest)
    asyncio.run(worker.handle("prepare", {"configuration": configuration, "pinned_artifacts": {}}))
    asyncio.run(worker.handle("activate", {}))
    while True:
        command, payload = connection.recv()
        try:
            result = asyncio.run(worker.handle(command, payload))
            connection.send((True, result))
            if command == "stop":
                break
        except Exception as exc:
            connection.send((False, f"{type(exc).__name__}: {exc}"))
    connection.close()


def test_registered_handler_executes_through_cme_and_provider_process():
    async def scenario():
        manifest = json.loads((PACKAGE / "manifest.activity-intake.json").read_text(encoding="utf-8"))
        artifact = PACKAGE / "intake.py"
        # The child process verifies exact bytes. The module identity digest is bound to
        # those bytes for this checkout, while deployed manifests pin canonical LF bytes.
        process_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        manifest["module_manifest"]["artifact"]["artifact_sha256"] = process_digest
        manifest["artifact_sha256"] = process_digest
        manifest["provider"]["artifact_sha256"] = process_digest
        manifest["operation"]["provider"]["artifact_sha256"] = process_digest
        module_manifest = manifest["module_manifest"]
        module_id, module_version = module_manifest["module_id"], module_manifest["module_version"]
        registry_row = {
            "module_id": module_id, "module_version": module_version,
            "lifecycle_state": "ACTIVE",
            "manifest": {"module_id": module_id, "module_version": module_version,
                         "artifact_digest": process_digest,
                         "capability_refs": module_manifest["capability_refs"],
                         "activity_handler": module_manifest["activity_handler"]},
        }
        resolved = resolve_activity_handler([registry_row], "notification.event.review")
        activity_id = str(uuid.uuid4())
        attempt_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        source_id = "r3a.institution-events"
        notification = {
            "contract_id": "r3a.notification-intake", "contract_version": "1.0.0",
            "source_id": source_id, "source_event_id": event_id, "event_id": event_id,
            "event_type": "process.failed", "correlation_id": correlation_id,
            "occurred_at": "2026-11-10T00:00:00Z", "received_at": "2026-11-10T00:00:01Z",
            "severity": "error", "payload_ref": f"r3a.institution_events/{event_id}",
            "provenance": {"store": "r3a.institution_events", "schema_version": 1,
                           "implementation_revision": "fixture-revision"},
            "evidence": {"subject_type": "process", "subject_id": "cme",
                         "prior_state": "RUNNING", "next_state": "FAILED",
                         "reason": "fixture failure", "outcome": "accepted",
                         "persisted_at": "2026-11-10T00:00:01Z", "source_evidence": {}},
        }
        source_evidence = {"source_id": f"notification:{source_id}:{event_id}",
                           "source_ref": notification["payload_ref"], "sha256": "a" * 64,
                           "provenance": "r3a.institution_events; fixture-revision"}
        idempotency_key = f"notification:{source_id}:{event_id}"
        activity = {
            "activity_id": activity_id, "attempt_id": attempt_id,
            "idempotency_key": idempotency_key, "activity_type": "notification.event.review",
            "input": {"resident_id": "resident.grace", "correlation_id": correlation_id,
                      "activity_input": {"event_kind": "notification", "notification": notification},
                      "activity_evidence": [source_evidence]},
            "checkpoint": {},
        }

        configuration = {"dsn_env": "R3A_NOTIFICATION_SOURCE_DSN",
                         "connect_timeout_seconds": 2, "statement_timeout_ms": 1000,
                         "source_id": source_id, "event_types": ["process.failed"]}
        process_context = multiprocessing.get_context("spawn")
        parent, child = process_context.Pipe()
        process = process_context.Process(
            target=_provider_child,
            args=(child, module_id, module_version, str(artifact), process_digest,
                  manifest["provider"]["entrypoint"], configuration))
        process.start()
        child.close()
        try:
            recorded_calls = []

            async def process_backed_call(_module_id, _version, operation, payload, **_kwargs):
                recorded_calls.append(payload)
                execute_payload = {"arguments": {"input": payload["input"],
                                                  "request": {"operation": operation,
                                                              "payload": payload}},
                                   "context": {"dispatcher": "CME",
                                               "activity_id": payload["activity_id"],
                                               "attempt_id": payload["attempt_id"],
                                               "correlation_id": payload["correlation_id"],
                                               "resident_id": "resident.grace",
                                               "handler": payload["handler"]}}
                await asyncio.to_thread(parent.send, (operation, execute_payload))
                success, response = await asyncio.to_thread(parent.recv)
                if not success:
                    raise RuntimeError(response)
                return {"result": response["provider_result"]["output"]}

            child_activity_id = str(uuid.uuid4())
            source_key = f"notification:{source_id}:{event_id}"
            cme = object.__new__(CME)
            cme.store = SimpleNamespace(rows=AsyncMock(return_value=[registry_row]),
                                        record_progress=AsyncMock(), block_activity=AsyncMock(),
                                        finish_activity=AsyncMock())
            cme.settings = SimpleNamespace(source_digest="notification-process-config")
            cme.module_id, cme.module_version = "resident.grace", "0.0.0"
            cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
                decision_id="decision", audit_event_id="audit", policy_revision="policy"))
            cme._registered_module_call = process_backed_call
            cme._dispatch_registered_handler_action = AsyncMock(return_value={
                "contract_id": "r3a.activity-handler.continuation", "contract_version": "1.0.0",
                "action_id": "notification.review." + hashlib.sha256(
                    f"{source_id}:{event_id}".encode()).hexdigest(),
                "outcome": "succeeded", "invocation": {"activity_id": child_activity_id,
                    "state": "COMPLETED", "result": {"decision": {
                        "status": "healthy", "assessment": "The event was reviewed against source evidence.",
                        "recommended_action": "No further action is indicated.",
                        "evidence_refs": [source_key]}}}, "evidence": [], "error": None})
            handler = await cme._registered_handler("notification.event.review")
            await cme._run_registered_activity(activity, handler)

            cme.store.finish_activity.assert_awaited_once()
            cme.store.block_activity.assert_not_awaited()
            cme.store.record_progress.assert_awaited()
            result = cme.store.finish_activity.await_args.args[1]["result"]
            checked = validate_activity_handler_payload(handler["handler"], "result", result)
            assert checked["outcome"] == "completed"
            assert checked["checkpoint"]["source_event_id"] == event_id
            assert checked["checkpoint"]["idempotency_key"] == idempotency_key
            assert checked["checkpoint"]["resident_activity_id"] == child_activity_id
            assert checked["checkpoint"]["assessment"] == "The event was reviewed against source evidence."
            assert checked["evidence"] == [source_evidence]
            assert checked["lifecycle_evidence"] == {
                "received": "grace.notification.received",
                "actionable": "grace.notification.actionable",
                "blocked": "grace.notification.blocked",
                "acknowledged": "grace.notification.acknowledged",
                "resolved": "grace.notification.resolved"}
            action = recorded_calls[0]
            assert action["execution_principal"] == "resident.grace"
            assert action["input"]["notification"]["source_event_id"] == event_id
            resumed = recorded_calls[1]
            assert resumed["continuation"]["action_id"] == cme._dispatch_registered_handler_action.await_args.args[3]["action"]["action_id"]
        finally:
            if process.is_alive():
                try:
                    parent.send(("stop", {}))
                    if parent.poll(3):
                        parent.recv()
                except (EOFError, BrokenPipeError, OSError):
                    process.terminate()
            process.join(3)
            if process.is_alive():
                process.terminate()
                process.join(3)
            parent.close()

    asyncio.run(scenario())
