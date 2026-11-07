"""Canonical R3A capability contracts, provider interface, and dynamic registry.

This module validates JSON Schema Draft 2020-12's intentionally small portable
subset used in R3A operation manifests and typed invocation payloads. It owns
discovery and provider binding only; CME owns authorization and dispatch.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import re
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


OPERATION_CONTRACT_ID = "r3a.capability-operation.v1"
INVOCATION_CONTRACT_ID = "r3a.capability-invocation.v1"
CONTRACT_VERSION = "1.0.0"
EFFECT_CLASSES = frozenset({"read", "isolated_write", "external_write"})
_SCHEMA_DIR = Path(__file__).with_name("schemas")


class CapabilityContractError(ValueError):
    """A capability operation, invocation, result, or registration is invalid."""


@dataclass(frozen=True)
class CapabilityProviderResult:
    """Typed provider boundary for operations whose output differs from its evidence."""

    output: Any
    evidence: Any


@runtime_checkable
class CapabilityProvider(Protocol):
    """Provider API. CME performs auth/dispatch, then invokes this typed boundary."""

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> Any:
        """Execute one operation; return output or CapabilityProviderResult(output, evidence)."""


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((_SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }[expected](value)


def validate_json(value: Any, schema: dict[str, Any], *, path: str = "$",
                  root_schema: dict[str, Any] | None = None) -> None:
    """Validate the portable JSON Schema subset and fail with a stable path."""
    if not isinstance(schema, dict):
        raise CapabilityContractError(f"{path}: schema must be an object")
    root = root_schema or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise CapabilityContractError(f"{path}: external schema references are unsupported")
        target: Any = root
        try:
            for key in ref[2:].split("/"):
                target = target[key.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            raise CapabilityContractError(f"{path}: unresolved schema reference") from None
        validate_json(value, target, path=path, root_schema=root)
        return
    expected = schema.get("type")
    if isinstance(expected, list):
        if not any(_type_matches(value, item) for item in expected):
            raise CapabilityContractError(f"{path}: value has the wrong type")
    elif expected and not _type_matches(value, expected):
        raise CapabilityContractError(f"{path}: expected {expected}")
    if "const" in schema and value != schema["const"]:
        raise CapabilityContractError(f"{path}: value does not match const")
    if "enum" in schema and value not in schema["enum"]:
        raise CapabilityContractError(f"{path}: value is outside enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        missing = set(required) - value.keys()
        if missing:
            raise CapabilityContractError(f"{path}: missing required fields {sorted(missing)}")
        extra = value.keys() - properties.keys()
        additional = schema.get("additionalProperties", True)
        if extra and additional is False:
            raise CapabilityContractError(f"{path}: unknown fields {sorted(extra)}")
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None and isinstance(additional, dict):
                child_schema = additional
            if child_schema is not None:
                validate_json(item, child_schema, path=f"{path}.{key}", root_schema=root)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise CapabilityContractError(f"{path}: array size is outside bounds")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise CapabilityContractError(f"{path}: array values must be unique")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                validate_json(item, schema["items"], path=f"{path}[{i}]", root_schema=root)
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf")):
            raise CapabilityContractError(f"{path}: string length is outside bounds")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise CapabilityContractError(f"{path}: string does not match pattern")
        if schema.get("format") == "date-time":
            _timestamp(value, path)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise CapabilityContractError(f"{path}: number must be finite")
        if value < schema.get("minimum", float("-inf")) or value > schema.get("maximum", float("inf")):
            raise CapabilityContractError(f"{path}: number is outside bounds")


def _timestamp(value: str, field: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise CapabilityContractError(f"{field}: expected ISO-8601 date-time") from None
    if result.tzinfo is None:
        raise CapabilityContractError(f"{field}: timestamp must include a timezone")
    return result.astimezone(timezone.utc)


def validate_schema_definition(schema: Any, *, path: str = "schema") -> None:
    """Validate R3A's supported self-contained JSON Schema subset."""
    if not isinstance(schema, dict):
        raise CapabilityContractError(f"{path}: schema must be an object")
    allowed = {"$schema", "$id", "title", "description", "type", "required", "properties",
               "additionalProperties", "items", "enum", "const", "pattern", "format",
               "minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum",
               "uniqueItems"}
    if set(schema) - allowed:
        raise CapabilityContractError(f"{path}: unsupported schema keywords {sorted(set(schema)-allowed)}")
    schema_type = schema.get("type")
    valid_types = {"object", "array", "string", "integer", "number", "boolean", "null"}
    type_set = set(schema_type) if isinstance(schema_type, list) else {schema_type}
    if not type_set or not type_set.issubset(valid_types) or (isinstance(schema_type, list) and len(type_set) != len(schema_type)):
        raise CapabilityContractError(f"{path}: unsupported schema type")
    if "object" in type_set:
        properties = schema.get("properties", {})
        if not isinstance(properties, dict) or any(not isinstance(k, str) for k in properties):
            raise CapabilityContractError(f"{path}.properties must be an object")
        required = schema.get("required", [])
        if (not isinstance(required, list) or any(not isinstance(k, str) for k in required)
                or not set(required).issubset(properties)):
            raise CapabilityContractError(f"{path}.required must name declared properties")
        additional = schema.get("additionalProperties", False)
        if not isinstance(additional, (bool, dict)):
            raise CapabilityContractError(f"{path}.additionalProperties must be boolean or a schema")
        if isinstance(additional, dict):
            validate_schema_definition(additional, path=f"{path}.additionalProperties")
        for key, child in properties.items():
            validate_schema_definition(child, path=f"{path}.{key}")
    if "array" in type_set:
        if "items" not in schema:
            raise CapabilityContractError(f"{path}.items is required for array schemas")
        validate_schema_definition(schema["items"], path=f"{path}.items")
        if schema.get("uniqueItems", False) not in (True, False):
            raise CapabilityContractError(f"{path}.uniqueItems must be boolean")
    if "string" in type_set:
        if "pattern" in schema:
            try:
                re.compile(schema["pattern"])
            except (TypeError, re.error):
                raise CapabilityContractError(f"{path}.pattern is invalid") from None
        if schema.get("format") not in (None, "date-time"):
            raise CapabilityContractError(f"{path}.format is unsupported")
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and (isinstance(schema[key], bool) or not isinstance(schema[key], int) or schema[key] < 0):
            raise CapabilityContractError(f"{path}.{key} must be a nonnegative integer")
    for key in ("minimum", "maximum"):
        if key in schema and (isinstance(schema[key], bool) or not isinstance(schema[key], (int, float))
                              or not math.isfinite(schema[key])):
            raise CapabilityContractError(f"{path}.{key} must be finite numeric")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise CapabilityContractError(f"{path}.enum must be an array")


