"""
R3 CONTROLLED SOURCE
File: r3a_runtime/grace_module.py
Component: R3A-GRACE-AP1
File Revision: 1.4.1
Created: 2026-11-06 UTC
Created By: Codex GPT-6
Purpose: Execute read-only Grace objectives through configured inference and resident-selected authorized capabilities.
Execution Model: Versioned JSON-lines resident module process supervised by CME.
Observability: Provider/model, request/result references and digests, citations, and failures are returned to durable activity state.
Dependencies: Python standard library; explicitly configured OpenAI-compatible model endpoint.
Authority: AP1 / R3A-019 and AP1 Slice 1 authorized by Steward; assigned authority and read-only configured capabilities are enforced.
Changed: 2026-11-06 | AP1-M1 | Codex GPT-6 | Implement local inference and read-only objective execution.
Changed: 2026-11-06 | AP1-M1 | Codex GPT-6 | Constrain JSON output and retain model response references on validation failure.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Execute selected configured model route and retain event/evidence lineage.
Changed: 2026-11-06T18:13:55Z | R3A-019 | Codex GPT-6 | Send only cited evidence content to inference and retain HTTP error details.
Changed: 2026-11-06T18:21:00Z | R3A-019 | Codex GPT-6 | Require model decisions to cite retrieved knowledge evidence.
Changed: 2026-11-06T18:31:45Z | R3A-019 | Codex GPT-6 | Clarify that model assessments answer objectives and reserve blocked for missing evidence.
Changed: 2026-11-06T18:38:00Z | R3A-019 | Codex GPT-6 | Request schema-constrained JSON and report missing decision fields precisely.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Validate optional versioned execution envelopes and retain selected role provenance.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Complete execution envelope identity checks and role provenance propagation.
Changed: 2026-11-07 | R3A-019 | Codex GPT-6 | Let Grace select authorized read capabilities and reason over returned evidence through durable continuation turns.
Changed: 2026-11-07 | R3A-019 | Codex GPT-6 | Normalize omitted arguments to an empty object only for no-argument capability manifests.
Changed: 2026-11-07T02:35:35Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Give Grace explicit objective criteria and continuation feedback.
Changed: 2026-11-07T02:41:51Z | R3A-019-ACCEPTANCE-CORRECTION | Codex GPT-6 | Deliver the versioned acceptance envelope in the resident inference context.
Changed: 2026-11-07T03:34:34Z | R3A-019-INBOX-LOOP | Codex GPT-6 | Constrain capability identifiers to the exact configured tool manifest values.
Supersedes: None.
Contracts: R3A-019; AP1-M1 Issue #43 acceptance; r3a.resident.execution.v1.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; automated inference responses are fixtures.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Support model-selected registered Engineering operations, typed proposals and post-execution resident assessment.
Changed: 2026-11-07 | R3A-AP2-AUTONOMY | Codex GPT-6 | Require evidence-bounded Engineering assessments and prohibit unsupported artifact claims.
History/Predecessor: Prior revision at baseline 3355abe96524a5260e9ba8395a9dfef5bfdd9422, blob 79b5db5747b261cbb3d8807988e8c63043e1d9ae.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

from .contracts import ContractEnvelope, ContractValidationError
from .config import load_settings
from .protocol import ModuleProtocolServer


RESIDENT_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["invoke_capability", "propose_engineering", "engineering_assess", "final"]},
        "contract_id": {"type": "string"},
        "contract_version": {"type": "string"},
        "capability_id": {"type": "string"},
        "arguments": {"type": "object"},
        "rationale": {"type": "string"},
        "proposal": {
            "type": "object",
            "properties": {
                "operation_id": {"type": "string"},
                "contract_version": {"type": "string"},
                "target": {"type": "object"},
                "inputs": {"type": "object"},
                "verification_plan": {"type": "object"},
            },
            "required": ["operation_id", "contract_version", "target", "inputs", "verification_plan"],
            "additionalProperties": False,
        },
        "engineering_assessment": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["ready_for_verification", "blocked"]},
                "assessment": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["status", "assessment", "evidence_refs"],
            "additionalProperties": False,
        },
        "decision": {
            "type": "object",
            "properties": {
                "assessment": {"type": "string"},
                "status": {"type": "string", "enum": ["healthy", "degraded", "blocked"]},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "recommended_action": {"type": "string"},
            },
            "required": ["assessment", "status", "evidence_refs", "recommended_action"],
            "additionalProperties": False,
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def resident_action_schema(available_tools: list[dict[str, Any]],
                           available_operations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Constrain capability selection to exact identifiers in this execution's manifest."""
    schema = json.loads(json.dumps(RESIDENT_ACTION_SCHEMA))
    capability_ids = [tool.get("capability_id") for tool in available_tools
                      if isinstance(tool, dict) and isinstance(tool.get("capability_id"), str)]
    if capability_ids:
        schema["properties"]["capability_id"]["enum"] = list(dict.fromkeys(capability_ids))
    operation_ids = [operation.get("operation_id") for operation in (available_operations or [])
                     if isinstance(operation, dict) and isinstance(operation.get("operation_id"), str)]
    if operation_ids:
        schema["properties"]["proposal"]["properties"]["operation_id"]["enum"] = list(dict.fromkeys(operation_ids))
    return schema


