"""Registered Engineering handler workflow parity through the published v1.1 socket."""
from __future__ import annotations

import hashlib
import json
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from r3a_plugins.engineering_workspace.provider import create_provider
from r3a_runtime.cme import CME
from r3a_runtime.module_extensions import validate_activity_handler


ACTIVITY = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"
CORRELATION = "33333333-3333-4333-8333-333333333333"
ASSIGNMENT = {
    "contract_id": "r3a.engineering-assignment", "contract_version": "1.0.0",
    "repository": "ppow1/R3", "baseline_ref": "main", "workspace_id": "workspace:test",
    "allowed_paths": ["artifacts/**"], "command_profiles": ["json-check"],
    "criteria": [{"criterion_id": "artifact_matches_proposal", "type": "json_fields_equal",
                   "artifact_path": "artifacts/result.json", "bindings": [
                       {"artifact_pointer": "/operation_id", "source": "operation",
                        "source_pointer": "/operation_id"},
                       {"artifact_pointer": "/inputs/path", "source": "operation",
                        "source_pointer": "/inputs/path"}]}],
    "verifier_id": "verifier.json-fields", "verifier_version": "1.0.0",
    "policy_revision": "engineering-policy-r1",
}


def _resident_continuation(action_id: str, decision: dict, *, activity_id: str) -> dict:
    return {"contract_id": "r3a.activity-handler.continuation", "contract_version": "1.0.0",
            "action_id": action_id, "outcome": "succeeded",
            "invocation": {"activity_id": activity_id, "state": "COMPLETED",
                           "result": {"decision": decision,
                                      "model": {"provider": "fixture", "name": "fixture-model",
                                                "request_ref": "req-1", "result_ref": "res-1",
                                                "result_sha256": "a" * 64}}},
            "evidence": [], "error": None}


def _proposal(content: str) -> dict:
    return {"status": "healthy", "recommended_action": json.dumps({
        "operation_id": "engineering.workspace.apply_patch", "contract_version": "1.0.0",
        "target": {"workspace_id": "workspace:test"},
        "inputs": {"path": "artifacts/result.json", "content": content},
        "verification_plan": {"summary": "Compare fields against the authorized operation."}},
        separators=(",", ":")), "assessment": "The operation is bounded and matches the assignment.",
        "evidence_refs": []}


def _handler_payload(principal: str = "resident:grace") -> dict:
    return {"contract_id": "r3a.activity-handler.request", "contract_version": "1.1.0",
            "activity_id": ACTIVITY, "attempt_id": ATTEMPT, "correlation_id": CORRELATION,
            "activity_type": "engineering.execute", "idempotency_key": "engineering-test-1",
            "execution_principal": principal, "input": {"objective": "Create the assigned JSON artifact.",
                                                            "engineering_assignment": ASSIGNMENT},
            "evidence": [], "checkpoint": {}, "continuation": None, "action_history": [],
            "handler": {"handler_id": "r3a.engineering.workflow", "handler_version": "1.0.0",
                        "module_id": "r3a.isolated_workspace", "module_version": "1.1.0",
                        "artifact_digest": "0" * 64},
            "declared_action_capabilities": ["engineering.workspace.apply_patch"],
            "authorized_capabilities": []}


def test_registered_handler_proposal_write_independent_verification_and_assessment(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = create_provider({"workspace_root": str(workspace)})
    payload = _handler_payload()
    content = json.dumps({"operation_id": "engineering.workspace.apply_patch",
                          "inputs": {"path": "artifacts/result.json"}}, separators=(",", ":"))

    first = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                            context={"config_revision": "cfg-r1"})
    assert first["outcome"] == "action_required"
    proposal_action = first["action"]
    assert proposal_action["contract_id"] == "r3a.activity-handler.objective-submission"
    assert proposal_action["target_resident_id"] == "resident:grace"

    payload.update(checkpoint=first["checkpoint"],
                   continuation=_resident_continuation(proposal_action["action_id"], _proposal(content),
                                                       activity_id="44444444-4444-4444-8444-444444444444"))
    second = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                             context={"config_revision": "cfg-r1"})
    assert second["outcome"] == "action_required"
    action = second["action"]
    assert action["contract_id"] == "r3a.activity-handler.action"
    assert action["durable_work"]["record"]["workspace_id"] == "workspace:test"

    operation_receipt = provider.invoke(action["input"], context={
        "effect_class": "isolated_write", "target": action["target"],
        "work_order": action["durable_work"]["record"], "invocation_id": "invocation-1"})
    assert operation_receipt["replayed"] is False
    invocation = {"outcome": "SUCCEEDED", "attempt_id": "55555555-5555-4555-8555-555555555555",
                  "authorization": {"decision_id": "66666666-6666-4666-8666-666666666666",
                                    "audit_event_id": "77777777-7777-4777-8777-777777777777",
                                    "provider_id": "fixture-grants", "policy_revision": "policy-r1"},
                  "evidence": [{"evidence_ref": "workspace:artifacts/result.json",
                                "sha256": hashlib.sha256(content.encode()).hexdigest()}]}
    payload.update(checkpoint=second["checkpoint"],
                   continuation={"contract_id": "r3a.activity-handler.continuation", "contract_version": "1.0.0",
                                 "action_id": action["action_id"], "outcome": "succeeded",
                                 "invocation": invocation, "evidence": invocation["evidence"], "error": None})
    third = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                            context={"config_revision": "cfg-r1"})
    assert third["outcome"] == "action_required"
    verification = third["checkpoint"]["verification"]
    assert verification["outcome"] == "PASS"
    assert verification["verifier_id"] == ASSIGNMENT["verifier_id"]

    assessment_action = third["action"]
    payload.update(checkpoint=third["checkpoint"],
                   continuation=_resident_continuation(
                       assessment_action["action_id"],
                       {"status": "healthy", "assessment": "The evidence is ready for verification.",
                        "recommended_action": "ready_for_verification", "evidence_refs": []},
                       activity_id="88888888-8888-4888-8888-888888888888"))
    complete = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                               context={"config_revision": "cfg-r1"})
    assert complete["outcome"] == "completed"
    assert complete["verification"]["outcome"] == "PASS"
    assert complete["work_order"]["resident_id"] == "resident:grace"
    assert (workspace / "artifacts/result.json").read_text() == content


