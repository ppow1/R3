# R3 CONTROLLED SOURCE
# File: r3_app.py
# Component: R3-APP
# File Revision: 1.0.18
# Created: Unknown (legacy; initial commit can establish earliest publication)
# Created By: Unknown (legacy)
# Purpose: Serve visual estate UI and authenticated, canonical R3A Steward API adapters
# Execution Model: Request-driven FastAPI service
# Observability: HTTP diagnostics, correlated CME results, and durable activity/event references; AP3 sessions are durably audited when enabled
# Dependencies: FastAPI, Git checkout, local artwork folder; optional r3a_runtime Steward access module
# Authority: R3 engineering guidance; AP3-M1 Issue #49; approved charter prevails
# Changed: 2026-11-07T21:48:11Z | AP3-M1 | Codex GPT-6 | Apply no-store headers and keep the authenticated status response freshness-aware.
# Changed: 2026-11-02 UTC | R3-AVATAR-001 | ChatGPT GPT-6 | Serve the fixed resident avatar frontend module
# Changed: 2026-11-01 UTC | R3-PANEL-INTERACTION-002 | ChatGPT GPT-6 | Align snapshot anchors and report dragged Infrastructure marker
# Supersedes: None
# Contracts: hints/file-provenance.md
# Tests: tests.test_r3a_website; API responses mocked at Unix socket boundary; live/browser verification pending
# History/Predecessor: Git blob b3195f5a0ea8bacc030b642bc3dbb76258a4e747
# Changed: 2026-11-07T21:40:20Z | R3A-007/R3A-010/R3A-013/R3A-017/R3A-019 | Codex GPT-6 | Add configurable Steward-authenticated AP1 diagnostics and durable Grace objective gateway.
# Changed: 2026-11-07T21:58:03Z | R3A-007/R3A-013 | Codex GPT-6 | Expose read-only effective sanitized configuration and bounded activation history from authoritative diagnostics.
# Changed: 2026-11-07T22:02:09Z | R3A-007/R3A-013 | Codex GPT-6 | Record focused API test coverage and current verification limits in provenance.
# Changed: 2026-11-07T22:04:07Z | R3A-007/R3A-010 | Codex GPT-6 | Add structured request correlation and preserve CME's actual objective correlation ID.
# Changed: 2026-11-07T23:40:00Z | R3A-007/R3A-010 | Codex GPT-6 | Serve versioned Steward workspace browser client module.
# Changed: 2026-11-07T23:55:00Z | R3A-010 | Codex GPT-6 | Replace temporary bearer checks with the shared AP3 opaque session and version the objective result.
# Changed: 2026-11-08T13:30:00Z | R3A-WEB-IDENTITY | Codex GPT-6 | Expose startup-captured build/version/environment identity for the Steward website.
# Changed: 2026-11-08T14:30:00Z | R3A-010/#49/#51 | Codex GPT-6 | Publish an externally configured, same-host existing portal login URL in website identity metadata.

"""R3 first vertical slice: shared read-only capabilities, not UI-owned logic.

Run: R3_REPO=/path/to/R3 uvicorn r3_app:app --host 127.0.0.1 --port 8303
Requires: fastapi, uvicorn. No GitHub credentials exposed to browsers.
"""
import os
import io
import zipfile
import subprocess
import hashlib
import platform
import sys
import struct
import math
import asyncio
import uuid
import json
import logging
import re
import urllib.parse
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("R3_REPO", Path(__file__).resolve().parent)).resolve()
ART = (ROOT / "assets" / "artwork").resolve()
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
app = FastAPI(title="R3 Institutional Capabilities", version="0.1.0")
website_logger = logging.getLogger("r3.website")


def _running_build_commit() -> str | None:
    """Capture deployed source revision once at process start; never report a later checkout head."""
    candidate = os.environ.get("R3_WEBSITE_BUILD_COMMIT", "").strip()
    if not candidate:
        try:
            candidate = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True, timeout=2,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", candidate):
        return None
    return candidate.lower()


