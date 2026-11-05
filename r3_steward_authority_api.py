"""R3 Steward Authority HTTP adapter.

All grant mutations go through Grace's canonical R3GrantManagement.
No website-owned grant registry, implicit grants or startup provisioning.
"""

# R3 CONTROLLED SOURCE
# File: r3_steward_authority_api.py
# Component: STEWARD-AUTHORITY-API
# File Revision: 1.1.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Steward-authorized R3 authority and resident credential operations
# Execution Model: FastAPI adapter over canonical R3 authority and local HR data
# Observability: HTTP outcomes; credential secrets are never returned
# Dependencies: FastAPI, R3 authority, classified HR records
# Authority: Steward-only mutations; existing grants remain canonical
# Changed: 2026-11-05 UTC | HR-CREDENTIAL-IDENTITY-001 | Codex | Resolve principals from confidential HR associations
# Supersedes: Git predecessor at d49a4bb35ae9bbfc75f79a3bad7adb8ee9abcac2
# Contracts: HR hr_records payload extensions; canonical R3 authority
# Tests: tests/test_hr_credential_provision.py
# History/Predecessor: Git commit d49a4bb35ae9bbfc75f79a3bad7adb8ee9abcac2

import os
from pathlib import Path


import json
import sqlite3
import time
from datetime import datetime, timezone

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



class ResidentCredentialProvision(BaseModel):
    resident_principal: str = Field(min_length=10, max_length=128)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=200)


RESIDENT_CREDENTIAL_EXPIRY = 2556143999.0
RESIDENT_CREDENTIAL_DIRECTORY = Path(
    "/home/admin1/.local/state/r3-runtime/credentials"
)



HR_RESIDENT_DATABASE = Path(
    "/home/admin1/.local/share/r3/hr/residents.sqlite3"
)

HR_PRINCIPAL_FIELD = "authority_principal"
HR_ASSOCIATION_CLASSIFICATION = "confidential"


def _validate_hr_resident_principal(principal):
    import re

    if not isinstance(principal, str) or not re.fullmatch(
        r"resident:[A-Za-z0-9_.:-]+", principal
    ):
        raise HTTPException(422, "Invalid resident principal")

    if not HR_RESIDENT_DATABASE.is_file():
        raise HTTPException(503, "Canonical HR roster unavailable")

    try:
        with sqlite3.connect(
            "file:" + str(HR_RESIDENT_DATABASE) + "?mode=ro",
            uri=True,
        ) as db:
            rows = db.execute(
                "SELECT resident_id, payload FROM hr_records"
            ).fetchall()
    except sqlite3.Error as exc:
        raise HTTPException(503, "Canonical HR roster unavailable") from exc

    matching_ids = []
    for resident_id, payload in rows:
        try:
            record = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(503, "Canonical HR record is invalid") from exc

        if not isinstance(record, dict) or record.get("resident_id") != resident_id:
            raise HTTPException(503, "Canonical HR record is invalid")

        # Principal links belong in a confidential extension so normal HR
        # views cannot disclose protected resident identities.
        locations = []
        for container_name in ("fields", "extensions"):
            container = record.get(container_name, {})
            if not isinstance(container, dict):
                raise HTTPException(503, "Canonical HR record is invalid")
            if HR_PRINCIPAL_FIELD in container:
                locations.append(container[HR_PRINCIPAL_FIELD])

        if len(locations) > 1:
            raise HTTPException(409, "Conflicting HR principal associations")
        if not locations:
            continue

        association = locations[0]
        if (
            not isinstance(association, dict)
            or association.get("classification") != HR_ASSOCIATION_CLASSIFICATION
        ):
            raise HTTPException(409, "Invalid HR principal association")
        associated_principal = association.get("value")
        if not isinstance(associated_principal, str) or not re.fullmatch(
            r"resident:[A-Za-z0-9_.:-]+", associated_principal
        ):
            raise HTTPException(409, "Invalid HR principal association")
        if associated_principal == principal:
            matching_ids.append(resident_id)

    if len(matching_ids) > 1:
        raise HTTPException(409, "Duplicate HR principal association")
    if not matching_ids:
        raise HTTPException(403, "Resident is not on the HR roster")

    return matching_ids[0]


def _provision_resident_credential(service, request, body):
    import re

    principal = body.resident_principal

    if not re.fullmatch(r"resident:[A-Za-z0-9_.:-]+", principal):
        raise HTTPException(422, "Invalid resident principal")

    hr_resident_id = _validate_hr_resident_principal(principal)

    if principal.lower() == "resident:grace":
        raise HTTPException(409, "Grace credential must be preserved")

    directory = RESIDENT_CREDENTIAL_DIRECTORY

    if not directory.is_dir() or directory.is_symlink():
        raise HTTPException(503, "Protected credential directory unavailable")

    if directory.stat().st_mode & 0o077:
        raise HTTPException(503, "Credential directory permissions too broad")

    if directory.stat().st_uid != os.geteuid():
        raise HTTPException(503, "Credential directory ownership mismatch")

    name = principal.split(":", 1)[1]

    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise HTTPException(422, "Unsupported credential filename")

    path = directory / (name + ".credential")

    if path.exists() or path.is_symlink():
        raise HTTPException(409, "Resident credential file already exists")

    result = _invoke(
        service.issue_resident_credential,
        steward_context=request,
        resident_principal=principal,
        expires_at=RESIDENT_CREDENTIAL_EXPIRY,
        reason=body.reason,
        idempotency_key=body.idempotency_key,
    )

    if result["status"] != "ISSUED":
        raise HTTPException(
            409,
            "Credential already issued; inspect existing credential record"
        )

    credential_id = result["credential_id"]
    credential = result["credential"]

    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        fd = os.open(path, flags, 0o600)

        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(credential + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            raise

        os.chmod(path, 0o600)

        verified = R3ResidentIdentity(service.authority).authenticate(
            credential
        )

        if verified != principal:
            raise RuntimeError("Credential verification mismatch")

        directory_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)

    except BaseException as exc:
        try:
            _invoke(
                service.revoke_resident_credential,
                steward_context=request,
                credential_id=credential_id,
                reason="Provisioning storage or verification failed",
            )
        except BaseException:
            raise HTTPException(
                503,
                "Credential provisioning failed; manual authority reconciliation required"
            ) from exc

        path.unlink(missing_ok=True)

        raise HTTPException(
            503,
            "Credential provisioning failed and issued credential was revoked"
        ) from exc

    return {
        "status": "ISSUED",
        "principal": principal,
        "hr_resident_id": hr_resident_id,
        "credential_id": credential_id,
        "expires_at": RESIDENT_CREDENTIAL_EXPIRY,
        "credential_file": path.name,
        "verified": True,
        "secret_returned": False,
    }


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


    @router.post("/resident-credentials/provision")
    def provision_resident_credential(
        request: Request,
        body: ResidentCredentialProvision,
    ):
        _steward(request, mutation=True)
        service = _service()
        return _provision_resident_credential(service, request, body)

    return router
