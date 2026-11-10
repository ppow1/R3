"""
R3 CONTROLLED SOURCE
File: r3a_plugins/engineering_workspace/provider.py
Component: R3A-ENGINEERING-WORKSPACE-AND-HANDLER
File Revision: 2.0.0
Created: 2026-11-10
Created By: Codex GPT-6
Purpose: Provide the bounded workspace operation and the AP2 registered durable activity handler.
Execution Model: Digest-pinned CME child process; domain work continues through handler actions/checkpoints.
Observability: CME invocation receipts, handler checkpoints, proposal/work-order lineage, and verifier evidence.
Dependencies: r3a.activity-handler@1.1.0; r3a.activity-handler.action@1.0.0; objective-submission@1.0.0; AP2 engineering contracts.
Authority: Steward FS-03 remediation directive, Issue #43.
Changed: 2026-11-10 | FS-03-HANDLER | Move Engineering proposal/execution/verification policy from CME into registered Engineering module.
Supersedes: Revision 1.0.0 provider-only implementation.
Contracts: r3a.engineering-proposal.v1; r3a.engineering-work-order.v1; r3a.verification-result.v1; capability-operation.v1; activity-handler.v1.1.
Tests: tests/test_r3a_engineering_handler.py; tests/test_r3a_engineering.py; tests/test_r3a_engineering_autonomy.py.
History/Predecessor: Prior artifact digest 0b92d126ed33c972ddee65d67b94c57794bcf64122ebe304c8a0e1ffeb064126.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from r3a_runtime.engineering import (
    CapabilityOperationRef, CriterionResult, EngineeringProposal, EngineeringWorkOrder,
    VerificationResult, proposal_digest, validate_engineering_assignment,
)


OPERATION_ID = "engineering.workspace.apply_patch"
OPERATION_VERSION = "1.0.0"
HANDLER_ID = "r3a.engineering.workflow"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(activity_id: str, purpose: str) -> str:
    return str(uuid.uuid5(uuid.UUID(activity_id), f"r3a.engineering.handler:{purpose}"))


def _within_assignment(path: Any, assignment: dict[str, Any]) -> bool:
    return (isinstance(path, str) and any(
        path == allowed or (allowed.endswith("**") and path.startswith(allowed[:-2]))
        for allowed in assignment["allowed_paths"]))


def _parse_resident_proposal(continuation: dict[str, Any], *, operation_id: str,
                             workspace_id: str, assignment: dict[str, Any]) -> dict[str, Any] | None:
    if continuation.get("outcome") != "succeeded":
        error = continuation.get("error") or {}
        raise RuntimeError(str(error.get("message") or "resident proposal objective did not complete"))
    invocation = continuation.get("invocation") or {}
    if invocation.get("state") != "COMPLETED":
        raise RuntimeError("resident proposal objective has no durable completed result")
    result = invocation.get("result") or {}
    decision = result.get("decision") if isinstance(result, dict) else None
    if isinstance(decision, dict) and decision.get("status") == "blocked":
        return None
    if not isinstance(decision, dict) or decision.get("status") not in {"healthy", "degraded"}:
        raise PermissionError("resident did not return an actionable Engineering proposal")
    text = decision.get("recommended_action")
    if not isinstance(text, str):
        raise ValueError("resident proposal must be returned in recommended_action")
    proposal = json.loads(text)
    if not isinstance(proposal, dict) or set(proposal) != {
            "operation_id", "contract_version", "target", "inputs", "verification_plan"}:
        raise ValueError("resident proposal fields do not match the Engineering proposal shape")
    if proposal["operation_id"] != operation_id or proposal["contract_version"] != OPERATION_VERSION:
        raise PermissionError("resident proposed an operation outside the Engineering module contract")
    target = proposal["target"]
    arguments = proposal["inputs"]
    if not isinstance(target, dict) or target != {"workspace_id": workspace_id}:
        raise PermissionError("resident proposal target is outside the assigned workspace")
    if not isinstance(arguments, dict) or set(arguments) != {"path", "content"}:
        raise ValueError("resident proposal inputs do not match the registered operation")
    if not _within_assignment(arguments.get("path"), assignment):
        raise PermissionError("resident proposal path is outside the institution-assigned allowlist")
    if not isinstance(arguments.get("content"), str):
        raise ValueError("resident proposal content must be text")
    if not isinstance(proposal["verification_plan"], dict):
        raise ValueError("resident proposal verification_plan must be an object")
    return proposal


def _objective_action(payload: dict[str, Any], state: dict[str, Any], *, purpose: str,
                      objective: str, timeout: int = 3600) -> dict[str, Any]:
    principal = payload.get("execution_principal")
    if not isinstance(principal, str) or not principal:
        raise ValueError("CME handler request lacks its server-derived execution principal")
    action = {
        "contract_id": "r3a.activity-handler.objective-submission", "contract_version": "1.0.0",
        "action_id": _stable_id(payload["activity_id"], purpose),
        "target_resident_id": principal, "objective": objective[:4000],
        "event_kind": "objective", "task_class": "objective_reasoning",
        "required_capabilities": [], "required_modalities": [],
        "acceptance_criteria": [], "notification_envelope": None,
        "timeout_seconds": timeout,
    }
    return {"outcome": "action_required", "action": action, "checkpoint": state,
            "progress": {"phase": state.get("phase", purpose)}}


def _proposal_object(payload: dict[str, Any], state: dict[str, Any], proposal_value: dict[str, Any],
                     invocation_result: dict[str, Any] | None = None) -> EngineeringProposal:
    assignment = state["assignment"]
    resident_id = payload["execution_principal"]
    op = CapabilityOperationRef(OPERATION_ID, OPERATION_VERSION, "isolated_write",
                                proposal_value["target"], proposal_value["inputs"])
    model_turn = state.get("proposal_turn") or {}
    return EngineeringProposal(
        proposal_id=state["proposal_id"], proposal_revision=int(state["proposal_revision"]),
        activity_id=payload["activity_id"], attempt_id=payload["attempt_id"],
        correlation_id=payload["correlation_id"], resident_id=resident_id,
        config_revision=str(state["config_revision"]), created_at=_now(),
        objective=str(state["objective"]), criteria=tuple(assignment["criteria"]),
        repository=assignment["repository"], baseline_ref=assignment["baseline_ref"],
        scope=assignment, proposed_operations=(op,),
        verification_plan=proposal_value["verification_plan"],
        reasoning_provenance={"resident_activity_id": model_turn.get("activity_id"),
                              "provider": (model_turn.get("model") or {}).get("provider"),
                              "model": (model_turn.get("model") or {}).get("name"),
                              "request_ref": (model_turn.get("model") or {}).get("request_ref"),
                              "result_ref": (model_turn.get("model") or {}).get("result_ref"),
                              "result_sha256": (model_turn.get("model") or {}).get("result_sha256")})


def _proposal_objective(payload: dict[str, Any], assignment: dict[str, Any], *, correction: dict[str, Any] | None = None) -> str:
    request = payload.get("input") or {}
    objective = str(request.get("objective") or "Complete the assigned Engineering work order.")
    if correction is None:
        task = {"objective": objective, "engineering_assignment": assignment,
                "allowed_operation": {"operation_id": OPERATION_ID,
                                     "operation_contract_version": OPERATION_VERSION},
                "response_shape": {"operation_id": OPERATION_ID, "contract_version": OPERATION_VERSION,
                                   "target": {"workspace_id": assignment["workspace_id"]},
                                   "inputs": {"path": "<allowed path>", "content": "<artifact bytes as text>"},
                                   "verification_plan": {"summary": "<brief>"}}}
        instruction = ("Act as the assigned resident. Propose one bounded operation only. Do not claim it ran. "
                       "Put a compact JSON object with exactly the response_shape keys in recommended_action. "
                       "The handler and CME will validate scope and authorization; do not change the operation ID.")
    else:
        task = {"objective": objective, "assignment": assignment,
                "failed_independent_verification": correction,
                "allowed_operation": {"operation_id": OPERATION_ID,
                                     "operation_contract_version": OPERATION_VERSION},
                "response_shape": {"operation_id": OPERATION_ID, "contract_version": OPERATION_VERSION,
                                   "target": {"workspace_id": assignment["workspace_id"]},
                                   "inputs": {"path": "<allowed path>", "content": "<corrected artifact bytes as text>"},
                                   "verification_plan": {"summary": "<brief>"}}}
        instruction = ("Review the actual verifier failure and choose at most one scoped correction. "
                       "If no safe correction fits the assignment, return blocked. Otherwise put the exact "
                       "response_shape JSON in recommended_action. Do not claim verification or completion.")
    return instruction + "\n" + json.dumps(task, ensure_ascii=False, separators=(",", ":"))


def _assessment_objective(payload: dict[str, Any], state: dict[str, Any]) -> str:
    result = {"invocation": state.get("invocation"), "artifact": state.get("artifact"),
              "independent_verification": state.get("verification")}
    return ("Assess this Engineering execution evidence against the assigned objective and criteria. "
            "Return status healthy only if it is appropriate to proceed, otherwise blocked. This is not "
            "verification or completion; an independent verifier controls acceptance. Set recommended_action "
            "to exactly ready_for_verification when appropriate, otherwise explain the block.\n" +
            json.dumps({"objective": state["objective"], "criteria": state["assignment"]["criteria"],
                        "execution_evidence": result}, ensure_ascii=False, separators=(",", ":")))


def _resident_decision(continuation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if continuation.get("outcome") != "succeeded":
        error = continuation.get("error") or {}
        raise RuntimeError(str(error.get("message") or "resident decision objective did not complete"))
    invocation = continuation.get("invocation") or {}
    if invocation.get("state") != "COMPLETED":
        raise RuntimeError("resident decision objective has no durable completed result")
    result = invocation.get("result") or {}
    decision = result.get("decision") if isinstance(result, dict) else None
    if not isinstance(decision, dict):
        raise ValueError("resident decision objective returned no typed decision")
    return invocation, decision


def _verify(work_order: EngineeringWorkOrder, workspace_root: Path,
            assignment: dict[str, Any]) -> tuple[VerificationResult, dict[str, Any]]:
    operation_ref = work_order.operation_refs[0]
    artifact_path = operation_ref.inputs["path"]
    root = workspace_root.resolve(strict=True)
    file_path = (root / artifact_path).resolve()
    if root not in file_path.parents:
        raise PermissionError("verification artifact resolves outside the configured workspace")
    evidence_ref = f"workspace:{artifact_path}"
    artifact = {"path": artifact_path, "evidence_ref": evidence_ref, "exists": file_path.is_file(),
                "sha256": None}
    results: list[CriterionResult] = []
    digests: dict[str, str] = {}
    operation = {"operation_id": operation_ref.operation_id,
                 "contract_version": operation_ref.contract_version,
                 "effect_class": operation_ref.effect_class,
                 "target": operation_ref.target, "inputs": operation_ref.inputs}
    for criterion in work_order.criteria:
        check_path = criterion["artifact_path"]
        check_ref = f"workspace:{check_path}"
        try:
            if not _within_assignment(check_path, assignment):
                raise PermissionError("verification criterion path is outside the assignment allowlist")
            check_file = (root / check_path).resolve()
            if root not in check_file.parents:
                raise PermissionError("verification criterion resolves outside the configured workspace")
            raw = check_file.read_bytes()
            digests[check_path] = hashlib.sha256(raw).hexdigest()
            document = json.loads(raw)
            if not isinstance(document, (dict, list)):
                raise ValueError("artifact JSON root must be an object or array")
            for binding in criterion["bindings"]:
                source = operation if binding["source"] == "operation" else work_order.to_dict()
                if _pointer(document, binding["artifact_pointer"]) != _pointer(source, binding["source_pointer"]):
                    raise ValueError("one or more declared artifact bindings differ")
            results.append(CriterionResult(criterion["criterion_id"], "PASS", (check_ref,),
                                           "all declared artifact bindings match"))
        except Exception as exc:
            results.append(CriterionResult(criterion["criterion_id"], "FAIL", (check_ref,),
                                           f"artifact could not satisfy declared check: {type(exc).__name__}: {exc}"))
    if file_path.is_file():
        raw = file_path.read_bytes()
        artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        if len(raw) <= 65536:
            try:
                artifact["content"] = raw.decode("utf-8")
            except UnicodeDecodeError:
                pass
    if not results:
        raise ValueError("Engineering work order has no verification criteria")
    if not results:
        raise ValueError("Engineering work order has no verification criteria")
    outcome = "PASS" if all(item.status == "PASS" for item in results) else "FAIL"
    verification = VerificationResult(
        verification_id=str(uuid.uuid5(uuid.UUID(work_order.work_order_id), "independent-verification-v1")),
        activity_id=work_order.activity_id, work_order_id=work_order.work_order_id,
        work_order_version=work_order.work_order_version,
        verifier_id=assignment["verifier_id"], verifier_version=assignment["verifier_version"],
        policy_revision=assignment["policy_revision"],
        artifact_digests=tuple("sha256:" + digests[path] for path in sorted(digests)),
        results=tuple(results), verified_at=_now(), outcome=outcome)
    return verification, artifact


def _pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("JSON pointer must be empty or begin with slash")
    current = value
    for raw_part in pointer[1:].split("/"):
        token = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[token]
        elif isinstance(current, list):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current


class IsolatedWorkspaceProvider:
    """One registered module implements the operation and Engineering activity handler."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = dict(configuration)
        self.root = Path(configuration["workspace_root"]).resolve(strict=True)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        request = arguments.get("request") if isinstance(arguments, dict) else None
        if isinstance(request, dict) and request.get("operation") == "execute":
            payload = request.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("Engineering handler execute envelope is invalid")
            return _run_handler(payload, self.configuration, context)
        return self._apply_patch(arguments, context)

    def _apply_patch(self, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        relative = arguments["path"]
        if (not isinstance(relative, str) or relative.startswith("/") or "\\" in relative
                or any(part in {"", ".", ".."} for part in relative.split("/"))):
            raise ValueError("workspace path must be normalized and relative")
        order = context["work_order"]
        if context["effect_class"] != "isolated_write" or context["target"]["workspace_id"] != order["workspace_id"]:
            raise PermissionError("provider target is outside the authorized isolated workspace")
        if not any(relative == pattern.removesuffix("**").rstrip("/")
                   or (pattern.endswith("**") and relative.startswith(pattern[:-2]))
                   for pattern in order["allowed_paths"]):
            raise PermissionError("provider path is outside the work-item allowlist")
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise PermissionError("workspace path escapes its configured root")
        payload = arguments["content"].encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = destination.read_bytes()
            if existing != payload:
                raise FileExistsError("idempotent target already contains different bytes")
            return {"path": relative, "sha256": hashlib.sha256(existing).hexdigest(),
                    "bytes_written": 0, "replayed": True}
        temporary = destination.with_name(destination.name + "." + context["invocation_id"] + ".tmp")
        created = False
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
                created = True
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise FileExistsError("concurrent invocation wrote different bytes")
            return {"path": relative, "sha256": digest, "bytes_written": len(payload),
                    "replayed": not created}
        finally:
            temporary.unlink(missing_ok=True)


def _run_handler(payload: dict[str, Any], configuration: dict[str, Any],
                 provider_context: dict[str, Any]) -> dict[str, Any]:
    checkpoint = payload.get("checkpoint") or {}
    if not isinstance(checkpoint, dict):
        raise ValueError("Engineering handler checkpoint must be an object")
    continuation = payload.get("continuation")
    request = payload.get("input") or {}
    state = dict(checkpoint)
    if not state:
        assignment_raw = request.get("engineering_assignment")
        assignment = validate_engineering_assignment(assignment_raw)
        objective = request.get("objective") or payload.get("objective")
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("Engineering activity input requires a nonempty objective")
        state = {"phase": "proposal_wait", "assignment": assignment, "objective": objective,
                 "config_revision": str(provider_context.get("config_revision") or "module-config"),
                 "proposal_revision": 1, "correction_count": 0, "resident_turns": []}
        return _objective_action(payload, state, purpose="proposal:1",
                                 objective=_proposal_objective(payload, assignment))

    phase = state.get("phase")
    if phase == "proposal_wait":
        invocation, decision = _resident_decision(continuation or {})
        state["resident_turns"].append({"activity_id": invocation.get("activity_id"),
                                       "result": invocation.get("result")})
        proposal_value = _parse_resident_proposal(
            continuation or {}, operation_id=OPERATION_ID,
            workspace_id=state["assignment"]["workspace_id"], assignment=state["assignment"])
        if proposal_value is None:
            return {"outcome": "blocked", "reason": "resident declined or blocked the assigned Engineering work",
                    "checkpoint": {**state, "phase": "proposal_blocked"}}
        state["proposal_value"] = proposal_value
        state["proposal_id"] = _stable_id(payload["activity_id"], f"proposal:{state['proposal_revision']}")
        state["work_order_id"] = str(uuid.uuid5(uuid.UUID(state["proposal_id"]),
                                                   f"work-order:{state['proposal_revision']}"))
        state["proposal_turn"] = {"activity_id": invocation.get("activity_id"),
                                  "model": (invocation.get("result") or {}).get("model")}
        proposal = _proposal_object(payload, state, proposal_value)
        state["proposal"] = proposal.to_dict()
        state["proposal_digest"] = proposal_digest(proposal)
        state["phase"] = "execution_wait"
        action = {"contract_id": "r3a.activity-handler.action", "contract_version": "1.0.0",
                  "action_id": state["work_order_id"], "operation_id": OPERATION_ID,
                  "operation_contract_version": OPERATION_VERSION,
                  "target": proposal_value["target"], "input": proposal_value["inputs"],
                  "evidence_purpose": "apply the authorized bounded Engineering work-order artifact",
                  "durable_work": {"contract_id": "r3a.activity-handler.work-item",
                                   "contract_version": "1.0.0", "work_id": state["work_order_id"],
                                   "record": {"workspace_id": state["assignment"]["workspace_id"],
                                              "allowed_paths": state["assignment"]["allowed_paths"],
                                              "repository": state["assignment"]["repository"],
                                              "baseline_ref": state["assignment"]["baseline_ref"],
                                              "proposal_digest": state["proposal_digest"]}}}
        state["operation_ref"] = proposal.to_dict()["proposed_operations"][0]
        return {"outcome": "action_required", "action": action, "checkpoint": state,
                "progress": {"phase": "engineering.work_order.proposed"}}

    if phase == "execution_wait":
        receipt = continuation or {}
        if receipt.get("outcome") != "succeeded":
            error = receipt.get("error") or {}
            return {"outcome": "blocked", "reason": str(error.get("message") or
                    "authorized Engineering operation did not succeed"),
                    "checkpoint": {**state, "phase": "execution_blocked", "continuation": receipt}}
        invocation = receipt.get("invocation") or {}
        if invocation.get("outcome") != "SUCCEEDED":
            return {"outcome": "blocked", "reason": "CME did not return a successful canonical invocation",
                    "checkpoint": {**state, "phase": "execution_blocked", "continuation": receipt}}
        authorization = invocation.get("authorization") or {}
        order = EngineeringWorkOrder(
            work_order_id=state["work_order_id"], work_order_version=1,
            activity_id=payload["activity_id"], attempt_id=str(invocation.get("attempt_id") or payload["attempt_id"]),
            correlation_id=payload["correlation_id"], proposal_id=state["proposal_id"],
            proposal_revision=state["proposal_revision"], proposal_digest=state["proposal_digest"],
            resident_id=payload["execution_principal"], config_revision=state["config_revision"],
            repository=state["assignment"]["repository"], baseline_ref=state["assignment"]["baseline_ref"],
            workspace_id=state["assignment"]["workspace_id"],
            allowed_paths=tuple(state["assignment"]["allowed_paths"]),
            command_profiles=tuple(state["assignment"]["command_profiles"]),
            operation_refs=(CapabilityOperationRef.from_dict(state["operation_ref"]),),
            authorization_decision_id=str(authorization.get("decision_id") or "missing-decision"),
            authorization_audit_event_id=str(authorization.get("audit_event_id") or "missing-audit"),
            authorization_provider_id=str(authorization.get("provider_id") or "cme"),
            policy_revision=authorization.get("policy_revision"), authorization_expires_at=None,
            criteria=tuple(state["assignment"]["criteria"]), issued_at=_now())
        state.update({"work_order": order.to_dict(), "invocation": invocation,
                      "phase": "assessment_wait"})
        verification, artifact = _verify(order, self_root(configuration), state["assignment"])
        state["verification"] = verification.to_dict()
        state["artifact"] = artifact
        objective = _assessment_objective(payload, state)
        return _objective_action(payload, state, purpose=f"assessment:{state['proposal_revision']}",
                                 objective=objective)

    if phase == "assessment_wait":
        _, decision = _resident_decision(continuation or {})
        state["resident_turns"].append({"activity_id": (continuation.get("invocation") or {}).get("activity_id"),
                                       "result": (continuation.get("invocation") or {}).get("result")})
        state["grace_assessment"] = decision
        if (decision.get("status") != "healthy"
                or decision.get("recommended_action") != "ready_for_verification"):
            return {"outcome": "blocked", "reason": str(decision.get("assessment") or
                    "resident assessed Engineering execution as blocked"), "checkpoint": state,
                    "evidence": state.get("invocation", {}).get("evidence", [])}
        verification = state["verification"]
        if verification.get("outcome") == "PASS":
            state["phase"] = "completed"
            return {"outcome": "completed", "reason": "resident assessment and independent verification passed",
                    "checkpoint": state,
                    "evidence": state.get("invocation", {}).get("evidence", []),
                    "work_order": state["work_order"], "proposal": state["proposal"],
                    "verification": verification, "resident_turns": state["resident_turns"]}
        if state["correction_count"] >= 1:
            return {"outcome": "blocked", "reason": "single bounded correction did not pass verification",
                    "checkpoint": {**state, "phase": "blocked"},
                    "verification": verification, "work_order": state["work_order"]}
        state["phase"] = "correction_wait"
        correction = {"verification": verification, "artifact": state.get("artifact"),
                      "work_order_id": state["work_order_id"]}
        return _objective_action(payload, state, purpose="correction:1",
                                 objective=_proposal_objective(payload, state["assignment"],
                                                               correction=correction))

    if phase == "correction_wait":
        invocation, _ = _resident_decision(continuation or {})
        state["resident_turns"].append({"activity_id": invocation.get("activity_id"),
                                       "result": invocation.get("result")})
        proposal_value = _parse_resident_proposal(
            continuation or {}, operation_id=OPERATION_ID,
            workspace_id=state["assignment"]["workspace_id"], assignment=state["assignment"])
        if proposal_value is None:
            return {"outcome": "blocked", "reason": "resident found no safe bounded correction",
                    "checkpoint": {**state, "phase": "correction_blocked"},
                    "verification": state.get("verification"), "work_order": state.get("work_order")}
        state["proposal_revision"] += 1
        state["correction_count"] += 1
        state["proposal_value"] = proposal_value
        state["proposal_id"] = _stable_id(payload["activity_id"], f"proposal:{state['proposal_revision']}")
        state["work_order_id"] = str(uuid.uuid5(uuid.UUID(state["proposal_id"]),
                                                   f"work-order:{state['proposal_revision']}"))
        state["proposal_turn"] = {"activity_id": invocation.get("activity_id"),
                                  "model": (invocation.get("result") or {}).get("model")}
        proposal = _proposal_object(payload, state, proposal_value)
        state["proposal"] = proposal.to_dict()
        state["proposal_digest"] = proposal_digest(proposal)
        state["phase"] = "execution_wait"
        action = {"contract_id": "r3a.activity-handler.action", "contract_version": "1.0.0",
                  "action_id": state["work_order_id"], "operation_id": OPERATION_ID,
                  "operation_contract_version": OPERATION_VERSION,
                  "target": proposal_value["target"], "input": proposal_value["inputs"],
                  "evidence_purpose": "apply the one bounded resident-selected correction",
                  "durable_work": {"contract_id": "r3a.activity-handler.work-item",
                                   "contract_version": "1.0.0", "work_id": state["work_order_id"],
                                   "record": {"workspace_id": state["assignment"]["workspace_id"],
                                              "allowed_paths": state["assignment"]["allowed_paths"],
                                              "repository": state["assignment"]["repository"],
                                              "baseline_ref": state["assignment"]["baseline_ref"],
                                              "proposal_digest": state["proposal_digest"]}}}
        state["operation_ref"] = proposal.to_dict()["proposed_operations"][0]
        return {"outcome": "action_required", "action": action, "checkpoint": state,
                "progress": {"phase": "engineering.corrective_proposal.selected"}}

    raise ValueError(f"unsupported Engineering handler checkpoint phase: {phase}")


def self_root(configuration: dict[str, Any]) -> Path:
    return Path(configuration["workspace_root"]).resolve(strict=True)


def create_provider(configuration: dict[str, Any]) -> IsolatedWorkspaceProvider:
    return IsolatedWorkspaceProvider(configuration)