WEBSITE_BUILD_COMMIT = _running_build_commit()
WEBSITE_BUILD_VERSION = app.version or None


@app.get("/api/v1/website/identity")
def website_identity(request: Request):
    """Identify this running R3A website process without claiming service integrations."""
    server = request.scope.get("server") or (None, None)
    identity = {
        "contract": "r3a.website-identification.v1",
        "contract_version": "1.0.0",
        "application": "Riverview R3 Alpha",
        "website_version": WEBSITE_BUILD_VERSION or "unknown",
        "build_commit": WEBSITE_BUILD_COMMIT or "unknown",
        "environment": os.environ.get("R3_WEBSITE_ENVIRONMENT", "unknown"),
        "service_port": server[1] if len(server) > 1 and server[1] else "unknown",
    }
    # The browser must visit the existing account portal on the same host so
    # its HttpOnly rv_account_session cookie is shared with this Website. Keep
    # the URL deployment-configured and reject cross-host/open-redirect values.
    portal_url = os.environ.get("R3_STEWARD_PORTAL_LOGIN_URL", "").strip()
    parsed_portal_url = urllib.parse.urlsplit(portal_url) if portal_url else None
    if (parsed_portal_url and parsed_portal_url.scheme in {"http", "https"}
            and parsed_portal_url.hostname == request.url.hostname
            and parsed_portal_url.path and not parsed_portal_url.username
            and not parsed_portal_url.password and not parsed_portal_url.query
            and not parsed_portal_url.fragment):
        identity["account_portal_login_url"] = portal_url
    roadmap_repository = os.environ.get("R3_WEBSITE_ROADMAP_REPOSITORY", "").strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", roadmap_repository):
        identity["roadmap_repository"] = roadmap_repository
    roadmap_api_base = os.environ.get("R3_WEBSITE_GITHUB_API_BASE", "").strip().rstrip("/")
    parsed_api_base = urllib.parse.urlsplit(roadmap_api_base) if roadmap_api_base else None
    if (parsed_api_base and parsed_api_base.scheme == "https" and parsed_api_base.hostname
            and not parsed_api_base.username and not parsed_api_base.password
            and not parsed_api_base.query and not parsed_api_base.fragment):
        identity["roadmap_api_base"] = roadmap_api_base
    return identity


@app.middleware("http")
async def log_correlated_request(request, call_next):
    request_id = str(uuid.uuid4())
    response = await call_next(request)
    route = request.scope.get("route")
    website_logger.info(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "method": request.method,
        "route": getattr(route, "path", request.url.path),
        "status_code": response.status_code,
    }, separators=(",", ":")))
    response.headers["X-Request-ID"] = request_id
    return response


class GraceObjectiveRequest(BaseModel):
    contract: Literal["r3a.grace-objective-submission.v1"]
    contract_version: Literal["1.0.0"]
    objective: str = Field(min_length=1, max_length=4000)
    acceptance_criteria: list[dict] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=8, max_length=200)


async def _steward_settings(request: Request):
    """Validate the shared AP3 cookie session and resolve external R3A runtime settings."""
    config_path = os.environ.get("R3A_CONFIG")
    access = getattr(app.state, "steward_access", None)
    if not access:
        raise HTTPException(503, "Steward operations are unavailable: shared AP3 session configuration is missing")
    await access.authenticated_principal(request, "steward.r3a.read_or_submit")
    if not config_path:
        access_config = getattr(access, "config", {})
        socket_path = access_config.get("cme", {}).get("control_socket") if isinstance(access_config, dict) else None
        if not isinstance(socket_path, str) or not Path(socket_path).is_absolute():
            raise HTTPException(503, "Steward operations are unavailable: configured CME socket is missing")
        return SimpleNamespace(control_socket=socket_path, diagnostics_socket=socket_path)
    try:
        from r3a_runtime.config import load_settings
        return load_settings(config_path)
    except Exception as exc:
        raise HTTPException(503, f"R3A runtime configuration unavailable: {type(exc).__name__}") from exc


