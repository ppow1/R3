"""Read-only R3A adapter for the authoritative HR resident record store.

This module owns the R3A provider boundary. It reads the configured SQLite
source directly in query-only mode and does not import or call an R/3 service.
Only HR record identity, office, status, schema/revision, and explicitly public
role text are projected. Responsibility bindings remain HR-owned configuration.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from r3a_runtime.capability_contracts import CapabilityProviderResult, validate_json


DIRECTORY_SCHEMA_ID = "r3a.institutional-directory.v1"
RESPONSIBILITY_CATALOG_SCHEMA_ID = "r3a.institutional-responsibility-catalog.v1"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
RESPONSIBILITY_CATALOG_SCHEMA = json.loads(
    Path(__file__).with_name("responsibility_catalog.schema.json").read_text(encoding="utf-8"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unavailable_source(*, observed_at: str, max_age: int, reason: str) -> dict[str, Any]:
    return {
        "source_id": "hr.resident-records",
        "source_contract": "r3.hr-resident-record.v1",
        "source_sha256": None,
        "source_modified_at": None,
        "observed_at": observed_at,
        "age_seconds": None,
        "max_age_seconds": max_age,
        "freshness": "unavailable",
        "availability": "unavailable",
        "error": reason,
        "record_count": 0,
        "complete_inventory": False,
        "total_matching_records": 0,
        "source_timestamp_basis": "SQLite source file last modification time; rows expose HR record revisions",
    }


def _read_public_role(payload: dict[str, Any]) -> str | None:
    fields = payload.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("invalid_hr_fields")
    role = fields.get("role")
    if not isinstance(role, dict):
        return None
    value = role.get("value")
    if role.get("classification") == "public" and isinstance(value, str):
        return value
    return None


def _read_residents(path: Path, *, filters: dict[str, Any], limit: int) -> tuple[list[dict[str, Any]], int]:
    uri = path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=2.0)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        clauses: list[str] = []
        parameters: list[Any] = []
        if filters.get("resident_id"):
            clauses.append("resident_id = ?")
            parameters.append(filters["resident_id"])
        if filters.get("office"):
            clauses.append("json_extract(payload, '$.office') = ?")
            parameters.append(filters["office"])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        total = int(connection.execute(
            "SELECT COUNT(*) FROM hr_records" + where, parameters).fetchone()[0])
        rows = connection.execute(
            "SELECT resident_id, revision, payload FROM hr_records" + where +
            " ORDER BY resident_id LIMIT ?", (*parameters, limit),
        ).fetchall()
        residents = []
        for row in rows:
            payload = json.loads(row["payload"])
            if not isinstance(payload, dict):
                raise ValueError("invalid_hr_record")
            resident_id = row["resident_id"]
            display_name = payload.get("display_name")
            office = payload.get("office")
            schema_version = payload.get("schema_version")
            status = payload.get("status")
            revision = row["revision"]
            if (not all(isinstance(item, str) and item for item in
                        (resident_id, display_name, office, status))
                    or type(schema_version) is not int or type(revision) is not int):
                raise ValueError("invalid_hr_record")
            residents.append({
                "resident_id": resident_id,
                "display_name": display_name,
                "office": office,
                "status": status,
                "schema_version": schema_version,
                "record_revision": revision,
                "role_description": _read_public_role(payload),
                "availability": None,
                "availability_state": "unavailable",
                "responsibilities": [],
                "responsibility_state": "unavailable",
            })
        connection.commit()
        return residents, total
    finally:
        connection.close()


def _catalog_from_context(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = context.get("capability_catalog", [])
    if not isinstance(catalog, list):
        raise ValueError("invalid_capability_catalog")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        if not isinstance(entry, dict) or not isinstance(entry.get("descriptor"), dict):
            raise ValueError("invalid_capability_catalog")
        descriptor = entry["descriptor"]
        operation_id = descriptor.get("operation_id")
        if not isinstance(operation_id, str) or operation_id in by_id:
            raise ValueError("invalid_capability_catalog")
        by_id[operation_id] = {
            "descriptor": descriptor,
            "presentation": entry.get("presentation", {}),
            "registry_observation": entry.get("registry_observation", {}),
        }
    return by_id


def _load_responsibility_catalog(config: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, str | None]:
    env_name = config["responsibility_catalog_path_env"]
    configured = os.environ.get(env_name)
    if not configured:
        return None, None, "responsibility_source_not_configured"
    path = Path(configured).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        return None, None, "responsibility_source_unavailable"
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        validate_json(catalog, RESPONSIBILITY_CATALOG_SCHEMA, path="$.responsibility_catalog")
        if catalog.get("schema_id") != RESPONSIBILITY_CATALOG_SCHEMA_ID:
            raise ValueError("responsibility_schema_id_mismatch")
        return catalog, _sha256(path), None
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return None, None, "responsibility_source_invalid"


def _apply_responsibilities(residents: list[dict[str, Any]], catalog: dict[str, Any] | None,
                            capabilities: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if catalog is None:
        return residents, "unavailable"
    office_rules = {entry["office"]: entry["responsibilities"] for entry in catalog["offices"]}
    for resident in residents:
        rules = office_rules.get(resident["office"])
        if rules is None:
            continue
        responsibilities = []
        for rule in rules:
            associated = []
            for capability_id in rule["capability_ids"]:
                registered = capabilities.get(capability_id)
                if registered is None:
                    associated.append({"operation_id": capability_id,
                                       "registry_state": "not_registered",
                                       "authorization_evaluated": False})
                else:
                    associated.append({"operation_id": capability_id,
                                       "descriptor": registered["descriptor"],
                                       "presentation": registered["presentation"],
                                       "registry_observation": registered["registry_observation"],
                                       "authorization_evaluated": False})
            responsibilities.append({"responsibility_id": rule["responsibility_id"],
                                     "description": rule["description"],
                                     "capabilities": associated})
        resident["responsibilities"] = responsibilities
        resident["responsibility_state"] = "measured"
    return residents, "measured"


class InstitutionalDirectoryProvider:
    """Bounded, read-only projection of HR facts and dynamically registered capabilities."""

    def __init__(self, configuration: dict[str, Any]):
        self.configuration = configuration

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        now = _now()
        observed_at = _iso(now)
        config = self.configuration
        max_age = int(config["max_age_seconds"])
        capabilities = _catalog_from_context(context)
        limit = min(max(1, int(arguments.get("limit", 50))), 50)
        path_value = os.environ.get(config["database_path_env"])
        if not path_value:
            source = _unavailable_source(observed_at=observed_at, max_age=max_age,
                                         reason="directory_source_not_configured")
            residents: list[dict[str, Any]] = []
            total = 0
            read_error = source["error"]
        else:
            path = Path(path_value).expanduser().resolve()
            try:
                if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
                    raise ValueError("directory_source_unavailable")
                before = path.stat()
                source_digest = _sha256(path)
                modified = datetime.fromtimestamp(before.st_mtime, timezone.utc)
                age = max(0.0, (now - modified).total_seconds())
                freshness = "fresh" if age <= max_age else "stale"
                residents, total = _read_residents(path, filters=arguments, limit=limit)
                after = path.stat()
                if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
                    raise ValueError("directory_source_changed_during_read")
                source = {
                    "source_id": "hr.resident-records",
                    "source_contract": "r3.hr-resident-record.v1",
                    "source_sha256": source_digest,
                    "source_modified_at": _iso(modified),
                    "observed_at": observed_at,
                    "age_seconds": age,
                    "max_age_seconds": max_age,
                    "freshness": freshness,
                    "availability": "measured",
                    "error": None,
                    "record_count": len(residents),
                    "complete_inventory": (not arguments.get("resident_id")
                                            and not arguments.get("office") and total <= limit),
                    "total_matching_records": total,
                    "source_timestamp_basis": "SQLite source file last modification time; rows expose HR record revisions",
                }
                read_error = None
            except (OSError, sqlite3.Error, json.JSONDecodeError, ValueError, TypeError):
                source = _unavailable_source(observed_at=observed_at, max_age=max_age,
                                             reason="directory_source_unavailable")
                residents = []
                total = 0
                read_error = source["error"]

        responsibility_catalog, responsibility_digest, responsibility_error = _load_responsibility_catalog(config)
        residents, responsibility_state = _apply_responsibilities(residents, responsibility_catalog, capabilities)
        offices_by_name: dict[str, dict[str, Any]] = {}
        for resident in residents:
            entry = offices_by_name.setdefault(resident["office"], {
                "office": resident["office"], "resident_ids": [],
                "responsibilities": resident["responsibilities"],
                "responsibility_state": resident["responsibility_state"],
            })
            entry["resident_ids"].append(resident["resident_id"])

        capability_records = [{
            "descriptor": entry["descriptor"],
            "presentation": entry["presentation"],
            "registry_observation": entry["registry_observation"],
            "authorization_evaluated": False,
        } for entry in sorted(capabilities.values(),
                              key=lambda item: item["descriptor"]["operation_id"])]
        output = {
            "schema_id": DIRECTORY_SCHEMA_ID,
            "schema_version": 1,
            "observed_at": observed_at,
            "source": source,
            "residents": residents,
            "offices": sorted(offices_by_name.values(), key=lambda item: item["office"]),
            "capabilities": capability_records,
            "responsibility_catalog": {
                "schema_id": RESPONSIBILITY_CATALOG_SCHEMA_ID,
                "state": responsibility_state,
                "source_sha256": responsibility_digest,
                "source_revision": responsibility_catalog.get("source_revision") if responsibility_catalog else None,
                "error": responsibility_error,
            },
        }
        evidence = [{
            "source_id": source["source_id"],
            "source_contract": source["source_contract"],
            "source_sha256": source["source_sha256"],
            "source_modified_at": source["source_modified_at"],
            "observed_at": source["observed_at"],
            "freshness": source["freshness"],
            "record_revisions": [{"resident_id": item["resident_id"],
                                  "record_revision": item["record_revision"]}
                                 for item in residents],
            "error": read_error,
        }, {
            "source_id": "r3a.capability-registry",
            "config_revision": context.get("config_revision"),
            "operation_ids": [item["descriptor"]["operation_id"] for item in capability_records],
            "availability_basis": "registered descriptors only; provider health and authorization not evaluated",
        }, {
            "source_id": "institutional.responsibility-catalog",
            "schema_id": RESPONSIBILITY_CATALOG_SCHEMA_ID,
            "state": responsibility_state,
            "source_sha256": responsibility_digest,
            "error": responsibility_error,
        }]
        return CapabilityProviderResult(output, evidence)


def create_provider(configuration: dict[str, Any]) -> InstitutionalDirectoryProvider:
    return InstitutionalDirectoryProvider(configuration)
