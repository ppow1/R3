"""Bridge the character workflow to the existing governed HR capability."""

from __future__ import annotations

from typing import Any, Callable

from .governance import GovernedActor


class HRCapabilityIdentityResolver:
    """Resolve canonical identities through an existing ``HRCapability``.

    ``resolve_verified_principal`` must translate the authenticated workflow
    actor into the server-created VerifiedPrincipal accepted by HRCapability.
    It must not trust a principal, role, or grant supplied in request data.
    """

    def __init__(self, hr_capability: Any, *,
                 resolve_verified_principal: Callable[[GovernedActor], Any]):
        if not callable(getattr(hr_capability, "read", None)):
            raise TypeError("existing HRCapability with read operation is required")
        if not callable(resolve_verified_principal):
            raise TypeError("trusted actor-to-HR-principal resolver is required")
        self._hr = hr_capability
        self._resolve_principal = resolve_verified_principal

    def __call__(self, actor: GovernedActor, resident_id: str) -> dict[str, Any]:
        if not isinstance(actor, GovernedActor) or not actor.principal_id or not actor.authentication_ref:
            raise PermissionError("authenticated institutional actor required")
        principal = self._resolve_principal(actor)
        if not getattr(principal, "principal_id", None) or not getattr(principal, "role", None):
            raise PermissionError("HR adapter requires a server-verified principal")
        record = self._hr.read(principal, resident_id)
        if record is None:
            return {"institutional_id": resident_id, "status": "missing",
                    "classification": "RESIDENT", "revision": None}
        if (record.get("resident_id") != resident_id
                or type(record.get("revision")) is not int
                or record["revision"] < 1):
            raise PermissionError("HR identity projection is invalid")
        return {"institutional_id": resident_id, "status": "authoritative",
                "classification": "RESIDENT", "revision": record["revision"],
                "source_ref": f"hr://record/{resident_id}@{record['revision']}"}