async def _steward_principal(request: Request, action: str = "steward.r3a.read_or_submit"):
    access = getattr(app.state, "steward_access", None)
    if not access:
        raise HTTPException(503, "Steward operations are unavailable: shared AP3 session is missing")
    principal = await access.authenticated_principal(request, action)
    return principal


class StewardConversationCreate(BaseModel):
    resident_id: str = Field(min_length=1, max_length=256)
    client_conversation_id: str


class StewardConversationMessage(BaseModel):
    client_message_id: str
    text: str = Field(min_length=1, max_length=2000)


async def _website_control_request(request: Request, principal: dict, operation: str,
                                   payload: dict, idempotency_key: str | None = None):
    settings = await _steward_settings(request)
    from r3a_runtime.control import control_request
    try:
        result = await control_request(settings.control_socket, operation,
                                       {**payload, "principal_id": principal["principal_id"]},
                                       idempotency_key=idempotency_key, timeout=8.0)
        return {**result, "resource_contract": result.get("contract"),
                "contract": "r3a.steward-workspace-web.v1"}
    except RuntimeError as exc:
        if str(exc).startswith("PermissionError:"):
            raise HTTPException(403, "Steward operation denied") from exc
        if "previous Grace turn is still processing" in str(exc):
            raise HTTPException(409, "Grace is still processing the previous turn") from exc
        if str(exc).startswith(("ValueError:", "LookupError:")):
            raise HTTPException(422, "Steward request is invalid or unavailable") from exc
        raise HTTPException(503, "Managed CME operation is unavailable") from exc
    except Exception as exc:
        raise HTTPException(503, f"Managed CME operation unavailable: {type(exc).__name__}") from exc


@app.get("/api/v1/steward/residents")
async def steward_residents(request: Request):
    principal = await _steward_principal(request)
    return await _website_control_request(request, principal, "steward.residents.discover", {},
                                          f"website-residents:{principal['principal_id']}:{uuid.uuid4()}")


@app.get("/api/v1/steward/conversations")
async def steward_conversations(request: Request, resident_id: str):
    if not resident_id or len(resident_id) > 256:
        raise HTTPException(422, "resident_id is invalid")
    principal = await _steward_principal(request)
    return await _website_control_request(request, principal, "steward.conversation.list",
                                          {"resident_id": resident_id})


@app.post("/api/v1/steward/conversations", status_code=201)
async def steward_create_conversation(body: StewardConversationCreate, request: Request):
    principal = await _steward_principal(request)
    try:
        uuid.UUID(body.client_conversation_id)
    except ValueError as exc:
        raise HTTPException(422, "client_conversation_id must be a UUID") from exc
    return await _website_control_request(
        request, principal, "steward.conversation.create",
        {"resident_id": body.resident_id,
         "client_conversation_id": body.client_conversation_id},
        f"website-conversation:{principal['principal_id']}:{body.client_conversation_id}")


@app.get("/api/v1/steward/conversations/{conversation_id}/messages")
async def steward_conversation_messages(conversation_id: str, request: Request):
    principal = await _steward_principal(request)
    try:
        uuid.UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(422, "conversation_id must be a UUID") from exc
    return await _website_control_request(request, principal, "steward.conversation.messages",
                                          {"conversation_id": conversation_id})


@app.post("/api/v1/steward/conversations/{conversation_id}/messages", status_code=202)
async def steward_send_conversation_message(conversation_id: str, body: StewardConversationMessage,
                                            request: Request):
    principal = await _steward_principal(request, "steward.r3a.read_or_submit")
    try:
        uuid.UUID(conversation_id)
        uuid.UUID(body.client_message_id)
    except ValueError as exc:
        raise HTTPException(422, "conversation_id and client_message_id must be UUIDs") from exc
    return await _website_control_request(
        request, principal, "steward.conversation.send",
        {"conversation_id": conversation_id, "client_message_id": body.client_message_id,
         "text": body.text},
        f"website-message:{conversation_id}:{body.client_message_id}")


