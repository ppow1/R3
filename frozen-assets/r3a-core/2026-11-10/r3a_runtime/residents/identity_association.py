"""Evidence contract joining established identity authorities without a registry."""

from __future__ import annotations

import re
from typing import Any


_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def validate_identity_association(value: Any) -> dict[str, Any]:
    """Validate a source-grounded association projection for a single resident.

    The projection is audit evidence, not an identity database. It deliberately
    requires the private HR principal association to exactly match the observed
    directory principal; display names and equal-looking IDs are not evidence.
    Credential material is reference-only.
    """
    if (not isinstance(value, dict)
            or value.get("schema_id") != "r3a.resident.identity-association"
            or value.get("schema_version") != 1
            or not _reference(value.get("association_ref"))):
        raise ValueError("unsupported resident identity association")
    hr = value.get("hr")
    dossier = value.get("dossier")
    directory = value.get("directory")
    runtime = value.get("runtime")
    if not all(isinstance(x, dict) for x in (hr, dossier, directory, runtime)):
        raise ValueError("association requires HR, dossier, directory, and runtime evidence")
    resident_id = value.get("resident_id")
    if not isinstance(resident_id, str) or not resident_id.startswith("r3:"):
        raise ValueError("canonical HR resident ID is required")
    if (hr.get("resident_id") != resident_id or type(hr.get("revision")) is not int
            or hr["revision"] < 1 or not _reference(hr.get("source_ref"))):
        raise ValueError("association requires a revisioned authoritative HR source reference")
    if (not _reference(hr.get("principal_association_ref"))
            or not isinstance(hr.get("authority_principal"), str)
            or not hr["authority_principal"].startswith("resident:")):
        raise ValueError("association requires a governed HR principal association")
    if (dossier.get("resident_id") != resident_id
            or not _SEMVER.fullmatch(str(dossier.get("revision", "")))
            or dossier.get("status") != "active"):
        raise ValueError("association requires the active dossier revision for the same HR identity")
    if (directory.get("source_id") != "riverview_authority.directory"
            or directory.get("source_contract") != "riverview-authority.directory.v1"
            or not _SHA256.fullmatch(str(directory.get("snapshot_sha256", "")))
            or not _timestamp(directory.get("observed_at"))
            or not isinstance(directory.get("principal_id"), str)
            or not directory["principal_id"].startswith("resident:")
            or directory.get("principal_id") != hr["authority_principal"]
            or not isinstance(directory.get("office_id"), str) or not directory["office_id"]
            or not isinstance(directory.get("office_role"), str) or not directory["office_role"]
            or type(directory.get("binding_revision")) is not int
            or directory["binding_revision"] < 1):
        raise ValueError("directory snapshot, principal, and office binding evidence do not agree")
    credential_ref = value.get("credential_ref")
    if not _reference(credential_ref) or any(token in credential_ref.casefold()
                                               for token in ("token=", "secret=", "bearer")):
        raise ValueError("credential reference must not contain credential material")
    grant_refs = value.get("grant_refs")
    if (not isinstance(grant_refs, list) or not grant_refs
            or any(not _reference(item) for item in grant_refs)):
        raise ValueError("exact grant references are required")
    if (not all(isinstance(runtime.get(key), str) and runtime[key]
                for key in ("profile_id", "profile_revision", "route_id"))):
        raise ValueError("runtime profile and route references are required")
    refs = value.get("evidence_refs")
    if not isinstance(refs, list) or len(refs) < 4 or any(not _reference(ref) for ref in refs):
        raise ValueError("association evidence references are incomplete")
    if not _timestamp(value.get("verified_at")):
        raise ValueError("association audit reference and timestamp are required")
    return value


def _reference(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value


def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    from datetime import datetime
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False
