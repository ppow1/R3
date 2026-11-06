"""
R3 CONTROLLED SOURCE
File: r3a_runtime/grace_module.py
Component: R3A-GRACE-AP1
File Revision: 1.0.1
Created: 2026-11-06 UTC
Created By: Codex GPT-6
Purpose: Execute bounded read-only Grace objectives with the configured real model and supplied authorized evidence.
Execution Model: Versioned JSON-lines resident module process supervised by CME.
Observability: Provider/model, request/result references and digests, citations, and failures are returned to durable activity state.
Dependencies: Python standard library; explicitly configured OpenAI-compatible model endpoint.
Authority: AP1-M1 authorized by Steward in GitHub Issue #43; read-only Grace objectives only.
Changed: 2026-11-06 | AP1-M1 | Codex GPT-6 | Implement local inference and read-only objective execution.
Changed: 2026-11-06 | AP1-M1 | Codex GPT-6 | Constrain JSON output and retain model response references on validation failure.
Supersedes: None.
Contracts: R3A-019; AP1-M1 Issue #43 acceptance.
Tests: Live model-backed objective and CME interruption evidence.
History/Predecessor: New AP1-M1 resident module.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import urllib.error
import urllib.request
import uuid
from typing import Any

from .config import load_settings
from .protocol import ModuleProtocolServer


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

    async def _model_request(self, request: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(request, separators=(",", ":")).encode()
        req = urllib.request.Request(self.settings.model_endpoint, data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")

        def invoke() -> dict[str, Any]:
            try:
                with urllib.request.urlopen(req, timeout=self.settings.model_timeout_seconds) as response:
                    if response.status != 200:
                        raise RuntimeError(f"model HTTP status {response.status}")
                    raw = response.read(1_000_000)
                    return json.loads(raw)
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
            evidence = payload.get("evidence")
            if not isinstance(objective, str) or not objective.strip() or not isinstance(evidence, list) or not evidence:
                raise ValueError("objective and authorized evidence are required")
            request_ref = str(payload["request_ref"])
            evidence_ids = {item["source_id"] for item in evidence}
            request = {
                "model": self.settings.model_name,
                "temperature": 0,
                "max_tokens": self.settings.model_max_tokens,
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [
                    {"role": "system", "content": (
                        "You are Grace. Use only evidence. Return one compact JSON object exactly shaped as "
                        "{\"assessment\":\"short\",\"status\":\"healthy|degraded|blocked\","
                        "\"evidence_refs\":[\"source_id\"],\"recommended_action\":\"short\"}. "
                        "Use only supplied source IDs; missing facts => blocked. Keep under 70 tokens." )},
                    {"role": "user", "content": json.dumps({"objective": objective, "evidence": evidence}, separators=(",", ":"))},
                ],
            }
            request_hash = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            response: dict[str, Any] | None = None
            choice = ""
            try:
                response = await self._model_request(request)
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
                if not isinstance(decision, dict) or not {"assessment", "status", "evidence_refs", "recommended_action"}.issubset(decision):
                    raise ValueError("model result does not satisfy the decision contract")
                if decision["status"] not in {"healthy", "degraded", "blocked"}:
                    raise ValueError("model returned an unsupported status")
                if not isinstance(decision["evidence_refs"], list) or not decision["evidence_refs"] or not set(decision["evidence_refs"]).issubset(evidence_ids):
                    raise ValueError("model cited missing or unauthorized evidence")
                finish_reason = response["choices"][0].get("finish_reason")
                if finish_reason == "length":
                    raise ValueError("model response reached max_tokens before completing")
                result_ref = str(response.get("id") or uuid.uuid4())
                result_hash = hashlib.sha256(choice.encode()).hexdigest()
                self.last_activity = {
                    "activity_id": payload["activity_id"], "attempt_id": payload["attempt_id"],
                    "objective": objective, "decision": decision,
                    "model": {"provider": self.settings.model_provider, "name": self.settings.model_name,
                              "request_ref": request_ref, "request_sha256": request_hash,
                              "result_ref": result_ref, "result_sha256": result_hash,
                              "usage": response.get("usage"), "finish_reason": finish_reason},
                    "evidence": [{"source_id": item["source_id"], "sha256": item["sha256"]} for item in evidence
                                 if item["source_id"] in decision["evidence_refs"]],
                    "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                }
                return self.last_activity
            except Exception as exc:
                result_ref = response.get("id") if isinstance(response, dict) else None
                finish = (response.get("choices") or [{}])[0].get("finish_reason") if isinstance(response, dict) else None
                result_hash = hashlib.sha256(choice.encode()).hexdigest() if isinstance(choice, str) and choice else None
                raise RuntimeError(f"Grace model execution failed provider={self.settings.model_provider} model={self.settings.model_name} request_ref={request_ref} result_ref={result_ref} finish_reason={finish} result_sha256={result_hash}: {type(exc).__name__}: {str(exc)[:1000]}") from exc
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