@app.get("/api/v1/steward/r3a/status")
async def steward_r3a_status(request: Request):
    settings = await _steward_settings(request)
    from r3a_runtime.control import control_request
    try:
        return await control_request(settings.control_socket, "diagnostics.status", timeout=4.0)
    except Exception as exc:
        raise HTTPException(503, f"R3A diagnostics unavailable: {type(exc).__name__}") from exc


@app.get("/api/v1/steward/about")
async def steward_about(request: Request):
    """Read-only, authenticated version and health projection for Settings/About."""
    settings = await _steward_settings(request)
    from r3a_runtime.control import control_request
    try:
        runtime = await control_request(settings.control_socket, "diagnostics.status", timeout=4.0)
    except Exception as exc:
        raise HTTPException(503, f"Managed runtime status unavailable: {type(exc).__name__}") from exc
    modules = [{key: module.get(key) for key in
                ("module_id", "module_version", "lifecycle_state", "health", "observed_at", "freshness")}
               for module in runtime.get("modules", []) if isinstance(module, dict)]
    processes = {item.get("component_id"): {
        "state": item.get("state"), "health": item.get("health"),
        "freshness": item.get("freshness"), "heartbeat_at": item.get("heartbeat_at")}
        for item in runtime.get("processes", []) if isinstance(item, dict)}
    grace = next((module for module in modules if module["module_id"] == "resident.grace"
                  and module["lifecycle_state"] == "ACTIVE"), None)
    return {"contract": "r3a.website-about.v1", "contract_version": "1.0.0",
            "observed_at": runtime.get("observed_at"),
            "integration_source_revision": os.environ.get("R3A_INTEGRATION_SOURCE_REVISION") or WEBSITE_BUILD_COMMIT,
            "deployed_runtime_revision": runtime.get("implementation_revision"),
            "website_build_revision": WEBSITE_BUILD_COMMIT,
            "website_version": WEBSITE_BUILD_VERSION or "unknown",
            "ring0": processes.get("ring0", {"health": "unknown"}),
            "cme": processes.get("cme", {"health": "unknown"}),
            "grace": {"module_id": "resident.grace",
                      "version": grace.get("module_version") if grace else None,
                      "health": grace.get("health") if grace else "unavailable"},
            "modules": modules, "freshness": runtime.get("source_freshness", "unknown")}


@app.get("/api/v1/steward/r3a/events")
async def steward_r3a_events(request: Request):
    settings = await _steward_settings(request)
    from r3a_runtime.control import control_request
    try:
        return await control_request(settings.control_socket, "diagnostics.events", timeout=4.0)
    except Exception as exc:
        raise HTTPException(503, f"R3A event history unavailable: {type(exc).__name__}") from exc


@app.get("/api/v1/steward/r3a/configuration")
async def steward_r3a_configuration(request: Request):
    settings = await _steward_settings(request)
    from r3a_runtime.control import control_request
    try:
        current, history = await asyncio.gather(
            control_request(settings.control_socket, "diagnostics.status", timeout=4.0),
            control_request(settings.control_socket, "diagnostics.events", timeout=4.0),
        )
    except Exception as exc:
        raise HTTPException(503, f"R3A configuration diagnostics unavailable: {type(exc).__name__}") from exc
    configuration = current.get("configuration")
    if not isinstance(configuration, dict):
        raise HTTPException(503, "R3A configuration revision is unavailable")
    activations = [event for event in history.get("events", [])
                   if event.get("event_type") == "config.activated"]
    return {
        "observed_at": current.get("observed_at"),
        "source": current.get("source", "unknown"),
        "revision": {key: configuration.get(key) for key in
                     ("revision_id", "schema_version", "source_digest", "activated_at", "actor")},
        "effective_values": configuration.get("config", {}),
        "activation_history": [{key: event.get(key) for key in
                                ("event_id", "occurred_at", "actor", "config_revision", "reason")}
                               for event in activations],
        "history_window": len(history.get("events", [])),
        "history_complete": False,
        "write_available": False,
    }


