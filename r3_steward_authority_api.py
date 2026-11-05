"""R3 Steward Authority HTTP adapter.

All grant mutations go through Grace's canonical R3GrantManagement.
No website-owned grant registry, implicit grants or startup provisioning.
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from r3_native_auth_api import authenticated_identity
from runtime.capability_authority import R3Authority
from runtime.grant_management import R3GrantManagement
from runtime.resident_identity import R3ResidentIdentity
from runtime.capabilities import CapabilityDenied, AuthorityUnavailable


class GrantRequest(BaseModel):
    target_principal: str
    resource_ref: str
    action: str
    operation: str
    scope_ref: str
    reason: str
    idempotency_key: str
    effective_at: float | None = None
    expires_at: float | None = None
    delegable: bool = False


class GrantDecision(BaseModel):
    request_id: str
    approve: bool
    reason: str


class GrantRevocation(BaseModel):
    grant_id: str
    reason: str


class GrantDelegation(BaseModel):
    parent_grant_id: str
    target_principal: str
    expires_at: float | None = None
    reason: str
    idempotency_key: str


def _service():
    database = os.environ.get("R3_CANONICAL_AUTHORITY_DB")

    if not database:
        raise HTTPException(
            503, "Canonical R3 authority database is not configured"
        )

    authority = R3Authority(Path(database).expanduser())

    def verify_steward(context):
        identity = authenticated_identity(context, mutation=False)
        if identity.get("role") != "steward":
            raise CapabilityDenied("Steward authority required")
        return identity["principal"]

    resident_identity = R3ResidentIdentity(authority)

    return R3GrantManagement(
        authority,
        authenticate_steward=verify_steward,
        authenticate_delegator=resident_identity.authenticate,
    )


def _steward(request, mutation=False):
    if mutation:
        from urllib.parse import urlsplit

        origin = request.headers.get("origin")
        host = request.headers.get("host")

        if not origin or not host:
            raise HTTPException(403, "Origin required")

        parsed = urlsplit(origin)
        if (
            parsed.scheme not in ("http", "https")
            or parsed.netloc != host
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise HTTPException(403, "Origin not allowed")

    identity = authenticated_identity(request, mutation=mutation)
    if identity.get("role") != "steward":
        raise HTTPException(403, "Steward authority required")
    return identity


def _invoke(method, **kwargs):
    try:
        return method(**kwargs)
    except CapabilityDenied as exc:
        raise HTTPException(403, str(exc)) from exc
    except AuthorityUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def build_steward_authority_router(root):
    router = APIRouter(prefix="/api/v1/steward-authority")

    @router.get("/capabilities")
    def capabilities(request: Request):
        _steward(request)
        return {
            "component": "Steward Authority",
            "contract": "r3.steward-authority.v1",
            "authority": "R3 canonical capability authority",
            "operations": {
                "inventory": "enabled",
                "pending": "enabled",
                "active": "enabled",
                "history": "enabled",
                "request": "enabled",
                "approve": "enabled",
                "deny": "enabled",
                "revoke": "enabled",
                "delegate": "independent resident bearer credential required",
                "renew": "request and approve replacement grant",
            },
            "mutations_enabled": True,
        }

    @router.get("/inventory")
    def inventory(request: Request):
        _steward(request)
        service = _service()
        return _invoke(
            service.list_grants, steward_context=request
        )

    @router.get("/pending")
    def pending(request: Request):
        _steward(request)
        service = _service()
        return _invoke(
            service.list_requests,
            steward_context=request,
            status="PENDING",
        )

    @router.get("/active")
    def active(request: Request):
        _steward(request)
        service = _service()
        return _invoke(
            service.list_grants,
            steward_context=request,
            active_only=True,
        )

    @router.get("/history")
    def history(request: Request):
        _steward(request)
        service = _service()
        return _invoke(
            service.history, steward_context=request
        )

    @router.post("/request")
    def request_grant(request: Request, body: GrantRequest):
        _steward(request, mutation=True)
        service = _service()
        return _invoke(
            service.request,
            steward_context=request,
            **body.model_dump(),
        )

    @router.post("/decide")
    def decide_grant(request: Request, body: GrantDecision):
        _steward(request, mutation=True)
        service = _service()
        return _invoke(
            service.decide,
            steward_context=request,
            **body.model_dump(),
        )

    @router.post("/revoke")
    def revoke_grant(request: Request, body: GrantRevocation):
        _steward(request, mutation=True)
        service = _service()
        return _invoke(
            service.revoke,
            steward_context=request,
            **body.model_dump(),
        )


    @router.post("/delegate")
    def delegate_grant(request: Request, body: GrantDelegation):
        authorization = request.headers.get("authorization", "")

        if not authorization.startswith("Bearer "):
            raise HTTPException(
                401, "R3 resident credential required"
            )

        credential = authorization[len("Bearer "):]

        if not credential or len(credential) > 200:
            raise HTTPException(
                401, "Invalid resident credential"
            )

        # No Steward browser-session fallback.
        # No caller-supplied principal is trusted.
        service = _service()

        return _invoke(
            service.delegate,
            resident_credential=credential,
            **body.model_dump(),
        )

    return router