def validate_operation(descriptor: Any) -> dict[str, Any]:
    schema = _load_schema("capability-operation.v1.schema.json")
    validate_json(descriptor, schema)
    for field in ("input_schema", "output_schema", "target_scope_schema"):
        validate_schema_definition(descriptor[field], path=f"$.{field}")
    validate_schema_definition(descriptor["evidence"]["schema"], path="$.evidence.schema")
    if descriptor["effect_class"] != "read" and not descriptor["recovery"]["idempotency_required"]:
        raise CapabilityContractError("write operations must require a stable idempotency key")
    if descriptor["recovery"]["idempotency_required"] and not descriptor["recovery"]["replay_safe"]:
        if descriptor["recovery"]["reconciliation_operation_id"] is None:
            # A non-replayable operation must have explicit reconciliation or be fail-closed.
            disposition = descriptor["execution"]["retry_disposition"]
            if disposition != "never":
                raise CapabilityContractError("non-replayable operation without reconciliation must never retry")
    return copy.deepcopy(descriptor)


def validate_invocation_request(request: Any, descriptor: dict[str, Any]) -> dict[str, Any]:
    schema = _load_schema("capability-invocation.v1.schema.json")
    request_schema = schema["$defs"]["request"]
    validate_json(request, request_schema, root_schema=schema)
    if request["operation_id"] != descriptor["operation_id"]:
        raise CapabilityContractError("invocation operation_id does not match registered operation")
    if request["operation_contract_version"] != descriptor["contract_version"]:
        raise CapabilityContractError("invocation operation contract version is unsupported")
    constraints = descriptor["caller_constraints"]
    caller = request["caller"]
    for field, caller_key in (("allowed_principals", "principal_id"),
                              ("allowed_residents", "resident_id"),
                              ("allowed_services", "service_id")):
        allowed = constraints[field]
        if allowed and caller[caller_key] not in allowed:
            raise CapabilityContractError(f"caller is outside {field}")
    validate_json(request["input"], descriptor["input_schema"], path="$.input")
    validate_json(request["target"], descriptor["target_scope_schema"], path="$.target")
    if descriptor["recovery"]["idempotency_required"] and not request["idempotency_key"]:
        raise CapabilityContractError("operation requires an idempotency key")
    deadline = request["deadline"]
    if deadline and _timestamp(deadline, "$.deadline") <= datetime.now(timezone.utc):
        raise CapabilityContractError("invocation deadline has expired")
    return copy.deepcopy(request)


