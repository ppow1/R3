"""Regression coverage for existing Riverview account authority integration."""
import json
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

import r3_chat_api


def request(method="GET", cookies=None, headers=None):
    hdr = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if cookies:
        hdr.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({"type": "http", "method": method, "path": "/api/v1/chat/session",
                    "headers": hdr, "query_string": b"", "scheme": "https",
                    "server": ("192.168.1.155", 443)})


CFG = {"website_auth_session_url": "http://127.0.0.1:8767/api/v1/auth/session",
       "website_auth_login_url": "http://127.0.0.1:8767/api/v1/auth/session"}


def test_auth_endpoint_must_be_loopback():
    assert r3_chat_api._auth_url(CFG, "website_auth_session_url").startswith("http://127.0.0.1:")
    for url in ("https://example.com/api/v1/auth/session",
                "http://127.0.0.1:8767/admin",
                "http://user:password@127.0.0.1:8767/api/v1/auth/session"):
        try:
            r3_chat_api._auth_url({"website_auth_session_url": url}, "website_auth_session_url")
        except HTTPException as exc:
            assert exc.status_code == 503
        else:
            raise AssertionError("Untrusted auth URL accepted")


def test_missing_cookie_denied_without_upstream_request():
    with patch.object(r3_chat_api, "_portal_request") as upstream:
        try:
            r3_chat_api._principal(request(), CFG)
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Unauthenticated request accepted")
        upstream.assert_not_called()


def test_steward_role_verified_upstream():
    body = json.dumps({"identity": {"email": "steward@example.org", "roles": ["steward"]}}).encode()
    with patch.object(r3_chat_api, "_portal_request", return_value=(200, body, [])) as upstream:
        principal = r3_chat_api._principal(
            request(cookies={"rv_account_session": "opaque"}), CFG)
        assert principal == "steward@example.org"
        upstream.assert_called_once()


def test_viewer_cannot_access_steward_routes():
    body = json.dumps({"identity": {"email": "viewer@example.org", "roles": ["viewer"]}}).encode()
    with patch.object(r3_chat_api, "_portal_request", return_value=(200, body, [])):
        try:
            r3_chat_api._principal(
                request(cookies={"rv_account_session": "opaque"}), CFG)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("Non-steward role accepted")


def test_expired_session_denied():
    with patch.object(r3_chat_api, "_portal_request", return_value=(401, b"{}", [])):
        try:
            r3_chat_api._principal(
                request(cookies={"rv_account_session": "expired"}), CFG)
        except HTTPException as exc:
            assert exc.status_code == 401
        else:
            raise AssertionError("Expired session accepted")


def test_cookie_contract_rejects_unexpected_cookie():
    assert len(r3_chat_api._browser_cookies([
        "rv_account_session=opaque; Secure; HttpOnly; Path=/",
        "rv_account_csrf=opaque; Secure; Path=/",
    ])) == 2
    try:
        r3_chat_api._browser_cookies(["other_cookie=unexpected"])
    except HTTPException as exc:
        assert exc.status_code == 502
    else:
        raise AssertionError("Unexpected cookie accepted")
