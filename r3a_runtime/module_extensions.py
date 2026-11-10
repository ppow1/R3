"""
R3 CONTROLLED SOURCE
File: r3a_runtime/module_extensions.py
Component: R3A-MODULE-EXTENSION-CONTRACTS
File Revision: 1.0.2
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Validate resident-executor bindings and durable activity-handler declarations.
Execution Model: Pure contract validation and registry resolution helpers.
Observability: Stable fail-closed diagnostics identify invalid metadata and compatibility.
Dependencies: Python standard library; capability contract JSON Schema validator.
Authority: AD-024; Modular Plugins #46. Bindings and registration grant no authority.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add generic resident and durable handler contract validation.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Resolve resident bindings against the active registry artifact and declared execution range.
Changed: 2026-11-10T01:26:34Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Validate configured binding targets against declared executor roles and immutable digests.
Supersedes: None
Contracts: r3a.resident.module-binding.v1; r3a.resident.execution-profile@1.0.0; r3a.activity-handler.v1; r3a.activity-intake.v1.
Tests: tests/test_r3a_module_extensions.py
History/Predecessor: Prior revision at commit 6eb7718, blob a1c351df83d9c6b6d1e377be7a15315b7c72dd9f.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any, Iterable

from .capability_contracts import CapabilityContractError, validate_json
from .module_contracts import semantic_version


class ModuleExtensionError(ValueError):
    """A role declaration is malformed, incompatible, or ambiguous."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$")
_RESIDENT_BINDING = Path(__file__).with_name("schemas") / "resident-module-binding.v1.schema.json"
_ACTIVITY_HANDLER = Path(__file__).with_name("schemas") / "activity-handler.v1.schema.json"


def _validate(value: Any, schema_path: Path, label: str) -> dict[str, Any]:
    import json

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate_json(value, schema)
    except (OSError, ValueError, CapabilityContractError) as exc:
        raise ModuleExtensionError(f"{label} is invalid: {exc}") from exc
    return dict(value)


def validate_resident_binding(value: Any) -> dict[str, Any]:
    """Validate a binding record without treating its HR reference as authority."""
    binding = _validate(value, _RESIDENT_BINDING, "resident module binding")
    if binding["contract_id"] != "r3a.resident.module-binding" or binding["contract_version"] != "1.0.0":
        raise ModuleExtensionError("resident module binding contract is incompatible")
    if not _IDENT.fullmatch(binding["resident_id"]):
        raise ModuleExtensionError("resident_id is not a canonical contract identifier")
    if not _IDENT.fullmatch(binding["module_id"]):
        raise ModuleExtensionError("module_id is invalid")
    try:
        semantic_version(binding["module_version"])
    except ValueError as exc:
        raise ModuleExtensionError("module_version must use semantic major.minor.patch") from exc
    association = binding["identity_association"]
    if association["record_id"] != binding["resident_id"]:
        raise ModuleExtensionError("identity association does not identify the bound resident")
    if not compatible_contract_range(binding["execution_contract_range"],
                                     contract_id="r3a.resident.execution", major=1, minor=0):
        raise ModuleExtensionError("resident execution contract range is incompatible with host v1.0")
    return binding


def validate_resident_bindings(values: Any) -> tuple[dict[str, Any], ...]:
    """Validate an external binding list and require one effective binding per resident."""
    if not isinstance(values, list):
        raise ModuleExtensionError("resident_module_bindings must be an array")
    bindings = tuple(validate_resident_binding(value) for value in values)
    resident_ids = [item["resident_id"] for item in bindings]
    if len(resident_ids) != len(set(resident_ids)):
        raise ModuleExtensionError("resident_module_bindings contains duplicate resident identities")
    return bindings


def validate_executor_configuration(binding: dict[str, Any], *, configuration_root: str | Path,
                                    schema: dict[str, Any]) -> dict[str, Any]:
    """Read and validate digest-pinned executor configuration under an approved root."""
    checked = validate_resident_binding(binding)
    reference = Path(checked["configuration_ref"])
    root = Path(configuration_root).resolve()
    if reference.is_absolute():
        raise ModuleExtensionError("executor configuration_ref must be relative to its configuration root")
    path = (root / reference).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ModuleExtensionError("executor configuration reference is unavailable or escapes its root")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != checked["configuration_revision"]:
        raise ModuleExtensionError("executor configuration revision does not match its content digest")
    import json
    try:
        value = json.loads(raw)
        validate_json(value, schema)
    except (UnicodeError, json.JSONDecodeError, CapabilityContractError) as exc:
        raise ModuleExtensionError(f"executor configuration is invalid: {exc}") from exc
    return value


