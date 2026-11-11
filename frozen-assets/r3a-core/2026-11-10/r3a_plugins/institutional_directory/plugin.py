"""Read-only R3A adapter for Riverview's authoritative institutional directory.

The provider connects directly to the configured, least-privilege PostgreSQL
reader for ``riverview_authority``. It never reads or calls the legacy R/3 HR
SQLite store or website service. The DSN is supplied out of band through an
environment variable named by plugin configuration and is never returned in
results or diagnostics.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable

from r3a_runtime.capability_contracts import CapabilityProviderResult, validate_json


DIRECTORY_SCHEMA_ID = "r3a.institutional-directory.v1"
SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
MAX_ROWS = 250

CAPABILITY_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["capability_id", "owner_office", "authority_action", "enabled",
                 "availability_policy", "registration_blocker", "input_schema",
                 "authorization_contract", "resources", "availability_state",
                 "availability_basis"],
    "properties": {
        "capability_id": {"type": "string"},
        "owner_office": {"type": ["string", "null"]},
        "authority_action": {"type": ["string", "null"]},
        "enabled": {"type": ["boolean", "null"]},
        "availability_policy": {"type": ["string", "object", "array", "null"],
                                "items": {"type": "string"}},
        "registration_blocker": {"type": ["string", "null"]},
        "input_schema": {"type": ["object", "null"]},
        "authorization_contract": {"type": ["string", "object", "null"]},
        "resources": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["resource_id", "implementation_ref"],
            "properties": {"resource_id": {"type": "string"},
                           "implementation_ref": {"type": ["string", "null"]}},
        }},
        "availability_state": {"const": "unavailable", "type": "string"},
        "availability_basis": {"type": "string"},
    },
}

OUTPUT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_id", "schema_version", "observed_at", "source",
                  "offices", "residents", "capabilities"],
    "properties": {
        "schema_id": {"const": DIRECTORY_SCHEMA_ID, "type": "string"},
        "schema_version": {"const": 1, "type": "integer"},
        "observed_at": {"type": "string", "format": "date-time"},
        "source": {
            "type": "object", "additionalProperties": False,
            "required": ["source_id", "source_contract", "snapshot_sha256", "observed_at",
                         "freshness", "availability", "error", "row_counts",
                         "potentially_truncated", "transaction_isolation", "timestamp_basis"],
            "properties": {
                "source_id": {"const": "riverview_authority.directory", "type": "string"},
                "source_contract": {"const": "riverview-authority.directory.v1", "type": "string"},
                "snapshot_sha256": {"type": ["string", "null"], "pattern": "^[a-f0-9]{64}$"},
                "observed_at": {"type": "string", "format": "date-time"},
                "freshness": {"enum": ["fresh", "unavailable"], "type": "string"},
                "availability": {"enum": ["measured", "unavailable"], "type": "string"},
                "error": {"type": ["string", "null"]},
                "row_counts": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
                "potentially_truncated": {"type": "boolean"},
                "transaction_isolation": {"type": "string"},
                "timestamp_basis": {"type": "string"},
            },
        },
        "offices": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["office_id", "office_role", "status", "residents", "capabilities"],
            "properties": {
                "office_id": {"type": "string"}, "office_role": {"type": "string"},
                "status": {"type": "string"},
                "residents": {"type": "array", "items": {"type": "string"}},
                "capabilities": {"type": "array", "items": CAPABILITY_SCHEMA},
            },
        }},
        "residents": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["resident_id", "display_name", "office_id", "office_role",
                         "office_status", "binding_revision", "availability",
                         "availability_state"],
            "properties": {
                "resident_id": {"type": "string"}, "display_name": {"type": ["string", "null"]},
                "office_id": {"type": "string"}, "office_role": {"type": "string"},
                "office_status": {"type": "string"}, "binding_revision": {"type": ["integer", "string"]},
                "availability": {"type": ["string", "null"]},
                "availability_state": {"enum": ["measured", "unavailable"], "type": "string"},
            },
        }},
        "capabilities": {"type": "array", "items": CAPABILITY_SCHEMA},
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _unavailable(observed_at: str, reason: str) -> dict[str, Any]:
    return {
        "source_id": "riverview_authority.directory",
        "source_contract": "riverview-authority.directory.v1",
        "snapshot_sha256": None, "observed_at": observed_at,
        "freshness": "unavailable", "availability": "unavailable",
        "error": reason, "row_counts": {"offices": 0, "bindings": 0,
                                           "residents": 0, "capabilities": 0,
                                           "resources": 0},
        "potentially_truncated": False,
        "transaction_isolation": "read_only_repeatable_read",
        "timestamp_basis": "PostgreSQL transaction snapshot observation time; binding_revision is source revision",
    }


def _normalize_rows(rows: dict[str, list[dict[str, Any]]], observed_at: str,
                    limit: int) -> dict[str, Any]:
    offices_by_id: dict[str, dict[str, Any]] = {}
    for row in rows["offices"]:
        office_id, office_role, status = row.get("office_id"), row.get("office_role"), row.get("status")
        if not all(isinstance(value, str) and value for value in (office_id, office_role, status)):
            raise ValueError("invalid_office_record")
        if office_id in offices_by_id:
            raise ValueError("duplicate_office_record")
        offices_by_id[office_id] = {"office_id": office_id, "office_role": office_role,
                                    "status": status, "residents": [], "capabilities": []}

    residents: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows["bindings"]:
        office_id, principal_id = row.get("office_id"), row.get("principal_id")
        if office_id not in offices_by_id or not isinstance(principal_id, str) or not principal_id:
            raise ValueError("invalid_resident_binding")
        key = (office_id, principal_id)
        resident = {"resident_id": principal_id, "display_name": None,
                    "office_id": office_id,
                    "office_role": offices_by_id[office_id]["office_role"],
                    "office_status": offices_by_id[office_id]["status"],
                    "binding_revision": row.get("binding_revision"),
                    "availability": None, "availability_state": "unavailable"}
        if key in residents and residents[key] != resident:
            raise ValueError("conflicting_resident_binding")
        residents[key] = resident
        offices_by_id[office_id]["residents"].append(principal_id)

    capability_ids: set[str] = set()
    capabilities: list[dict[str, Any]] = []
    for row in rows["capabilities"]:
        capability_id, owner_office = row.get("capability_id"), row.get("owner_office")
        if not isinstance(capability_id, str) or not capability_id or capability_id in capability_ids:
            raise ValueError("invalid_capability_record")
        capability_ids.add(capability_id)
        item = {
            "capability_id": capability_id, "owner_office": owner_office,
            "authority_action": row.get("authority_action"),
            "enabled": row.get("enabled"),
            "availability_policy": row.get("availability_policy"),
            "registration_blocker": row.get("registration_blocker"),
            "input_schema": row.get("input_schema"),
            "authorization_contract": row.get("authorization_contract"),
            "resources": sorted(row.get("resources", []), key=lambda value: value["resource_id"]),
            "availability_state": "unavailable",
            "availability_basis": "directory metadata is authoritative; provider health was not probed",
        }
        capabilities.append(item)
        if owner_office in offices_by_id:
            offices_by_id[owner_office]["capabilities"].append(item)

    for office in offices_by_id.values():
        office["residents"] = sorted(set(office["residents"]))
        office["capabilities"].sort(key=lambda item: item["capability_id"])

    canonical_rows = {key: rows[key] for key in sorted(rows)}
    snapshot_digest = hashlib.sha256(json.dumps(
        canonical_rows, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    counts = {key: len(value) for key, value in rows.items()}
    return {
        "schema_id": DIRECTORY_SCHEMA_ID, "schema_version": 1, "observed_at": observed_at,
        "source": {
            "source_id": "riverview_authority.directory",
            "source_contract": "riverview-authority.directory.v1",
            "snapshot_sha256": snapshot_digest, "observed_at": observed_at,
            "freshness": "fresh", "availability": "measured", "error": None,
            "row_counts": counts,
            "potentially_truncated": any(len(items) >= limit for items in rows.values()),
            "transaction_isolation": "read_only_repeatable_read",
            "timestamp_basis": "PostgreSQL transaction snapshot observation time; binding_revision is source revision",
        },
        "offices": sorted(offices_by_id.values(), key=lambda item: item["office_id"]),
        "residents": sorted(residents.values(), key=lambda item: (item["office_id"], item["resident_id"])),
        "capabilities": sorted(capabilities, key=lambda item: item["capability_id"]),
    }


class InstitutionalDirectoryProvider:
    """Bounded read-only snapshot adapter for the authoritative Riverview directory."""

    def __init__(self, configuration: dict[str, Any], *,
                 connect: Callable[..., Any] | None = None):
        self.configuration = configuration
        self._connect = connect

    def _connection(self, dsn: str):
        if self._connect is not None:
            return self._connect(dsn)
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(dsn, connect_timeout=int(self.configuration["connect_timeout_seconds"]),
                               autocommit=True, row_factory=dict_row,
                               options="-c default_transaction_read_only=on -c statement_timeout=3000")

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> CapabilityProviderResult:
        del context  # Directory authority is separate from the dynamic R3A execution registry.
        observed_at = _iso(_now())
        env_name = self.configuration["dsn_env"]
        dsn = os.environ.get(env_name, "")
        schema = self.configuration["schema"]
        limit = min(max(1, int(arguments.get("limit", MAX_ROWS))), MAX_ROWS)
        if not dsn:
            result = _unavailable(observed_at, "directory_source_not_configured")
            output = {"schema_id": DIRECTORY_SCHEMA_ID, "schema_version": 1,
                      "observed_at": observed_at, "source": result,
                      "offices": [], "residents": [], "capabilities": []}
            evidence = [{"source_id": result["source_id"], "source_contract": result["source_contract"],
                         "snapshot_sha256": None, "observed_at": observed_at,
                         "freshness": "unavailable", "error": result["error"]}]
            validate_json(output, OUTPUT_SCHEMA, path="$.output")
            return CapabilityProviderResult(output, evidence)
        if not SCHEMA_NAME.fullmatch(schema):
            raise ValueError("invalid_directory_schema_configuration")
        try:
            connection = self._connection(dsn)
            try:
                connection.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                where_office = " AND o.office_id = %(office_id)s" if arguments.get("office_id") else ""
                parameters: dict[str, Any] = {"limit": limit}
                if arguments.get("office_id"):
                    parameters["office_id"] = arguments["office_id"]
                office_rows = connection.execute(
                    f'SELECT o.office_id,o.office_role,o.status FROM "{schema}".institutional_offices o '
                    f'WHERE TRUE{where_office} ORDER BY o.office_id LIMIT %(limit)s', parameters).fetchall()
                offices = [dict(row) for row in office_rows]
                office_ids = [row["office_id"] for row in offices]
                bindings: list[dict[str, Any]] = []
                capabilities: list[dict[str, Any]] = []
                if office_ids:
                    bindings = [dict(row) for row in connection.execute(
                        f'SELECT b.office_id,r.principal_id,b.binding_revision FROM "{schema}".office_bindings b '
                        f'JOIN "{schema}".resident_occupants r ON r.occupant_id=b.occupant_id '
                        'WHERE r.retired_at IS NULL AND b.office_id = ANY(%(office_ids)s) '
                        'AND (%(resident_id)s::text IS NULL OR r.principal_id = %(resident_id)s::text) '
                        'ORDER BY b.office_id,r.principal_id LIMIT %(limit)s',
                        {"office_ids": office_ids, "resident_id": arguments.get("resident_id"),
                         "limit": limit}).fetchall()]
                    catalog_rows = connection.execute(
                        f'SELECT c.capability_id,c.owner_office,c.authority_action,c.enabled,'
                        f'c.availability_policy,c.registration_blocker,c.input_schema,c.authorization_contract '
                        f'FROM "{schema}".capability_catalog c WHERE c.owner_office = ANY(%(office_ids)s) '
                        'ORDER BY c.capability_id LIMIT %(limit)s',
                        {"office_ids": office_ids, "limit": limit}).fetchall()
                    capabilities = [dict(row) for row in catalog_rows]
                    capability_ids = [row["capability_id"] for row in capabilities]
                    if capability_ids:
                        resources = [dict(row) for row in connection.execute(
                            f'SELECT capability_id,resource_id,implementation_ref FROM "{schema}".capability_resources '
                            'WHERE capability_id = ANY(%(capability_ids)s) ORDER BY capability_id,resource_id '
                            'LIMIT %(limit)s', {"capability_ids": capability_ids, "limit": limit}).fetchall()]
                        by_capability: dict[str, list[dict[str, Any]]] = {}
                        for row in resources:
                            by_capability.setdefault(row["capability_id"], []).append({
                                "resource_id": row["resource_id"],
                                "implementation_ref": row["implementation_ref"]})
                        for row in capabilities:
                            row["resources"] = by_capability.get(row["capability_id"], [])
                    else:
                        resources = []
                        for row in capabilities:
                            row["resources"] = []
                else:
                    resources = []
                result = _normalize_rows({"offices": offices, "bindings": bindings,
                                          "capabilities": capabilities, "resources": resources},
                                         observed_at, limit)
                connection.execute("COMMIT")
            finally:
                connection.close()
        except Exception as exc:
            # Keep credentials, SQL and server diagnostics out of returned evidence.
            error_type = type(exc).__name__
            result = {"schema_id": DIRECTORY_SCHEMA_ID, "schema_version": 1,
                      "observed_at": observed_at,
                      "source": _unavailable(observed_at, f"directory_source_unavailable:{error_type}"),
                      "offices": [], "residents": [], "capabilities": []}
            evidence = [{"source_id": result["source"]["source_id"],
                         "source_contract": result["source"]["source_contract"],
                         "snapshot_sha256": None, "observed_at": observed_at,
                         "freshness": "unavailable", "error": result["source"]["error"]}]
            validate_json(result, OUTPUT_SCHEMA, path="$.output")
            return CapabilityProviderResult(result, evidence)

        validate_json(result, OUTPUT_SCHEMA, path="$.output")
        evidence = [{"source_id": result["source"]["source_id"],
                     "source_contract": result["source"]["source_contract"],
                     "snapshot_sha256": result["source"]["snapshot_sha256"],
                     "observed_at": observed_at, "freshness": result["source"]["freshness"],
                     "row_counts": result["source"]["row_counts"],
                     "transaction_isolation": result["source"]["transaction_isolation"],
                     "error": None}]
        return CapabilityProviderResult(result, evidence)


def create_provider(configuration: dict[str, Any]) -> InstitutionalDirectoryProvider:
    return InstitutionalDirectoryProvider(configuration)