def provider_usage_record(provider_usage: Any, *, request_ref: str, route_id: str,
                         provider: str, model: str, started_at: datetime,
                         finished_at: datetime, elapsed_ms: float) -> dict[str, Any]:
    """Preserve exact provider token counts and append R3A-measured call timing."""
    usage = dict(provider_usage) if isinstance(provider_usage, dict) else {}
    usage["r3a_measurement"] = {
        "request_ref": request_ref,
        "request_started_at": started_at.isoformat().replace("+00:00", "Z"),
        "request_finished_at": finished_at.isoformat().replace("+00:00", "Z"),
        "elapsed_ms": round(float(elapsed_ms), 3),
        "route_id": route_id, "provider": provider, "model": model,
        "stream_deltas": None,
        "stream_cadence_state": "unavailable_grace_provider_uses_buffered_response",
    }
    return usage


class GraceResident:
    def __init__(self, module_id: str, module_version: str, config_path: str):
        self.module_id = module_id
        self.module_version = module_version
        self.settings = load_settings(config_path)
        if self.settings.module_id != module_id or not self.settings.model_endpoint:
            raise ValueError("Grace resident identity or model configuration does not match bootstrap")
        self.state = "INSTALLED"
        self.last_activity: dict[str, Any] | None = None
        self.stopping = asyncio.Event()

    async def _model_request(self, endpoint: str, timeout_seconds: float,
                             request: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(request, separators=(",", ":")).encode()
        req = urllib.request.Request(endpoint, data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")

        def invoke() -> dict[str, Any]:
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    if response.status != 200:
                        raise RuntimeError(f"model HTTP status {response.status}")
                    raw = response.read(1_000_000)
                    return json.loads(raw)
            except urllib.error.HTTPError as exc:
                detail = exc.read(4000).decode("utf-8", "replace")
                raise RuntimeError(f"model HTTP status {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"model transport failed: {exc}") from exc

        return await asyncio.to_thread(invoke)

    async def handle(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "hello":
            return {"contract_id": "r3a.module.v1", "supported_protocol": {"major": 1, "min_minor": 0, "max_minor": 0},
                    "capabilities": list(self.settings.module_capabilities), "pid": os.getpid(),
                    "provider": self.settings.model_provider, "model": self.settings.model_name}
        if operation == "health":
            return {"state": self.state, "health": "healthy" if self.settings.model_endpoint else "degraded",
                    "pid": os.getpid(), "last_activity": self.last_activity,
                    "provider": self.settings.model_provider, "model": self.settings.model_name}
        if operation == "prepare":
            self.state = "ACTIVATING"
            return {"prepared": True, "module_id": self.module_id}
        if operation == "activate":
            self.state = "ACTIVE"
            return {"active": True}
        if operation == "execute":
            if self.state != "ACTIVE":
                raise RuntimeError("Grace resident is not active")
            envelope_value = payload.get("contract_envelope")
            if envelope_value is not None:
                envelope = ContractEnvelope.from_dict(
                    envelope_value, expected_contract="r3a.resident.execution")
                if envelope.resident_id != self.module_id:
                    raise ContractValidationError("resident identity mismatch")
                if envelope.activity_id != str(payload.get("activity_id")) or \
                        envelope.attempt_id != str(payload.get("attempt_id")):
                    raise ContractValidationError("activity/attempt identity mismatch")
                if envelope.config_revision != str(payload.get("config_revision")):
                    raise ContractValidationError("configuration revision mismatch")
            if payload.get("activity_type") == "foundation.observe":
                required = {"activity_id", "attempt_id", "processes", "postgres"}
                if not required.issubset(payload):
                    raise ValueError("observer input is incomplete")
                self.last_activity = {key: payload[key] for key in ("activity_id", "attempt_id", "processes", "postgres", "config_revision")}
                self.last_activity["resident"] = "Grace"
                return self.last_activity
            if payload.get("activity_type") != "grace.objective":
                raise ValueError("unsupported activity type")
            objective = payload.get("objective")
            evidence = payload.get("evidence", [])
            if (not isinstance(objective, str) or not objective.strip()
                    or not isinstance(evidence, list)):
                raise ValueError("objective and evidence collection are required")
            request_ref = str(payload["request_ref"])
            route = self.settings.model_route(payload.get("route_id"))
            tools = payload.get("available_tools", [])
            if not isinstance(tools, list):
                raise ValueError("available_tools must be an array")
            available_operations = payload.get("available_engineering_operations", [])
            engineering_assignment = payload.get("engineering_assignment")
            if not isinstance(available_operations, list):
                raise ValueError("available_engineering_operations must be an array")
            conversation = payload.get("conversation", [])
            if not isinstance(conversation, list) or any(
                    not isinstance(message, dict) or message.get("role") not in {"assistant", "user"}
                    or not isinstance(message.get("content"), str) for message in conversation):
                raise ValueError("conversation must contain assistant/user text messages")
            request = {
                "model": route.model,
                "temperature": 0,
                "max_tokens": route.max_tokens,
                "response_format": {"type": "json_object", "schema": resident_action_schema(tools, available_operations)},
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [
                    {"role": "system", "content": (
                        "You are Grace, the resident responsible for reasoning about the assigned objective. "
                        "Select actions yourself. You may request a capability only from the supplied available_tools list; "
                        "copy its capability_id verbatim, including punctuation; never replace periods with underscores. "
                        "The institutional runtime will enforce authorization and return its result. Do not claim a capability "
                        "was used until its result appears in the conversation. Use only evidence returned by the runtime. "
                        "If evidence is empty and the objective asks for institutional facts, do not guess or return a healthy answer. "
                        "Request a relevant listed capability; if none can supply the facts, return a justified blocked decision. "
                        "If the institutional runtime rejects a proposed completion with acceptance feedback, reassess the original objective "
                        "against all returned evidence and continue with an authorized capability when useful; do not repeat an unsupported final. "
                        "When more information is needed, return {\"action\":\"invoke_capability\","
                        "\"contract_id\":\"r3a.resident-capability-tool\",\"contract_version\":\"1.0.0\","
                        "\"capability_id\":\"exact capability_id\",\"arguments\":{...},"
                        "\"rationale\":\"why this helps the objective\"}. When ready, return "
                        "{\"action\":\"final\",\"decision\":{\"assessment\":\"answer the objective\","
                        "\"status\":\"healthy|degraded|blocked\",\"evidence_refs\":[\"source_id\"],"
                        "\"recommended_action\":\"next action or none\"}}. For final answers cite only returned source IDs. "
                        "For an Engineering assignment, independently inspect the objective, acceptance criteria, and listed canonical operation descriptors. Select an operation and typed target/inputs yourself, then return {\"action\":\"propose_engineering\",\"rationale\":\"why this operation and approach fit\",\"proposal\":{\"operation_id\":\"registered operation ID\",\"contract_version\":\"1.0.0\",\"target\":{},\"inputs\":{},\"verification_plan\":{}}}. The CME validates scope and authorization before execution. After the runtime returns execution evidence, assess that evidence and return {\"action\":\"engineering_assess\",\"engineering_assessment\":{\"status\":\"ready_for_verification|blocked\",\"assessment\":\"evidence-grounded assessment\",\"evidence_refs\":[\"execution evidence references\"]}}. Mention only facts present in supplied evidence and criteria; do not claim checks, signatures, or properties that were not performed or verified. This assessment does not itself accept the deliverable. "
                        "Use blocked only when required facts remain unavailable or ambiguous; explain why in assessment. "
                        "Never imply external actions were performed. Return one compact JSON object." )},
                    *conversation,
                    {"role": "user", "content": json.dumps({"event_kind": payload.get("event_kind", "objective"),
                                                                  "objective": objective,
                                                                  "acceptance_contract": payload.get("acceptance_contract", {}),
                                                                  "engineering_assignment": engineering_assignment,
                                                                  "available_engineering_operations": available_operations,
                                                                  "engineering_execution_result": payload.get("engineering_execution_result"),
                                                                  "available_tools": tools,
                                                                  "required_evidence_refs": payload.get("required_evidence_refs", []),
                                                                  "evidence": evidence},
                                                                 separators=(",", ":"))},
                ],
            }
            request_hash = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            response: dict[str, Any] | None = None
            choice = ""
            try:
                request_started_at = datetime.now(timezone.utc)
                request_started_clock = time.perf_counter()
                response = await self._model_request(route.endpoint, route.timeout_seconds, request)
                request_finished_at = datetime.now(timezone.utc)
                call_elapsed_ms = round((time.perf_counter() - request_started_clock) * 1000, 3)
                choice = response["choices"][0]["message"]["content"]
                if not isinstance(choice, str) or not choice.strip():
                    raise ValueError("configured model returned empty content")
                result_text = choice.strip()
                if result_text.startswith("```json"):
                    result_text = result_text[7:]
                elif result_text.startswith("```"):
                    result_text = result_text[3:]
                if result_text.endswith("```"):
                    result_text = result_text[:-3]
                result_text = result_text.strip()
                decision = json.loads(result_text)
                if not isinstance(decision, dict):
                    raise ValueError("model result must be a JSON object")
                if decision.get("action") == "invoke_capability":
                    required_fields = {"action", "contract_id", "contract_version",
                                       "capability_id", "rationale"}
                    allowed_fields = required_fields | {"arguments"}
                    selected_tool = next((tool for tool in tools
                                          if isinstance(tool, dict)
                                          and tool.get("capability_id") == decision.get("capability_id")), None)
                    argument_schema = selected_tool.get("arguments_schema", {}) if selected_tool else {}
                    no_arguments = (isinstance(argument_schema, dict)
                                    and argument_schema.get("properties", {}) == {}
                                    and not argument_schema.get("required", []))
                    if set(decision) == required_fields and no_arguments:
                        decision["arguments"] = {}
                    elif set(decision) != allowed_fields:
                        raise ValueError("capability request fields are invalid")
                    version_parts = str(decision["contract_version"]).split(".")
                    if (decision["contract_id"] != "r3a.resident-capability-tool"
                            or len(version_parts) != 3 or not all(part.isdigit() for part in version_parts)
                            or version_parts[0] != "1"):
                        raise ValueError("capability request contract is incompatible")
                    if (not isinstance(decision["capability_id"], str)
                            or not isinstance(decision["arguments"], dict)
                            or not isinstance(decision["rationale"], str)
                            or not decision["rationale"].strip()):
                        raise ValueError("capability request is incomplete")
                    tool_ids = {tool.get("capability_id") for tool in tools if isinstance(tool, dict)}
                    if decision["capability_id"] not in tool_ids:
                        raise ValueError("model requested a capability not present in its tool manifest")
                    final_decision = None
                elif decision.get("action") == "propose_engineering":
                    if set(decision) != {"action", "proposal", "rationale"} or not isinstance(decision["proposal"], dict):
                        raise ValueError("Engineering proposal action fields are invalid")
                    if not isinstance(decision["rationale"], str) or not decision["rationale"].strip():
                        raise ValueError("Engineering proposal requires a rationale")
                    proposed = decision["proposal"]
                    required = {"operation_id", "contract_version", "target", "inputs", "verification_plan"}
                    if set(proposed) != required or not isinstance(proposed["target"], dict) or \
                            not isinstance(proposed["inputs"], dict) or not isinstance(proposed["verification_plan"], dict):
                        raise ValueError("Engineering proposal payload is malformed")
                    if proposed["operation_id"] not in {op.get("operation_id") for op in available_operations}:
                        raise ValueError("Grace selected an operation absent from canonical discovery")
                    final_decision = None
                elif decision.get("action") == "engineering_assess":
                    if set(decision) != {"action", "engineering_assessment"} or not isinstance(decision["engineering_assessment"], dict):
                        raise ValueError("Engineering assessment action fields are invalid")
                    assessment = decision["engineering_assessment"]
                    if set(assessment) != {"status", "assessment", "evidence_refs"} or \
                            assessment["status"] not in {"ready_for_verification", "blocked"} or \
                            not isinstance(assessment["assessment"], str) or not assessment["assessment"].strip() or \
                            not isinstance(assessment["evidence_refs"], list) or \
                            any(not isinstance(ref, str) for ref in assessment["evidence_refs"]):
                        raise ValueError("Engineering assessment payload is invalid")
                    final_decision = None
                elif decision.get("action") == "final":
                    if set(decision) != {"action", "decision"} or not isinstance(decision["decision"], dict):
                        raise ValueError("final action fields are invalid")
                    final_decision = decision["decision"]
                    required_fields = {"assessment", "status", "evidence_refs", "recommended_action"}
                    missing_fields = required_fields - final_decision.keys()
                    if missing_fields:
                        raise ValueError(f"model result is missing decision fields: {sorted(missing_fields)}")
                    if final_decision["status"] not in {"healthy", "degraded", "blocked"}:
                        raise ValueError("model returned an unsupported status")
                    if (not isinstance(final_decision["assessment"], str)
                            or not isinstance(final_decision["recommended_action"], str)
                            or not isinstance(final_decision["evidence_refs"], list)
                            or any(not isinstance(ref, str) for ref in final_decision["evidence_refs"])):
                        raise ValueError("model final decision contains invalid or unauthorized evidence")
                else:
                    raise ValueError("model returned an unsupported action")
                finish_reason = response["choices"][0].get("finish_reason")
                if finish_reason == "length":
                    raise ValueError("model response reached max_tokens before completing")
                result_ref = str(response.get("id") or uuid.uuid4())
                result_hash = hashlib.sha256(choice.encode()).hexdigest()
                usage_record = provider_usage_record(
                    response.get("usage"), request_ref=request_ref, route_id=route.route_id,
                    provider=route.provider, model=route.model, started_at=request_started_at,
                    finished_at=request_finished_at, elapsed_ms=call_elapsed_ms)
                self.last_activity = {
                    "activity_id": payload["activity_id"], "attempt_id": payload["attempt_id"],
                    "objective": objective, "event_kind": payload.get("event_kind", "objective"),
                    "action": decision["action"], "decision": final_decision,
                    "capability_request": (decision if decision["action"] == "invoke_capability" else None),
                    "engineering_proposal": decision.get("proposal") if decision["action"] == "propose_engineering" else None,
                    "engineering_assessment": decision.get("engineering_assessment") if decision["action"] == "engineering_assess" else None,
                    "rationale": decision.get("rationale"),
                    "model_content": choice,
                    "model": {"route_id": route.route_id, "provider": route.provider, "name": route.model,
                              "role_id": payload.get("selected_role_id"),
                              "request_ref": request_ref, "request_sha256": request_hash,
                              "result_ref": result_ref, "result_sha256": result_hash,
                              "usage": usage_record, "finish_reason": finish_reason},
                    "evidence": [{"source_id": item["source_id"], "sha256": item["sha256"]} for item in evidence
                                 if item.get("source_id") in (final_decision or {}).get("evidence_refs", [])],
                    "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                }
                return self.last_activity
            except Exception as exc:
                result_ref = response.get("id") if isinstance(response, dict) else None
                finish = (response.get("choices") or [{}])[0].get("finish_reason") if isinstance(response, dict) else None
                result_hash = hashlib.sha256(choice.encode()).hexdigest() if isinstance(choice, str) and choice else None
                raise RuntimeError(f"Grace model execution failed route={route.route_id} provider={route.provider} model={route.model} request_ref={request_ref} result_ref={result_ref} finish_reason={finish} result_sha256={result_hash} model_content_prefix={choice[:1000]!r}: {type(exc).__name__}: {str(exc)[:1000]}") from exc
        if operation == "checkpoint":
            return {"state": self.state, "last_activity": self.last_activity}
        if operation == "stop":
            self.state = "STOPPED"
            self.stopping.set()
            return {"stopped": True}
        raise ValueError(f"Unsupported module operation: {operation}")


async def run(socket_path: str, module_id: str, module_version: str, config_path: str) -> None:
    module = GraceResident(module_id, module_version, config_path)
    server = ModuleProtocolServer(socket_path, module_id, module_version, module.handle)
    await server.start()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, module.stopping.set)
        except NotImplementedError:
            pass
    await module.stopping.wait()
    await server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--module-version", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    asyncio.run(run(args.socket, args.module_id, args.module_version, args.config))


if __name__ == "__main__":
    main()
