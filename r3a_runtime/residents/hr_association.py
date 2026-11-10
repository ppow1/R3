"""Authenticated, revision-checked HR principal association adapter.

The adapter writes only through an explicitly provenance-capable operation exposed by
the authoritative HR host. It never writes an association into the dossier database.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Callable

from .governance import GovernedActor
from .r3_authority_adapter import R3CapabilityGrantAdapter


_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def validate_association_evidence(evidence: Any, *, resident_id: str,
                                 expected_hr_revision: int,
                                 now: datetime | None = None) -> dict[str, Any]:
    """Validate a server-resolved HR-to-directory edge from a fresh R3A snapshot.

    The resolver, not the caller, supplies the HR key/revision and canonical
    directory principal. Directory discovery alone cannot establish that edge.
    """
    required = {"source_id", "source_contract", "snapshot_sha256", "observed_at",
                "hr_resident_id", "hr_revision", "hr_source_ref", "principal_id",
                "office_id", "office_role", "office_status", "binding_revision",
                "evidence_refs", "verified_at"}
    if not isinstance(evidence, dict) or set(evidence) != required:
        raise ValueError("association requires a complete, privacy-minimized source evidence record")
    if (evidence["source_id"] != "riverview_authority.directory"
            or evidence["source_contract"] != "riverview-authority.directory.v1"
            or not isinstance(evidence["snapshot_sha256"], str)
            or not _SHA256.fullmatch(evidence["snapshot_sha256"])):
        raise ValueError("authoritative directory source and snapshot digest are required")
    if (evidence["hr_resident_id"] != resident_id
            or type(evidence["hr_revision"]) is not int
            or evidence["hr_revision"] != expected_hr_revision
            or not isinstance(evidence["hr_source_ref"], str)
            or not evidence["hr_source_ref"].strip()):
        raise ValueError("directory evidence must bind the exact revisioned HR identity")
    if (not isinstance(evidence["principal_id"], str)
            or not evidence["principal_id"].startswith("resident:")):
        raise ValueError("canonical directory resident principal is required")
    if (not isinstance(evidence["office_id"], str) or not evidence["office_id"]
            or not isinstance(evidence["office_role"], str) or not evidence["office_role"]
            or evidence["office_status"] != "active"
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
    observed_at = datetime.fromisoformat(evidence["observed_at"].replace("Z", "+00:00"))
    current_time = now or datetime.now(timezone.utc)
    age_seconds = (current_time - observed_at.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -30 or age_seconds > 300:
        raise ValueError("directory association evidence is stale")
    refs = evidence["evidence_refs"]
    if not isinstance(refs, list) or not refs or any(
            not isinstance(ref, str) or not ref.strip() or "\n" in ref for ref in refs):
        raise ValueError("association evidence references are required")
    return dict(evidence)


class HRPrincipalAssociationAdapter:
    """Call the R3 HR authority's audited provenance-bearing association operation."""

    OPERATION = "associate_authority_principal_with_provenance"

    def __init__(self, hr_capability: Any, grants: R3CapabilityGrantAdapter, *,
                 resolve_directory_evidence: Callable[[GovernedActor, str, str], dict[str, Any]]):
        if not callable(resolve_directory_evidence):
            raise TypeError("server-side authoritative directory evidence resolver is required")
        self.hr = hr_capability
        self.grants = grants
        self._resolve_evidence = resolve_directory_evidence

    def associate(self, actor: GovernedActor, *, resident_id: str,
                  expected_hr_revision: int, evidence_ref: str,
                  idempotency_key: str, correlation_id: str) -> dict[str, Any]:
        if (not isinstance(actor, GovernedActor) or not actor.principal_id
                or not actor.authentication_ref):
            raise PermissionError("server-authenticated HR actor is required")
        if not isinstance(resident_id, str) or not resident_id.startswith("r3:"):
            raise ValueError("canonical existing HR resident identity is required")
        if type(expected_hr_revision) is not int or expected_hr_revision < 1:
            raise ValueError("revision-checked existing HR record is required")
        if not isinstance(evidence_ref, str) or not evidence_ref.strip():
            raise ValueError("opaque source evidence reference is required")
        if (not isinstance(idempotency_key, str) or not idempotency_key.strip()
                or len(idempotency_key) > 200):
            raise ValueError("stable association idempotency key is required")
        if not isinstance(correlation_id, str) or not correlation_id.strip() or len(correlation_id) > 200:
            raise ValueError("stable association correlation ID is required")
        principal = self.grants.verified_principal(actor)
        if not self.grants.authorize_hr(principal, "hr.write", resident_id,
                                        correlation_id=correlation_id):
            raise PermissionError("exact scoped HR write capability denied")
        current = self.hr.read(principal, resident_id)
        if not isinstance(current, dict) or current.get("resident_id") != resident_id:
            raise PermissionError("existing authoritative HR record could not be resolved")
        if current.get("revision") != expected_hr_revision:
            raise RuntimeError("HR revision conflict; association must be re-read and re-reviewed")
        if current.get("status") != "active":
            raise PermissionError("active HR appointment decision is required before association")
        provenance = validate_association_evidence(
            self._resolve_evidence(actor, resident_id, evidence_ref),
            resident_id=resident_id, expected_hr_revision=expected_hr_revision)
        if evidence_ref not in provenance["evidence_refs"]:
            raise PermissionError("resolved authoritative evidence does not match the requested evidence reference")
        operation = getattr(self.hr, self.OPERATION, None)
        if not callable(operation):
            raise NotImplementedError(
                "authoritative HR host lacks associate_authority_principal_with_provenance; "
                "the current association operation cannot persist source evidence"
            )
        result = operation(
            principal=principal,
            resident_id=resident_id,
            authority_principal=provenance["principal_id"],
            expected_revision=expected_hr_revision,
            provenance=provenance,
            evidence_ref=evidence_ref,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
        )
        if (not isinstance(result, dict) or result.get("resident_id") != resident_id
                or result.get("authority_principal") != provenance["principal_id"]
                or type(result.get("revision")) is not int
                or result["revision"] <= expected_hr_revision
                or result.get("provenance") != provenance
                or result.get("idempotency_key") != idempotency_key
                or result.get("correlation_id") != correlation_id
                or not isinstance(result.get("association_ref"), str)
                or not result["association_ref"].strip()
                or not isinstance(result.get("audit_event_ref"), str)
                or not result["audit_event_ref"].strip()):
            raise RuntimeError("HR association operation did not return auditable persisted evidence")
        return result