def validate_invocation_result(result: Any, descriptor: dict[str, Any]) -> dict[str, Any]:
    schema = _load_schema("capability-invocation.v1.schema.json")
    result_schema = schema["$defs"]["result"]
    validate_json(result, result_schema, root_schema=schema)
    if result["operation_id"] != descriptor["operation_id"]:
        raise CapabilityContractError("result operation_id does not match registered operation")
    if result["operation_contract_version"] != descriptor["contract_version"]:
        raise CapabilityContractError("result operation contract version is unsupported")
    expected_provider = descriptor["provider"]
    if (result["provider"]["provider_id"] != expected_provider["provider_id"]
            or result["provider"]["provider_version"] != expected_provider["provider_version"]
            or result["provider"]["artifact_sha256"] != expected_provider["artifact_sha256"]):
        raise CapabilityContractError("result provider provenance does not match the registered descriptor")
    started, finished = _timestamp(result["started_at"], "$.started_at"), _timestamp(result["finished_at"], "$.finished_at")
    if finished < started:
        raise CapabilityContractError("result finished_at precedes started_at")
    if result["outcome"] == "SUCCEEDED":
        if result["output"] is None or result["error"] is not None:
            raise CapabilityContractError("SUCCEEDED result requires output and forbids error")
        validate_json(result["output"], descriptor["output_schema"], path="$.output")
    elif result["outcome"] in {"FAILED", "DENIED", "DEFERRED", "UNKNOWN"}:
        if result["error"] is None or result["output"] is not None:
            raise CapabilityContractError("non-success result requires error and forbids output")
    if result["outcome"] == "SUCCEEDED":
        evidence_schema = descriptor["evidence"]["schema"]
        if evidence_schema.get("type") == "array":
            validate_json(result["evidence"], evidence_schema, path="$.evidence")
        else:
            for index, item in enumerate(result["evidence"]):
                validate_json(item, evidence_schema, path=f"$.evidence[{index}]")
    if result["outcome"] == "DENIED" and result["effect_disposition"] != "NOT_STARTED":
        raise CapabilityContractError("DENIED invocation must have NOT_STARTED effect disposition")
    if result["outcome"] == "SUCCEEDED" and (result["authorization"] is None
                                               or result["authorization"]["allowed"] is not True):
        raise CapabilityContractError("SUCCEEDED result requires a CME ALLOW decision reference")
    if result["outcome"] == "DENIED" and (result["authorization"] is None
                                             or result["authorization"]["allowed"] is not False):
        raise CapabilityContractError("DENIED result requires a CME DENY decision reference")
    if result["outcome"] in {"FAILED", "DEFERRED"} and result["authorization"] is None:
        raise CapabilityContractError("provider execution result requires a CME authorization reference")
    if result["outcome"] in {"SUCCEEDED", "FAILED", "DENIED"} and (
            not result["authorization"]["decision_id"] or not result["authorization"]["audit_event_id"]):
        raise CapabilityContractError("completed authorization requires decision and audit references")
    if result["outcome"] == "SUCCEEDED":
        expected_disposition = "NOT_STARTED" if descriptor["effect_class"] == "read" else "COMMITTED"
        if result["effect_disposition"] != expected_disposition:
            raise CapabilityContractError("successful result has an invalid effect disposition")
    if result["outcome"] == "UNKNOWN" and result["effect_disposition"] != "UNKNOWN":
        raise CapabilityContractError("UNKNOWN result requires UNKNOWN effect disposition")
    return copy.deepcopy(result)


