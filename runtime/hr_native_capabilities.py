# R3 CONTROLLED SOURCE
# File: runtime/hr_native_capabilities.py
# Component: R3-HR-NATIVE-CAPABILITIES
# Purpose: Native-tool capability definitions backed by R3 HR storage.
# Authorization: The existing CapabilityRegistry verifies exact resident grants
# and writes durable audits before invoking these executors.
"""R3 HR capability definitions for registration with the existing native tool router.

No independent listener, credential issuer, or grant authority is created here.
Caller-provided role/identity is never trusted. Read responses expose public
fields only; classified access needs a separately authorized extension.
"""
from __future__ import annotations

from pathlib import Path
from runtime.capabilities import Capability
from runtime.hr_store import HRStore
from runtime.hr_records import HRField, ResidentHRRecord

RESOURCE = "r3:hr"
SCOPE = "scope_ref"

def _record(data: dict) -> ResidentHRRecord:
    if not isinstance(data, dict):
        raise ValueError("record must be object")
    def unpack(name):
        raw = data.get(name, {})
        if not isinstance(raw, dict):
            raise ValueError("invalid fields")
        return {k: HRField(**v) for k, v in raw.items()}
    return ResidentHRRecord(
        resident_id=data["resident_id"],
        display_name=data["display_name"],
        office=data["office"],
        status=data.get("status", "onboarding"),
        schema_version=data.get("schema_version", 1),
        fields=unpack("fields"), extensions=unpack("extensions"),
        history_refs=list(data.get("history_refs", [])),
    )

def native_hr_capabilities(database: str | Path) -> tuple[Capability, ...]:
    """Return capabilities for ToolRouter(capabilities=...), not a new router.

    The router's canonical R3Authority grant check is mandatory. The
    read-only descriptors return only public-classified HR fields.
    """
    path = Path(database)
    if not path.is_file():
        raise FileNotFoundError("HR database must already exist")

    def directory(params):
        store = HRStore(path)
        try:
            result = []
            for rid in store.resident_ids():
                found = store.get(rid)
                if found:
                    item, revision = found
                    visible = item.view(role="approved_requester")
                    visible["revision"] = revision
                    result.append(visible)
            return result
        finally:
            store.close()

    def read(params):
        rid = params.get("resident_id")
        if not isinstance(rid, str) or not rid:
            raise ValueError("resident_id required")
        store = HRStore(path)
        try:
            found = store.get(rid)
            if found is None:
                return None
            item, revision = found
            visible = item.view(role="approved_requester")
            visible["revision"] = revision
            return visible
        finally:
            store.close()

    def save(params):
        record = _record(params["record"])
        expected = params.get("expected_revision")
        if expected is not None and (type(expected) is not int or expected < 1):
            raise ValueError("invalid expected_revision")
        store = HRStore(path)
        try:
            return {"revision": store.put(record, expected_revision=expected)}
        finally:
            store.close()

    def schema(properties, required=()):
        return {"type": "object", "properties": {
            SCOPE: {"type": "string"}, **properties},
            "required": [SCOPE, *required], "additionalProperties": False}

    return (
        Capability(name="hr.directory", action="hr.directory",
                   description="List R3 residents and public HR fields",
                   parameters=schema({}), executor=directory,
                   read_only=True, resource_ref=RESOURCE),
        Capability(name="hr.read", action="hr.read",
                   description="Read a resident's public HR record",
                   parameters=schema({"resident_id": {"type": "string"}},
                                     ("resident_id",)),
                   executor=read, read_only=True, resource_ref=RESOURCE),
        Capability(name="hr.save", action="hr.save",
                   description="Create or revise an HR record with an exact write grant",
                   parameters=schema({
                       "record": {"type": "object"},
                       "expected_revision": {"type": "integer", "minimum": 1}},
                       ("record",)),
                   executor=save, read_only=False, resource_ref=RESOURCE),
    )
