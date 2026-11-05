# R3 CONTROLLED SOURCE
# File: runtime/hr_stdio.py
# Component: HR-STDIO
# File Revision: 1.3.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Transport-neutral JSON-lines stdio dispatcher for R/3 HR
# Execution Model: Synchronous stream adapter; trusted host injects identity
# Observability: Structured result/error; no sensitive data in errors
# Dependencies: Python 3.10+ standard library; runtime/hr_capability.py
# Authority: Only host-injected verified identity; no request-supplied identity
# Changed: 2026-11-05 UTC | HR-004 | Add stdio transport dispatcher
# Supersedes: None
# Contracts: runtime/hr_capability.py; hints/architecture.md
# Tests: tests/test_hr_stdio.py
# Changed: 2026-11-05 UTC | HR-008 | Discover stored residents without caller-supplied IDs
# Changed: 2026-11-05 UTC | HR-009 | Support create/update over local stdio
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-002 | Codex | Add explicit no-rotation principal association workflow
# History/Predecessor: e66c60be7f9657aeb1909e7d33decce9b53c43fc
"""A stdio adapter, NOT a standalone unauthenticated HR server.

The trusted host creates HRCapability with real Comms grant enforcement,
authenticates its session and injects the resulting principal. Request JSON
cannot select principal, role, grants, database, or permissions.
"""
from __future__ import annotations
import json
from typing import TextIO
from runtime.hr_capability import HRCapability, VerifiedPrincipal
from runtime.hr_records import HRField, ResidentHRRecord

def dispatch(capability: HRCapability, principal: VerifiedPrincipal, request: dict) -> dict:
    if not isinstance(request, dict):
        return {"ok": False, "error": "invalid_request"}
    if any(key in request for key in ("principal", "role", "grants", "token", "credential", "db_path")):
        return {"ok": False, "error": "identity_override_forbidden"}
    try:
        operation = request.get("operation")
        if operation == "hr.read":
            rid = request.get("resident_id")
            if not isinstance(rid, str) or not rid.strip():
                return {"ok": False, "error": "invalid_resident_id"}
            fields = request.get("requested_fields", [])
            if not isinstance(fields, list) or not all(isinstance(x, str) for x in fields):
                return {"ok": False, "error": "invalid_requested_fields"}
            result = capability.read(principal, rid, approved_fields=frozenset(fields))
            return {"ok": True, "result": result}
        if operation == "hr.directory":
            ids = request.get("resident_ids")
            if ids is not None and (not isinstance(ids, list) or not all(isinstance(x, str) and x.strip() for x in ids)):
                return {"ok": False, "error": "invalid_resident_ids"}
            return {"ok": True, "result": capability.directory(principal, ids)}
        if operation == "hr.save":
            payload = request.get("record")
            if not isinstance(payload, dict):
                return {"ok": False, "error": "invalid_record"}
            revision = request.get("expected_revision")
            if revision is not None and (type(revision) is not int or revision < 1):
                return {"ok": False, "error": "invalid_revision"}
            def fields(name):
                raw = payload.get(name, {})
                if not isinstance(raw, dict):
                    raise ValueError("invalid fields")
                return {key: HRField(**entry) for key, entry in raw.items()}
            record = ResidentHRRecord(
                resident_id=payload["resident_id"],
                display_name=payload["display_name"],
                office=payload["office"],
                status=payload.get("status", "onboarding"),
                schema_version=payload.get("schema_version", 1),
                fields=fields("fields"), extensions=fields("extensions"),
                history_refs=payload.get("history_refs", []))
            return {"ok": True, "revision": capability.save(
                principal, record, expected_revision=revision)}
        if operation == "hr.associate_principal":
            resident_id = request.get("resident_id")
            authority_principal = request.get("authority_principal")
            revision = request.get("expected_revision")
            if not isinstance(resident_id, str) or not resident_id.strip():
                return {"ok": False, "error": "invalid_resident_id"}
            if not isinstance(authority_principal, str):
                return {"ok": False, "error": "invalid_authority_principal"}
            if type(revision) is not int or revision < 1:
                return {"ok": False, "error": "invalid_revision"}
            return {"ok": True, "revision": capability.associate_authority_principal(
                principal, resident_id, authority_principal,
                expected_revision=revision)}
        return {"ok": False, "error": "unsupported_operation"}
    except PermissionError:
        return {"ok": False, "error": "forbidden"}
    except (TypeError, ValueError, KeyError):
        return {"ok": False, "error": "invalid_request"}

def serve(capability: HRCapability, principal: VerifiedPrincipal,
          input_stream: TextIO, output_stream: TextIO) -> None:
    """Serve one JSON object per line; no host authentication implemented here."""
    for line in input_stream:
        try:
            request = json.loads(line)
            response = dispatch(capability, principal, request)
        except (json.JSONDecodeError, UnicodeError):
            response = {"ok": False, "error": "invalid_json"}
        output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
        output_stream.flush()
