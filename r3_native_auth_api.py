# R3 CONTROLLED SOURCE
# File: r3_native_auth_api.py
# Component: R3-NATIVE-WEBSITE-AUTH
# File Revision: 1.0.0
# Created: 2026-11-04 UTC | ChatGPT GPT-6
# Purpose: Native R3 website authentication HTTP adapter.
# Authority: Steward; Website Development #16
# Supersedes: None
# Tests: tests/test_r3_native_auth_api.py

"""R3 human authentication adapter; no R2 service dependency."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from r3_native_sessions import AuthenticationDenied, NativeSessions

SESSION_COOKIE = "r3_steward_session"
CSRF_COOKIE = "r3_steward_csrf"


def native_store():
    path = Path(
        os.environ.get(
            "R3_NATIVE_AUTH_DB",
            "~/.local/share/r3/auth/sessions.sqlite",
        )
    ).expanduser()

    try:
        return NativeSessions(path)
    except (AuthenticationDenied, OSError, ValueError) as exc:
        raise HTTPException(
            503, "R3 authentication unavailable"
        ) from exc


def authenticated_identity(request, *, mutation=False):
    token = request.cookies.get(SESSION_COOKIE)
    csrf = request.headers.get("X-Riverview-CSRF")

    try:
        return native_store().authenticate(
            token, csrf=csrf, mutation=mutation
        )
    except AuthenticationDenied as exc:
        raise HTTPException(
            401, "R3 authentication required"
        ) from exc


def build_native_auth_router(
    store_factory=native_store,
    allowed_origins=(),
):
    router = APIRouter()
    origins = frozenset(allowed_origins)

    def check_origin(request):
        origin = request.headers.get("origin")
        if not origin or origin not in origins:
            raise HTTPException(403, "Origin not allowed")

    @router.post("/api/v1/native-auth/login")
    async def login(request: Request):
        check_origin(request)

        raw = await request.body()
        if len(raw) > 16384:
            raise HTTPException(413, "Request too large")

        try:
            import json
            data = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(400, "Invalid JSON") from exc

        if not isinstance(data, dict):
            raise HTTPException(400, "Invalid credentials")

        try:
            session = store_factory().login(
                data.get("email"),
                data.get("password"),
            )
        except AuthenticationDenied as exc:
            raise HTTPException(
                401, "Invalid credentials"
            ) from exc

        response = JSONResponse({
            "authenticated": True,
            "role": session["role"],
        })

        response.set_cookie(
            SESSION_COOKIE,
            session["token"],
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
            max_age=session["expires_in"],
        )
        response.set_cookie(
            CSRF_COOKIE,
            session["csrf"],
            httponly=False,
            secure=True,
            samesite="strict",
            path="/",
            max_age=session["expires_in"],
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get("/api/v1/native-auth/session")
    def session(request: Request):
        token = request.cookies.get(SESSION_COOKIE)
        try:
            identity = store_factory().authenticate(token)
        except AuthenticationDenied as exc:
            raise HTTPException(
                401, "R3 authentication required"
            ) from exc

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

    @router.delete("/api/v1/native-auth/session")
    def logout(request: Request):
        check_origin(request)

        token = request.cookies.get(SESSION_COOKIE)
        csrf = request.headers.get("X-Riverview-CSRF")

        try:
            store = store_factory()
            store.authenticate(token, csrf=csrf, mutation=True)
            store.logout(token)
        except AuthenticationDenied as exc:
            raise HTTPException(
                401, "R3 authentication required"
            ) from exc

        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    return router