@app.post("/api/v1/steward/r3a/objectives", status_code=202)
async def submit_grace_objective(request: GraceObjectiveRequest, http_request: Request):
    settings = await _steward_settings(http_request)
    from r3a_runtime.control import control_request
    try:
        result = await control_request(settings.control_socket, "grace.objective.submit", {
            "objective": request.objective,
            "event_kind": "objective",
            "acceptance_criteria": request.acceptance_criteria,
            "task_class": "objective_reasoning",
        }, idempotency_key=request.idempotency_key, timeout=6.0)
        return {"contract": "r3a.grace-objective-submission.v1", "contract_version": "1.0.0", **result}
    except Exception as exc:
        raise HTTPException(503, f"Grace objective was not accepted: {type(exc).__name__}") from exc


@app.middleware("http")
async def steward_no_store_headers(request, call_next):
    response = await call_next(request)
    if (request.url.path.startswith("/api/v1/steward/")
            or request.url.path.startswith("/api/v1/notifications")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# Authenticated access is opt-in and fails closed when explicitly configured but invalid.
# There is no default listener, identity, credential, session store, or public route exposure.
if os.environ.get("R3A_STEWARD_ACCESS_CONFIG"):
    from r3a_runtime.steward_access import create_access_from_environment
    app.state.steward_access = create_access_from_environment()
    app.include_router(app.state.steward_access.router())
else:
    app.state.steward_access = None

def git(*args):
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                       text=True, timeout=12, check=False)
    if p.returncode:
        raise HTTPException(503, "Git information unavailable")
    return p.stdout.strip()

@app.get("/api/v1/health")
def health():
    return {"service": "r3", "status": "running", "repository_present": (ROOT / ".git").exists(),
            "artwork_directory_present": ART.is_dir()}

@app.get("/api/v1/engineering/branches")
def branches():
    lines = git("for-each-ref", "--format=%(refname:short)%09%(objectname)%09%(committerdate:iso8601)", "refs/heads/")
    return {"repository": "R3", "branches": [
        {"name": parts[0], "commit": parts[1], "last_commit_at": parts[2]}
        for line in lines.splitlines() if len(parts := line.split("\t")) == 3
    ], "activity_note": "Commit recency does not establish an active worker"}

@app.get("/api/v1/engineering/worktrees")
def worktrees():
    raw = git("worktree", "list", "--porcelain")
    entries = []
    for block in raw.split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        if fields.get("worktree"):
            entries.append({"path": fields["worktree"], "commit": fields.get("HEAD"),
                            "branch": fields.get("branch"), "locked": "locked" in block})
    return {"worktrees": entries, "activity_note": "A checked-out worktree is not proof of active execution"}

LATEST_BROWSER_CAPTURE = None

def artwork_files():
    if not ART.is_dir():
        return []
    return sorted((p for p in ART.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS),
                  key=lambda p: p.relative_to(ART).as_posix())

@app.get("/api/v1/artwork")
def artwork():
    return {"source": "local_git_checkout", "items": [
        {"path": p.relative_to(ART).as_posix(), "bytes": p.stat().st_size,
         "url": "/api/v1/artwork/file/" + p.relative_to(ART).as_posix()}
        for p in artwork_files()]}

@app.get("/api/v1/artwork/file/{relative_path:path}")
def artwork_file(relative_path: str):
    path = (ART / relative_path).resolve()
    if not path.is_relative_to(ART) or path.suffix.lower() not in EXTENSIONS or not path.is_file():
        raise HTTPException(404, "Artwork not found")
    return FileResponse(path)

