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
    if method in {"POST", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            headers["Origin"] = origin
    if method == "DELETE":
        csrf = request.headers.get("X-Riverview-CSRF")
        if csrf:
            headers["X-Riverview-CSRF"] = csrf
        origin = request.headers.get("origin")
        if origin:
            headers["Origin"] = origin
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.read(MAX_BODY), res.headers.get_all("Set-Cookie", [])
    except urllib.error.HTTPError as err:
        return err.code, err.read(MAX_BODY), err.headers.get_all("Set-Cookie", [])
    except (OSError, TimeoutError) as exc:
        raise HTTPException(503, "Website sign-in service is unavailable") from exc


def _auth_url(cfg: dict[str, Any], key: str) -> str:
    value = cfg.get(key)
    if not isinstance(value, str):
        raise HTTPException(503, "Website authentication configuration is missing")
    url = urllib.parse.urlparse(value)
    if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.fragment:
        raise HTTPException(503, "Website authentication must use loopback")
    if url.path != "/api/v1/auth/session" or url.query:
        raise HTTPException(503, "Unexpected website authentication endpoint")
    return value


def _portal_identity(request: Request, cfg: dict[str, Any]) -> dict[str, Any]:
    if not request.cookies.get("rv_account_session"):
        raise HTTPException(401, "Sign in to R3")
    status, raw, _ = _portal_request(
        _auth_url(cfg, "website_auth_session_url"), request
    )
    if status == 401 or status == 403:
        raise HTTPException(401, "Sign in to R3")
    if status != 200:
        raise HTTPException(503, "Website authentication service unavailable")
    try:
        body = json.loads(raw)
        identity = body["identity"]
        if not isinstance(identity["email"], str) or not isinstance(identity["roles"], list):
            raise ValueError("Invalid identity")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(502, "Invalid website authentication response") from exc
    return identity


def _principal(request: Request, cfg: dict[str, Any]) -> str:
    identity = _portal_identity(request, cfg)
    if "steward" not in identity["roles"]:
        raise HTTPException(403, "Steward access required")
    return identity["email"]


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
    return urllib.parse.quote(str(cfg["resident_id"]), safe="")


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

        status, payload, cookies = _portal_request(
            _auth_url(cfg, "website_auth_login_url"), request,
            method="POST", body=raw, content_type="application/json"
        )
        if status in (401, 403):
            raise HTTPException(401, "Invalid credentials")
        if status != 200:
            raise HTTPException(503, "Website sign-in service unavailable")
        try:
            identity = json.loads(payload)["identity"]
            roles = identity["roles"]
            if not isinstance(roles, list):
                raise ValueError("Invalid roles")
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(502, "Invalid website sign-in response") from exc
        if "steward" not in roles:
            raise HTTPException(403, "Steward access required")
        response = JSONResponse(
            {"authenticated": True, "role": "steward"},
            headers={"Cache-Control": "no-store"},
        )
        if len(cookies) != 2:
            raise HTTPException(502, "Website authentication cookies missing")
        for cookie in _browser_cookies(cookies):
            response.headers.append("set-cookie", cookie)
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

        _portal_identity(request, cfg)
        status, _, _ = _portal_request(
            _auth_url(cfg, "website_auth_session_url"),
            request, method="DELETE"
        )
        if status in (401, 403):
            raise HTTPException(401, "Invalid session or CSRF")
        if status != 200:
            raise HTTPException(503, "Website logout unavailable")
        response = JSONResponse(
            {"authenticated": False},
            headers={"Cache-Control": "no-store"},
        )
        response.delete_cookie("rv_account_session", path="/")
        response.delete_cookie("rv_account_csrf", path="/")
        return response

    @router.get("/api/v1/chat/session")
    def session(request: Request):
        cfg = load_config()
        _origin(request, cfg)

        identity = _portal_identity(request, cfg)
        return JSONResponse(
            {"authenticated": True, "identity": {
                "email": identity["email"], "roles": identity["roles"]
            }},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/api/v1/chat/capabilities")
    def capabilities(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        return _runtime(cfg, principal, f"/v1/residents/{_resident(cfg)}/capabilities")

    @router.get("/api/v1/chat/conversations")
    def conversations(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        return _runtime(cfg, principal, f"/v1/residents/{_resident(cfg)}/conversations")

    @router.post("/api/v1/chat/conversations")
    async def create_conversation(request: Request):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        raw = await request.body()
        if len(raw) > 8192:
            raise HTTPException(413, "Conversation request is too large")
        try:
            body = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid conversation request") from exc
        if not isinstance(body, dict) or not isinstance(body.get("title", "Steward conversation"), str):
            raise HTTPException(400, "Conversation title must be text")
        return _runtime(cfg, principal, f"/v1/residents/{_resident(cfg)}/conversations", "POST", body)

    @router.get("/api/v1/chat/conversations/{conversation_id}/messages")
    def messages(conversation_id: str, request: Request, after: int = 0, limit: int = 200):
        cfg = load_config(); _origin(request, cfg); principal = _principal(request, cfg)
        try:
            cid = str(uuid.UUID(conversation_id))
        except (ValueError, AttributeError) as exc:
            raise HTTPException(400, "Invalid conversation id") from exc
        if after < 0 or not 1 <= limit <= 200:
            raise HTTPException(400, "Invalid message page")
        return _runtime(cfg, principal, f"/v1/conversations/{cid}/messages", query=f"after={after}&limit={limit}")

    @router.post("/api/v1/chat/conversations/{conversation_id}/messages")
    async def send_message(conversation_id: str, request: Request):
        cfg = load_config(); _origin(request, cfg, required=True); principal = _principal(request, cfg)
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
        return _runtime(cfg, principal, f"/v1/conversations/{cid}/messages", "POST", body)

    return router
