"""
R3 CONTROLLED SOURCE
File: r3a_runtime/engineering_verifier.py
Component: R3A-AP2-INDEPENDENT-VERIFICATION
File Revision: 1.0.0
Created: 2026-11-07T15:00:00Z
Created By: Codex GPT-6
Purpose: Independently inspect isolated Engineering artifacts against declarative, assignment-owned criteria.
Execution Model: Read-only verifier over workspace bytes, canonical operation descriptor, and immutable work order.
Observability: Typed criterion results reference actual artifact SHA-256 digests.
Dependencies: Python standard library; r3a_runtime.engineering; unified capability operation descriptor.
Authority: AP2 R3A-011/R3A-012, Issue #43; unified operation contract, Issue #46.
Changed: 2026-11-07 | AP2-AUTONOMY | Codex GPT-6 | Add data-driven isolated artifact verifier.
Supersedes: None.
Contracts: r3a.verification-result.v1.
Tests: tests/test_r3a_engineering_autonomy.py.
History/Predecessor: New file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .engineering import (CriterionResult, EngineeringWorkOrder, VerificationResult)
from .db import utcnow
import uuid


class EngineeringVerificationError(ValueError):
    """The assignment's declarative verification criteria are invalid."""


def _pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise EngineeringVerificationError("JSON pointer must be empty or begin with '/'")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(pointer)
    return current


def verify_workspace_artifact(work_order: EngineeringWorkOrder, operation: dict[str, Any],
                              workspace_root: str | Path, *, verifier_id: str,
                              verifier_version: str, policy_revision: str) -> VerificationResult:
    """Evaluate exact assignment criteria against disk bytes and registered operation facts."""
    if len(work_order.operation_refs) != 1:
        raise EngineeringVerificationError("this verifier expects one bounded operation per work order")
    operation_ref = work_order.operation_refs[0]
    if operation.get("operation_id") != operation_ref.operation_id or \
            operation.get("contract_version") != operation_ref.contract_version:
        raise EngineeringVerificationError("verifier descriptor does not match the authorized operation")
    provider_configuration = operation.get("configuration") or {}
    configured_root = provider_configuration.get("workspace_root")
    root = Path(workspace_root if workspace_root is not None else configured_root).resolve(strict=True)
    criterion_results: list[CriterionResult] = []
    artifact_digests: dict[str, str] = {}
    for criterion in work_order.criteria:
        criterion_id = criterion.get("criterion_id")
        if criterion.get("type") != "json_fields_equal" or not isinstance(criterion.get("bindings"), list):
            raise EngineeringVerificationError(f"unsupported declarative criterion: {criterion_id}")
        artifact_path = criterion.get("artifact_path")
        if not isinstance(artifact_path, str) or artifact_path not in work_order.allowed_paths and not any(
                artifact_path.startswith(pattern[:-2]) for pattern in work_order.allowed_paths if pattern.endswith("**")):
            raise EngineeringVerificationError("criterion artifact path is outside the authorized work-order scope")
        path = (root / artifact_path).resolve()
        if root not in path.parents:
            raise EngineeringVerificationError("criterion artifact resolves outside its isolated workspace")
        evidence_ref = f"workspace:{artifact_path}"
        try:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            artifact_digests[artifact_path] = digest
            document = json.loads(raw)
            if not isinstance(document, (dict, list)):
                raise ValueError("artifact JSON root must be an object or array")
            mismatches = []
            for binding in criterion["bindings"]:
                if not isinstance(binding, dict) or set(binding) != {
                        "artifact_pointer", "source", "source_pointer"}:
                    raise EngineeringVerificationError("criterion bindings require artifact/source pointers")
                source = operation if binding["source"] == "operation" else \
                         work_order.to_dict() if binding["source"] == "work_order" else None
                if source is None:
                    raise EngineeringVerificationError("criterion source must be operation or work_order")
                if _pointer(document, binding["artifact_pointer"]) != _pointer(source, binding["source_pointer"]):
                    mismatches.append(binding)
            if mismatches:
                criterion_results.append(CriterionResult(criterion_id, "FAIL", (evidence_ref,),
                                                         f"{len(mismatches)} declared artifact bindings differ"))
            else:
                criterion_results.append(CriterionResult(criterion_id, "PASS", (evidence_ref,),
                                                         f"{len(criterion['bindings'])} declared bindings match inspected artifact bytes"))
        except Exception as exc:
            criterion_results.append(CriterionResult(criterion_id, "FAIL", (evidence_ref,),
                                                     f"artifact could not satisfy the declared check: {type(exc).__name__}: {exc}"))
    outcome = "PASS" if all(item.status == "PASS" for item in criterion_results) else "FAIL"
    return VerificationResult(
        verification_id=str(uuid.uuid4()), activity_id=work_order.activity_id,
        work_order_id=work_order.work_order_id, work_order_version=work_order.work_order_version,
        verifier_id=verifier_id, verifier_version=verifier_version,
        policy_revision=policy_revision,
        artifact_digests=tuple("sha256:" + artifact_digests[path] for path in sorted(artifact_digests)),
        results=tuple(criterion_results), verified_at=utcnow().isoformat(), outcome=outcome)