def validate_activity_handler(value: Any) -> dict[str, Any]:
    """Validate generic handler metadata, including schemas and recovery/resource declarations."""
    handler = _validate(value, _ACTIVITY_HANDLER, "activity handler")
    if handler["contract_id"] != "r3a.activity-handler" or handler["contract_version"] != "1.0.0":
        raise ModuleExtensionError("activity handler contract is incompatible")
    try:
        semantic_version(handler["handler_version"])
    except ValueError as exc:
        raise ModuleExtensionError("handler_version must use semantic major.minor.patch") from exc
    for activity_type in handler["activity_types"]:
        if not _IDENT.fullmatch(activity_type):
            raise ModuleExtensionError("activity_types contains an invalid identifier")
    schema_fields = ("request_schema", "result_schema", "progress_schema", "checkpoint_schema")
    for field in schema_fields:
        if not isinstance(handler[field], dict):
            raise ModuleExtensionError(f"{field} must be a JSON Schema object")
        _validate_schema_declaration(handler[field], field)
    for key, contract_id in (("activity_contract_range", "r3a.activity-intake"),
                             ("handler_contract_range", "r3a.activity-handler")):
        version_range = handler[key]
        if (version_range["contract_id"] != contract_id
                or version_range["major"] != 1
                or version_range["min_minor"] > version_range["max_minor"]):
            raise ModuleExtensionError(f"{key} is incompatible")
    constraints = handler["resource_constraints"]
    if any(isinstance(constraints[key], bool) or not isinstance(constraints[key], int)
           or constraints[key] < 1 for key in ("cpu_millis", "memory_bytes", "max_concurrency")):
        raise ModuleExtensionError("resource_constraints must declare positive integer requirements")
    if handler["recovery"]["mode"] == "checkpointed" and not handler["recovery"]["checkpoint_contract"]:
        raise ModuleExtensionError("checkpointed recovery requires a checkpoint contract")
    return handler


def _validate_schema_declaration(schema: Any, field: str, depth: int = 0) -> None:
    """Check the same portable JSON Schema subset used for module configuration."""
    supported = {"object", "array", "string", "integer", "number", "boolean", "null"}
    if depth > 32 or not isinstance(schema, dict):
        raise ModuleExtensionError(f"{field} schema nesting is invalid")
    supported_keywords = {"$schema", "$id", "title", "description", "type", "properties",
                          "required", "additionalProperties", "items", "minItems", "maxItems",
                          "uniqueItems", "minLength", "maxLength", "pattern", "enum", "const",
                          "minimum", "maximum"}
    if set(schema) - supported_keywords:
        raise ModuleExtensionError(f"{field} schema uses unsupported keywords")
    kind = schema.get("type")
    if isinstance(kind, list):
        types = kind
    else:
        types = [kind]
    if not types or any(item not in supported for item in types):
        raise ModuleExtensionError(f"{field} schema uses an unsupported JSON type")
    if "properties" in schema:
        properties = schema["properties"]
        if not isinstance(properties, dict):
            raise ModuleExtensionError(f"{field}.properties must be an object")
        required = schema.get("required", [])
        if (not isinstance(required, list) or any(not isinstance(key, str) for key in required)
                or not set(required).issubset(properties)):
            raise ModuleExtensionError(f"{field}.required must reference declared properties")
        for name, child in properties.items():
            if not isinstance(name, str):
                raise ModuleExtensionError(f"{field} property names must be text")
            _validate_schema_declaration(child, f"{field}.{name}", depth + 1)
    if "items" in schema:
        _validate_schema_declaration(schema["items"], f"{field}[]", depth + 1)
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], (bool, dict)):
        raise ModuleExtensionError(f"{field}.additionalProperties is invalid")
    if isinstance(schema.get("additionalProperties"), dict):
        _validate_schema_declaration(schema["additionalProperties"], f"{field}.*", depth + 1)
    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            raise ModuleExtensionError(f"{field}.pattern must be text")
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ModuleExtensionError(f"{field}.pattern is invalid") from exc
    for lower, upper in (("minItems", "maxItems"), ("minLength", "maxLength"), ("minimum", "maximum")):
        lo, hi = schema.get(lower), schema.get(upper)
        if lo is not None and (isinstance(lo, bool) or not isinstance(lo, (int, float))):
            raise ModuleExtensionError(f"{field}.{lower} has an invalid bound")
        if hi is not None and (isinstance(hi, bool) or not isinstance(hi, (int, float))):
            raise ModuleExtensionError(f"{field}.{upper} has an invalid bound")
        if ((isinstance(lo, float) and not math.isfinite(lo))
                or (isinstance(hi, float) and not math.isfinite(hi))
                or (lo is not None and hi is not None and lo > hi)):
            raise ModuleExtensionError(f"{field} has an invalid range")


