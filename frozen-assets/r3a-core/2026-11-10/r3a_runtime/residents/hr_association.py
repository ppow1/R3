"""Authenticated, revision-checked HR principal association adapter.

The adapter writes only through an explicitly provenance-capable operation exposed by
the authoritative HR host. It never writes an association into the dossier database.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Callable

from .governance import GovernedActor
from .r3_authority_adapter import R3CapabilityGrantAdapter


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def validate_association_evidence(evidence: Any, *, authority_principal: str) -> dict[str, Any]:
    required = {"source_id", "source_contract", "snapshot_sha256", "observed_at",
                "principal_id", "office_id", "office_role", "binding_revision",
                "evidence_refs", "verified_at"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise ValueError("association requires a complete, privacy-minimized source evidence record")
    if (evidence["source_id"] != "riverview_authority.directory"
            or evidence["source_contract"] != "riverview-authority.directory.v1"
            or not isinstance(evidence["snapshot_sha256"], str)
            or not _SHA256.fullmatch(evidence["snapshot_sha256"])):
        raise ValueError("authoritative directory source and snapshot digest are required")
    if evidence["principal_id"] != authority_principal or not authority_principal.startswith("resident:"):
        raise ValueError("HR association principal must exactly match the observed canonical directory principal")
    if (not isinstance(evidence["office_id"], str) or not evidence["office_id"]
            or not isinstance(evidence["office_role"], str) or not evidence["office_role"]
            or type(evidence["binding_revision"]) is not int or evidence["binding_revision"] < 1):
        raise ValueError("current authoritative office binding evidence is required")
    for key in ("observed_at", "verified_at"):
        if not isinstance(evidence[key], str):
            raise ValueError("association evidence timestamps are required")
        try:
            if datetime.fromisoformat(evidence[key].replace("Z", "+00:00")).tzinfo is None:
                raise ValueError("association evidence timestamps must include a timezone")
        except ValueError as exc:
            raise ValueError("association evidence timestamp is invalid") from exc
    refs = evidence["evidence_refs"]
    if not isinstance(refs, list) or not refs or any(
            not isinstance(ref, str) or not ref.strip() or "\n" in ref for ref in refs):
        raise ValueError("association evidence references are required")
    return dict(evidence)


class HRPrincipalAssociationAdapter:
    """Call the R3 HR authority's audited provenance-bearing association operation."""

    OPERATION = "associate_authority_principal_with_provenance"

    def __init__(self, hr_capability: Any, grants: R3CapabilityGrantAdapter, *,
                 resolve_directory_evidence: Callable[[GovernedActor, str], dict[str, Any]]):
        if not callable(resolve_directory_evidence):
            raise TypeError("server-side authoritative directory evidence resolver is required")
        self.hr = hr_capability
        self.grants = grants
        self._resolve_evidence = resolve_directory_evidence

    def associate(self, actor: GovernedActor, *, resident_id: str,
                  authority_principal: str, expected_hr_revision: int,
                  evidence_ref: str) -> dict[str, Any]:
        if (not isinstance(actor, GovernedActor) or not actor.principal_id
                or not actor.authentication_ref):
            raise PermissionError("server-authenticated HR actor is required")
        if not isinstance(resident_id, str) or not resident_id.startswith("r3:"):
            raise ValueError("canonical existing HR resident identity is required")
        if type(expected_hr_revision) is not int or expected_hr_revision < 1:
            raise ValueError("revision-checked existing HR record is required")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise ValueError("opaque source evidence reference is required")
        principal = self.grants.verified_principal(actor)
        if not self.grants.authorize_hr(principal, "hr.write", resident_id):
            raise PermissionError("exact scoped HR write capability denied")
        provenance = validate_association_evidence(
            self._resolve_evidence(actor, evidence_ref), authority_principal=authority_principal)
        if evidence_ref not in provenance["evidence_refs"]:
            raise PermissionError("resolved authoritative evidence does not match the requested evidence reference")
        current = self.hr.read(principal, resident_id)
        if not isinstance(current, dict) or current.get("resident_id") != resident_id:
            raise PermissionError("existing authoritative HR record could not be resolved")
        if current.get("revision") != expected_hr_revision:
            raise RuntimeError("HR revision conflict; association must be re-read and re-reviewed")
        operation = getattr(self.hr, self.OPERATION, None)
        if not callable(operation):
            raise NotImplementedError(
                "authoritative HR host lacks associate_authority_principal_with_provenance; "
                "the current association operation cannot persist source evidence"
            )
        result = operation(
            principal=principal,
            resident_id=resident_id,
            authority_principal=authority_principal,
            expected_revision=expected_hr_revision,
            provenance=provenance,
        )
        if (not isinstance(result, dict) or result.get("resident_id") != resident_id
                or result.get("authority_principal") != authority_principal
                or type(result.get("revision")) is not int
                or result["revision"] <= expected_hr_revision
                or result.get("provenance") != provenance):
            raise RuntimeError("HR association operation did not return auditable persisted evidence")
        return result
