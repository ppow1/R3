"""
R3 CONTROLLED SOURCE
File: r3a_runtime/config.py
Component: R3A-BOOTSTRAP-CONFIG
File Revision: 1.5.0
Created: 2026-11-06T15:04:00Z
Created By: Codex GPT-6
Purpose: Strictly validate external R3A AP0-M1 bootstrap and operating settings.
Execution Model: Shared synchronous configuration parser.
Observability: Configuration revision digest and validation errors.
Dependencies: Python 3.12 standard library.
Authority: AP1 / R3A-019 and AP1 Slices 1–2 authorized by Steward; isolated R3A only.
Changed: 2026-11-06T15:04:00Z | R3A-AP0-M1 | Codex GPT-6 | Add fail-closed external configuration parser.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Restrict observer capabilities to the two AP0 read-only contracts.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Validate Grace model, capability, and allowlisted knowledge configuration.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Add external model routes while retaining legacy single-route config compatibility.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add validated configurable model roles and authorization provider selection.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Preserve route-only configuration compatibility and finalize strict role/provider validation.
Changed: 2026-11-07T00:20:59Z | R3A-AP1-SLICE-2 | Codex GPT-6 | Validate external provider endpoints, matching origins, private-network HTTP, freshness, timeouts and retries.
Changed: 2026-11-07 | R3A-PLUG-001 | Codex GPT-6 | Load versioned capability plug-in manifests and external configuration with artifact digest validation.
Changed: 2026-11-07 | R3A-PLUG-002 | Codex GPT-6 | Validate plug-in configuration against each manifest's portable schema, without capability-specific host validation.
Changed: 2026-11-07 | R3A-AP2-ESCALATED-REASONING | Codex GPT-6 | Add externally configured v1 escalation policy with per-activity request and completion-token budgets.
Supersedes: None.
Contracts: AP0-001/008/009; R3A-019; Issue #46; AP0-M1 D7; r3a_runtime.contracts; hints/file-provenance.md.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py; tests/test_r3a_octominer_plugin.py.
History/Predecessor: Git blob 189c6ef7ef3821f9140bddbeac8d04c177ca32ac at commit ad16700f1e94dd36c81cac5383f9f2e2771a98a1.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """A bootstrap file is missing, malformed, or outside its contract."""


@dataclass(frozen=True)
class ModelRoute:
    route_id: str
    provider: str
    endpoint: str
    model: str
    timeout_seconds: float
    max_tokens: int


@dataclass(frozen=True)
class ModelRole:
    role_id: str
    route_id: str
    capabilities: tuple[str, ...]
    modalities: tuple[str, ...]
    fallback_roles: tuple[str, ...]
    readiness_max_age_seconds: float
    unavailable_action: str
    deferral_seconds: float
    concurrency: int
    readiness: "ModelReadinessPolicy | None" = None


@dataclass(frozen=True)
class ModelReadinessPolicy:
    provider_id: str
    contract_version: str
    endpoint: str
    timeout_seconds: float
    max_attempts: int
    retry_delay_seconds: float
    poll_interval_seconds: float
    api_key_env: str | None = None


@dataclass(frozen=True)
class AuthorizationProviderSettings:
    provider_id: str
    contract_version: str
    options: dict[str, Any]


@dataclass(frozen=True)
class ReasoningEscalationPolicy:
    contract_id: str
    contract_version: str
    enabled: bool
    authorization_capability_id: str
    allowed_role_ids: tuple[str, ...]
    max_requests_per_activity: int
    max_completion_tokens_per_activity: int


def resolve_model_route(routes: tuple[ModelRoute, ...], default_route: str,
                        requested_route: str | None = None) -> ModelRoute:
    selected = requested_route or default_route
    for route in routes:
        if route.route_id == selected:
            return route
    raise ConfigurationError(f"Unknown configured Grace model route: {selected}")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationError(f"Duplicate configuration key: {key}")
        result[key] = value
    return result


def _keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    missing = expected - value.keys()
    extra = value.keys() - expected
    if missing or extra:
        raise ConfigurationError(
            f"{where} keys invalid; missing={sorted(missing)}, unknown={sorted(extra)}"
        )


def _validate_plugin_config(value: Any, schema: dict[str, Any], where: str) -> None:
    """Validate the portable JSON Schema subset used by capability manifests."""
    if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
        raise ConfigurationError(f"{where} schema must declare an object with properties")
    required = schema.get("required", [])
    if (not isinstance(required, list) or any(not isinstance(key, str) for key in required)
            or not set(required).issubset(schema["properties"])):
        raise ConfigurationError(f"{where} schema has invalid required fields")
    supported_types = {"string", "integer", "number", "boolean", "object", "array"}
    for key, field_schema in schema["properties"].items():
        if (not isinstance(key, str) or not isinstance(field_schema, dict)
                or field_schema.get("type") not in supported_types):
            raise ConfigurationError(f"{where} schema property {key!r} has an unsupported declaration")
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    missing = set(required) - value.keys()
    extra = value.keys() - schema["properties"].keys()
    if missing or (extra and schema.get("additionalProperties", False) is False):
        raise ConfigurationError(f"{where} fields invalid; missing={sorted(missing)}, unknown={sorted(extra)}")
    for key, item in value.items():
        field_schema = schema["properties"].get(key)
        if not isinstance(field_schema, dict):
            continue
        field_type = field_schema.get("type")
        type_ok = {
            "string": lambda x: isinstance(x, str),
            "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x),
            "boolean": lambda x: isinstance(x, bool),
            "object": lambda x: isinstance(x, dict),
            "array": lambda x: isinstance(x, list),
        }.get(field_type)
        if type_ok is None or not type_ok(item):
            raise ConfigurationError(f"{where}.{key} does not match its declared JSON type")
        if field_type == "string":
            if len(item) < field_schema.get("minLength", 0):
                raise ConfigurationError(f"{where}.{key} is shorter than its declared minimum")
            pattern = field_schema.get("pattern")
            if pattern is not None and (not isinstance(pattern, str) or re.fullmatch(pattern, item) is None):
                raise ConfigurationError(f"{where}.{key} does not match its declared pattern")
        if field_type in {"integer", "number"}:
            if "minimum" in field_schema and item < field_schema["minimum"]:
                raise ConfigurationError(f"{where}.{key} is below its declared minimum")
            if "maximum" in field_schema and item > field_schema["maximum"]:
                raise ConfigurationError(f"{where}.{key} is above its declared maximum")


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be nonempty text")
    return value


def _positive(value: Any, where: str, *, minimum: float = 0.01) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{where} must be a number")
    if not math.isfinite(value) or value < minimum:
        raise ConfigurationError(f"{where} must be finite and >= {minimum}")
    return float(value)


def _absolute_path(value: Any, where: str) -> Path:
    raw = Path(_text(value, where)).expanduser()
    if not raw.is_absolute():
        raise ConfigurationError(f"{where} must be an absolute path")
    return raw.resolve()


def _service_endpoint(value: Any, where: str) -> str:
    endpoint = _text(value, where)
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.fragment or parsed.query):
        raise ConfigurationError(f"{where} must be an HTTP(S) endpoint without embedded credentials, query or fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ConfigurationError(f"{where} contains an invalid port") from exc
    if parsed.scheme == "http" and parsed.hostname not in {"localhost"}:
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise ConfigurationError(f"{where} may use plain HTTP only for loopback or a private IP") from exc
        if not (address.is_loopback or address.is_private):
            raise ConfigurationError(f"{where} may use plain HTTP only for loopback or a private IP")
    return endpoint


@dataclass(frozen=True)
class Settings:
    instance_id: str
    source_path: Path
    source_digest: str
    data_dir: Path
    database: str
    database_user: str
    database_socket_dir: Path
    database_port: int
    control_socket: Path
    diagnostics_socket: Path
    module_socket: Path
    machine_catalog_dir: Path
    module_id: str
    module_version: str
    module_contract_id: str
    module_protocol_major: int
    module_protocol_minor: int
    module_capabilities: tuple[str, ...]
    module_owner: str
    module_entrypoint: str
    module_source: Path
    module_digest: str
    observer_interval_seconds: float
    scheduler_interval_seconds: float
    lease_seconds: float
    heartbeat_interval_seconds: float
    heartbeat_stale_after_seconds: float
    diagnostic_stale_after_seconds: float
    restart_initial_seconds: float
    restart_max_seconds: float
    worker_concurrency: int
    model_provider: str | None
    model_endpoint: str | None
    model_name: str | None
    model_timeout_seconds: float
    model_max_tokens: int
    model_routes: tuple[ModelRoute, ...]
    default_model_route: str
    model_roles: tuple[ModelRole, ...]
    default_model_role: str | None
    reasoning_escalation: ReasoningEscalationPolicy | None
    authorization_provider: AuthorizationProviderSettings
    knowledge_sources: tuple[Path, ...]
    capability_registry: Any

    def model_route(self, route_id: str | None = None) -> ModelRoute:
        return resolve_model_route(self.model_routes, self.default_model_route, route_id)

    @property
    def connection_info(self) -> dict[str, Any]:
        return {
            "dbname": self.database,
            "user": self.database_user,
            "host": str(self.database_socket_dir),
            "port": self.database_port,
            "connect_timeout": 3,
            "application_name": f"r3a-{self.instance_id}",
            "options": "-c search_path=r3a,public",
        }


def load_settings(path: str | Path) -> Settings:
    source = Path(path).expanduser().resolve()
    try:
        raw_bytes = source.read_bytes()
        value = json.loads(raw_bytes, object_pairs_hook=_object_pairs)
    except ConfigurationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot read bootstrap config {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError("bootstrap config must be a JSON object")
    expected_root = {"schema_version", "instance_id", "paths", "postgres", "module", "timing"}
    extra = value.keys() - expected_root - {"grace", "authorization", "capability_plugins", "capability_operations"}
    missing = expected_root - value.keys()
    if missing or extra:
        raise ConfigurationError(f"root keys invalid; missing={sorted(missing)}, unknown={sorted(extra)}")
    if value["schema_version"] != 1:
        raise ConfigurationError("schema_version must equal 1")
    instance_id = _text(value["instance_id"], "instance_id")
    if not instance_id.startswith("r3a_") or not instance_id.replace("_", "").isalnum():
        raise ConfigurationError("instance_id must use the isolated r3a_<name> form")

    paths = value["paths"]
    if not isinstance(paths, dict):
        raise ConfigurationError("paths must be an object")
    _keys(paths, {"data_dir", "postgres_socket_dir", "control_socket", "diagnostics_socket", "module_socket", "machine_catalog_dir"}, "paths")
    data_dir = _absolute_path(paths["data_dir"], "paths.data_dir")
    socket_dir = _absolute_path(paths["postgres_socket_dir"], "paths.postgres_socket_dir")
    if not socket_dir.is_relative_to(data_dir):
        raise ConfigurationError("postgres_socket_dir must be inside data_dir")
    control_socket = _absolute_path(paths["control_socket"], "paths.control_socket")
    diagnostics_socket = _absolute_path(paths["diagnostics_socket"], "paths.diagnostics_socket")
    module_socket = _absolute_path(paths["module_socket"], "paths.module_socket")
    for name, socket_path in (("control_socket", control_socket), ("diagnostics_socket", diagnostics_socket), ("module_socket", module_socket)):
        if not socket_path.is_relative_to(data_dir):
            raise ConfigurationError(f"{name} must be inside data_dir")
    if control_socket == diagnostics_socket or module_socket in {control_socket, diagnostics_socket}:
        raise ConfigurationError("control, diagnostics and module sockets must be distinct")
    machine_catalog_dir = _absolute_path(paths["machine_catalog_dir"], "paths.machine_catalog_dir")

    postgres = value["postgres"]
    if not isinstance(postgres, dict):
        raise ConfigurationError("postgres must be an object")
    _keys(postgres, {"database", "user", "socket_dir", "port"}, "postgres")
    database = _text(postgres["database"], "postgres.database")
    if database != instance_id:
        raise ConfigurationError("database name must equal the isolated instance_id")
    database_user = _text(postgres["user"], "postgres.user")
    if database_user != "r3a_runtime":
        raise ConfigurationError("postgres.user must be the least-privilege r3a_runtime role")
    configured_socket = _absolute_path(postgres["socket_dir"], "postgres.socket_dir")
    if configured_socket != socket_dir:
        raise ConfigurationError("paths.postgres_socket_dir and postgres.socket_dir must match")
    port = postgres["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ConfigurationError("postgres.port must be an unprivileged port from 1024 to 65535")

    module = value["module"]
    if not isinstance(module, dict):
        raise ConfigurationError("module must be an object")
    _keys(module, {"module_id", "version", "contract_id", "protocol_major", "protocol_minor", "capabilities", "owner", "entrypoint", "source", "sha256"}, "module")
    module_id = _text(module["module_id"], "module.module_id")
    module_version = _text(module["version"], "module.version")
    if not all(part.isdigit() for part in module_version.split(".")) or len(module_version.split(".")) != 3:
        raise ConfigurationError("module.version must be semantic major.minor.patch numbers")
    module_contract_id = _text(module["contract_id"], "module.contract_id")
    proto_major, proto_minor = module["protocol_major"], module["protocol_minor"]
    if isinstance(proto_major, bool) or not isinstance(proto_major, int) or proto_major != 1:
        raise ConfigurationError("module.protocol_major must equal the supported protocol major 1")
    if isinstance(proto_minor, bool) or not isinstance(proto_minor, int) or proto_minor < 0:
        raise ConfigurationError("module.protocol_minor must be a nonnegative integer")
    capabilities = module["capabilities"]
    if (not isinstance(capabilities, list) or not capabilities
            or any(not isinstance(cap, str) or not cap.strip() for cap in capabilities)
            or len(set(capabilities)) != len(capabilities)):
        raise ConfigurationError("module.capabilities must be a nonempty list of unique capability IDs")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", cap) for cap in capabilities):
        raise ConfigurationError("module.capabilities contains an invalid capability identifier")
    module_owner = _text(module["owner"], "module.owner")
    entrypoint = _text(module["entrypoint"], "module.entrypoint")
    if entrypoint not in {"r3a_runtime.observer_module", "r3a_runtime.grace_module"}:
        raise ConfigurationError("module.entrypoint is not supported by this R3A installation")
    if (entrypoint == "r3a_runtime.observer_module") != (module_id == "foundation.observer"):
        raise ConfigurationError("module_id must match its supported module entrypoint")
    module_source = _absolute_path(module["source"], "module.source")
    module_digest = _text(module["sha256"], "module.sha256").lower()
    if len(module_digest) != 64 or any(c not in "0123456789abcdef" for c in module_digest):
        raise ConfigurationError("module.sha256 must be a SHA-256 hex digest")
    if not module_source.is_file():
        raise ConfigurationError(f"module source does not exist: {module_source}")
    actual_digest = hashlib.sha256(module_source.read_bytes()).hexdigest()
    if actual_digest != module_digest:
        raise ConfigurationError("module source digest does not match the registered manifest")

    grace = value.get("grace")
    model_provider = model_endpoint = model_name = None
    model_timeout_seconds = 120.0
    model_max_tokens = 192
    model_routes: tuple[ModelRoute, ...] = ()
    default_model_route = "default"
    model_roles: tuple[ModelRole, ...] = ()
    default_model_role: str | None = None
    reasoning_escalation: ReasoningEscalationPolicy | None = None
    knowledge_sources: tuple[Path, ...] = ()
    if entrypoint == "r3a_runtime.grace_module" or grace is not None:
        if not isinstance(grace, dict):
            raise ConfigurationError("grace must be an object when the Grace resident is configured")
        legacy_keys = {"provider", "endpoint", "model", "timeout_seconds", "max_tokens", "knowledge_sources"}
        route_keys = {"routes", "default_route", "knowledge_sources"}
        role_route_keys = route_keys | {"role_registry"}
        escalation_keys = {"reasoning_escalation"}
        if set(grace) == legacy_keys:
            route_data = [{"route_id": "default", "provider": grace["provider"],
                           "endpoint": grace["endpoint"], "model": grace["model"],
                           "timeout_seconds": grace["timeout_seconds"], "max_tokens": grace["max_tokens"]}]
            default_model_route = "default"
        elif set(grace) in (route_keys, role_route_keys,
                            route_keys | escalation_keys, role_route_keys | escalation_keys):
            route_data = grace["routes"]
            default_model_route = _text(grace["default_route"], "grace.default_route")
        else:
            raise ConfigurationError("grace must use the legacy single-route or configured routes schema")
        if not isinstance(route_data, list) or not route_data:
            raise ConfigurationError("grace.routes must be a nonempty list")
        parsed_routes = []
        route_ids: set[str] = set()
        for index, item in enumerate(route_data):
            where = f"grace.routes[{index}]"
            if not isinstance(item, dict):
                raise ConfigurationError(f"{where} must be an object")
            _keys(item, {"route_id", "provider", "endpoint", "model", "timeout_seconds", "max_tokens"}, where)
            route_id = _text(item["route_id"], f"{where}.route_id")
            if not re.fullmatch(r"[A-Za-z0-9._-]+", route_id) or route_id in route_ids:
                raise ConfigurationError(f"{where}.route_id must be unique and use letters, numbers, dot, underscore or hyphen")
            route_ids.add(route_id)
            provider = _text(item["provider"], f"{where}.provider")
            if provider != "openai-compatible":
                raise ConfigurationError(f"{where}.provider must equal openai-compatible")
            endpoint = _service_endpoint(item["endpoint"], f"{where}.endpoint")
            model = _text(item["model"], f"{where}.model")
            timeout = _positive(item["timeout_seconds"], f"{where}.timeout_seconds")
            max_tokens = item["max_tokens"]
            if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 64 <= max_tokens <= 512:
                raise ConfigurationError(f"{where}.max_tokens must be an integer from 64 through 512")
            parsed_routes.append(ModelRoute(route_id, provider, endpoint, model, timeout, max_tokens))
        if default_model_route not in route_ids:
            raise ConfigurationError("grace.default_route must identify a configured route")
        model_routes = tuple(parsed_routes)
        default_route = next(item for item in model_routes if item.route_id == default_model_route)
        model_provider, model_endpoint, model_name = default_route.provider, default_route.endpoint, default_route.model
        model_timeout_seconds, model_max_tokens = default_route.timeout_seconds, default_route.max_tokens
        sources = grace["knowledge_sources"]
        if (not isinstance(sources, list) or not sources or
                any(not isinstance(item, str) for item in sources) or len(set(sources)) != len(sources)):
            raise ConfigurationError("grace.knowledge_sources must be a nonempty unique path list")
        resolved = tuple(_absolute_path(item, "grace.knowledge_sources[]") for item in sources)
        if any(not item.is_file() for item in resolved):
            raise ConfigurationError("every configured knowledge source must exist and be a regular file")
        knowledge_sources = resolved
        if "role_registry" in grace:
            registry = grace["role_registry"]
            if not isinstance(registry, dict):
                raise ConfigurationError("grace.role_registry must be an object")
            _keys(registry, {"schema_version", "default_role", "roles"}, "grace.role_registry")
            if registry["schema_version"] != 1:
                raise ConfigurationError("grace.role_registry.schema_version must equal 1")
            default_model_role = _text(registry["default_role"], "grace.role_registry.default_role")
            raw_roles = registry["roles"]
            if not isinstance(raw_roles, list) or not raw_roles:
                raise ConfigurationError("grace.role_registry.roles must be a nonempty list")
            parsed_roles: list[ModelRole] = []
            role_ids: set[str] = set()
            for index, item in enumerate(raw_roles):
                where = f"grace.role_registry.roles[{index}]"
                if not isinstance(item, dict):
                    raise ConfigurationError(f"{where} must be an object")
                role_keys = {"role_id", "route_id", "capabilities", "modalities", "fallback_roles",
                             "readiness_max_age_seconds", "unavailable_action", "deferral_seconds",
                             "concurrency"}
                if "readiness" not in item:
                    if item.keys() - role_keys or role_keys - item.keys():
                        _keys(item, role_keys, where)
                    readiness = None
                else:
                    if item.keys() - (role_keys | {"readiness"}) or role_keys - item.keys():
                        _keys(item, role_keys | {"readiness"}, where)
                    raw_readiness = item["readiness"]
                    if not isinstance(raw_readiness, dict):
                        raise ConfigurationError(f"{where}.readiness must be an object")
                    required_readiness = {"provider_id", "contract_version", "endpoint", "timeout_seconds",
                                          "max_attempts", "retry_delay_seconds", "poll_interval_seconds"}
                    optional_readiness = {"api_key_env"}
                    if (required_readiness - raw_readiness.keys()
                            or raw_readiness.keys() - required_readiness - optional_readiness):
                        raise ConfigurationError(f"{where}.readiness fields are invalid")
                    provider_id = _text(raw_readiness["provider_id"], f"{where}.readiness.provider_id")
                    provider_version = _text(raw_readiness["contract_version"],
                                             f"{where}.readiness.contract_version")
                    version_parts = provider_version.split(".")
                    if (len(version_parts) != 3 or not all(part.isdigit() for part in version_parts)
                            or version_parts[0] != "1"):
                        raise ConfigurationError(f"{where}.readiness.contract_version must be v1 semver")
                    readiness_endpoint = _service_endpoint(raw_readiness["endpoint"],
                                                           f"{where}.readiness.endpoint")
                    attempts = raw_readiness["max_attempts"]
                    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 5:
                        raise ConfigurationError(f"{where}.readiness.max_attempts must be from 1 through 5")
                    api_key_env = raw_readiness.get("api_key_env")
                    if api_key_env is not None and (not isinstance(api_key_env, str)
                                                    or not re.fullmatch(r"[A-Z][A-Z0-9_]*", api_key_env)):
                        raise ConfigurationError(f"{where}.readiness.api_key_env must be an environment variable name")
                    readiness = ModelReadinessPolicy(
                        provider_id, provider_version, readiness_endpoint,
                        _positive(raw_readiness["timeout_seconds"], f"{where}.readiness.timeout_seconds"),
                        attempts,
                        _positive(raw_readiness["retry_delay_seconds"],
                                  f"{where}.readiness.retry_delay_seconds", minimum=0),
                        _positive(raw_readiness["poll_interval_seconds"],
                                  f"{where}.readiness.poll_interval_seconds"), api_key_env)
                role_id = _text(item["role_id"], f"{where}.role_id")
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", role_id) or role_id in role_ids:
                    raise ConfigurationError(f"{where}.role_id must be unique and use contract-safe characters")
                role_ids.add(role_id)
                route_id = _text(item["route_id"], f"{where}.route_id")
                if route_id not in route_ids:
                    raise ConfigurationError(f"{where}.route_id must identify a configured route")
                if readiness is not None:
                    route_entry = next(entry for entry in parsed_routes if entry.route_id == route_id)
                    model_origin = urlsplit(route_entry.endpoint)
                    readiness_origin = urlsplit(readiness.endpoint)
                    model_port = model_origin.port or (443 if model_origin.scheme == "https" else 80)
                    readiness_port = readiness_origin.port or (
                        443 if readiness_origin.scheme == "https" else 80)
                    if (model_origin.scheme, model_origin.hostname, model_port) != (
                            readiness_origin.scheme, readiness_origin.hostname, readiness_port):
                        raise ConfigurationError(f"{where}.readiness.endpoint must use the configured model provider origin")
                def string_list(field: str) -> tuple[str, ...]:
                    values = item[field]
                    if (not isinstance(values, list) or not values
                            or any(not isinstance(entry, str) or not entry.strip() for entry in values)
                            or len(set(values)) != len(values)):
                        raise ConfigurationError(f"{where}.{field} must be a nonempty unique text list")
                    return tuple(values)
                capabilities_for_role = string_list("capabilities")
                modalities = string_list("modalities")
                fallbacks = item["fallback_roles"]
                if (not isinstance(fallbacks, list) or any(not isinstance(entry, str) or not entry.strip()
                                                           for entry in fallbacks)
                        or len(set(fallbacks)) != len(fallbacks) or role_id in fallbacks):
                    raise ConfigurationError(f"{where}.fallback_roles must be a unique list excluding itself")
                action = item["unavailable_action"]
                if action not in {"defer", "block"}:
                    raise ConfigurationError(f"{where}.unavailable_action must be defer or block")
                concurrency = item["concurrency"]
                if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
                    raise ConfigurationError(f"{where}.concurrency must be a positive integer")
                parsed_roles.append(ModelRole(
                    role_id=role_id, route_id=route_id, capabilities=capabilities_for_role,
                    modalities=modalities, fallback_roles=tuple(fallbacks),
                    readiness_max_age_seconds=_positive(item["readiness_max_age_seconds"],
                                                         f"{where}.readiness_max_age_seconds"),
                    unavailable_action=action,
                    deferral_seconds=_positive(item["deferral_seconds"], f"{where}.deferral_seconds"),
                    concurrency=concurrency, readiness=readiness))
            if default_model_role not in role_ids:
                raise ConfigurationError("grace.role_registry.default_role must identify a configured role")
            for role in parsed_roles:
                if set(role.fallback_roles) - role_ids:
                    raise ConfigurationError(f"role {role.role_id} references an unconfigured fallback role")
            model_roles = tuple(parsed_roles)

        raw_escalation = grace.get("reasoning_escalation")
        if raw_escalation is not None:
            if not isinstance(raw_escalation, dict):
                raise ConfigurationError("grace.reasoning_escalation must be an object")
            required_escalation = {"contract_id", "contract_version", "enabled",
                                   "authorization_capability_id", "allowed_role_ids",
                                   "max_requests_per_activity", "max_completion_tokens_per_activity"}
            _keys(raw_escalation, required_escalation, "grace.reasoning_escalation")
            contract_id = _text(raw_escalation["contract_id"],
                                "grace.reasoning_escalation.contract_id")
            contract_version = _text(raw_escalation["contract_version"],
                                     "grace.reasoning_escalation.contract_version")
            if (contract_id != "r3a.reasoning-escalation-policy"
                    or re.fullmatch(r"1\.[0-9]+\.[0-9]+", contract_version) is None):
                raise ConfigurationError("grace.reasoning_escalation contract must be supported v1 semver")
            enabled = raw_escalation["enabled"]
            if not isinstance(enabled, bool):
                raise ConfigurationError("grace.reasoning_escalation.enabled must be boolean")
            grant = _text(raw_escalation["authorization_capability_id"],
                          "grace.reasoning_escalation.authorization_capability_id")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", grant):
                raise ConfigurationError("reasoning escalation authorization capability ID is invalid")
            if enabled and grant not in capabilities:
                raise ConfigurationError("enabled reasoning escalation must be declared in module.capabilities")
            allowed = raw_escalation["allowed_role_ids"]
            if (not isinstance(allowed, list) or any(not isinstance(item, str) or not item.strip()
                                                      for item in allowed)
                    or len(set(allowed)) != len(allowed)):
                raise ConfigurationError("reasoning escalation allowed_role_ids must be a unique text list")
            if set(allowed) - {role.role_id for role in model_roles}:
                raise ConfigurationError("reasoning escalation references an unconfigured role")
            if enabled and not allowed:
                raise ConfigurationError("enabled reasoning escalation requires at least one allowed role")
            max_requests = raw_escalation["max_requests_per_activity"]
            max_tokens = raw_escalation["max_completion_tokens_per_activity"]
            if isinstance(max_requests, bool) or not isinstance(max_requests, int) or not 1 <= max_requests <= 5:
                raise ConfigurationError("reasoning escalation max_requests_per_activity must be from 1 through 5")
            if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 1 <= max_tokens <= 8192:
                raise ConfigurationError("reasoning escalation token budget must be from 1 through 8192")
            reasoning_escalation = ReasoningEscalationPolicy(
                contract_id, contract_version, enabled, grant, tuple(allowed), max_requests, max_tokens)

    authorization = value.get("authorization", {"provider_id": "capability_grants",
                                                    "contract_version": "1.0.0", "options": {}})
    if not isinstance(authorization, dict):
        raise ConfigurationError("authorization must be an object")
    _keys(authorization, {"provider_id", "contract_version", "options"}, "authorization")
    authorization_provider_id = _text(authorization["provider_id"], "authorization.provider_id")
    authorization_contract_version = _text(authorization["contract_version"],
                                           "authorization.contract_version")
    version_parts = authorization_contract_version.split(".")
    if (len(version_parts) != 3 or not all(part.isdigit() for part in version_parts)
            or version_parts[0] != "1"):
        raise ConfigurationError("authorization.contract_version must use semantic major.minor.patch form")
    authorization_options = authorization["options"]
    if not isinstance(authorization_options, dict):
        raise ConfigurationError("authorization.options must be an object")
    authorization_provider = AuthorizationProviderSettings(
        authorization_provider_id, authorization_contract_version, authorization_options)
    if entrypoint == "r3a_runtime.grace_module" and not (model_endpoint and model_name and knowledge_sources):
        raise ConfigurationError("Grace requires explicit model and knowledge-source configuration")

    from .capability_contracts import (CapabilityContractError, CapabilityRegistry,
                                       operation_from_manifest)
    capability_registry = CapabilityRegistry()
    plugin_ids: set[str] = set()
    if "capability_plugins" in value and "capability_operations" in value:
        raise ConfigurationError("use one capability_operations registry input; capability_plugins is a compatibility alias")
    raw_plugins = value.get("capability_operations", value.get("capability_plugins", []))
    if not isinstance(raw_plugins, list):
        raise ConfigurationError("capability_operations must be an array")
    for index, item in enumerate(raw_plugins):
        where = f"capability_operations[{index}]"
        if not isinstance(item, dict):
            raise ConfigurationError(f"{where} must be an object")
        _keys(item, {"manifest", "configuration"}, where)
        manifest_path = _absolute_path(item["manifest"], f"{where}.manifest")
        configuration_path = _absolute_path(item["configuration"], f"{where}.configuration")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
            plugin_config = json.loads(configuration_path.read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
        except (OSError, UnicodeError, json.JSONDecodeError, ConfigurationError) as exc:
            raise ConfigurationError(f"Cannot load {where}: {exc}") from exc
        required_manifest = {"schema_version", "plugin_id", "plugin_version",
                             "configuration_schema", "artifact_ref", "artifact_sha256"}
        if not isinstance(manifest, dict):
            raise ConfigurationError(f"{where}.manifest must contain an object")
        optional_manifest = {"supporting_artifacts", "operation", "provider", "contract_id",
                             "contract_version", "capability_id", "tool", "entrypoint", "read_only"}
        _keys(manifest, required_manifest | (optional_manifest & manifest.keys()),
              f"{where}.manifest")
        if manifest["schema_version"] != 1:
            raise ConfigurationError(f"{where} must declare schema_version 1")
        if "operation" not in manifest and manifest.get("read_only") is not True:
            raise ConfigurationError(f"{where} legacy manifest must declare read_only true")
        schema = manifest["configuration_schema"]
        if not isinstance(schema, dict):
            raise ConfigurationError(f"{where}.manifest.configuration_schema must be a JSON Schema object")
        _validate_plugin_config(plugin_config, schema, f"{where}.configuration")
        if "entrypoint" in manifest and (not isinstance(manifest["entrypoint"], str) or ":" not in manifest["entrypoint"]
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*", manifest["entrypoint"])):
            raise ConfigurationError(f"{where}.entrypoint must be a Python module:function reference")
        if "tool" in manifest:
            tool = manifest["tool"]
            if (not isinstance(tool, dict) or set(tool) != {"name", "description", "arguments_schema"}
                    or not isinstance(tool["arguments_schema"], dict)):
                raise ConfigurationError(f"{where}.tool is invalid")
        artifact = Path(_text(manifest["artifact_ref"], f"{where}.artifact_ref"))
        if artifact.is_absolute():
            raise ConfigurationError(f"{where}.artifact_ref must be relative to its manifest")
        artifact_path = (manifest_path.parent / artifact).resolve()
        if not artifact_path.is_relative_to(manifest_path.parent) or not artifact_path.is_file():
            raise ConfigurationError(f"{where}.artifact_ref must resolve to a file beside the manifest")
        artifact_digest = _text(manifest["artifact_sha256"], f"{where}.artifact_sha256").lower()
        if (not re.fullmatch(r"[0-9a-f]{64}", artifact_digest)
                or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != artifact_digest):
            raise ConfigurationError(f"{where} artifact digest does not match")
        support_files = manifest.get("supporting_artifacts", [])
        if not isinstance(support_files, list):
            raise ConfigurationError(f"{where}.supporting_artifacts must be an array")
        seen_support: set[str] = set()
        pinned_digests = {artifact_digest}
        for support in support_files:
            if not isinstance(support, dict) or set(support) != {"artifact_ref", "artifact_sha256"}:
                raise ConfigurationError(f"{where}.supporting_artifacts entry is invalid")
            support_ref = Path(_text(support["artifact_ref"], f"{where}.supporting_artifacts.artifact_ref"))
            if support_ref.is_absolute() or str(support_ref) in seen_support:
                raise ConfigurationError(f"{where}.supporting_artifacts contains duplicate or absolute paths")
            seen_support.add(str(support_ref))
            support_path = (manifest_path.parent / support_ref).resolve()
            support_hash = _text(support["artifact_sha256"], f"{where}.supporting_artifacts.sha256").lower()
            if (not support_path.is_relative_to(manifest_path.parent) or not support_path.is_file()
                    or not re.fullmatch(r"[0-9a-f]{64}", support_hash)
                    or hashlib.sha256(support_path.read_bytes()).hexdigest() != support_hash):
                raise ConfigurationError(f"{where} supporting artifact digest does not match")
            pinned_digests.add(support_hash)
        try:
            operation = operation_from_manifest(manifest)
            operation_id = operation["operation_id"]
            capability_id = manifest.get("capability_id", operation_id)
            if capability_id in plugin_ids or capability_id not in capabilities:
                raise CapabilityContractError("operation_id must be unique and explicitly declared in module.capabilities")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", capability_id):
                raise CapabilityContractError("operation_id is invalid")
            if operation["provider"]["artifact_sha256"] not in pinned_digests:
                raise CapabilityContractError("operation provider digest must pin a declared artifact")
            capability_registry.register(operation, plugin_config, legacy_manifest=manifest)
        except (CapabilityContractError, KeyError, TypeError) as exc:
            raise ConfigurationError(f"{where}.manifest operation contract is invalid: {exc}") from exc
        plugin_ids.add(capability_id)

    timing = value["timing"]
    if not isinstance(timing, dict):
        raise ConfigurationError("timing must be an object")
    _keys(timing, {"observer_interval_seconds", "scheduler_interval_seconds", "lease_seconds", "heartbeat_interval_seconds", "heartbeat_stale_after_seconds", "diagnostic_stale_after_seconds", "restart_initial_seconds", "restart_max_seconds", "worker_concurrency"}, "timing")
    concurrency = timing["worker_concurrency"]
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise ConfigurationError("worker_concurrency must be a positive integer")
    initial = _positive(timing["restart_initial_seconds"], "timing.restart_initial_seconds")
    maximum = _positive(timing["restart_max_seconds"], "timing.restart_max_seconds")
    if maximum < initial:
        raise ConfigurationError("restart_max_seconds must be >= restart_initial_seconds")
    stale = _positive(timing["heartbeat_stale_after_seconds"], "timing.heartbeat_stale_after_seconds")
    heartbeat = _positive(timing["heartbeat_interval_seconds"], "timing.heartbeat_interval_seconds")
    if stale <= heartbeat:
        raise ConfigurationError("heartbeat_stale_after_seconds must exceed heartbeat_interval_seconds")

    return Settings(
        instance_id=instance_id,
        source_path=source,
        source_digest=hashlib.sha256(raw_bytes).hexdigest(),
        data_dir=data_dir,
        database=database,
        database_user=database_user,
        database_socket_dir=socket_dir,
        database_port=port,
        control_socket=control_socket,
        diagnostics_socket=diagnostics_socket,
        module_socket=module_socket,
        machine_catalog_dir=machine_catalog_dir,
        module_id=module_id,
        module_version=module_version,
        module_contract_id=module_contract_id,
        module_protocol_major=proto_major,
        module_protocol_minor=proto_minor,
        module_capabilities=tuple(capabilities),
        module_owner=module_owner,
        module_entrypoint=entrypoint,
        module_source=module_source,
        module_digest=module_digest,
        observer_interval_seconds=_positive(timing["observer_interval_seconds"], "timing.observer_interval_seconds"),
        scheduler_interval_seconds=_positive(timing["scheduler_interval_seconds"], "timing.scheduler_interval_seconds"),
        lease_seconds=_positive(timing["lease_seconds"], "timing.lease_seconds"),
        heartbeat_interval_seconds=heartbeat,
        heartbeat_stale_after_seconds=stale,
        diagnostic_stale_after_seconds=_positive(timing["diagnostic_stale_after_seconds"], "timing.diagnostic_stale_after_seconds"),
        restart_initial_seconds=initial,
        restart_max_seconds=maximum,
        worker_concurrency=concurrency,
        model_provider=model_provider,
        model_endpoint=model_endpoint,
        model_name=model_name,
        model_timeout_seconds=model_timeout_seconds,
        model_max_tokens=model_max_tokens,
        model_routes=model_routes,
        default_model_route=default_model_route,
        model_roles=model_roles,
        default_model_role=default_model_role,
        reasoning_escalation=reasoning_escalation,
        authorization_provider=authorization_provider,
        knowledge_sources=knowledge_sources,
        capability_registry=capability_registry,
    )


def _redact_provider_options(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("<redacted>" if re.search(r"secret|password|token|credential|api.?key", key, re.I)
                      else _redact_provider_options(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_provider_options(item) for item in value]
    return value


def sanitized_config(settings: Settings) -> dict[str, Any]:
    """Return non-secret effective values suitable for durable config history."""
    return {
        "instance_id": settings.instance_id,
        "database": {"name": settings.database, "user": settings.database_user,
                     "socket_dir": str(settings.database_socket_dir), "port": settings.database_port},
        "paths": {"data_dir": str(settings.data_dir), "control_socket": str(settings.control_socket),
                  "diagnostics_socket": str(settings.diagnostics_socket), "module_socket": str(settings.module_socket)},
        "module": {"module_id": settings.module_id, "version": settings.module_version,
                   "contract_id": settings.module_contract_id,
                   "protocol_major": settings.module_protocol_major,
                   "protocol_minor": settings.module_protocol_minor,
                   "capabilities": list(settings.module_capabilities), "owner": settings.module_owner,
                   "entrypoint": settings.module_entrypoint, "source": str(settings.module_source),
                   "sha256": settings.module_digest},
        "authorization": {"provider_id": settings.authorization_provider.provider_id,
                          "contract_version": settings.authorization_provider.contract_version,
                          "options": _redact_provider_options(settings.authorization_provider.options)},
        "grace": ({"default_route": settings.default_model_route,
                   "routes": [{"route_id": route.route_id, "provider": route.provider,
                               "endpoint": route.endpoint, "model": route.model,
                               "timeout_seconds": route.timeout_seconds, "max_tokens": route.max_tokens}
                              for route in settings.model_routes],
                   "knowledge_sources": [str(path) for path in settings.knowledge_sources],
                   "role_registry": ({"schema_version": 1, "default_role": settings.default_model_role,
                                      "roles": [{"role_id": role.role_id, "route_id": role.route_id,
                                                 "capabilities": list(role.capabilities),
                                                 "modalities": list(role.modalities),
                                                 "fallback_roles": list(role.fallback_roles),
                                                 "readiness_max_age_seconds": role.readiness_max_age_seconds,
                                                 "unavailable_action": role.unavailable_action,
                                                 "deferral_seconds": role.deferral_seconds,
                                                 "concurrency": role.concurrency}
                                                for role in settings.model_roles]}
                                     if settings.model_roles else None),
                   "reasoning_escalation": ({"contract_id": settings.reasoning_escalation.contract_id,
                                              "contract_version": settings.reasoning_escalation.contract_version,
                                              "enabled": settings.reasoning_escalation.enabled,
                                              "authorization_capability_id": settings.reasoning_escalation.authorization_capability_id,
                                              "allowed_role_ids": list(settings.reasoning_escalation.allowed_role_ids),
                                              "max_requests_per_activity": settings.reasoning_escalation.max_requests_per_activity,
                                              "max_completion_tokens_per_activity": settings.reasoning_escalation.max_completion_tokens_per_activity}
                                             if settings.reasoning_escalation else None)}
                  if settings.model_endpoint else None),
        "timing": {"observer_interval_seconds": settings.observer_interval_seconds,
                   "scheduler_interval_seconds": settings.scheduler_interval_seconds,
                   "lease_seconds": settings.lease_seconds,
                   "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
                   "heartbeat_stale_after_seconds": settings.heartbeat_stale_after_seconds,
                   "diagnostic_stale_after_seconds": settings.diagnostic_stale_after_seconds,
                   "restart_initial_seconds": settings.restart_initial_seconds,
                   "restart_max_seconds": settings.restart_max_seconds,
                   "worker_concurrency": settings.worker_concurrency},
    }
