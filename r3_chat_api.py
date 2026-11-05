# R3 CONTROLLED SOURCE
# File: r3_chat_api.py
# Component: WEBSITE-CHAT-API
# File Revision: 1.1.0
# Created: Unknown (legacy)
# Created By: Unknown (legacy)
# Purpose: Authenticated website proxy to resident conversation service.
# Execution Model: FastAPI routes; loopback runtime requests with server credential.
# Observability: Sanitized errors; no-store responses; no credential logging.
# Dependencies: R3 native sessions; HR capability directory; runtime conversation API.
# Authority: Authenticated Steward; native CSRF for mutations; conversation owner checks.
# Changed: 2026-11-05 UTC | WEBSITE-MULTIRESIDENT-CHAT | ChatGPT GPT-6 | Add authorized dynamic HR routing and mutation CSRF enforcement.
# Supersedes: Prior website Grace-only proxy; predecessor blob 24be131
# Contracts: runtime/conversations.py; runtime/hr_capability.py; hints/r3-runtime-routing.md
# Tests: tests/test_chat_api.py; tests/test_website_hr_directory.py; tests/test_conversation_runtime_integration.py
# History/Predecessor: Git blob 24be131
"""Website-only proxy for the deployed durable R3 conversation service."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from r3_native_auth_api import native_store, SESSION_COOKIE, CSRF_COOKIE
from r3_native_sessions import AuthenticationDenied
from r3_resident_directory import (
    AuthorizedStewardSession, load_residents, require_resident, runtime_resident_id,
)

CONFIG_PATH = Path(os.environ.get("R3_WEBSITE_CHAT_CONFIG", "~/.config/r3/chat.json")).expanduser()
MAX_BODY = 1_100_000


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Website chat configuration is unavailable") from exc
    required = {
        "conversation_api_base_url", "conversation_api_credential_file",
        "resident_id", "required_role", "request_timeout_seconds", "allowed_origins",
    }
    if not isinstance(cfg, dict) or required - cfg.keys():
        raise HTTPException(503, "Website chat configuration is invalid")
    api = urllib.parse.urlparse(cfg["conversation_api_base_url"])
    if api.scheme != "http" or api.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(503, "Conversation API must remain on loopback")
    if not isinstance(cfg["allowed_origins"], list) or not cfg["allowed_origins"]:
        raise HTTPException(503, "Website chat origins are invalid")
    return cfg


def _origin(request: Request, cfg: dict[str, Any], required: bool = False) -> None:
    origin = request.headers.get("origin")
    if required and not origin:
        raise HTTPException(403, "Request origin is required")
    if origin and origin not in cfg["allowed_origins"]:
        raise HTTPException(403, "Request origin is not allowed")


# R3-AUTH-COOKIE-002
def _browser_cookies(headers):
    """Preserve both cookies and make the session usable under /r3."""
    result = []
    for cookie in headers:
        name = cookie.split("=", 1)[0].strip()
        if name not in {"rv_account_session", "rv_account_csrf"}:
            raise HTTPException(502, "Unexpected authentication cookie")
        parts = cookie.split(";")
        parts = [p for p in parts if not p.strip().lower().startswith("path=")]
        parts.append(" Path=/")
        result.append(";".join(parts))
    return result


def _portal_request(url: str, request: Request, method: str = "GET",
                    body: bytes | None = None,
                    content_type: str | None = None,
                    timeout: int = 15) -> tuple[int, bytes, list[str]]:
    headers = {"Accept": "application/json"}
    cookie = request.headers.get("cookie")
    if cookie:
        headers["Cookie"] = cookie
    if body is not None:
        headers["Content-Type"] = content_type or "application/json"
    if method == "DELETE":
        csrf = request.headers.get("X-Riverview-CSRF")
        if csrf:
            headers["X-Riverview-CSRF"] = csrf
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read(MAX_BODY), res.headers.get_all("Set-Cookie", [])
    except urllib.error.HTTPError as err:
        return err.code, err.read(MAX_BODY), err.headers.get_all("Set-Cookie", [])
    except (OSError, TimeoutError) as exc:
        raise HTTPException(503, "Website sign-in service is unavailable") from exc


def _principal(request: Request, cfg: dict[str, Any], *, mutation: bool = False) -> AuthorizedStewardSession:
    """Validate R3-native human session, never browser identity headers."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Sign in to R3")
    try:
        identity = native_store().authenticate(
            token,
            csrf=request.headers.get("X-Riverview-CSRF"),
            mutation=mutation,
        )
    except AuthenticationDenied as exc:
        raise HTTPException(401, "Sign in to R3") from exc

    if identity["role"] != "steward":
        raise HTTPException(403, "Steward access required")

    return AuthorizedStewardSession(identity["email"], identity["role"])



