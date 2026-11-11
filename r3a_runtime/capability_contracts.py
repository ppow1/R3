# R3 CONTROLLED SOURCE
# File: r3a_runtime/capability_contracts.py
# Component: R3A-CAPABILITY-CONTRACTS
# File Revision: 1.0.2
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Validate typed capability operations, provider manifests, invocations, and module registration metadata.
# Execution Model: Pure contract validation and dynamic in-process registry.
# Observability: Stable contract validation failures before registration or invocation.
# Dependencies: Python standard library; versioned JSON schemas under r3a_runtime/schemas.
# Authority: Existing R3A capability-provider architecture; AD-024 permits additive module role metadata.
# Changed: 2026-11-10T02:02:46Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Select the declared module-manifest minor schema and reject role metadata under v1.0.0.
# Supersedes: None
# Contracts: r3a.capability-operation.v1; r3a.capability-invocation.v1; r3a.module-manifest.v1@1.0.0 and @1.1.0; AD-024 role contracts.
# Tests: tests/test_r3a_capability_contracts.py; tests/test_r3a_module_extensions.py.
# History/Predecessor: Prior source at integration commit 9a41d7e9647d37c2b7dc6f2aca3be3f5f82ccfe9, blob cedb0e412df130e1db842a8ef116085cc6c8cbc8.
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
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


OPERATION_CONTRACT_ID = "r3a.capability-operation.v1"
INVOCATION_CONTRACT_ID = "r3a.capability-invocation.v1"
CONTRACT_VERSION = "1.0.0"
EFFECT_CLASSES = frozenset({"read", "isolated_write", "external_write", "steward_read", "steward_write"})
_SCHEMA_DIR = Path(__file__).with_name("schemas")


class CapabilityContractError(ValueError):
    """A capability operation, invocation, result, or registration is invalid."""


@dataclass(frozen=True)
class CapabilityProviderResult:
    """Typed provider boundary for operations whose output differs from its evidence."""

    output: Any
    evidence: Any