def normalize_provider_result(value: Any, descriptor: dict[str, Any]) -> tuple[Any, Any]:
    """Validate provider output and evidence without inventing evidence fields.

    Existing providers may return their evidence as the output when it satisfies both
    schemas. Providers with distinct shapes return CapabilityProviderResult explicitly.
    """
    if isinstance(value, CapabilityProviderResult):
        output, evidence = value.output, value.evidence
    else:
        output = evidence = value
    validate_json(output, descriptor["output_schema"], path="$.output")
    evidence_schema = descriptor["evidence"]["schema"]
    if evidence_schema.get("type") == "array":
        validate_json(evidence, evidence_schema, path="$.evidence")
    elif isinstance(evidence, list):
        for index, item in enumerate(evidence):
            validate_json(item, evidence_schema, path=f"$.evidence[{index}]")
    else:
        validate_json(evidence, evidence_schema, path="$.evidence")
    return copy.deepcopy(output), copy.deepcopy(evidence)


@dataclass(frozen=True)
class RegisteredOperation:
    descriptor: dict[str, Any]
    configuration: dict[str, Any]
    legacy_manifest: dict[str, Any] | None = None

    def resident_tool_projection(self) -> dict[str, Any]:
        """Compatibility projection for the pre-v1 resident tool schema only."""
        descriptor = self.descriptor
        tool = (self.legacy_manifest or {}).get("tool")
        display = descriptor.get("resident_tool", {})
        return {"contract_id": (self.legacy_manifest or {}).get("contract_id", "r3a.resident-capability-tool"),
                "contract_version": (self.legacy_manifest or {}).get("contract_version", CONTRACT_VERSION),
                "capability_id": descriptor["operation_id"],
                "name": (tool or {}).get("name", display.get("name", descriptor["operation_id"].replace(".", "_"))),
                "description": (tool or {}).get("description", display.get("description", "")),
                "arguments_schema": (tool or {}).get("arguments_schema", descriptor["input_schema"])}

    def load_provider(self) -> CapabilityProvider:
        if self.legacy_manifest is not None and "operation" not in self.legacy_manifest:
            module_name, object_name = self.legacy_manifest["entrypoint"].split(":", 1)
            module = importlib.import_module(module_name)
            _assert_module_digest(module, self.descriptor["provider"]["artifact_sha256"])
            function = getattr(module, object_name)

            class LegacyReadOnlyProvider:
                def invoke(inner_self, arguments: dict[str, Any], *, context: dict[str, Any]) -> Any:
                    if arguments:
                        raise CapabilityContractError("legacy read-only provider accepts no arguments")
                    return function(self.configuration)

            return LegacyReadOnlyProvider()
        module_name, object_name = self.descriptor["provider"]["entrypoint"].split(":", 1)
        module = importlib.import_module(module_name)
        _assert_module_digest(module, self.descriptor["provider"]["artifact_sha256"])
        factory = getattr(module, object_name)
        provider = factory(self.configuration)
        if not isinstance(provider, CapabilityProvider):
            raise CapabilityContractError("provider entrypoint did not return a CapabilityProvider")
        return provider


def _assert_module_digest(module: Any, expected_digest: str) -> None:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not Path(module_file).is_file():
        raise CapabilityContractError("provider entrypoint has no inspectable source file")
    actual = hashlib.sha256(Path(module_file).read_bytes()).hexdigest()
    if actual != expected_digest:
        raise CapabilityContractError("provider entrypoint source does not match its pinned artifact digest")


