# R3 CONTROLLED SOURCE
# File: runtime/hr_governed_capabilities.py
# Purpose: Register persistent R3 HR tools with the existing governed gateway.
# Authority: Existing R3 resident identity, canonical grants, and audit only.
"""Governed HR tools; registration never grants execution authority."""
from __future__ import annotations

from pathlib import Path

from runtime.capabilities import CapabilityDenied
from runtime.governed_tools import GovernedCapability, GovernedToolGateway
from runtime.hr_records import HRField, ResidentHRRecord
from runtime.hr_store import HRStore

RESOURCE = "r3:hr"


def _assert_scope(params, context, expected):
    if params.get("scope_ref") != context.scope_ref or context.scope_ref != expected:
        raise CapabilityDenied("HR scope mismatch")
    if context.resource_id != RESOURCE:
        raise CapabilityDenied("Incorrect HR resource authority")


def _decode_record(raw):
    if not isinstance(raw, dict):
        raise ValueError("HR record must be an object")
    def fields(name):
        values = raw.get(name, {})
        if not isinstance(values, dict):
            raise ValueError("Invalid HR fields")
        return {key: HRField(**entry) for key, entry in values.items()}
    return ResidentHRRecord(
        resident_id=raw["resident_id"], display_name=raw["display_name"],
        office=raw["office"], status=raw.get("status", "onboarding"),
        schema_version=raw.get("schema_version", 1),
        fields=fields("fields"), extensions=fields("extensions"),
        history_refs=list(raw.get("history_refs", [])),
    )


def register_hr_governed_tools(gateway: GovernedToolGateway, database: str | Path):
    """Register read/directory/write; no grants, credentials, or HTTP endpoints."""
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError("Existing HR database required")

    def directory(params, context):
        _assert_scope(params, context, "r3:hr:directory")
        store = HRStore(database)
        try:
            result = []
            for resident_id in store.resident_ids():
                found = store.get(resident_id)
                if found is None:
                    continue
                record, revision = found
                public = record.view(role="resident")
                public["revision"] = revision
                result.append(public)
            return result
        finally:
            store.close()

    def read(params, context):
        resident_id = params.get("resident_id")
        if not isinstance(resident_id, str) or not resident_id:
            raise ValueError("resident_id required")
        _assert_scope(params, context, resident_id)
        store = HRStore(database)
        try:
            found = store.get(resident_id)
            if found is None:
                return None
            record, revision = found
            public = record.view(role="resident")
            public["revision"] = revision
            return public
        finally:
            store.close()

    def save(params, context):
        record = _decode_record(params.get("record"))
        _assert_scope(params, context, record.resident_id)
        # Never accept a caller-provided identity, role or grant.
        expected = params.get("expected_revision")
        if expected is not None and (type(expected) is not int or expected < 1):
            raise ValueError("Invalid revision")
        store = HRStore(database)
        try:
            revision = store.put(record, expected_revision=expected)
            return {"resident_id": record.resident_id, "revision": revision}
        finally:
            store.close()

    def schema(properties, required=()):
        return {"type": "object", "properties": {
            "scope_ref": {"type": "string"}, **properties},
            "required": ["scope_ref", *required],
            "additionalProperties": False}

    gateway.register(GovernedCapability(
        name="hr.directory", resource_id=RESOURCE,
        action="hr.directory", operation="read",
        description="List public R3 resident HR records",
        parameters=schema({}), executor=directory))
    gateway.register(GovernedCapability(
        name="hr.read", resource_id=RESOURCE,
        action="hr.read", operation="read",
        description="Read a single public R3 resident HR record",
        parameters=schema({"resident_id": {"type": "string"}}, ("resident_id",)),
        executor=read))
    gateway.register(GovernedCapability(
        name="hr.save", resource_id=RESOURCE,
        action="hr.save", operation="write",
        description="Create or update one R3 HR record under exact Steward-approved grant",
        parameters=schema({"record": {"type": "object"},
                           "expected_revision": {"type": "integer", "minimum": 1}},
                          ("record",)), executor=save))