def _humanize_capability_name(value: str) -> str:
    """Render a registered label/legacy ID as readable text without changing its identity."""
    words = re.sub(r"[._:-]+", " ", str(value)).split()
    return " ".join(word if word.isupper() else word[:1].upper() + word[1:] for word in words)


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
                  root_schema: dict[str, Any] | None = None,
                  _ref_stack: frozenset[str] = frozenset()) -> None:
    """Validate the portable JSON Schema subset and fail with a stable path."""
    if not isinstance(schema, dict):
        raise CapabilityContractError(f"{path}: schema must be an object")
    root = root_schema or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise CapabilityContractError(f"{path}: external schema references are unsupported")
        if ref in _ref_stack:
            raise CapabilityContractError(f"{path}: recursive schema references are unsupported")
        target: Any = root
        try:
            for key in ref[2:].split("/"):
                target = target[key.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            raise CapabilityContractError(f"{path}: unresolved schema reference") from None
        validate_json(value, target, path=path, root_schema=root, _ref_stack=_ref_stack | {ref})
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
                validate_json(item, child_schema, path=f"{path}.{key}", root_schema=root,
                              _ref_stack=_ref_stack)
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            raise CapabilityContractError(f"{path}: array size is outside bounds")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise CapabilityContractError(f"{path}: array values must be unique")
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                validate_json(item, schema["items"], path=f"{path}[{i}]", root_schema=root,
                              _ref_stack=_ref_stack)
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


def validate_schema_definition(schema: Any, *, path: str = "schema",
                              root_schema: dict[str, Any] | None = None,
                              _ref_stack: frozenset[str] = frozenset()) -> None:
    """Validate R3A's supported self-contained JSON Schema subset."""
    if not isinstance(schema, dict):
        raise CapabilityContractError(f"{path}: schema must be an object")
    root = root_schema or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or set(schema) != {"$ref"}:
            raise CapabilityContractError(f"{path}: only local reference-only schema nodes are supported")
        if ref in _ref_stack:
            raise CapabilityContractError(f"{path}: recursive schema references are unsupported")
        target: Any = root
        try:
            for key in ref[2:].split("/"):
                target = target[key.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            raise CapabilityContractError(f"{path}: unresolved schema reference") from None
        validate_schema_definition(target, path=path + "->$ref", root_schema=root,
                                   _ref_stack=_ref_stack | {ref})
        return
    allowed = {"$schema", "$id", "$defs", "title", "description", "type", "required", "properties",
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
            validate_schema_definition(additional, path=f"{path}.additionalProperties", root_schema=root,
                                       _ref_stack=_ref_stack)
        for key, child in properties.items():
            validate_schema_definition(child, path=f"{path}.{key}", root_schema=root,
                                       _ref_stack=_ref_stack)
    if "$defs" in schema:
        definitions = schema["$defs"]
        if not isinstance(definitions, dict) or any(not isinstance(k, str) for k in definitions):
            raise CapabilityContractError(f"{path}.$defs must be an object")
        for key, child in definitions.items():
            validate_schema_definition(child, path=f"{path}.$defs.{key}", root_schema=root,
                                       _ref_stack=_ref_stack)
    if "array" in type_set:
        if "items" not in schema:
            raise CapabilityContractError(f"{path}.items is required for array schemas")
        validate_schema_definition(schema["items"], path=f"{path}.items", root_schema=root,
                                   _ref_stack=_ref_stack)
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
    if descriptor["effect_class"] in {"steward_read", "steward_write"}:
        if descriptor["contract_version"] != "1.1.0":
            raise CapabilityContractError("Steward effects require capability-operation.v1 contract 1.1.0")
        principals = descriptor["caller_constraints"]["allowed_principals"]
        if not principals or descriptor["caller_constraints"]["allowed_residents"] or descriptor["caller_constraints"]["allowed_services"]:
            raise CapabilityContractError("Steward effects must be restricted to explicit Steward principals")
    elif descriptor["contract_version"] != "1.0.0":
        raise CapabilityContractError("capability-operation.v1 1.1.0 is reserved for Steward operations")
    if descriptor["effect_class"] in {"isolated_write", "external_write", "steward_write"} and not descriptor["recovery"]["idempotency_required"]:
        raise CapabilityContractError("write operations must require a stable idempotency key")
    if descriptor["recovery"]["idempotency_required"] and not descriptor["recovery"]["replay_safe"]:
        if descriptor["recovery"]["reconciliation_operation_id"] is None:
            # A non-replayable operation must have explicit reconciliation or be fail-closed.
            disposition = descriptor["execution"]["retry_disposition"]
            if disposition != "never":
                raise CapabilityContractError("non-replayable operation without reconciliation must never retry")
    return copy.deepcopy(descriptor)


def validate_module_manifest(module_manifest: Any, operation: dict[str, Any],
                             source_manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate optional module lifecycle metadata attached to an operation manifest."""
    if not isinstance(module_manifest, dict):
        raise CapabilityContractError("module manifest must be an object")
    contract = (module_manifest.get("contract_id"), module_manifest.get("contract_version"))
    manifest_schemas = {
        ("r3a.module-manifest.v1", "1.0.0"): "module-manifest.v1.schema.json",
        ("r3a.module-manifest.v1", "1.1.0"): "module-manifest.v1.1.schema.json",
    }
    schema_name = manifest_schemas.get(contract)
    if schema_name is None:
        raise CapabilityContractError("module manifest contract version is unsupported")
    validate_json(module_manifest, _load_schema(schema_name))
    try:
        from .module_extensions import (ModuleExtensionError, validate_activity_handler,
                                        validate_resident_executor_declaration)
        if "resident_executor" in module_manifest:
            validate_resident_executor_declaration(module_manifest["resident_executor"])
        if "activity_handler" in module_manifest:
            handler = validate_activity_handler(module_manifest["activity_handler"])
            if set(handler["required_capabilities"]) - set(module_manifest["capability_refs"]):
                raise CapabilityContractError(
                    "activity handler requires a capability not declared in module capability_refs")
    except ModuleExtensionError as exc:
        raise CapabilityContractError(str(exc)) from exc
    provider = operation["provider"]
    if (module_manifest["module_id"] != provider["provider_id"]
            or module_manifest["module_version"] != provider["provider_version"]):
        raise CapabilityContractError("module manifest identity/version does not match operation provider")
    binding = module_manifest["binding"]
    if (binding["entrypoint"] != provider["entrypoint"]
            or binding["protocol_min_minor"] > binding["protocol_max_minor"]):
        raise CapabilityContractError("module binding does not match provider or has an invalid protocol range")
    artifact = module_manifest["artifact"]
    if (artifact["artifact_sha256"] != provider["artifact_sha256"]
            or artifact["artifact_sha256"] != source_manifest.get("artifact_sha256")):
        raise CapabilityContractError("module artifact digest does not match the pinned provider artifact")
    config_schema = source_manifest.get("configuration_schema", {})
    config_schema_id = config_schema.get("schema_id") if isinstance(config_schema, dict) else None
    if module_manifest["configuration"]["schema_ref"] != config_schema_id:
        raise CapabilityContractError("module configuration schema reference does not match the external schema")
    if operation["operation_id"] not in module_manifest["capability_refs"]:
        raise CapabilityContractError("module manifest does not reference its operation")
    return copy.deepcopy(module_manifest)


def validate_invocation_request(request: Any, descriptor: dict[str, Any]) -> dict[str, Any]:
    schema = _load_schema("capability-invocation.v1.schema.json")
    request_schema = schema["$defs"]["request"]
    validate_json(request, request_schema, root_schema=schema)
    if request["operation_id"] != descriptor["operation_id"]:
        raise CapabilityContractError("invocation operation_id does not match registered operation")
    if request["operation_contract_version"] != descriptor["contract_version"]:
        raise CapabilityContractError("invocation operation contract version is unsupported")
    constraints = descriptor["caller_constraints"]
    if descriptor["effect_class"] in {"steward_read", "steward_write"}:
        if request["contract_version"] != "1.1.0" or request["operation_contract_version"] != "1.1.0":
            raise CapabilityContractError("Steward effects require invocation and operation contract 1.1.0")
    if descriptor["effect_class"] in {"steward_read", "steward_write"}:
        if request["activity_id"] is not None or request["attempt_id"] is not None or request["work_order"] is not None or request.get("budget_reservation") is not None:
            raise CapabilityContractError("Steward operation cannot be attached to resident activity work")
    elif request["activity_id"] is None or request["attempt_id"] is None:
        caller = request["caller"]
        # A direct, authenticated principal may make a read-only request without
        # manufacturing resident activity lineage. CME still applies the normal
        # capability grant check and writes an invocation/audit record. Resident,
        # service, and effectful calls retain their durable activity requirements.
        direct_principal_read = (
            descriptor["effect_class"] == "read"
            and isinstance(caller.get("principal_id"), str)
            and bool(caller["principal_id"].strip())
            and caller.get("resident_id") is None
            and caller.get("service_id") is None
        )
        if not direct_principal_read:
            raise CapabilityContractError("activity_id and attempt_id are required outside direct Steward operations")
    caller = request["caller"]
    for field, caller_key in (("allowed_principals", "principal_id"),
                              ("allowed_residents", "resident_id"),
                              ("allowed_services", "service_id")):
        allowed = constraints[field]
        if allowed and caller[caller_key] not in allowed:
            raise CapabilityContractError(f"caller is outside {field}")
    validate_json(request["input"], descriptor["input_schema"], path="$.input")
    validate_json(request["target"], descriptor["target_scope_schema"], path="$.target")
    reservation = request.get("budget_reservation")
    if reservation is not None:
        validate_json(reservation, schema["$defs"]["request"]["properties"]["budget_reservation"],
                      path="$.budget_reservation")
        if reservation["activity_id"] != request["activity_id"]:
            raise CapabilityContractError("budget reservation activity does not match invocation lineage")
        if descriptor["effect_class"] != "external_write" or request["work_order"] is not None:
            raise CapabilityContractError("activity budget reservations apply only to external calls without work orders")
    elif descriptor["effect_class"] == "external_write" and request["work_order"] is None:
        raise CapabilityContractError("external invocation without a work order requires a durable budget reservation")
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
        expected_disposition = "NOT_STARTED" if descriptor["effect_class"] in {"read", "steward_read"} else "COMMITTED"
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

    def presentation_projection(self) -> dict[str, Any]:
        """Separate stable operation identity from its human-facing registry label."""
        descriptor = self.descriptor
        tool = (self.legacy_manifest or {}).get("tool")
        display = descriptor.get("resident_tool", {})
        raw_name = (tool or {}).get("name") or display.get("name")
        name = _humanize_capability_name(raw_name or descriptor["operation_id"])
        description = (tool or {}).get("description") or display.get("description")
        return {"name": name,
                "description": description or "No description is registered for this capability.",
                "description_registered": bool(description)}

    def resident_tool_projection(self) -> dict[str, Any]:
        """Compatibility projection for the pre-v1 resident tool schema only."""
        descriptor = self.descriptor
        tool = (self.legacy_manifest or {}).get("tool") or {}
        presentation = self.presentation_projection()
        return {"contract_id": (self.legacy_manifest or {}).get("contract_id", "r3a.resident-capability-tool"),
                "contract_version": (self.legacy_manifest or {}).get("contract_version", CONTRACT_VERSION),
                "capability_id": descriptor["operation_id"],
                "name": presentation["name"],
                "description": presentation["description"],
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
        self._operations: dict[tuple[str, str, str], RegisteredOperation] = {}
        self._active: dict[str, tuple[str, str, str]] = {}
        self._provider_states: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}

    def register(self, descriptor: dict[str, Any], configuration: dict[str, Any], *,
                 legacy_manifest: dict[str, Any] | None = None) -> RegisteredOperation:
        checked = validate_operation(descriptor)
        operation_id = checked["operation_id"]
        provider = checked["provider"]
        identity = (operation_id, provider["provider_id"], provider["provider_version"])
        if identity in self._operations:
            raise CapabilityContractError(f"operation provider version already registered: {identity}")
        if not isinstance(configuration, dict):
            raise CapabilityContractError("provider configuration must be an object")
        registered = RegisteredOperation(checked, copy.deepcopy(configuration), copy.deepcopy(legacy_manifest))
        self._operations[identity] = registered
        self._active.setdefault(operation_id, identity)
        self._provider_states.setdefault((provider["provider_id"], provider["provider_version"]),
                                         ("registered", {}))
        return self._copy(registered)

    def set_provider_state(self, provider_id: str, provider_version: str, state: str,
                           diagnostic: dict[str, Any] | None = None) -> None:
        """Record an observed provider binding state without changing authorization."""
        if not any(item.descriptor["provider"]["provider_id"] == provider_id
                   and item.descriptor["provider"]["provider_version"] == provider_version
                   for item in self._operations.values()):
            raise KeyError(f"unknown provider: {provider_id}@{provider_version}")
        self._provider_states[(provider_id, provider_version)] = (state, copy.deepcopy(diagnostic or {}))

    def discover(self, *, include_disabled: bool = False,
                 include_versions: bool = False) -> tuple[dict[str, Any], ...]:
        """Return stable operation identity plus a separate human presentation projection."""
        records = []
        items = self._operations.values() if include_versions else (
            self._operations[key] for key in self._active.values())
        for item in sorted(items, key=lambda x: (x.descriptor["operation_id"],
                                                 x.descriptor["provider"]["provider_version"])):
            descriptor = item.descriptor
            if descriptor["lifecycle"]["desired_state"] == "disabled" and not include_disabled:
                continue
            provider_key = (descriptor["provider"]["provider_id"],
                            descriptor["provider"]["provider_version"])
            state, diagnostic = self._provider_states.get(provider_key, ("registered", {}))
            records.append({"descriptor": copy.deepcopy(descriptor),
                            "presentation": item.presentation_projection(),
                            "registry_observation": {"state": state,
                                                     "diagnostic": copy.deepcopy(diagnostic),
                                                     "health": "not_probed",
                                                     "provider_availability": "not_probed",
                                                     "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}})
        return tuple(records)

    def resolve(self, operation_id: str, contract_version: str = CONTRACT_VERSION, *,
                include_stopped: bool = False) -> RegisteredOperation:
        identity = self._active.get(operation_id)
        operation = self._operations.get(identity) if identity else None
        if operation is None:
            raise KeyError(f"unknown operation: {operation_id}")
        if operation.descriptor["contract_version"] != contract_version:
            raise CapabilityContractError("operation contract version mismatch")
        if operation.descriptor["lifecycle"]["desired_state"] != "enabled":
            raise CapabilityContractError("operation is disabled")
        provider = operation.descriptor["provider"]
        state = self._provider_states.get((provider["provider_id"], provider["provider_version"]),
                                          ("registered", {}))[0]
        if not include_stopped and state in {"STOPPED", "FAILED", "INCOMPATIBLE"}:
            raise CapabilityContractError(f"provider is {state.lower()}")
        return self._copy(operation)

    def resolve_provider(self, operation_id: str, provider_version: str) -> RegisteredOperation:
        """Resolve an installed implementation version for lifecycle management."""
        matches = [item for key, item in self._operations.items()
                   if key[0] == operation_id and key[2] == provider_version]
        if len(matches) != 1:
            raise KeyError(f"unknown or ambiguous operation provider: {operation_id}@{provider_version}")
        return self._copy(matches[0])

    def activate_provider(self, operation_id: str, provider_version: str) -> RegisteredOperation:
        """Select a previously discovered provider version after readiness succeeds."""
        candidate = self.resolve_provider(operation_id, provider_version)
        if candidate.descriptor["lifecycle"]["desired_state"] != "enabled":
            raise CapabilityContractError("operation is disabled")
        provider = candidate.descriptor["provider"]
        state = self._provider_states.get((provider["provider_id"], provider["provider_version"]),
                                          ("registered", {}))[0]
        if state not in {"ACTIVE", "registered", "INSTALLED"}:
            raise CapabilityContractError(f"provider is not ready for activation ({state})")
        self._active[operation_id] = (operation_id, provider["provider_id"], provider["provider_version"])
        return candidate

    @staticmethod
    def _copy(operation: RegisteredOperation) -> RegisteredOperation:
        return RegisteredOperation(copy.deepcopy(operation.descriptor),
                                   copy.deepcopy(operation.configuration),
                                   copy.deepcopy(operation.legacy_manifest))

    def __len__(self) -> int:
        return len(self._active)


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
    if "module_manifest" in manifest:
        validate_module_manifest(manifest["module_manifest"], descriptor, manifest)
    return descriptor
