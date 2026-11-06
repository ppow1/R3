"""
R3 CONTROLLED SOURCE
File: r3a_runtime/config.py
Component: R3A-BOOTSTRAP-CONFIG
File Revision: 1.1.0
Created: 2026-11-06T15:04:00Z
Created By: Codex GPT-6
Purpose: Strictly validate external R3A AP0-M1 bootstrap and operating settings.
Execution Model: Shared synchronous configuration parser.
Observability: Configuration revision digest and validation errors.
Dependencies: Python 3.12 standard library.
Authority: AP1 / R3A-019 and AP1 Slice 1 authorized by Steward; isolated R3A only.
Changed: 2026-11-06T15:04:00Z | R3A-AP0-M1 | Codex GPT-6 | Add fail-closed external configuration parser.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Restrict observer capabilities to the two AP0 read-only contracts.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Validate Grace model, capability, and allowlisted knowledge configuration.
Changed: 2026-11-06T18:02:08Z | R3A-019 | Codex GPT-6 | Add external model routes while retaining legacy single-route config compatibility.
Changed: 2026-11-06T23:19:46Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Add validated configurable model roles and authorization provider selection.
Changed: 2026-11-06T23:43:25Z | R3A-AP1-SLICE-1 | Codex GPT-6 | Preserve route-only configuration compatibility and finalize strict role/provider validation.
Supersedes: None.
Contracts: AP0-001/008/009; R3A-019; AP0-M1 D7; r3a_runtime.contracts; hints/file-provenance.md.
Tests: tests/test_r3a_ap1.py; tests/test_r3a_modular_autonomy.py.
History/Predecessor: Git blob 01c6d0c93648ce63a93cf3e8fcbdda61a47e82a9 at commit cc7f662c04a4ba8eb327edd134e2ded92ef9786c.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


@dataclass(frozen=True)
class AuthorizationProviderSettings:
    provider_id: str
    contract_version: str
    options: dict[str, Any]


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
    authorization_provider: AuthorizationProviderSettings
    knowledge_sources: tuple[Path, ...]

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
    extra = value.keys() - expected_root - {"grace", "authorization"}
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
    knowledge_sources: tuple[Path, ...] = ()
    if entrypoint == "r3a_runtime.grace_module" or grace is not None:
        if not isinstance(grace, dict):
            raise ConfigurationError("grace must be an object when the Grace resident is configured")
        legacy_keys = {"provider", "endpoint", "model", "timeout_seconds", "max_tokens", "knowledge_sources"}
        route_keys = {"routes", "default_route", "knowledge_sources"}
        role_route_keys = route_keys | {"role_registry"}
        if set(grace) == legacy_keys:
            route_data = [{"route_id": "default", "provider": grace["provider"],
                           "endpoint": grace["endpoint"], "model": grace["model"],
                           "timeout_seconds": grace["timeout_seconds"], "max_tokens": grace["max_tokens"]}]
            default_model_route = "default"
        elif set(grace) in (route_keys, role_route_keys):
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
            endpoint = _text(item["endpoint"], f"{where}.endpoint")
            if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:", "https://")):
                raise ConfigurationError(f"{where}.endpoint must use loopback HTTP or HTTPS")
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
                _keys(item, {"role_id", "route_id", "capabilities", "modalities", "fallback_roles",
                             "readiness_max_age_seconds", "unavailable_action", "deferral_seconds",
                             "concurrency"}, where)
                role_id = _text(item["role_id"], f"{where}.role_id")
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", role_id) or role_id in role_ids:
                    raise ConfigurationError(f"{where}.role_id must be unique and use contract-safe characters")
                role_ids.add(role_id)
                route_id = _text(item["route_id"], f"{where}.route_id")
                if route_id not in route_ids:
                    raise ConfigurationError(f"{where}.route_id must identify a configured route")
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
                    concurrency=concurrency))
            if default_model_role not in role_ids:
                raise ConfigurationError("grace.role_registry.default_role must identify a configured role")
            for role in parsed_roles:
                if set(role.fallback_roles) - role_ids:
                    raise ConfigurationError(f"role {role.role_id} references an unconfigured fallback role")
            model_roles = tuple(parsed_roles)

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
        authorization_provider=authorization_provider,
        knowledge_sources=knowledge_sources,
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
                                     if settings.model_roles else None)}
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
