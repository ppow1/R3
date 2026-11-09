"""
R3 CONTROLLED SOURCE
File: r3a_runtime/steward_access.py
Component: R3A-AP3-STEWARD-ACCESS
File Revision: 1.2.0
Created: 2026-11-07T21:37:42Z
Created By: Codex GPT-6
Purpose: Verify Steward identity through a replaceable institutional adapter, manage revocable durable sessions, and audit portal operations.
Execution Model: FastAPI router over a PostgreSQL session/audit store and the existing CME control socket.
Observability: Versioned structured audit events with request correlation and session provenance; secret values are excluded.
Dependencies: FastAPI, psycopg, r3a_runtime.control; existing R3 account portal or trusted ingress; CME; Bitwarden provider for HMAC ingress binding.
Authority: AP3-M1 / R3A-010, R3A-013; Issue #49; Roadmap Baseline 1.0; no exception.
Changed: 2026-11-07T21:37:42Z | AP3-M1 | Codex GPT-6 | Implement ingress-asserted identity, PostgreSQL sessions, CME authorization delegation, and freshness-aware endpoints.
Changed: 2026-11-07T21:44:36Z | AP3-M1 | Codex GPT-6 | Preserve authentication factor provenance and mount the touch-friendly Steward access interface.
Changed: 2026-11-07T21:48:11Z | AP3-M1 | Codex GPT-6 | Read live CME health through the private socket and audit freshness-aware status.
Changed: 2026-11-07T21:53:47Z | AP3-M1 | Codex GPT-6 | Consume the published Issue #50 Bitwarden lease contract without an environment-secret fallback.
Changed: 2026-11-07T21:56:49Z | AP3-M1 | Codex GPT-6 | Tighten external config scalar validation and ensure boolean values cannot masquerade as thresholds.
Changed: 2026-11-07T22:02:18Z | AP3-M1 | Codex GPT-6 | Audit invalid-origin and invalid-session attempts; make connection timeout configurable.
Changed: 2026-11-07T22:03:19Z | AP3-M1 | Codex GPT-6 | Require Secure cookies when remote transport is configured.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Bind replaceable versioned identity providers and publish authoritative session principal projections.
Changed: 2026-11-07T23:43:25Z | AP3-M1 | Codex GPT-6 | Validate normalized identity-provider results before shared session issuance.
Changed: 2026-11-07T23:53:17Z | AP3-M1/AP3-M2 | Codex GPT-6 | Align Bitwarden 1.1.0 reference, preserve finite provider reason codes, and persist provider/machine-principal contract provenance.
Changed: 2026-11-07T23:53:17Z | AP3-M1/#51 | Codex GPT-6 | Expose a shared FastAPI principal dependency for Website routes on the same session authority.
Changed: 2026-11-07T23:57:23Z | AP3-M1/#51 | Codex GPT-6 | Return unavailable explicitly from Website dependencies when session storage cannot be read.
Changed: 2026-11-08T00:01:13Z | AP3-M1/#51 | Codex GPT-6 | Share the session cookie across /api/v1, require Origin on Website mutations, and expose generic CME discovery.
Changed: 2026-11-08T13:45:00Z | AP3-M1/#51 | Codex GPT-6 | Bind the existing R3 account-session authority through the versioned identity-provider contract.
Supersedes: None.
Contracts: r3a.identity-provider.v1; r3a.steward-principal.v1; r3a.steward-session.v1; r3a.capability-invocation.v1; r3a.secrets.provider.v1; r3a.machine-principal.v1.
Tests: tests/test_r3a_steward_access.py; tests/test_r3a_capability_contracts.py.
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger("r3a.steward_access")
IDENTITY_CONTRACT = "r3a.steward-identity.v1"
IDENTITY_PROVIDER_CONTRACT = "r3a.identity-provider.v1"
PRINCIPAL_CONTRACT = "r3a.steward-principal.v1"
SESSION_CONTRACT = "r3a.steward-session.v1"


class AccessUnavailable(RuntimeError):
    """The configured identity, session, or CME dependency is unavailable."""

    def __init__(self, code: str, *, outcome: str = "UNAVAILABLE", reason_code: str | None = None):
        self.code = code
        self.outcome = (outcome if isinstance(outcome, str)
                        and outcome in {"UNAVAILABLE", "DENIED", "NOT_FOUND", "FAILED"}
                        else "UNAVAILABLE")
        self.reason_code = reason_code if isinstance(reason_code, str) else None
        super().__init__(code)


SECRET_PROVIDER_REASON_CODES = frozenset({
    "provider_unavailable", "credentials_unavailable", "cli_unavailable", "request_timeout",
    "provider_start_failed", "access_denied", "reference_not_found", "provider_failure",
    "invalid_reference", "invalid_request", "response_invalid", "response_mismatch",
})
SECRET_PROVIDER_DEFAULT_REASON = {
    "UNAVAILABLE": "provider_unavailable", "DENIED": "access_denied",
    "NOT_FOUND": "reference_not_found", "FAILED": "provider_failure",
}


class SessionStore(Protocol):
    def create(self, *, token_digest: str, principal_id: str, issuer: str,
               authenticated_at: datetime, factor_refs: list[str], expires_at: datetime,
               assertion_id: str, correlation_id: str, secret_provenance: dict[str, Any]) -> None: ...
    def read(self, token_digest: str) -> dict[str, Any] | None: ...
    def revoke(self, token_digest: str, *, correlation_id: str) -> bool: ...
    def audit(self, *, event_type: str, principal_id: str | None, outcome: str,
              correlation_id: str, details: dict[str, Any]) -> str: ...


class SecretProvider(Protocol):
    provider_id: str
    provider_version: str
    def resolve(self, reference: Any, *, correlation_id: str) -> Any: ...


class IdentityProvider(Protocol):
    """Replaceable trusted adapter; it returns normalized authority, never a session or grant."""
    contract_id: str
    contract_version: str

    def authenticate(self, request: Request, *, correlation_id: str) -> "IdentityAssertion": ...


class PostgresSessionStore:
    """Persist only token digests and identity metadata; audit through AP0's event ledger."""
    def __init__(self, dsn: str, connect_timeout_seconds: float):
        if not dsn:
            raise AccessUnavailable("session_store_unavailable")
        self._dsn, self._connect_timeout_seconds = dsn, connect_timeout_seconds

    def health(self) -> str:
        try:
            with self._connect() as conn:
                conn.execute("SELECT token_digest FROM r3a.steward_sessions LIMIT 0").fetchone()
            return "ready"
        except Exception as exc:
            raise AccessUnavailable("session_store_unavailable") from exc

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self._dsn, connect_timeout=self._connect_timeout_seconds,
                                   row_factory=dict_row)
        except Exception as exc:
            raise AccessUnavailable("session_store_unavailable") from exc

    def create(self, *, token_digest: str, principal_id: str, issuer: str,
               authenticated_at: datetime, factor_refs: list[str], expires_at: datetime,
               assertion_id: str, correlation_id: str,
               secret_provenance: dict[str, Any]) -> None:
        event_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        try:
            with self._connect() as conn, conn.transaction():
                conn.execute(
                    "INSERT INTO r3a.steward_sessions "
                    "(token_digest,principal_id,issuer,assertion_id,authenticated_at,factor_refs,issued_at,expires_at,correlation_id) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (token_digest, principal_id, issuer, assertion_id, authenticated_at,
                     json.dumps(factor_refs), now, expires_at, correlation_id))
                conn.execute(
                    "INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,"
                    "occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence) "
                    "VALUES (%s,'steward.session.created',1,'steward_session',%s,%s,%s,%s,%s,'accepted','ap3-m1',%s)",
                    (event_id, token_digest[:24], now, f"principal:{principal_id}", correlation_id,
                     "authenticated ingress assertion accepted", json.dumps({"contract": SESSION_CONTRACT,
                     "issuer": issuer, "authenticated_at": authenticated_at.isoformat(),
                     "factor_refs": factor_refs, "secret_provider": secret_provenance,
                     "expires_at": expires_at.isoformat()})))
        except Exception as exc:
            if "UniqueViolation" in type(exc).__name__:
                raise PermissionError("identity_assertion_replayed") from exc
            raise AccessUnavailable("session_store_unavailable") from exc

    def read(self, token_digest: str) -> dict[str, Any] | None:
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT principal_id,issuer,authenticated_at,factor_refs,issued_at,expires_at,revoked_at,correlation_id "
                    "FROM r3a.steward_sessions WHERE token_digest=%s", (token_digest,)).fetchone()
            return dict(row) if row else None
        except Exception as exc:
            raise AccessUnavailable("session_store_unavailable") from exc

    def revoke(self, token_digest: str, *, correlation_id: str) -> bool:
        event_id, now = uuid.uuid4(), datetime.now(timezone.utc)
        try:
            with self._connect() as conn, conn.transaction():
                row = conn.execute(
                    "UPDATE r3a.steward_sessions SET revoked_at=%s WHERE token_digest=%s "
                    "AND revoked_at IS NULL RETURNING principal_id", (now, token_digest)).fetchone()
                if row:
                    conn.execute(
                        "INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,"
                        "occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence) "
                        "VALUES (%s,'steward.session.revoked',1,'steward_session',%s,%s,%s,%s,%s,'accepted','ap3-m1',%s)",
                        (event_id, token_digest[:24], now, f"principal:{row['principal_id']}", correlation_id,
                         "Steward session revoked", json.dumps({"contract": SESSION_CONTRACT})))
            return bool(row)
        except Exception as exc:
            raise AccessUnavailable("session_store_unavailable") from exc

    def audit(self, *, event_type: str, principal_id: str | None, outcome: str,
              correlation_id: str, details: dict[str, Any]) -> str:
        event_id, now = uuid.uuid4(), datetime.now(timezone.utc)
        try:
            with self._connect() as conn, conn.transaction():
                conn.execute(
                    "INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,"
                    "occurred_at,actor,correlation_id,reason,outcome,implementation_revision,evidence) "
                    "VALUES (%s,%s,1,'steward_operation',%s,%s,%s,%s,%s,%s,'ap3-m1',%s)",
                    (event_id, event_type, principal_id or "unknown", now,
                     f"principal:{principal_id}" if principal_id else "principal:unknown", correlation_id,
                     event_type.replace(".", " "), outcome,
                     json.dumps({"contract": IDENTITY_CONTRACT, **details}, sort_keys=True)))
            return str(event_id)
        except Exception as exc:
            raise AccessUnavailable("audit_store_unavailable") from exc