def _runtime(cfg: dict[str, Any], principal: str, path: str, method: str = "GET",
             body: dict[str, Any] | None = None, query: str = "") -> JSONResponse:
    token_path = Path(cfg["conversation_api_credential_file"]).expanduser()
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise HTTPException(503, "Conversation service credential is unavailable on the server") from exc
    if not token or "\n" in token or "\r" in token:
        raise HTTPException(503, "Conversation service credential is invalid")
    url = cfg["conversation_api_base_url"].rstrip("/") + path + ("?" + query if query else "")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/json", "Authorization": "Bearer " + token,
        "X-R3-Principal": principal, "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=int(cfg["request_timeout_seconds"])) as res:
            payload, status = res.read(MAX_BODY), res.status
    except urllib.error.HTTPError as err:
        status, payload = err.code, err.read(MAX_BODY)
    except (OSError, TimeoutError) as exc:
        raise HTTPException(503, "Grace conversation service is temporarily unavailable") from exc
    try:
        data_out = json.loads(payload) if payload else {}
    except ValueError:
        raise HTTPException(502, "Grace conversation service returned invalid data")
    if status >= 400:
        raise HTTPException(status if status < 500 else 502,
                            "Grace conversation request was rejected" if status < 500 else "Grace conversation service error")
    return JSONResponse(data_out, status_code=status, headers={"Cache-Control": "no-store"})


def _resident(cfg: dict[str, Any]) -> str:
    # Legacy Grace URLs retain their established configured resident while
    # resolving it against the runtime's real resident registry.
    configured = str(cfg["resident_id"])
    canonical = configured if configured.startswith("r3:") else "r3:" + configured.casefold()
    return urllib.parse.quote(
        runtime_resident_id(canonical, legacy_runtime_id=configured), safe=""
    )


def _ensure_conversation_resident(cfg: dict[str, Any], principal: str,
                                  runtime_id: str, conversation_id: str) -> None:
    """Bind a conversation token to the selected resident before message access."""
    result = _runtime(
        cfg, principal,
        f"/v1/residents/{urllib.parse.quote(runtime_id, safe='')}/conversations",
    )
    try:
        payload = json.loads(result.body)
        rows = payload.get("conversations", payload.get("items", []))
        if not isinstance(rows, list) or not any(
            isinstance(row, dict)
            and (row.get("conversation_id") or row.get("id")) == conversation_id
            for row in rows
        ):
            raise HTTPException(404, "Conversation unavailable for selected resident")
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(502, "Conversation service returned an invalid list") from exc