# Visual prototype: source approved art directly from preserved ZIP; do not use substitute imagery.
ZIP_PATH = ROOT / "assets" / "visual-concepts" / "Riverview3_Visual_Concept_Library.zip"
VISUAL_NAME = "Riverview3_Visual_Concept_Library/backgrounds/R3_modern_estate_clean_concept.png"

@app.get("/")
def visual_home():
    page = ROOT / "web" / "index.html"
    if not page.is_file():
        raise HTTPException(404, "Visual prototype not installed")
    return FileResponse(page, media_type="text/html")


@app.get("/favicon.svg")
def website_favicon():
    icon = ROOT / "web" / "favicon.svg"
    if not icon.is_file():
        raise HTTPException(404, "Website icon unavailable")
    return FileResponse(icon, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/web/resident-avatar.js")
def resident_avatar_module():
    """Serve the fixed R3 website module; no request-controlled filesystem path."""
    module = ROOT / "web" / "resident-avatar.js"
    if not module.is_file():
        raise HTTPException(404, "Resident avatar module unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/steward")
def steward_access_page():
    """Serve the same-origin mobile-friendly Steward access interface."""
    page = ROOT / "web" / "steward.html"
    if not page.is_file():
        raise HTTPException(404, "Steward access interface unavailable")
    return FileResponse(page, media_type="text/html", headers={
        "Cache-Control": "no-store",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    })


@app.get("/web/steward.js")
def steward_access_script():
    script = ROOT / "web" / "steward.js"
    if not script.is_file():
        raise HTTPException(404, "Steward access interface unavailable")
    return FileResponse(script, media_type="text/javascript", headers={"Cache-Control": "no-cache",
                       "X-Content-Type-Options": "nosniff"})
@app.get("/web/steward-workspace-api.mjs")
def steward_workspace_module():
    """Serve the same-origin client for the versioned Steward workspace APIs."""
    module = ROOT / "web" / "steward-workspace-api.mjs"
    if not module.is_file():
        raise HTTPException(404, "Steward workspace client unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/web/roadmap-status.mjs")
def roadmap_status_module():
    module = ROOT / "web" / "roadmap-status.mjs"
    if not module.is_file():
        raise HTTPException(404, "Roadmap status interface unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache",
                       "X-Content-Type-Options": "nosniff"})



def _base_snapshot():
    try:
        source_commit = git("rev-parse", "HEAD")
        source_branch = git("branch", "--show-current") or "detached"
        working_tree_clean = not bool(git("status", "--porcelain"))
    except HTTPException:
        source_commit, source_branch, working_tree_clean = None, None, None

    if not ZIP_PATH.is_file():
        raise HTTPException(503, "Approved visual archive unavailable")
    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            data = archive.read(VISUAL_NAME)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(503, "Approved visual background unavailable") from exc
    if len(data) < 24 or data[:8] != bytes([137, 80, 78, 71, 13, 10, 26, 10]):
        raise HTTPException(503, "Approved visual background is not a valid PNG")
    width, height = struct.unpack(">II", data[16:24])

    return {
        "schema_version": "r3.website.diagnostic-snapshot.v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "service": {"name": "r3", "status": "running", "api_version": app.version},
        "source": {
            "repository": "R3",
            "branch": source_branch,
            "commit": source_commit,
            "working_tree_clean": working_tree_clean,
        },
        "runtime": {"python": platform.python_version(), "platform": platform.system()},
        "artwork": {
            "file": Path(VISUAL_NAME).name,
            "media_type": "image/png",
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "width_px": width,
            "height_px": height,
        },
        "ui_contract": {
            "engineering_entrance_image_fraction": {"x": 0.377, "y": 0.653},
            "minimized_opacity": 0.45,
            "background_rendering": "cover",
        },
        "engineering": {
            "branches": branches()["branches"],
            "worktrees": worktrees()["worktrees"],
        },
        "privacy": {
            "credentials": "excluded",
            "environment_variables": "excluded",
            "absolute_paths": "excluded",
            "arbitrary_file_contents": "excluded",
        },
    }