@dataclass(frozen=True)
class IdentityAssertion:
    issuer: str
    principal_id: str
    assertion_id: str
    issued_at: int
    authenticated_at: datetime
    factor_refs: tuple[str, ...]
    secret_provenance: dict[str, Any]


class HmacIngressIdentityProvider:
    """Default adapter for an ingress-signed assertion; session handling stays in StewardAccess."""
    contract_id = IDENTITY_PROVIDER_CONTRACT
    contract_version = "1.0.0"

    def __init__(self, config: dict[str, Any], secret_provider: SecretProvider, secret_reference: Any):
        self.config = config
        self.secret_provider = secret_provider
        self.secret_reference = secret_reference

    def authenticate(self, request: Request, *, correlation_id: str) -> IdentityAssertion:
        issuer = request.headers.get("x-r3-identity-issuer", "")
        principal = request.headers.get("x-r3-identity-subject", "")
        assertion_id = request.headers.get("x-r3-identity-id", "")
        timestamp_text = request.headers.get("x-r3-identity-time", "")
        authenticated_at_text = request.headers.get("x-r3-identity-authenticated-at", "")
        factor_text = request.headers.get("x-r3-identity-factors", "")
        signature = request.headers.get("x-r3-identity-signature", "")
        try:
            issued_at = int(timestamp_text)
            authenticated_at = datetime.fromisoformat(authenticated_at_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PermissionError("invalid_identity_assertion") from exc
        factors = tuple(item for item in factor_text.split(",") if item)
        identity = self.config["identity"]
        if not issuer or issuer != identity["issuer"] or principal != identity["steward_principal_id"]:
            raise PermissionError("identity_not_authorized")
        if (not assertion_id or any(ord(char) < 33 or ord(char) == 127 for char in assertion_id)
                or abs(time.time() - issued_at) > identity["assertion_max_age_seconds"]):
            raise PermissionError("identity_assertion_expired_or_invalid")
        if authenticated_at.tzinfo is None or authenticated_at > datetime.now(timezone.utc):
            raise PermissionError("identity_authentication_time_invalid")
        lease = None
        try:
            lease = self.secret_provider.resolve(self.secret_reference, correlation_id=correlation_id)
            key = lease.reveal()
            machine = lease.machine_principal
            secret_provenance = {"contract_id": "r3a.secrets.provider.v1",
                                 "contract_version": "1.1.0",
                                 "provider_id": lease.provider_id,
                                 "provider_version": lease.provider_version,
                                 "secret_id": lease.secret_id,
                                 "remote_revision": lease.remote_revision,
                                 "fetched_at": lease.fetched_at,
                                 "machine_principal": {
                                     "contract_id": machine.contract_id,
                                     "contract_version": machine.contract_version,
                                     "principal_id": machine.principal_id,
                                     "issuer": machine.issuer,
                                     "authenticated_at": machine.authenticated_at,
                                     "correlation_id": machine.correlation_id}}
        except Exception as exc:
            outcome = getattr(exc, "outcome", "UNAVAILABLE")
            if not isinstance(outcome, str) or outcome not in SECRET_PROVIDER_DEFAULT_REASON:
                outcome = "UNAVAILABLE"
            supplied_reason = getattr(exc, "reason_code", None)
            reason_code = (supplied_reason if isinstance(supplied_reason, str)
                           and supplied_reason in SECRET_PROVIDER_REASON_CODES
                           else SECRET_PROVIDER_DEFAULT_REASON[outcome])
            raise AccessUnavailable("identity_secret_unavailable", outcome=outcome,
                                    reason_code=reason_code) from None
        finally:
            if lease is not None:
                lease.close()
        message = "\n".join((issuer, principal, assertion_id, timestamp_text,
                               authenticated_at_text, factor_text)).encode()
        expected = hmac.new(key.encode(), message, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature):
            raise PermissionError("identity_assertion_invalid")
        return IdentityAssertion(issuer, principal, assertion_id, issued_at,
                                authenticated_at.astimezone(timezone.utc), factors, secret_provenance)


class R3AccountSessionIdentityProvider:
    """Bind the established R3 account portal session to the shared AP3 session store."""
    contract_id = IDENTITY_PROVIDER_CONTRACT
    contract_version = "1.0.0"
    portal_cookie_name = "rv_account_session"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def authenticate(self, request: Request, *, correlation_id: str) -> IdentityAssertion:
        portal_cookie = request.cookies.get(self.portal_cookie_name, "")
        if not portal_cookie or len(portal_cookie) > 4096:
            raise PermissionError("identity_not_authenticated")
        identity_config = self.config["identity"]
        headers = {"Accept": "application/json", "Cookie": f"{self.portal_cookie_name}={portal_cookie}",
                   "X-Correlation-ID": correlation_id}
        req = urllib.request.Request(identity_config["session_url"], headers=headers, method="GET")
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                return None
        try:
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(req, timeout=identity_config.get("request_timeout_seconds", 5)) as response:
                status, body = response.status, response.read(65537)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise PermissionError("identity_not_authenticated") from None
            raise AccessUnavailable("identity_provider_unavailable") from None
        except (OSError, TimeoutError, urllib.error.URLError):
            raise AccessUnavailable("identity_provider_unavailable") from None
        if status in {401, 403}:
            raise PermissionError("identity_not_authenticated")
        if status != 200:
            raise AccessUnavailable("identity_provider_unavailable")
        if len(body) > 65536:
            raise AccessUnavailable("identity_provider_response_invalid")
        try:
            session = json.loads(body)
        except (TypeError, ValueError):
            raise AccessUnavailable("identity_provider_response_invalid") from None
        identity = session.get("identity") if isinstance(session, dict) else None
        if (not isinstance(session, dict) or session.get("authenticated") is not True
                or not isinstance(identity, dict)):
            raise PermissionError("identity_not_authenticated")
        email = identity.get("email")
        roles = identity.get("roles", session.get("roles", []))
        if (not isinstance(email, str) or "@" not in email or not isinstance(roles, list)
                or identity_config["required_role"] not in roles):
            raise PermissionError("identity_not_authorized")
        authenticated_at = datetime.now(timezone.utc)
        timestamp = identity.get("authenticated_at", session.get("authenticated_at"))
        if timestamp is not None:
            try:
                authenticated_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            except ValueError:
                raise AccessUnavailable("identity_provider_response_invalid") from None
            if authenticated_at.tzinfo is None or authenticated_at > datetime.now(timezone.utc):
                raise AccessUnavailable("identity_provider_response_invalid")
            authenticated_at = authenticated_at.astimezone(timezone.utc)
        factors = identity.get("factor_refs", session.get("factor_refs", []))
        if (not isinstance(factors, list)
                or any(not isinstance(item, str) or not item or len(item) > 128 for item in factors)):
            raise AccessUnavailable("identity_provider_response_invalid")
        return IdentityAssertion(
            identity_config["issuer"], email.strip().lower(), str(uuid.uuid4()), int(time.time()),
            authenticated_at, tuple(factors),
            {"identity_provider_id": "r3.account-session",
             "identity_provider_contract_id": self.contract_id,
             "identity_provider_contract_version": self.contract_version,
             "identity_source_issuer": identity_config["issuer"]})


class StewardAccess:
    def __init__(self, config: dict[str, Any], store: SessionStore,
                 identity_provider: IdentityProvider):
        self.config, self.store = config, store
        if (identity_provider.contract_id != IDENTITY_PROVIDER_CONTRACT
                or identity_provider.contract_version.split(".", 1)[0] != "1"):
            raise AccessUnavailable("identity_provider_contract_unsupported")
        self.identity_provider = identity_provider

    @staticmethod
    async def _store_call(method, *args, **kwargs):
        return await run_in_threadpool(method, *args, **kwargs)

    async def _audit(self, **event):
        try:
            return await self._store_call(self.store.audit, **event)
        except AccessUnavailable as exc:
            logger.error("steward_audit_unavailable", extra={
                "correlation_id": event.get("correlation_id"),
                "event_type": event.get("event_type"),
                "reason_code": exc.reason_code or exc.code,
            })
            raise HTTPException(503, "Steward audit state unavailable") from exc

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _correlation(self, request: Request) -> str:
        supplied = request.headers.get("x-correlation-id", "")
        try:
            return str(uuid.UUID(supplied)) if supplied else str(uuid.uuid4())
        except ValueError:
            return str(uuid.uuid4())

    async def _session(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise PermissionError("session_required")
        token_digest = self._digest(token)
        record = await self._store_call(self.store.read, token_digest)
        if not record or record.get("revoked_at") or record["expires_at"] <= datetime.now(timezone.utc):
            raise PermissionError("session_invalid_or_expired")
        account_check = getattr(self.identity_provider, "principal_active", None)
        if account_check is not None and not await self._store_call(account_check, record["principal_id"]):
            await self._store_call(self.store.revoke, token_digest,
                                   correlation_id=str(uuid.uuid4()))
            raise PermissionError("identity_account_inactive")
        return record

    async def authenticated_principal(self, request: Request,
                                     action: str = "session.protected_read") -> dict[str, Any]:
        """FastAPI dependency for same-origin website adapters sharing this session authority."""
        correlation = self._correlation(request)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            await self._require_origin(request, request.headers.get("origin"), action)
        try:
            record = await self._session(request.cookies.get(self.config["session"]["cookie_name"]))
        except PermissionError as exc:
            try:
                await self._audit(event_type="steward.website.access_denied", principal_id=None,
                    outcome="denied", correlation_id=correlation,
                    details={"route": request.scope.get("route").path
                             if request.scope.get("route") else "unknown",
                             "reason": str(exc)})
            except AccessUnavailable as audit_exc:
                raise HTTPException(503, "Steward audit state unavailable") from audit_exc
            raise HTTPException(401, "Steward session unavailable") from exc
        except AccessUnavailable as exc:
            raise HTTPException(503, "Steward session state unavailable") from exc
        return {"contract": PRINCIPAL_CONTRACT, "principal_id": record["principal_id"],
                "issuer": record["issuer"], "authenticated_at": record["authenticated_at"].isoformat(),
                "factor_refs": list(record["factor_refs"])}

    @staticmethod
    def _validate_provider_assertion(assertion: Any) -> IdentityAssertion:
        if (not isinstance(assertion, IdentityAssertion)
                or not isinstance(assertion.issuer, str) or not assertion.issuer
                or not isinstance(assertion.principal_id, str) or not assertion.principal_id
                or not isinstance(assertion.assertion_id, str) or not assertion.assertion_id
                or not isinstance(assertion.authenticated_at, datetime)
                or assertion.authenticated_at.tzinfo is None
                or assertion.authenticated_at > datetime.now(timezone.utc)
                or not isinstance(assertion.factor_refs, tuple)
                or any(not isinstance(factor, str) or not factor for factor in assertion.factor_refs)
                or not isinstance(assertion.secret_provenance, dict)):
            raise AccessUnavailable("identity_provider_contract_result_invalid")
        return assertion

    async def _require_origin(self, request: Request, origin: str | None, action: str) -> None:
        try:
            self._verify_origin(origin)
        except HTTPException:
            correlation = self._correlation(request)
            try:
                await self._audit(event_type="steward.request.denied", principal_id=None,
                    outcome="denied", correlation_id=correlation,
                    details={"action": action, "reason": "origin_not_allowed"})
            except AccessUnavailable as exc:
                raise HTTPException(503, "Steward audit state unavailable") from exc
            raise

    def router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1/steward", tags=["steward-access"])

        @router.post("/session")
        async def start_session(request: Request, response: Response,
                                origin: str | None = Header(default=None)):
            correlation = self._correlation(request)
            response.headers["Cache-Control"] = "no-store"
            try:
                await self._require_origin(request, origin, "session.create")
                if getattr(self.identity_provider, "requires_credentials", False):
                    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if content_type != "application/json":
                        raise PermissionError("invalid_credentials")
                    raw = bytearray()
                    async for chunk in request.stream():
                        raw.extend(chunk)
                        if len(raw) > 8192:
                            raise PermissionError("invalid_credentials")
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        raise PermissionError("invalid_credentials") from None
                    allowed = {"intent", "login_name", "password", "challenge"}
                    if not isinstance(payload, dict) or set(payload) - allowed:
                        raise PermissionError("invalid_credentials")
                    request.state.r3a_identity_payload = payload
                assertion = await self._store_call(self.identity_provider.authenticate,
                                                   request, correlation_id=correlation)
                assertion = self._validate_provider_assertion(assertion)
                token = secrets.token_urlsafe(32)
                expires = datetime.now(timezone.utc) + timedelta(seconds=self.config["session"]["lifetime_seconds"])
                await self._store_call(self.store.create, token_digest=self._digest(token),
                                       principal_id=assertion.principal_id, issuer=assertion.issuer,
                                       authenticated_at=assertion.authenticated_at,
                                       factor_refs=list(assertion.factor_refs), expires_at=expires,
                                       assertion_id=assertion.assertion_id, correlation_id=correlation,
                                       secret_provenance=assertion.secret_provenance)
                response.set_cookie(self.config["session"]["cookie_name"], token,
                                    max_age=self.config["session"]["lifetime_seconds"],
                                    httponly=True, secure=self.config["session"]["secure_cookie"],
                                    samesite="strict", path="/api/v1")
                logger.info("steward_session_created", extra={"correlation_id": correlation,
                            "principal_id": assertion.principal_id, "contract": SESSION_CONTRACT})
                return {"contract": SESSION_CONTRACT, "state": "authenticated",
                        "principal": {"contract": PRINCIPAL_CONTRACT,
                                      "principal_id": assertion.principal_id,
                                      "issuer": assertion.issuer,
                                      "authenticated_at": assertion.authenticated_at.isoformat(),
                                      "factor_refs": list(assertion.factor_refs)},
                        "principal_id": assertion.principal_id,
                        "authenticated_at": assertion.authenticated_at.isoformat(),
                        "factor_refs": list(assertion.factor_refs),
                        "expires_at": expires.isoformat(), "freshness": "current",
                        "correlation_id": correlation}
            except PermissionError as exc:
                try:
                    await self._audit(event_type="steward.authentication.denied",
                                       principal_id=None, outcome="denied", correlation_id=correlation,
                                       details={"reason": str(exc)})
                except HTTPException:
                    return JSONResponse(status_code=503, content={"detail": "Steward audit state unavailable"},
                                        headers={"Cache-Control": "no-store"})
                return JSONResponse(status_code=401, content={"detail": "Steward authentication denied"},
                                    headers={"Cache-Control": "no-store"})
            except AccessUnavailable as exc:
                try:
                    await self._audit(event_type="steward.authentication.unavailable",
                        principal_id=None, outcome="unavailable", correlation_id=correlation,
                        details={"reason_code": exc.reason_code or exc.code,
                                 "provider_outcome": exc.outcome})
                except HTTPException:
                    return JSONResponse(status_code=503, content={"detail": "Steward audit state unavailable"},
                                        headers={"Cache-Control": "no-store"})
                return JSONResponse(status_code=503, content={"detail": "Steward authentication unavailable"},
                                    headers={"Cache-Control": "no-store"})
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                                    headers={"Cache-Control": "no-store"})

        @router.get("/session")
        async def session_status(request: Request, response: Response):
            response.headers["Cache-Control"] = "no-store"
            correlation = self._correlation(request)
            try:
                record = await self._session(request.cookies.get(self.config["session"]["cookie_name"]))
                return {"contract": SESSION_CONTRACT, "state": "authenticated",
                        "principal": {"contract": PRINCIPAL_CONTRACT,
                                      "principal_id": record["principal_id"],
                                      "issuer": record["issuer"],
                                      "authenticated_at": record["authenticated_at"].isoformat(),
                                      "factor_refs": record["factor_refs"]},
                        "principal_id": record["principal_id"],
                        "authenticated_at": record["authenticated_at"].isoformat(),
                        "factor_refs": record["factor_refs"],
                        "expires_at": record["expires_at"].isoformat(), "freshness": "current",
                        "correlation_id": correlation}
            except PermissionError as exc:
                await self._audit(event_type="steward.session.access_denied",
                                       principal_id=None, outcome="denied", correlation_id=correlation,
                                       details={"action": "session.read", "reason": str(exc)})
                raise HTTPException(401, "Steward session unavailable") from exc
            except AccessUnavailable as exc:
                raise HTTPException(503, "Session state unavailable") from exc

        @router.delete("/session")
        async def end_session(request: Request, response: Response,
                              origin: str | None = Header(default=None)):
            response.headers["Cache-Control"] = "no-store"
            correlation = self._correlation(request)
            await self._require_origin(request, origin, "session.revoke")
            try:
                token = request.cookies.get(self.config["session"]["cookie_name"])
                record = await self._session(token)
                revoked = await self._store_call(self.store.revoke, self._digest(token), correlation_id=correlation)
                response.delete_cookie(self.config["session"]["cookie_name"], path="/api/v1",
                                       secure=self.config["session"]["secure_cookie"], httponly=True,
                                       samesite="strict")
                return {"contract": SESSION_CONTRACT, "state": "revoked", "revoked": revoked,
                        "principal_id": record["principal_id"],
                        "correlation_id": correlation}
            except PermissionError as exc:
                await self._audit(event_type="steward.session.revocation_denied",
                                       principal_id=None, outcome="denied", correlation_id=correlation,
                                       details={"action": "session.revoke", "reason": str(exc)})
                raise HTTPException(401, "Steward session unavailable") from exc
            except AccessUnavailable as exc:
                raise HTTPException(503, "Session state unavailable") from exc

        @router.get("/capabilities")
        async def discover_capabilities(request: Request):
            """Expose generic read-only operation discovery; discovery never grants invocation."""
            correlation = self._correlation(request)
            try:
                identity = await self._session(
                    request.cookies.get(self.config["session"]["cookie_name"]))
                from .control import control_request
                result = await control_request(
                    self.config["cme"]["control_socket"], "capability.discover", {},
                    timeout=self.config["cme"]["request_timeout_seconds"])
                operations = result.get("operations", []) if isinstance(result, dict) else []
                audit_id = await self._audit(event_type="steward.capability_discovery",
                    principal_id=identity["principal_id"], outcome="accepted",
                    correlation_id=correlation,
                    details={"operation_count": len(operations) if isinstance(operations, list) else None})
                return {"contract": "r3a.steward-capability-discovery.v1",
                        "operations": operations if isinstance(operations, list) else [],
                        "authorization_evaluated": False,
                        "effect": "none; discovery does not authorize invocation",
                        "audit_event_id": audit_id, "correlation_id": correlation,
                        "freshness": "current", "observed_at": datetime.now(timezone.utc).isoformat()}
            except PermissionError as exc:
                await self._audit(event_type="steward.capability_discovery_denied",
                    principal_id=None, outcome="denied", correlation_id=correlation,
                    details={"reason": str(exc)})
                raise HTTPException(401, "Steward session unavailable") from exc
            except AccessUnavailable as exc:
                raise HTTPException(503, "Session state unavailable") from exc
            except Exception as exc:
                await self._audit(event_type="steward.capability_discovery_unavailable",
                    principal_id=None, outcome="unavailable", correlation_id=correlation,
                    details={"error_type": type(exc).__name__})
                raise HTTPException(503, "CME capability registry unavailable") from exc

        @router.post("/operations/invoke")
        async def invoke_operation(request: Request, origin: str | None = Header(default=None)):
            correlation = self._correlation(request)
            await self._require_origin(request, origin, "capability.invoke")
            identity = None
            try:
                identity = await self._session(request.cookies.get(self.config["session"]["cookie_name"]))
                supplied = await request.json()
                if not isinstance(supplied, dict) or not isinstance(supplied.get("request"), dict):
                    raise HTTPException(422, "A canonical capability invocation is required")
                invocation = dict(supplied["request"])
                caller = dict(invocation.get("caller") or {})
                caller["principal_id"] = identity["principal_id"]
                caller["resident_id"] = None
                caller["service_id"] = None
                invocation["caller"] = caller
                invocation["correlation_id"] = correlation
                from .control import control_request
                result = await control_request(self.config["cme"]["control_socket"], "capability.invoke",
                                               {"request": invocation},
                                               idempotency_key=invocation.get("idempotency_key"),
                                               timeout=self.config["cme"]["request_timeout_seconds"])
                audit_id = await self._audit(event_type="steward.operation.completed",
                    principal_id=identity["principal_id"], outcome="accepted", correlation_id=correlation,
                    details={"operation_id": invocation.get("operation_id"),
                             "invocation_id": invocation.get("invocation_id"),
                             "result_state": result.get("state") if isinstance(result, dict) else None})
                return {"contract": "r3a.steward-operation-result.v1", "result": result,
                        "audit_event_id": audit_id, "correlation_id": correlation,
                        "freshness": "current"}
            except PermissionError as exc:
                audit_id = await self._audit(event_type="steward.operation.denied", principal_id=None,
                    outcome="denied", correlation_id=correlation, details={"reason": str(exc)})
                raise HTTPException(401, "Steward operation denied", headers={"X-Audit-Event-ID": audit_id}) from exc
            except AccessUnavailable as exc:
                raise HTTPException(503, "Steward operation unavailable") from exc
            except HTTPException:
                raise
            except RuntimeError as exc:
                if str(exc).startswith("PermissionError:"):
                    audit_id = await self._audit(event_type="steward.operation.denied", principal_id=identity["principal_id"],
                        outcome="denied", correlation_id=correlation,
                        details={"operation_id": (locals().get("invocation") or {}).get("operation_id"),
                                 "reason": "authoritative_grant_denied"})
                    raise HTTPException(403, "Steward operation denied", headers={"X-Audit-Event-ID": audit_id}) from exc
                audit_id = await self._audit(event_type="steward.operation.unavailable", principal_id=identity["principal_id"],
                    outcome="unavailable", correlation_id=correlation,
                    details={"error_type": type(exc).__name__})
                raise HTTPException(503, "Authoritative capability service unavailable") from exc
            except Exception as exc:
                # CME denial is audited there; the portal records only the correlated unavailable outcome.
                audit_id = await self._audit(event_type="steward.operation.unavailable",
                    principal_id=identity["principal_id"] if identity else None,
                    outcome="unavailable", correlation_id=correlation,
                    details={"error_type": type(exc).__name__})
                logger.warning("steward_operation_unavailable", extra={"correlation_id": correlation,
                               "audit_event_id": audit_id, "error_type": type(exc).__name__})
                raise HTTPException(503, "Authoritative capability service unavailable or denied") from exc

        @router.get("/status")
        async def access_status(request: Request):
            correlation = self._correlation(request)
            try:
                identity = await self._session(request.cookies.get(self.config["session"]["cookie_name"]))
                cme = None
                try:
                    from .control import control_request
                    cme = await control_request(self.config["cme"]["control_socket"], "health",
                                               timeout=self.config["cme"]["request_timeout_seconds"])
                except Exception:
                    pass
                tick_age = cme.get("scheduler_tick_age_seconds") if cme else None
                if not isinstance(tick_age, (int, float)) or isinstance(tick_age, bool):
                    freshness = "unavailable"
                elif tick_age > self.config["cme"]["health_stale_after_seconds"]:
                    freshness = "stale"
                else:
                    freshness = "current"
                audit_id = await self._audit(event_type="steward.state.read", principal_id=identity["principal_id"],
                    outcome={"current": "accepted", "stale": "stale", "unavailable": "unavailable"}[freshness],
                    correlation_id=correlation,
                    details={"source": "cme.health", "freshness": freshness})
                return {"contract": "r3a.steward-access-status.v1", "principal_id": identity["principal_id"],
                        "authentication": "authenticated", "session_freshness": "current",
                        "cme": {"health": cme.get("health") if cme else "unavailable",
                                "state": cme.get("state") if cme else "unknown",
                                "scheduler_tick_age_seconds": tick_age, "freshness": freshness},
                        "remote_transport": self.config["remote_transport"]["state"],
                        "freshness": freshness,
                        "audit_event_id": audit_id, "correlation_id": correlation,
                        "observed_at": datetime.now(timezone.utc).isoformat()}
            except PermissionError as exc:
                await self._audit(event_type="steward.state.read_denied",
                                       principal_id=None, outcome="denied", correlation_id=correlation,
                                       details={"reason": str(exc)})
                raise HTTPException(401, "Steward session unavailable") from exc
            except AccessUnavailable as exc:
                raise HTTPException(503, "Session state unavailable") from exc

        @router.get("/health")
        async def health():
            try:
                provider_health, store_health = await self._store_call(self.identity_provider.health), await self._store_call(self.store.health)
                return {"contract": "r3a.steward-auth-health.v1", "state": "ready",
                        "identity_provider": provider_health, "session_store": store_health}
            except AccessUnavailable:
                return JSONResponse(status_code=503, content={"contract": "r3a.steward-auth-health.v1",
                    "state": "unavailable", "identity_provider": "unavailable",
                    "session_store": "unavailable"})

        return router

    def _verify_origin(self, origin: str | None) -> None:
        if origin not in self.config["session"]["allowed_origins"]:
            raise HTTPException(403, "Request origin is not allowed")


def load_access_config(path: str | Path) -> dict[str, Any]:
    """Load strict external JSON configuration; no identity endpoint or credentials are defaulted."""
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccessUnavailable("steward_access_configuration_unavailable") from exc
    required = {"schema_id", "schema_version", "enabled", "identity", "session", "cme",
                "remote_transport", "session_dsn_env"}
    optional = {"secret_provider_manifest", "secret_provider_config", "identity_mode"}
    if (not isinstance(config, dict) or not required <= set(config)
            or set(config) - required - optional):
        raise AccessUnavailable("steward_access_configuration_invalid")
    if (config["schema_id"] != "r3a.steward-access.config.v1"
            or type(config["schema_version"]) is not int or config["schema_version"] != 1):
        raise AccessUnavailable("steward_access_configuration_version_unsupported")
    if config["enabled"] is not True:
        raise AccessUnavailable("steward_access_disabled")
    identity_keys = {"issuer", "steward_principal_id", "assertion_secret_ref", "assertion_max_age_seconds"}
    portal_identity_keys = {"provider", "issuer", "session_url", "required_role", "request_timeout_seconds"}
    native_identity_keys = {"provider", "issuer"}
    session_keys = {"cookie_name", "lifetime_seconds", "secure_cookie", "allowed_origins",
                    "connect_timeout_seconds"}
    cme_keys = {"control_socket", "request_timeout_seconds", "health_stale_after_seconds"}
    transport_keys = {"state", "public_exposure"}
    for section, keys in (("session", session_keys), ("cme", cme_keys),
                          ("remote_transport", transport_keys)):
        if not isinstance(config[section], dict) or set(config[section]) != keys:
            raise AccessUnavailable(f"steward_access_{section}_configuration_invalid")
    identity = config["identity"]
    identity_provider = identity.get("provider", "hmac-ingress") if isinstance(identity, dict) else None
    if config.get("identity_mode") not in {None, "independent"}:
        raise AccessUnavailable("steward_access_identity_mode_invalid")
    if config.get("identity_mode") == "independent" and identity_provider != "r3a.native":
        raise AccessUnavailable("legacy_identity_provider_forbidden")
    if identity_provider == "r3a.native" and config.get("identity_mode") != "independent":
        raise AccessUnavailable("independent_identity_mode_required")
    expected_identity_keys = (identity_keys if identity_provider == "hmac-ingress"
                              else portal_identity_keys if identity_provider == "r3.account-session"
                              else native_identity_keys if identity_provider == "r3a.native"
                              else set())
    if not expected_identity_keys or set(identity) != expected_identity_keys:
        raise AccessUnavailable("steward_access_identity_configuration_invalid")
    if config["remote_transport"]["public_exposure"] is not False:
        raise AccessUnavailable("public_exposure_requires_separate_review")
    if (not isinstance(config["session_dsn_env"], str)
            or re.fullmatch(r"[A-Z][A-Z0-9_]*", config["session_dsn_env"]) is None
            or not os.environ.get(config["session_dsn_env"], "")):
        raise AccessUnavailable("session_store_unavailable")
    session = config["session"]
    cme = config["cme"]
    transport = config["remote_transport"]
    if identity_provider == "hmac-ingress":
        if (any(not isinstance(identity.get(key), str) or not identity[key]
                for key in ("issuer", "steward_principal_id"))
                or type(identity.get("assertion_max_age_seconds")) is not int
                or identity["assertion_max_age_seconds"] <= 0):
            raise AccessUnavailable("steward_access_identity_configuration_invalid")
        secret_ref = identity.get("assertion_secret_ref")
        if (not isinstance(secret_ref, dict)
                or set(secret_ref) != {"provider_id", "provider_version", "secret_id"}
                or any(not isinstance(value, str) or not value for value in secret_ref.values())):
            raise AccessUnavailable("steward_access_secret_reference_invalid")
        if any(not isinstance(config.get(key), str) or not Path(config[key]).is_absolute()
               for key in ("secret_provider_manifest", "secret_provider_config")):
            raise AccessUnavailable("steward_access_secret_provider_configuration_invalid")
    elif identity_provider == "r3.account-session":
        issuer, role, url = identity.get("issuer"), identity.get("required_role"), identity.get("session_url")
        parsed = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        if (not isinstance(issuer, str) or not issuer or not isinstance(role, str) or not role
                or parsed is None or parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.port is None or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path != "/api/v1/auth/session"
                or not isinstance(identity.get("request_timeout_seconds"), (int, float))
                or isinstance(identity.get("request_timeout_seconds"), bool)
                or identity["request_timeout_seconds"] <= 0):
            raise AccessUnavailable("steward_access_identity_configuration_invalid")
    else:
        if identity.get("issuer") != "r3a-steward":
            raise AccessUnavailable("steward_access_identity_configuration_invalid")
        if session.get("cookie_name") != "r3a_steward_session":
            raise AccessUnavailable("steward_access_cookie_configuration_invalid")
        if (not isinstance(session.get("allowed_origins"), list)
                or any(not isinstance(origin, str) for origin in session["allowed_origins"])):
            raise AccessUnavailable("steward_access_session_configuration_invalid")
        native_origin_schemes = set()
        if not session.get("allowed_origins"):
            raise AccessUnavailable("steward_access_origin_must_be_lan_only")
        for origin in session.get("allowed_origins", []):
            try:
                parsed_origin = urllib.parse.urlsplit(origin)
            except ValueError as exc:
                raise AccessUnavailable("steward_access_origin_must_be_lan_only") from exc
            native_origin_schemes.add(parsed_origin.scheme)
            try:
                address = ipaddress.ip_address(parsed_origin.hostname or "")
            except ValueError:
                if (parsed_origin.hostname or "").lower() != "localhost":
                    raise AccessUnavailable("steward_access_origin_must_be_lan_only")
                address = ipaddress.ip_address("127.0.0.1")
            if (parsed_origin.scheme not in {"http", "https"} or not (address.is_private or address.is_loopback)
                    or parsed_origin.username or parsed_origin.password or parsed_origin.path
                    or parsed_origin.query or parsed_origin.fragment):
                raise AccessUnavailable("steward_access_origin_must_be_lan_only")
        if (len(native_origin_schemes) > 1
                or (native_origin_schemes == {"https"}) != (session.get("secure_cookie") is True)):
            raise AccessUnavailable("steward_access_cookie_transport_mismatch")
    if (not isinstance(session.get("cookie_name"), str) or not session["cookie_name"]
            or type(session.get("lifetime_seconds")) is not int or session["lifetime_seconds"] <= 0
            or not isinstance(session.get("connect_timeout_seconds"), (int, float))
            or isinstance(session.get("connect_timeout_seconds"), bool)
            or session["connect_timeout_seconds"] <= 0
            or not isinstance(session.get("secure_cookie"), bool)
            or not isinstance(session.get("allowed_origins"), list)
            or any(not isinstance(origin, str) or not origin for origin in session["allowed_origins"])):
        raise AccessUnavailable("steward_access_session_configuration_invalid")
    if transport.get("state") == "configured" and not session["secure_cookie"]:
        raise AccessUnavailable("secure_cookie_required_for_remote_transport")
    if transport.get("state") == "configured":
        origins = session["allowed_origins"]
        if not origins:
            raise AccessUnavailable("https_origin_required_for_remote_transport")
        for origin in origins:
            parsed_origin = urllib.parse.urlsplit(origin)
            if (parsed_origin.scheme != "https" or not parsed_origin.hostname
                    or parsed_origin.username or parsed_origin.password
                    or parsed_origin.path or parsed_origin.query or parsed_origin.fragment):
                raise AccessUnavailable("https_origin_required_for_remote_transport")
    if (not isinstance(cme.get("control_socket"), str) or not Path(cme["control_socket"]).is_absolute()
            or not isinstance(cme.get("request_timeout_seconds"), (int, float))
            or isinstance(cme.get("request_timeout_seconds"), bool)
            or cme["request_timeout_seconds"] <= 0
            or not isinstance(cme.get("health_stale_after_seconds"), (int, float))
            or isinstance(cme.get("health_stale_after_seconds"), bool)
            or cme["health_stale_after_seconds"] <= 0):
        raise AccessUnavailable("steward_access_cme_configuration_invalid")
    if transport.get("state") not in {"unavailable", "stale", "configured"}:
        raise AccessUnavailable("steward_access_transport_configuration_invalid")
    return config


def create_access_from_environment() -> StewardAccess:
    config_path = os.environ.get("R3A_STEWARD_ACCESS_CONFIG", "")
    if not config_path:
        raise AccessUnavailable("steward_access_configuration_unavailable")
    config = load_access_config(config_path)
    dsn = os.environ.get(config["session_dsn_env"], "")
    identity_kind = config["identity"].get("provider", "hmac-ingress")
    if identity_kind == "r3.account-session":
        identity_provider = R3AccountSessionIdentityProvider(config)
    elif identity_kind == "r3a.native":
        from .steward_identity import PostgresStewardIdentityRepository, R3aNativeIdentityProvider
        identity_provider = R3aNativeIdentityProvider(
            config["identity"],
            PostgresStewardIdentityRepository(dsn, config["session"]["connect_timeout_seconds"]))
    else:
        try:
            from r3a_plugins.bitwarden_secrets.provider import load_configured_provider
            from r3a_runtime.secrets import SecretReference
            provider = load_configured_provider(config["secret_provider_manifest"],
                                                config["secret_provider_config"])
            secret_reference = SecretReference(**config["identity"]["assertion_secret_ref"])
        except Exception as exc:
            raise AccessUnavailable("steward_identity_provider_unavailable") from exc
        identity_provider = HmacIngressIdentityProvider(config, provider, secret_reference)
    return StewardAccess(config,
                         PostgresSessionStore(dsn, config["session"]["connect_timeout_seconds"]),
                         identity_provider)


def create_router_from_environment() -> APIRouter:
    """Compatibility factory for applications that only mount the canonical AP3 router."""
    return create_access_from_environment().router()


async def require_steward_principal(request: Request) -> dict[str, Any]:
    """Reusable website route dependency; app.state must hold the shared StewardAccess instance."""
    access = getattr(request.app.state, "steward_access", None)
    if access is None:
        raise HTTPException(503, "Steward session service unavailable")
    return await access.authenticated_principal(request)