class CapabilityRegistry:
    """Single in-process dynamic registry. Discovery makes no authorization decision."""

    def __init__(self) -> None:
        self._operations: dict[str, RegisteredOperation] = {}

    def register(self, descriptor: dict[str, Any], configuration: dict[str, Any], *,
                 legacy_manifest: dict[str, Any] | None = None) -> RegisteredOperation:
        checked = validate_operation(descriptor)
        operation_id = checked["operation_id"]
        if operation_id in self._operations:
            raise CapabilityContractError(f"operation already registered: {operation_id}")
        if not isinstance(configuration, dict):
            raise CapabilityContractError("provider configuration must be an object")
        registered = RegisteredOperation(checked, copy.deepcopy(configuration), copy.deepcopy(legacy_manifest))
        self._operations[operation_id] = registered
        return self._copy(registered)

    def discover(self, *, include_disabled: bool = False) -> tuple[dict[str, Any], ...]:
        """Return operation descriptors and registry health, never grants/authorization."""
        records = []
        for item in sorted(self._operations.values(), key=lambda x: x.descriptor["operation_id"]):
            descriptor = item.descriptor
            if descriptor["lifecycle"]["desired_state"] == "disabled" and not include_disabled:
                continue
            presentation = descriptor.get("resident_tool", {})
            records.append({"descriptor": copy.deepcopy(descriptor),
                            "presentation": {
                                "name": presentation.get("name") or descriptor["operation_id"].replace(".", "_"),
                                "description": presentation.get("description", ""),
                                "description_registered": bool(presentation.get("description")),
                            },
                            "registry_observation": {
                                "state": "registered", "health": "not_probed",
                                "provider_availability": "not_probed",
                                "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}})
        return tuple(records)

    def resolve(self, operation_id: str, contract_version: str = CONTRACT_VERSION) -> RegisteredOperation:
        operation = self._operations.get(operation_id)
        if operation is None:
            raise KeyError(f"unknown operation: {operation_id}")
        if operation.descriptor["contract_version"] != contract_version:
            raise CapabilityContractError("operation contract version mismatch")
        if operation.descriptor["lifecycle"]["desired_state"] != "enabled":
            raise CapabilityContractError("operation is disabled")
        return self._copy(operation)

    @staticmethod
    def _copy(operation: RegisteredOperation) -> RegisteredOperation:
        return RegisteredOperation(copy.deepcopy(operation.descriptor),
                                   copy.deepcopy(operation.configuration),
                                   copy.deepcopy(operation.legacy_manifest))

    def __len__(self) -> int:
        return len(self._operations)


def legacy_read_only_operation(manifest: dict[str, Any]) -> dict[str, Any]:
    """Translate a legacy manifest into the canonical descriptor; never infer write."""
    if manifest.get("read_only") is not True:
        raise CapabilityContractError("legacy manifest without read_only=true cannot be adapted")
    provider_entrypoint = manifest.get("provider", {}).get("entrypoint", manifest.get("entrypoint"))
    provider_version = manifest.get("provider", {}).get("provider_version", manifest.get("plugin_version"))
    provider_id = manifest.get("provider", {}).get("provider_id", manifest.get("plugin_id"))
    artifact_digest = manifest.get("provider", {}).get("artifact_sha256", manifest.get("artifact_sha256"))
    tool = manifest.get("tool", {})
    return {
        "contract_id": OPERATION_CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "operation_id": manifest["capability_id"], "operation_revision": manifest.get("plugin_version", "legacy"),
        "provider": {"provider_id": provider_id, "provider_version": provider_version,
                     "entrypoint": provider_entrypoint, "artifact_sha256": artifact_digest},
        "input_schema": tool.get("arguments_schema", {"type": "object", "properties": {}, "additionalProperties": False}),
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "effect_class": "read",
        "caller_constraints": {"allowed_principals": [], "allowed_residents": [], "allowed_services": []},
        "target_scope_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "required_grants": [manifest["capability_id"]],
        "evidence": {"schema": {"type": "object"}, "verification_obligations": ["verify_source_and_freshness"]},
        "recovery": {"idempotency_required": False, "idempotency_scope": "invocation", "replay_safe": True,
                     "reconciliation_operation_id": None},
        "execution": {"timeout_seconds": 30, "retry_disposition": "safe_retry"},
        "lifecycle": {"desired_state": "enabled"},
        "resident_tool": {"name": tool.get("name", manifest["capability_id"]),
                           "description": tool.get("description", "")},
    }


def operation_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Load a canonical descriptor or adapt an explicitly read-only legacy manifest."""
    if "operation" in manifest:
        descriptor = validate_operation(manifest["operation"])
        provider = manifest.get("provider")
        if not isinstance(provider, dict) or provider != descriptor["provider"]:
            raise CapabilityContractError("manifest provider binding does not match operation descriptor")
    else:
        legacy_required = {"contract_id", "contract_version", "capability_id", "tool", "entrypoint", "read_only"}
        if not legacy_required.issubset(manifest):
            raise CapabilityContractError("legacy manifest is missing compatibility fields")
        descriptor = validate_operation(legacy_read_only_operation(manifest))
    operation_id = descriptor["operation_id"]
    if manifest.get("capability_id", operation_id) != operation_id:
        raise CapabilityContractError("legacy capability_id must match operation_id")
    if "read_only" in manifest and manifest["read_only"] is not (descriptor["effect_class"] == "read"):
        raise CapabilityContractError("legacy read_only projection conflicts with canonical effect_class")
    return descriptor