def _runtime_capabilities(cfg: dict[str, Any], principal: str,
                          runtime_id: str) -> JSONResponse:
    response = _runtime(
        cfg, principal,
        f"/v1/residents/{urllib.parse.quote(runtime_id, safe='')}/capabilities",
    )
    try:
        data = json.loads(response.body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(502, "Conversation service returned invalid capabilities") from exc
    if not isinstance(data, dict) or data.get("resident") != runtime_id:
        raise HTTPException(502, "Conversation runtime identity did not match the HR association")
    return response


def build_chat_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/v1/chat/login")
    async def login(request: Request):
        cfg = load_config()
        _origin(request, cfg, required=True)

        raw = await request.body()
        if len(raw) > 16384:
            raise HTTPException(413, "Login request is too large")

        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid sign-in request") from exc

        if not isinstance(data, dict):
            raise HTTPException(400, "Invalid sign-in request")

        try:
            session = native_store().login(
                data.get("email"),
                data.get("password"),
            )
        except AuthenticationDenied as exc:
            raise HTTPException(401, "Invalid credentials") from exc

        response = JSONResponse(
            {"authenticated": True, "role": session["role"]},
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            SESSION_COOKIE, session["token"],
            httponly=True, secure=True,
            samesite="strict", path="/",
            max_age=session["expires_in"],
        )
        response.set_cookie(
            CSRF_COOKIE, session["csrf"],
            httponly=False, secure=True,
            samesite="strict", path="/",
            max_age=session["expires_in"],
        )
        return response

    @router.post("/api/v1/chat/password-reset")
    async def password_reset(request: Request):
        cfg = load_config()
        _origin(request, cfg, required=True)
        # Recovery requires a separately approved, audited workflow.
        # Never forward credentials or recovery requests to R2.
        return JSONResponse(
            {"detail": "R3-native password recovery is not configured"},
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )

    @router.delete("/api/v1/chat/session")
    def logout(request: Request):
        cfg = load_config()
        _origin(request, cfg, required=True)

        token = request.cookies.get(SESSION_COOKIE)
        csrf = request.headers.get("X-Riverview-CSRF")

        try:
            store = native_store()
            store.authenticate(token, csrf=csrf, mutation=True)
            store.logout(token)
        except AuthenticationDenied as exc:
            raise HTTPException(401, "Invalid session or CSRF") from exc

        response = JSONResponse(
            {"authenticated": False},
            headers={"Cache-Control": "no-store"},
        )
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    @router.get("/api/v1/chat/session")
    def session(request: Request):
        cfg = load_config()
        _origin(request, cfg)

        token = request.cookies.get(SESSION_COOKIE)

        try:
            identity = native_store().authenticate(token)
        except AuthenticationDenied as exc:
            raise HTTPException(401, "Sign in to R3") from exc

        return JSONResponse(
            {
                "authenticated": True,
                "identity": {
                    "email": identity["email"],
                    "roles": [identity["role"]],
                },
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/api/v1/chat/residents")
    def resident_directory(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        # Directory membership is not proof of runtime readiness or permission to converse.
        return JSONResponse({"residents": [
            {key: value for key, value in row.items() if not key.startswith("_")}
            for row in load_residents(principal, legacy_runtime_id=str(cfg["resident_id"]))
        ]}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/chat/residents/{resident_id}/capabilities")
    def resident_capabilities(resident_id: str, request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        resident = require_resident(resident_id, principal, legacy_runtime_id=str(cfg["resident_id"]))
        if not resident["_runtime_id"]:
            raise HTTPException(404, "Resident conversation runtime unavailable")
        return _runtime_capabilities(cfg, principal.principal_id, resident["_runtime_id"])

    @router.get("/api/v1/chat/residents/{resident_id}/conversations")
    def resident_conversations(resident_id: str, request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        resident = require_resident(resident_id, principal, legacy_runtime_id=str(cfg["resident_id"]))
        if not resident["_runtime_id"]:
            raise HTTPException(404, "Resident conversation runtime unavailable")
        runtime_id = urllib.parse.quote(resident["_runtime_id"], safe="")
        return _runtime(cfg, principal.principal_id, f"/v1/residents/{runtime_id}/conversations")

    @router.post("/api/v1/chat/residents/{resident_id}/conversations")
    async def resident_create_conversation(resident_id: str, request: Request):
        cfg = load_config(); _origin(request, cfg, required=True); principal = _principal(request, cfg, mutation=True)
        resident = require_resident(resident_id, principal, legacy_runtime_id=str(cfg["resident_id"]))
        if not resident["_runtime_id"]:
            raise HTTPException(404, "Resident conversation runtime unavailable")
        raw = await request.body()
        if len(raw) > 8192:
            raise HTTPException(413, "Conversation request is too large")
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid conversation request") from exc
        if not isinstance(body, dict) or not isinstance(body.get("title", "Steward conversation"), str):
            raise HTTPException(400, "Conversation title must be text")
        runtime_id = urllib.parse.quote(resident["_runtime_id"], safe="")
        return _runtime(cfg, principal.principal_id, f"/v1/residents/{runtime_id}/conversations", "POST", body)

    @router.get("/api/v1/chat/capabilities")
    def capabilities(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        canonical = str(cfg["resident_id"])
        require_resident(canonical if canonical.startswith("r3:") else "r3:" + canonical.casefold(), principal, legacy_runtime_id=str(cfg["resident_id"]))
        return _runtime_capabilities(cfg, principal.principal_id, _resident(cfg))

    @router.get("/api/v1/chat/conversations")
    def conversations(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        canonical = str(cfg["resident_id"])
        require_resident(canonical if canonical.startswith("r3:") else "r3:" + canonical.casefold(), principal, legacy_runtime_id=str(cfg["resident_id"]))
        return _runtime(cfg, principal.principal_id, f"/v1/residents/{_resident(cfg)}/conversations")

    @router.post("/api/v1/chat/conversations")
    async def create_conversation(request: Request):
        cfg = load_config(); _origin(request, cfg, required=True); principal = _principal(request, cfg, mutation=True)
        canonical = str(cfg["resident_id"])
        require_resident(canonical if canonical.startswith("r3:") else "r3:" + canonical.casefold(), principal, legacy_runtime_id=str(cfg["resident_id"]))
        raw = await request.body()
        if len(raw) > 8192:
            raise HTTPException(413, "Conversation request is too large")
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid conversation request") from exc
        if not isinstance(body, dict) or not isinstance(body.get("title", "Steward conversation"), str):
            raise HTTPException(400, "Conversation title must be text")
        return _runtime(cfg, principal.principal_id,
                        f"/v1/residents/{_resident(cfg)}/conversations", "POST", body)

    def _messages(conversation_id: str, request: Request, after: int, limit: int,
                  resident_id: str | None = None):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        try:
            cid = str(uuid.UUID(conversation_id))
        except (ValueError, AttributeError) as exc:
            raise HTTPException(400, "Invalid conversation id") from exc
        if after < 0 or not 1 <= limit <= 200:
            raise HTTPException(400, "Invalid message page")
        if resident_id is None:
            configured = str(cfg["resident_id"])
            resident_id = configured if configured.startswith("r3:") else "r3:" + configured.casefold()
            resident = require_resident(resident_id, principal, legacy_runtime_id=configured)
        else:
            resident = require_resident(resident_id, principal, legacy_runtime_id=str(cfg["resident_id"]))
        runtime_id = resident["_runtime_id"]
        if not runtime_id:
            raise HTTPException(404, "Resident conversation runtime unavailable")
        _ensure_conversation_resident(cfg, principal.principal_id, runtime_id, cid)
        return _runtime(cfg, principal.principal_id, f"/v1/conversations/{cid}/messages",
                        query=f"after={after}&limit={limit}")

    @router.get("/api/v1/chat/residents/{resident_id}/conversations/{conversation_id}/messages")
    def resident_messages(resident_id: str, conversation_id: str, request: Request,
                          after: int = 0, limit: int = 200):
        return _messages(conversation_id, request, after, limit, resident_id)

    @router.get("/api/v1/chat/conversations/{conversation_id}/messages")
    def messages(conversation_id: str, request: Request, after: int = 0, limit: int = 200):
        return _messages(conversation_id, request, after, limit)

    async def _send_message(conversation_id: str, request: Request,
                            resident_id: str | None = None):
        cfg = load_config(); _origin(request, cfg, required=True); principal = _principal(request, cfg, mutation=True)
        try:
            cid = str(uuid.UUID(conversation_id))
        except (ValueError, AttributeError) as exc:
            raise HTTPException(400, "Invalid conversation id") from exc
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "Message request is too large")
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid message request") from exc
        if (not isinstance(body, dict) or not isinstance(body.get("content"), str)
                or not body["content"].strip() or len(body["content"]) > 100000
                or not isinstance(body.get("client_message_id"), str)
                or not 1 <= len(body["client_message_id"]) <= 160):
            raise HTTPException(400, "Message content or retry id is invalid")
        if resident_id is None:
            configured = str(cfg["resident_id"])
            resident_id = configured if configured.startswith("r3:") else "r3:" + configured.casefold()
            resident = require_resident(resident_id, principal, legacy_runtime_id=configured)
        else:
            resident = require_resident(resident_id, principal, legacy_runtime_id=str(cfg["resident_id"]))
        runtime_id = resident["_runtime_id"]
        if not runtime_id:
            raise HTTPException(404, "Resident conversation runtime unavailable")
        _ensure_conversation_resident(cfg, principal.principal_id, runtime_id, cid)
        return _runtime(cfg, principal.principal_id, f"/v1/conversations/{cid}/messages", "POST", body)

    @router.post("/api/v1/chat/residents/{resident_id}/conversations/{conversation_id}/messages")
    async def resident_send_message(resident_id: str, conversation_id: str, request: Request):
        return await _send_message(conversation_id, request, resident_id)

    @router.post("/api/v1/chat/conversations/{conversation_id}/messages")
    async def send_message(conversation_id: str, request: Request):
        return await _send_message(conversation_id, request)

    return router