def validate_resident_executor_declaration(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
            "contract_id", "contract_version", "execution_contract_range"}:
        raise ModuleExtensionError("resident_executor declaration fields are invalid")
    if value["contract_id"] != "r3a.resident.executor" or value["contract_version"] != "1.0.0":
        raise ModuleExtensionError("resident_executor declaration contract is incompatible")
    version_range = value["execution_contract_range"]
    if (not isinstance(version_range, dict)
            or set(version_range) != {"contract_id", "major", "min_minor", "max_minor"}
            or version_range["contract_id"] != "r3a.resident.execution"
            or version_range["major"] != 1
            or any(isinstance(version_range[key], bool) or not isinstance(version_range[key], int)
                   for key in ("major", "min_minor", "max_minor"))
            or version_range["min_minor"] < 0
            or version_range["max_minor"] < version_range["min_minor"]):
        raise ModuleExtensionError("resident executor contract range is invalid or incompatible")
    return dict(value)


def resolve_resident_binding(bindings: Iterable[dict[str, Any]], resident_id: str,
                             identity_association: dict[str, str],
                             modules: Iterable[dict[str, Any]], *,
                             execution_contract_minor: int = 0) -> dict[str, Any]:
    """Resolve one authoritative identity to one active, declared executor version."""
    checked = [validate_resident_binding(item) for item in bindings
               if isinstance(item, dict) and item.get("resident_id") == resident_id]
    if len(checked) != 1:
        raise ModuleExtensionError("resident module binding is missing or ambiguous")
    binding = checked[0]
    if binding["identity_association"] != identity_association:
        raise ModuleExtensionError("resident identity/HR association is invalid or stale")
    module_rows = [item for item in modules if isinstance(item, dict)
                   and item.get("module_id") == binding["module_id"]
                   and item.get("module_version") == binding["module_version"]]
    if len(module_rows) != 1:
        raise ModuleExtensionError("bound resident executor is missing or ambiguous in the module registry")
    module = module_rows[0]
    if module.get("lifecycle_state") != "ACTIVE":
        raise ModuleExtensionError("bound resident executor is not active")
    manifest = module.get("manifest")
    if (not isinstance(manifest, dict)
            or manifest.get("module_id") != binding["module_id"]
            or manifest.get("module_version") != binding["module_version"]
            or manifest.get("artifact_digest") != binding["artifact_digest"]
            or not _SHA256.fullmatch(str(manifest.get("artifact_digest", "")))):
        raise ModuleExtensionError("bound resident executor artifact does not match registry identity")
    validate_resident_binding_target(binding, manifest)
    return {"binding": binding, "module": module, "module_id": binding["module_id"],
            "module_version": binding["module_version"], "artifact_digest": binding["artifact_digest"],
            "binding_revision": binding["binding_revision"],
            "configuration_ref": binding["configuration_ref"],
            "configuration_revision": binding["configuration_revision"]}


