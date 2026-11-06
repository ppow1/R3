"""
R3 CONTROLLED SOURCE
File: r3a_runtime/config.py
Component: R3A-BOOTSTRAP-CONFIG
File Revision: 1.0.0
Created: 2026-11-06T15:04:00Z
Created By: Codex GPT-6
Purpose: Strictly validate external R3A AP0-M1 bootstrap and operating settings.
Execution Model: Shared synchronous configuration parser.
Observability: Configuration revision digest and validation errors.
Dependencies: Python 3.12 standard library.
Authority: AP0-M1 authorized by Steward in Issue #42; AP1-M1 authorized in Issue #43; isolated R3A only.
Changed: 2026-11-06T15:04:00Z | R3A-AP0-M1 | Codex GPT-6 | Add fail-closed external configuration parser.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Restrict observer capabilities to the two AP0 read-only contracts.
Changed: 2026-11-06 | R3A-AP1-M1 | Codex GPT-6 | Validate Grace model, capability, and allowlisted knowledge configuration.
Supersedes: None.
Contracts: AP0-001/009; R3A-019; AP0-M1 D7; hints/file-provenance.md.
Tests: Live AP1-M1 model configuration preflight and operation.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(ValueError):
    """A bootstrap file is missing, malformed, or outside its contract."""


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
    knowledge_sources: tuple[Path, ...]

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
    extra = value.keys() - expected_root - {"grace"}
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
    ap0_caps = {"host.process.read", "postgres.readiness"}
    ap1_caps = ap0_caps | {"institution.knowledge.read", "institution.diagnostics.read"}
    if set(capabilities) not in (ap0_caps, ap1_caps):
        raise ConfigurationError("module.capabilities must use the supported AP0 or AP1 read-only capability set")
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
    knowledge_sources: tuple[Path, ...] = ()
    if entrypoint == "r3a_runtime.grace_module" or grace is not None:
        if not isinstance(grace, dict):
            raise ConfigurationError("grace must be an object when the Grace resident is configured")
        _keys(grace, {"provider", "endpoint", "model", "timeout_seconds", "max_tokens", "knowledge_sources"}, "grace")
        model_provider = _text(grace["provider"], "grace.provider")
        if model_provider != "openai-compatible":
            raise ConfigurationError("grace.provider must equal openai-compatible")
        model_endpoint = _text(grace["endpoint"], "grace.endpoint")
        if not model_endpoint.startswith(("http://127.0.0.1:", "http://localhost:", "https://")):
            raise ConfigurationError("grace.endpoint must use loopback HTTP or HTTPS")
        model_name = _text(grace["model"], "grace.model")
        model_timeout_seconds = _positive(grace["timeout_seconds"], "grace.timeout_seconds")
        model_max_tokens = grace["max_tokens"]
        if isinstance(model_max_tokens, bool) or not isinstance(model_max_tokens, int) or not 64 <= model_max_tokens <= 512:
            raise ConfigurationError("grace.max_tokens must be an integer from 64 through 512")
        sources = grace["knowledge_sources"]
        if (not isinstance(sources, list) or not sources or
                any(not isinstance(item, str) for item in sources) or len(set(sources)) != len(sources)):
            raise ConfigurationError("grace.knowledge_sources must be a nonempty unique path list")
        resolved = tuple(_absolute_path(item, "grace.knowledge_sources[]") for item in sources)
        if any(not item.is_file() for item in resolved):
            raise ConfigurationError("every configured knowledge source must exist and be a regular file")
        knowledge_sources = resolved
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
        knowledge_sources=knowledge_sources,
    )


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
        "grace": ({"provider": settings.model_provider, "endpoint": settings.model_endpoint,
                   "model": settings.model_name, "timeout_seconds": settings.model_timeout_seconds,
                   "max_tokens": settings.model_max_tokens,
                   "knowledge_sources": [str(path) for path in settings.knowledge_sources]}
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
