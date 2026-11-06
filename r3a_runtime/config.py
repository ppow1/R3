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
Authority: AP0-M1 implementation authorized by Steward in GitHub Issue #42; isolated R3A only.
Changed: 2026-11-06T15:04:00Z | R3A-AP0-M1 | Codex GPT-6 | Add fail-closed external configuration parser.
Changed: 2026-11-06T15:46:11Z | R3A-AP0-M1 | Codex GPT-6 | Restrict observer capabilities to the two AP0 read-only contracts.
Supersedes: None.
Contracts: AP0-001/009; AP0-M1 D7; hints/file-provenance.md.
Tests: tests/test_r3a_config.py.
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
    _keys(value, {"schema_version", "instance_id", "paths", "postgres", "module", "timing"}, "root")
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
    if set(capabilities) != {"host.process.read", "postgres.readiness"}:
        raise ConfigurationError("AP0-M1 foundation observer supports only host.process.read and postgres.readiness")
    module_owner = _text(module["owner"], "module.owner")
    entrypoint = _text(module["entrypoint"], "module.entrypoint")
    if entrypoint != "r3a_runtime.observer_module":
        raise ConfigurationError("module.entrypoint is not supported by this AP0-M1 installation")
    module_source = _absolute_path(module["source"], "module.source")
    module_digest = _text(module["sha256"], "module.sha256").lower()
    if len(module_digest) != 64 or any(c not in "0123456789abcdef" for c in module_digest):
        raise ConfigurationError("module.sha256 must be a SHA-256 hex digest")
    if not module_source.is_file():
        raise ConfigurationError(f"module source does not exist: {module_source}")
    actual_digest = hashlib.sha256(module_source.read_bytes()).hexdigest()
    if actual_digest != module_digest:
        raise ConfigurationError("module source digest does not match the registered manifest")

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
