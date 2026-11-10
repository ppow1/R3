"""
R3 CONTROLLED SOURCE
File: r3a_runtime/modular_dispatch.py
Component: R3A-MODULAR-DISPATCH-CONTRACTS
File Revision: 1.0.3
Created: 2026-11-10T00:49:41Z
Created By: Codex GPT-6
Purpose: Validate and resolve generic resident bindings from CME registry observations.
Execution Model: Synchronous contract validation used by async CME dispatch.
Observability: Resolution outcomes include contract identity, registry identity, and explicit denial reasons.
Dependencies: Existing module registry, resident profile, activity intake, identity/HR authority, and CME authorization.
Authority: AD-024; Steward Directive Issue #43; bindings and registration do not grant execution authority.
Changed: 2026-11-10T00:49:41Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Add generic resident binding and activity-handler contract validation.
Changed: 2026-11-10T01:00:00Z | R3A-AD024-MODULAR-DISPATCH | Codex GPT-6 | Resolve authoritative resident bindings and reject missing, stale, inactive, or incompatible registry entries.
Changed: 2026-11-10T02:00:00Z | R3A-AD024-INTEROP | Codex GPT-6 | Remove private activity-handler shape validation in favor of the shared #46 module_extensions contract helper.
Changed: 2026-11-10T02:20:00Z | R3A-AD024-INTEROP | Codex GPT-6 | Limit this resolver module to resident binding contracts; handler contracts are owned by #46 module_extensions.
Supersedes: None
Contracts: r3a.resident.module-binding.v1; r3a.resident.execution-profile@1.0.0; r3a.module.v1.
Tests: tests/test_r3a_modular_dispatch.py
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


class DispatchContractError(ValueError):
    """A registered binding or handler cannot safely receive work."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DispatchContractError(f"{field} must be a nonempty string")
    return value


def validate_resident_binding(value: Any) -> dict[str, Any]:
    """Validate the published resident binding shape; authoritative association is checked separately."""
    required = {"contract_id", "contract_version", "resident_id", "module_id", "module_version",
                "artifact_digest", "execution_contract_range", "binding_revision", "configuration_ref",
                "configuration_revision", "identity_association"}
    if not isinstance(value, dict) or set(value) != required:
        raise DispatchContractError("resident binding fields do not match r3a.resident.module-binding.v1")
    if value["contract_id"] != "r3a.resident.module-binding" or value["contract_version"] != "1.0.0":
        raise DispatchContractError("resident binding contract is incompatible")
    for key in ("resident_id", "module_id"):
        if not _IDENT.fullmatch(_text(value[key], key)):
            raise DispatchContractError(f"{key} is invalid")
    if not _SEMVER.fullmatch(_text(value["module_version"], "module_version")):
        raise DispatchContractError("module_version must be semantic major.minor.patch")
    digest = _text(value["artifact_digest"], "artifact_digest")
    if not _SHA256.fullmatch(digest):
        raise DispatchContractError("artifact_digest must be a lowercase SHA-256 digest")
    for key in ("binding_revision", "configuration_revision"):
        if not _text(value[key], key):
            raise DispatchContractError(f"{key} is required")
    _text(value["configuration_ref"], "configuration_ref")
    contract_range = value["execution_contract_range"]
    if not isinstance(contract_range, dict) or set(contract_range) != {"contract_id", "major", "min_minor", "max_minor"}:
        raise DispatchContractError("execution_contract_range is invalid")
    if (contract_range["contract_id"] != "r3a.resident.execution"
            or any(isinstance(contract_range[k], bool) or not isinstance(contract_range[k], int)
                   for k in ("major", "min_minor", "max_minor"))
            or contract_range["major"] < 1 or contract_range["min_minor"] < 0
            or contract_range["max_minor"] < contract_range["min_minor"]):
        raise DispatchContractError("execution_contract_range is incompatible")
    association = value["identity_association"]
    if (not isinstance(association, dict)
            or set(association) != {"authority", "record_id", "record_revision"}
            or not all(isinstance(association[k], str) and association[k].strip()
                       for k in association)):
        raise DispatchContractError("identity_association must reference the authoritative HR/directory record")
    return dict(value)