def _number(value, minimum, maximum):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and minimum <= value <= maximum


def _validate_browser_capture(payload):
    viewport = payload.get("viewport_css_px")
    panel = payload.get("panel")
    rect = panel.get("rect_css_px") if isinstance(panel, dict) else None
    dpr = payload.get("device_pixel_ratio")
    anchor = payload.get("entrance_anchor_image_fraction")
    infrastructure_anchor = payload.get("infrastructure_anchor_image_fraction")
    image_size = payload.get("background_intrinsic_px")
    if not isinstance(viewport, dict) or not _number(viewport.get("width"), 1, 10000) or not _number(viewport.get("height"), 1, 10000):
        raise HTTPException(422, "Invalid viewport dimensions")
    if not _number(dpr, 0.1, 8) or not isinstance(panel, dict) or panel.get("state") not in {"minimized", "expanded"}:
        raise HTTPException(422, "Invalid browser panel state")
    if not isinstance(rect, dict) or any(not _number(rect.get(k), -1000, 12000) for k in ("x", "y", "width", "height")):
        raise HTTPException(422, "Invalid panel rectangle")
    if rect["width"] < 1 or rect["height"] < 1 or not _number(panel.get("opacity"), 0, 1):
        raise HTTPException(422, "Invalid panel size or opacity")
    if not isinstance(anchor, dict) or any(not _number(anchor.get(k), 0, 1) for k in ("x", "y")):
        raise HTTPException(422, "Invalid image anchor")
    if infrastructure_anchor is not None and (not isinstance(infrastructure_anchor, dict) or any(not _number(infrastructure_anchor.get(k), 0, 1) for k in ("x", "y"))):
        raise HTTPException(422, "Invalid Infrastructure anchor")
    if not isinstance(image_size, dict) or any(not _number(image_size.get(k), 1, 20000) for k in ("width", "height")):
        raise HTTPException(422, "Invalid background dimensions")
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "viewport_css_px": {"width": viewport["width"], "height": viewport["height"]},
        "device_pixel_ratio": dpr,
        "panel": {
            "state": panel["state"],
            "rect_css_px": {k: rect[k] for k in ("x", "y", "width", "height")},
            "opacity": panel["opacity"],
        },
        "entrance_anchor_image_fraction": {"x": anchor["x"], "y": anchor["y"]},
        "background_intrinsic_px": {"width": image_size["width"], "height": image_size["height"]},
        **({"infrastructure_anchor_image_fraction": {"x": infrastructure_anchor["x"], "y": infrastructure_anchor["y"]}} if infrastructure_anchor is not None else {}),
    }


@app.get("/api/v1/snapshot")
def snapshot():
    """Return a bounded read-only snapshot, including the latest browser capture if available."""
    result = _base_snapshot()
    result["browser"] = LATEST_BROWSER_CAPTURE or {"status": "not captured"}
    return result


@app.post("/api/v1/snapshot")
def capture_snapshot(browser: dict = Body(...)):
    """Accept one bounded browser geometry capture and expose it through the snapshot API."""
    global LATEST_BROWSER_CAPTURE
    LATEST_BROWSER_CAPTURE = _validate_browser_capture(browser)
    result = _base_snapshot()
    result["browser"] = LATEST_BROWSER_CAPTURE
    return result


@app.get("/api/v1/visual/background")
def visual_background():
    if not ZIP_PATH.is_file():
        raise HTTPException(503, "Approved visual archive unavailable")
    try:
        with zipfile.ZipFile(ZIP_PATH) as archive:
            if VISUAL_NAME not in archive.namelist():
                raise HTTPException(503, "Approved background missing from archive")
            data = archive.read(VISUAL_NAME)
    except (OSError, zipfile.BadZipFile) as exc:
        raise HTTPException(503, "Approved visual archive unreadable") from exc
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