def validate_resident_binding_target(binding: dict[str, Any], module_manifest: dict[str, Any], *,
                                     execution_contract_minor: int = 0) -> dict[str, Any]:
    """Validate that binding metadata names a module manifest declaring that role."""
    binding = validate_resident_binding(binding)
    if (not isinstance(module_manifest, dict)
            or module_manifest.get("module_id") != binding["module_id"]
            or module_manifest.get("module_version") != binding["module_version"]
            or module_manifest.get("artifact_digest") != binding["artifact_digest"]
            or not _SHA256.fullmatch(str(module_manifest.get("artifact_digest", "")))):
        raise ModuleExtensionError("resident binding does not match the declared module version and artifact")
    declaration = validate_resident_executor_declaration(module_manifest.get("resident_executor"))
    supported = declaration["execution_contract_range"]
    requested = binding["execution_contract_range"]
    if (not compatible_contract_range(supported, contract_id="r3a.resident.execution", major=1,
                                      minor=execution_contract_minor)
            or not compatible_contract_range(requested, contract_id="r3a.resident.execution",
                                             major=1, minor=execution_contract_minor)
            or requested["min_minor"] < supported["min_minor"]
            or requested["max_minor"] > supported["max_minor"]):
        raise ModuleExtensionError("resident executor contract range is incompatible with registered module")
    return declaration


def validate_resident_binding_targets(bindings: Iterable[dict[str, Any]],
                                      modules: Iterable[dict[str, Any]], *,
                                      execution_contract_minor: int = 0) -> tuple[dict[str, Any], ...]:
    """Ensure each configured binding names one declared role and pinned artifact."""
    declarations: dict[tuple[str, str], dict[str, Any]] = {}
    for module in modules:
        if not isinstance(module, dict):
            continue
        key = (str(module.get("module_id", "")), str(module.get("module_version", "")))
        if key in declarations and declarations[key] != module:
            raise ModuleExtensionError("module registry contains conflicting declarations for one version")
        declarations[key] = module
    validated = []
    for raw in bindings:
        binding = validate_resident_binding(raw)
        target = declarations.get((binding["module_id"], binding["module_version"]))
        if target is None:
            raise ModuleExtensionError("resident binding references an unregistered module version")
        validate_resident_binding_target(binding, target,
                                         execution_contract_minor=execution_contract_minor)
        validated.append(binding)
    return tuple(validated)


def compatible_contract_range(value: dict[str, Any], *, contract_id: str,
                              major: int, minor: int) -> bool:
    """Return true only when a declared major/minor range admits the host contract."""
    if value.get("contract_id") != contract_id or value.get("major") != major:
        return False
    lo, hi = value.get("min_minor"), value.get("max_minor")
    return (isinstance(lo, int) and not isinstance(lo, bool)
            and isinstance(hi, int) and not isinstance(hi, bool)
            and lo <= minor <= hi)


def resolve_activity_handler(registry: Iterable[dict[str, Any]], activity_type: str, *,
                             activity_contract_minor: int = 0) -> dict[str, Any]:
    """Resolve exactly one active, digest-pinned compatible registered handler."""
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in registry:
        if not isinstance(row, dict) or row.get("lifecycle_state") != "ACTIVE":
            continue
        manifest = row.get("manifest")
        handler_raw = manifest.get("activity_handler") if isinstance(manifest, dict) else None
        if handler_raw is None:
            continue
        handler = validate_activity_handler(handler_raw)
        if activity_type not in handler["activity_types"]:
            continue
        if not compatible_contract_range(handler["activity_contract_range"],
                                         contract_id="r3a.activity-intake", major=1,
                                         minor=activity_contract_minor):
            continue
        if not compatible_contract_range(handler["handler_contract_range"],
                                         contract_id="r3a.activity-handler", major=1, minor=0):
            continue
        if not _SHA256.fullmatch(str(manifest.get("artifact_digest", ""))):
            raise ModuleExtensionError("registered handler artifact digest is invalid")
        if (manifest.get("module_id") != row.get("module_id")
                or manifest.get("module_version") != row.get("module_version")):
            raise ModuleExtensionError("registered handler manifest identity does not match registry")
        candidates.append((row, handler))
    if len(candidates) != 1:
        raise ModuleExtensionError("activity handler is missing, ambiguous, disabled, or incompatible")
    row, handler = candidates[0]
    return {"module": row, "handler": handler, "module_id": row["module_id"],
            "module_version": row["module_version"],
            "artifact_digest": row["manifest"]["artifact_digest"]}
