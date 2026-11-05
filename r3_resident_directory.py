# R3 CONTROLLED SOURCE
# File: r3_resident_directory.py
# Component: WEBSITE-HR-RESIDENT-DIRECTORY
# File Revision: 1.1.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Project authorized, current HR residents into the website Chat directory.
# Execution Model: Per-request HRStore read through HRCapability.
# Observability: No HR values or credentials logged; responses are no-store.
# Dependencies: runtime.hr_store; runtime.hr_capability; runtime.hr_records.
# Authority: Authenticated R3 Steward session; HR capability disclosure contract.
# Changed: 2026-11-05 UTC | WEBSITE-MULTIRESIDENT-CHAT | ChatGPT GPT-6 | Replace website roster with authorized HR directory projection.
# Supersedes: 1.0.0 static website roster reader; predecessor blob c8557ec
# Contracts: runtime/hr_capability.py; runtime/hr_records.py; hints/file-provenance.md
# Tests: tests/test_website_hr_directory.py
# History/Predecessor: Git blob c8557ec
"""Authorized dynamic resident directory backed by the canonical HR store."""
from __future__ import annotations

import os
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

HR_DATABASE = Path(os.environ.get(
    "R3_HR_DATABASE", "/home/admin1/.local/share/r3/hr/residents.sqlite3"
))
RUNTIME_CONFIG = Path(os.environ.get(
    "R3_RUNTIME_CONFIG", str(Path(__file__).resolve().parent / "config" / "runtime.json")
))
RUNTIME_IDENTITY_MAP = (
    Path(os.environ["R3_WEBSITE_RESIDENT_RUNTIME_MAP"]).expanduser()
    if os.environ.get("R3_WEBSITE_RESIDENT_RUNTIME_MAP") else None
)


@dataclass(frozen=True)
class AuthorizedStewardSession:
    """Server-created identity token passed from native website authentication."""
    principal_id: str
    role: str = "steward"


def _directory():
    """Return a fresh authorized HR capability and its owned store connection."""
    try:
        from runtime.hr_capability import HRCapability, VerifiedPrincipal
        from runtime.hr_store import HRStore
    except ImportError as exc:
        raise HTTPException(503, "Institutional HR directory dependency is unavailable") from exc
    try:
        store = HRStore(HR_DATABASE)
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Institutional HR directory is unavailable") from exc

    # The caller reaches this only after the website's native session has been
    # authenticated as Steward. This maps that existing authority into the HR
    # capability; it issues no grant and accepts no browser supplied role.
    def authorize(principal, action: str, scope: str) -> bool:
        return (isinstance(principal, VerifiedPrincipal)
                and principal.role == "steward"
                and action == "hr.read"
                and bool(scope))

    return HRCapability(store, authorize), store, VerifiedPrincipal


def load_residents(steward_session: AuthorizedStewardSession,
                   *, legacy_runtime_id: str | None = None) -> list[dict]:
    """Read and project all current HR residents for a verified Steward session."""
    if (not isinstance(steward_session, AuthorizedStewardSession)
            or steward_session.role != "steward"
            or not steward_session.principal_id.strip()):
        raise HTTPException(401, "Steward access required")
    capability, store, principal_type = _directory()
    rows = []
    try:
        records = capability.directory(principal_type(steward_session.principal_id, "steward"))
        for record in records:
            status = record["status"]
            if status.casefold() in {"deactivated", "inactive", "terminated"}:
                continue
            fields = record.get("fields", {})
            personnel_classification = fields.get("personnel_classification")
            protected = personnel_classification == "protected"
            authority_principal = None
            try:
                authority_principal = capability.resolve_authority_principal(
                    principal_type(steward_session.principal_id, "steward"),
                    record["resident_id"],
                )
            except ValueError:
                # Missing, duplicate, or invalid associations leave Chat unavailable.
                pass
            try:
                runtime_id = runtime_resident_id(
                    record["resident_id"], authority_principal,
                    legacy_runtime_id=legacy_runtime_id,
                )
            except HTTPException as exc:
                if exc.status_code == 404:
                    runtime_id = None
                else:
                    raise
            rows.append({
                "id": record["resident_id"],
                "name": record["display_name"],
                "position": fields.get("role", record["office"]),
                "department": record["office"],
                "status": status,
                "protected": protected,
                "revision": record["revision"],
                # A configured runtime is still probed by its capabilities endpoint.
                "availability": "unknown" if runtime_id else "unavailable",
                # Private adapter-only value; the API directory route strips it.
                "_runtime_id": runtime_id,
            })
        return rows
    except PermissionError as exc:
        raise HTTPException(403, "Steward access required") from exc
    except (KeyError, TypeError, ValueError, AttributeError, sqlite3.Error) as exc:
        raise HTTPException(503, "Institutional HR directory response is invalid") from exc
    finally:
        store.close()


def require_resident(resident_id: str, steward_session: AuthorizedStewardSession,
                     *, legacy_runtime_id: str | None = None) -> dict:
    for resident in load_residents(steward_session, legacy_runtime_id=legacy_runtime_id):
        if resident["id"] == resident_id:
            return resident
    raise HTTPException(404, "Resident unavailable")


def runtime_resident_id(resident_id: str, authority_principal: str | None = None,
                        *, legacy_runtime_id: str | None = None,
                        identity_map: dict[str, str] | None = None) -> str:
    """Resolve an explicit HR-principal binding to a configured runtime key."""
    try:
        runtime = json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
        configured = runtime["residents"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Resident runtime registry is unavailable") from exc
    if not isinstance(configured, dict):
        raise HTTPException(503, "Resident runtime registry is invalid")
    namespace, separator, _local_id = resident_id.partition(":")
    if not separator or namespace != "r3":
        raise HTTPException(404, "Resident conversation runtime unavailable")
    legacy_candidate = legacy_runtime_id.casefold() if legacy_runtime_id else None
    if legacy_candidate and legacy_candidate.startswith("r3:"):
        legacy_candidate = legacy_candidate[3:]
    if legacy_candidate and resident_id == "r3:" + legacy_candidate:
        candidate = legacy_candidate
    else:
        if identity_map is None:
            identity_map = _load_runtime_identity_map()
        if not isinstance(authority_principal, str) or not isinstance(identity_map, dict):
            raise HTTPException(404, "Resident conversation runtime unavailable")
        candidate = identity_map.get(authority_principal)
        if not isinstance(candidate, str):
            raise HTTPException(404, "Resident conversation runtime unavailable")
    if candidate not in configured:
        raise HTTPException(404, "Resident conversation runtime unavailable")
    return candidate


def _load_runtime_identity_map() -> dict[str, str]:
    """Load private exact principal-to-runtime bindings; absence fails closed."""
    if RUNTIME_IDENTITY_MAP is None or not RUNTIME_IDENTITY_MAP.exists():
        return {}
    try:
        raw = json.loads(RUNTIME_IDENTITY_MAP.read_text(encoding="utf-8"))
        mapping = raw["authority_principals"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Resident runtime identity map is invalid") from exc
    if (not isinstance(mapping, dict)
            or any(not isinstance(principal, str) or not isinstance(runtime_id, str)
                   for principal, runtime_id in mapping.items())):
        raise HTTPException(503, "Resident runtime identity map is invalid")
    return mapping