def resolve_resident_binding(bindings: Iterable[dict[str, Any]], resident_id: str,
                             identity_association: dict[str, str], modules: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Resolve one exact current association to one active immutable registered executor."""
    matches = [validate_resident_binding(binding) for binding in bindings
               if isinstance(binding, dict) and binding.get("resident_id") == resident_id]
    if len(matches) != 1:
        raise DispatchContractError("resident binding is missing or ambiguous")
    binding = matches[0]
    if binding["identity_association"] != identity_association:
        raise DispatchContractError("resident identity/HR association is invalid or stale")
    registered = [m for m in modules if isinstance(m, dict)
                  and m.get("module_id") == binding["module_id"]
                  and m.get("module_version") == binding["module_version"]]
    if len(registered) != 1:
        raise DispatchContractError("bound resident executor is missing or ambiguous in the module registry")
    module = registered[0]
    if module.get("lifecycle_state") != "ACTIVE":
        raise DispatchContractError("bound resident executor is not active")
    manifest = module.get("manifest")
    if (not isinstance(manifest, dict) or manifest.get("artifact_digest") != binding["artifact_digest"]
            or manifest.get("module_id") != binding["module_id"]
            or manifest.get("module_version") != binding["module_version"]):
        raise DispatchContractError("bound resident executor artifact does not match registry identity")
    supported = manifest.get("resident_execution_contract_range")
    requested = binding["execution_contract_range"]
    if (not isinstance(supported, dict)
            or set(supported) != {"contract_id", "major", "min_minor", "max_minor"}
            or supported.get("contract_id") != requested["contract_id"]
            or supported.get("major") != requested["major"]
            or any(isinstance(supported.get(key), bool) or not isinstance(supported.get(key), int)
                   for key in ("min_minor", "max_minor"))
            or supported["min_minor"] > requested["min_minor"]
            or supported["max_minor"] < requested["max_minor"]):
        raise DispatchContractError("registered executor does not declare a compatible resident execution contract")
    return {"binding": binding, "module": module, "module_id": binding["module_id"],
            "module_version": binding["module_version"], "artifact_digest": binding["artifact_digest"],
            "binding_revision": binding["binding_revision"],
            "configuration_ref": binding["configuration_ref"],
            "configuration_revision": binding["configuration_revision"]}


def build_resident_execution_profile(binding: dict[str, Any], directory_snapshot: dict[str, Any],
                                     configuration_path: str | Path) -> dict[str, Any]:
    """Join binding to a fresh authoritative directory row and the digest-pinned executor config."""
    checked = validate_resident_binding(binding)
    source = directory_snapshot.get("source") if isinstance(directory_snapshot, dict) else None
    if (not isinstance(source, dict) or source.get("availability") != "measured"
            or source.get("freshness") != "fresh" or not _SHA256.fullmatch(str(source.get("snapshot_sha256", "")))):
        raise DispatchContractError("authoritative resident directory snapshot is unavailable or stale")
    residents = [row for row in directory_snapshot.get("residents", [])
                 if isinstance(row, dict) and row.get("resident_id") == checked["resident_id"]]
    if len(residents) != 1:
        raise DispatchContractError("authoritative resident identity is missing or ambiguous")
    resident = residents[0]
    association = checked["identity_association"]
    if (association["authority"] != source.get("source_id")
            or association["record_id"] != resident.get("resident_id")
            or association["record_revision"] != resident.get("binding_revision")):
        raise DispatchContractError("configured resident binding does not match the current HR/directory association")
    config_path = Path(configuration_path)
    if not config_path.is_absolute() or not config_path.is_file():
        raise DispatchContractError("resident executor configuration reference is unavailable")
    config_bytes = config_path.read_bytes()
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    if config_digest != checked["configuration_revision"]:
        raise DispatchContractError("resident executor configuration revision does not match its digest")
    config = json.loads(config_bytes)
    route_id = config.get("resident_model_route_id")
    if route_id is None and isinstance(config.get("grace"), dict):
        grace = config["grace"]
        route_id = grace.get("default_route")
        if route_id is None and isinstance(grace.get("routes"), list) and grace["routes"]:
            route_id = grace["routes"][0].get("route_id")
        if route_id is None:
            route_id = "default"
    if not isinstance(route_id, str) or not route_id:
        raise DispatchContractError("resident executor configuration does not declare a model route")
    office_id, office_role = resident.get("office_id"), resident.get("office_role")
    if not isinstance(office_id, str) or not isinstance(office_role, str):
        raise DispatchContractError("authoritative resident record lacks its office association")
    return {"contract_id": "r3a.resident.execution-profile", "contract_version": "1.0.0",
            "resident_id": checked["resident_id"], "display_name": resident.get("display_name"),
            "office_id": office_id, "office_role": office_role,
            "directory_evidence": {"source_id": source["source_id"],
                                   "snapshot_sha256": source["snapshot_sha256"],
                                   "observed_at": source["observed_at"]},
            "model_route_id": route_id, "config_revision": config_digest}