def test_handler_checkpoint_replay_keeps_stable_nonprimary_resident_action(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = create_provider({"workspace_root": str(workspace)})
    payload = _handler_payload(principal="resident:vicky")
    first = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                            context={"config_revision": "cfg-r1"})
    replay = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                             context={"config_revision": "cfg-r1"})
    assert replay["action"]["action_id"] == first["action"]["action_id"]
    assert replay["action"]["target_resident_id"] == "resident:vicky"


def test_independent_verifier_failure_requests_one_correction_then_preserves_blocked_result(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    provider = create_provider({"workspace_root": str(workspace)})
    payload = _handler_payload()
    first = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                            context={"config_revision": "cfg-r1"})
    proposal_action = first["action"]
    payload.update(checkpoint=first["checkpoint"],
                   continuation=_resident_continuation(
                       proposal_action["action_id"], _proposal("{}"),
                       activity_id="44444444-4444-4444-8444-444444444444"))
    second = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                             context={"config_revision": "cfg-r1"})
    action = second["action"]
    write_receipt = provider.invoke(action["input"], context={
        "effect_class": "isolated_write", "target": action["target"],
        "work_order": action["durable_work"]["record"], "invocation_id": "invocation-fail"})
    invocation = {"outcome": "SUCCEEDED", "attempt_id": "55555555-5555-4555-8555-555555555555",
                  "authorization": {"decision_id": "66666666-6666-4666-8666-666666666666",
                                    "audit_event_id": "77777777-7777-4777-8777-777777777777",
                                    "provider_id": "fixture-grants", "policy_revision": "policy-r1"},
                  "evidence": [{"evidence_ref": "workspace:artifacts/result.json",
                                "sha256": write_receipt["sha256"]}]}
    payload.update(checkpoint=second["checkpoint"],
                   continuation={"contract_id": "r3a.activity-handler.continuation", "contract_version": "1.0.0",
                                 "action_id": action["action_id"], "outcome": "succeeded",
                                 "invocation": invocation, "evidence": invocation["evidence"], "error": None})
    third = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                            context={"config_revision": "cfg-r1"})
    assert third["checkpoint"]["verification"]["outcome"] == "FAIL"
    assert third["action"]["contract_id"] == "r3a.activity-handler.objective-submission"
    payload.update(checkpoint=third["checkpoint"],
                   continuation=_resident_continuation(
                       third["action"]["action_id"],
                       {"status": "healthy", "assessment": "The failure is confirmed; attempt one safe correction.",
                        "recommended_action": "ready_for_verification", "evidence_refs": []},
                       activity_id="99999999-9999-4999-8999-999999999999"))
    correction = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                                 context={"config_revision": "cfg-r1"})
    assert correction["action"]["contract_id"] == "r3a.activity-handler.objective-submission"
    payload.update(checkpoint=correction["checkpoint"],
                   continuation=_resident_continuation(
                       correction["action"]["action_id"],
                       {"status": "blocked", "assessment": "No safe correction is available.",
                        "recommended_action": "blocked", "evidence_refs": []},
                       activity_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"))
    blocked = provider.invoke({"request": {"operation": "execute", "payload": payload}},
                             context={"config_revision": "cfg-r1"})
    assert blocked["outcome"] == "blocked"
    assert blocked["checkpoint"]["phase"] == "correction_blocked"


def test_cme_runs_registered_engineering_handler_through_v11_action_continuation(tmp_path: Path):
    """Exercise CME handler discovery payload/loop and the real Engineering provider interface."""
    async def exercise():
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        module = create_provider({"workspace_root": str(workspace)})
        manifest = json.loads((Path(__file__).parents[1] /
                               "r3a_plugins/engineering_workspace/manifest.json").read_text())
        module_manifest = manifest["module_manifest"]
        handler = validate_activity_handler(module_manifest["activity_handler"])
        resolved = {"handler": handler,
                    "module": {"manifest": module_manifest},
                    "module_id": module_manifest["module_id"],
                    "module_version": module_manifest["module_version"],
                    "artifact_digest": module_manifest["artifact"]["artifact_sha256"]}
        operation = manifest["operation"]
        cme = object.__new__(CME)
        cme.module_id = "r3a.cme"
        cme.settings = SimpleNamespace(source_digest="cfg-r1",
                                       capability_registry=SimpleNamespace(
                                           resolve=lambda operation_id, version: SimpleNamespace(
                                               descriptor=operation)))
        cme.store = SimpleNamespace(record_progress=AsyncMock(), finish_activity=AsyncMock(),
                                    block_activity=AsyncMock())
        cme._authorization_decision = AsyncMock(return_value=SimpleNamespace(
            decision_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            audit_event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", policy_revision="policy-r1"))
        content = json.dumps({"operation_id": "engineering.workspace.apply_patch",
                              "inputs": {"path": "artifacts/result.json"}}, separators=(",", ":"))
        proposal = _proposal(content)
        objective_count = 0

        async def resident_continuation(_activity, _resolved, _handler, action, _pending):
            nonlocal objective_count
            objective_count += 1
            decision = (proposal if objective_count == 1 else {
                "status": "healthy", "assessment": "The verifier and execution evidence pass.",
                "recommended_action": "ready_for_verification", "evidence_refs": []})
            child_id = ("cccccccc-cccc-4ccc-8ccc-cccccccccccc" if objective_count == 1
                        else "dddddddd-dddd-4ddd-8ddd-dddddddddddd")
            return _resident_continuation(action["action_id"], decision, activity_id=child_id)

        cme._dispatch_handler_objective_submission = AsyncMock(side_effect=resident_continuation)

        async def registered_call(module_id, module_version, operation_name, payload, **_kwargs):
            assert (module_id, module_version, operation_name) == (
                "r3a.isolated_workspace", "1.1.0", "execute")
            result = module.invoke({"request": {"operation": "execute", "payload": payload}},
                                   context={"config_revision": "cfg-r1"})
            return {"result": result}

        async def canonical_invoke(request, *, _handler_work_item, _handler_action):
            assert _handler_action is True
            assert _handler_work_item["handler"]["module_id"] == "r3a.isolated_workspace"
            output = module.invoke(request["input"], context={
                "effect_class": "isolated_write", "target": request["target"],
                "work_order": _handler_work_item["record"],
                "invocation_id": request["invocation_id"]})
            return {"contract_id": "r3a.capability-invocation.v1", "contract_version": "1.1.0",
                    "invocation_id": request["invocation_id"], "operation_id": request["operation_id"],
                    "operation_contract_version": request["operation_contract_version"],
                    "activity_id": request["activity_id"], "attempt_id": request["attempt_id"],
                    "correlation_id": request["correlation_id"], "outcome": "SUCCEEDED",
                    "attempt_id": request["attempt_id"],
                    "authorization": {"decision_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
                                      "audit_event_id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                                      "provider_id": "fixture-grants", "policy_revision": "policy-r1"},
                    "evidence": [{"evidence_ref": "workspace:artifacts/result.json",
                                  "sha256": output["sha256"]}], "output": output}

        cme._registered_module_call = registered_call
        cme.invoke_capability = canonical_invoke
        activity = {"activity_id": ACTIVITY, "attempt_id": ATTEMPT,
                    "activity_type": "engineering.execute", "idempotency_key": "engineering-cme-test",
                    "checkpoint": {}, "input": {"objective": "Create and independently verify the assigned JSON artifact.",
                                                  "activity_input": {"resident_id": "resident:vicky",
                                                                     "engineering_assignment": ASSIGNMENT}}}
        await cme._run_registered_activity(activity, resolved)
        cme.store.finish_activity.assert_awaited_once()
        cme._authorization_decision.assert_awaited_once()
        assert cme._authorization_decision.await_args.kwargs["resident_id"] == "resident:vicky"
        cme._dispatch_handler_objective_submission.assert_awaited()
        result = cme.store.finish_activity.await_args.args[1]["result"]
        assert result["outcome"] == "completed"
        assert result["verification"]["outcome"] == "PASS"
        assert (workspace / "artifacts/result.json").read_text() == content

    asyncio.run(exercise())
