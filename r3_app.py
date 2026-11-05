# R3 CONTROLLED SOURCE
# File: r3_app.py
# Component: R3-APP
# File Revision: 1.0.12
# Created: Unknown (legacy; initial commit can establish earliest publication)
# Created By: Unknown (legacy)
# Purpose: Initial shared read-only institutional API
# Execution Model: Request-driven FastAPI service
# Observability: HTTP health endpoint; no deployed verification
# Dependencies: FastAPI, Git checkout, local artwork folder
# Authority: R3 engineering guidance; approved charter prevails
# Changed: 2026-11-02 UTC | R3-AVATAR-001 | ChatGPT GPT-6 | Serve the fixed resident avatar frontend module
# Changed: 2026-11-03 UTC | R3-SETTINGS-WORKBENCH-001 | ChatGPT GPT-6 | Connect settings UI to guarded local JSON configuration API
# Changed: 2026-11-01 UTC | R3-PANEL-INTERACTION-002 | ChatGPT GPT-6 | Align snapshot anchors and report dragged Infrastructure marker
# Changed: 2026-11-05 UTC | HR-010 | Initialize persistent HR capability inside R3 app lifecycle
# Changed: 2026-11-05 UTC | R3-AUTH-REGRESSION-001 | Avoid loading unrelated chat configuration before rejecting anonymous requests.
# Supersedes: None
# Contracts: hints/file-provenance.md
# Tests: Not run for this source change; module route and browser verification pending
# History/Predecessor: Git blob b3195f5a0ea8bacc030b642bc3dbb76258a4e747; prior revision in commit 8750557799b19a00fc976496fd345feae4bbc547.

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
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Body, Request
from fastapi.responses import FileResponse, Response
from r3_settings_api import build_settings_router
from r3_chat_api import build_chat_router

ROOT = Path(os.environ.get("R3_REPO", Path(__file__).resolve().parent)).resolve()
ART = (ROOT / "assets" / "artwork").resolve()
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
app = FastAPI(title="R3 Institutional Capabilities", version="0.1.0")
app.include_router(build_settings_router(ROOT))
app.include_router(build_chat_router())

# R3-native sitewide Steward authentication.
from r3_native_auth_api import build_native_auth_router
app.include_router(build_native_auth_router(
    allowed_origins=("https://riverview.ionoge.com",)
))

# The HR capability lives in this R/3 process. No separate HR service or MCP
# dependency. Host-internal callers supply their already-established principal
# and authorization callback; browser requests cannot select either.
def get_hr_capability(principal, authorize):
    from runtime.hr_capability import HRCapability, VerifiedPrincipal
    from runtime.hr_store import HRStore
    if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
        raise PermissionError("verified R3 principal required")
    db_path = os.environ.get("R3_HR_DB_PATH")
    if not db_path:
        raise RuntimeError("R3_HR_DB_PATH is not configured")
    return HRCapability(HRStore(db_path), authorize)

def hr_storage_status():
    db_path = os.environ.get("R3_HR_DB_PATH")
    if not db_path:
        return "unconfigured"
    return "ready" if Path(db_path).parent.is_dir() else "storage_unavailable"


def git(*args):
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                       text=True, timeout=12, check=False)
    if p.returncode:
        raise HTTPException(503, "Git information unavailable")
    return p.stdout.strip()



# R3-SITE-AUTH-001
# R3-native Steward session verification; no R2 authentication dependency.
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from r3_chat_api import _principal as _auth_principal

_PUBLIC_ROUTES = frozenset({
    "/login",
    "/api/v1/native-auth/login",
    "/api/v1/health",
    "/api/v1/chat/login",
    "/api/v1/chat/password-reset",
    "/api/v1/chat/session",
})

@app.middleware("http")
async def r3_site_authentication(request: Request, call_next):
    path = request.scope.get("path", request.url.path)

    resident_delegation = (
        path == "/api/v1/steward-authority/delegate"
        and request.method == "POST"
    )
    if (path not in _PUBLIC_ROUTES and not resident_delegation) or (
        path == "/api/v1/chat/session" and request.method == "DELETE"
    ):
        try:
            # Site authorization depends on the native session store. The chat
            # proxy configuration is unrelated and may be unavailable while a
            # valid anonymous request still needs a 401 or login redirect.
            _auth_principal(request, {})
        except HTTPException as exc:
            if exc.status_code in (401, 403):
                if path == "/" and request.method == "GET":
                    prefix = "/r3" if request.headers.get("x-forwarded-prefix") == "/r3" else ""
                    return RedirectResponse(
                        prefix + "/login",
                        status_code=303,
                        headers={"Cache-Control": "no-store"}
                    )
                return JSONResponse(
                    {"detail": "Steward authentication required"},
                    status_code=401,
                    headers={"Cache-Control": "no-store"}
                )
            return JSONResponse(
                {"detail": "Authentication service unavailable"},
                status_code=503,
                headers={"Cache-Control": "no-store"}
            )

    response = await call_next(request)
    if path == "/login" or path.startswith("/api/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/login")
def r3_login_page():
    return HTMLResponse("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>R3 Steward Sign In</title>
<style>
body{font:16px system-ui;background:#111c28;color:#f2f5f9;
display:grid;place-items:center;min-height:95vh}
main{width:min(380px,90vw);padding:28px;
border:1px solid #526175;border-radius:12px}
label{display:block;margin:14px 0}
input{box-sizing:border-box;width:100%;padding:10px;margin-top:6px}
button{padding:10px 18px;margin-right:8px;cursor:pointer}
</style>
</head>
<body>
<main>
<h1>R3 Steward Sign In</h1>
<form id="login">
<label>Email<input name="email" type="email"
autocomplete="username" required></label>
<label>Password<input name="password" type="password"
autocomplete="current-password" required></label>
<button type="submit">Sign in</button>
<button id="reset" type="button">Reset password</button>
</form>
<p id="status" role="status" aria-live="polite"></p>
</main>
<script>
const base=location.pathname.startsWith('/r3/')?'/r3':'';
const form=document.getElementById('login');
const status=document.getElementById('status');
form.addEventListener('submit',async e=>{
 e.preventDefault();
 status.textContent='Signing in...';
 try{
  const r=await fetch(base+'/api/v1/chat/login',{
   method:'POST',credentials:'same-origin',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({
    email:form.elements.email.value,
    password:form.elements.password.value
   })
  });
  if(!r.ok){status.textContent='Sign-in unsuccessful';return;}
  location.assign(base+'/');
 }catch(_){status.textContent='Sign-in service unavailable';}
});
document.getElementById('reset').addEventListener('click',async()=>{
 const email=form.elements.email.value;
 if(!email){status.textContent='Enter your email first';return;}
 try{
  await fetch(base+'/api/v1/chat/password-reset',{
   method:'POST',credentials:'same-origin',
   headers:{'Content-Type':'application/json'},
   body:JSON.stringify({email})
  });
  status.textContent='If eligible, recovery instructions will be sent.';
 }catch(_){status.textContent='Recovery service unavailable';}
});
</script>
</body>
</html>""",headers={
 "Cache-Control":"no-store",
 "Content-Security-Policy":
 "default-src 'none'; script-src 'unsafe-inline'; "
 "style-src 'unsafe-inline'; connect-src 'self'; "
 "form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
})

@app.middleware("http")
async def r3_subpath_adapter(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("x-forwarded-prefix") != "/r3" or not (response.headers.get("content-type", "").startswith("text/html")):
        return response
    chunks = [chunk async for chunk in response.body_iterator]
    page = b"".join(chunks).decode("utf-8")
    page = page.replace('href="/web/', 'href="/r3/web/')
    page = page.replace('src="/web/', 'src="/r3/web/')
    page = page.replace('src="/assets/', 'src="/r3/assets/')
    page = page.replace("url('/assets/", "url('/r3/assets/")
    page = page.replace('url("/assets/', 'url("/r3/assets/')
    prefix = "<script>window.R3_BASE='/r3';const __r3fetch=window.fetch.bind(window);window.fetch=(input,opts)=>{let u=typeof input==='string'?input:input.url;if(u.startsWith('/api/v1/')&&!u.startsWith('/api/v1/auth/')){u='/r3'+u;input=typeof input==='string'?u:new Request(u,input)}return __r3fetch(input,opts)};</script>"
    page = page.replace("<head>", "<head>" + prefix, 1)
    return Response(page, status_code=response.status_code, media_type="text/html", headers={"Cache-Control": "no-store"})

@app.get("/api/v1/health")
def health():
    return {"service": "r3", "status": "running", "repository_present": (ROOT / ".git").exists(),
            "artwork_directory_present": ART.is_dir(), "hr_storage": hr_storage_status()}

@app.get("/api/v1/institution/runtime")
def institution_runtime():
    """Return a fresh, read-only runtime health snapshot to website observers."""
    import json
    health_path = Path(os.environ.get("R3_RUNTIME_HEALTH_FILE", "/home/admin1/.local/state/r3-runtime/health.json")).expanduser()
    try:
        if health_path.stat().st_size > 1048576:
            raise ValueError("snapshot exceeds size limit")
        payload = json.loads(health_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Institutional runtime telemetry unavailable") from exc
    if not isinstance(payload, dict):
        raise HTTPException(503, "Institutional runtime telemetry invalid")
    observed_at = payload.get("observed_at")
    if isinstance(observed_at, bool) or not isinstance(observed_at, (int, float)):
        raise HTTPException(503, "Institutional runtime timestamp unavailable")
    age = datetime.now(timezone.utc).timestamp() - observed_at
    if age < 0 or age > 15:
        raise HTTPException(503, "Institutional runtime telemetry stale")
    raw_state = payload.get("state")
    if not isinstance(raw_state, dict):
        raise HTTPException(503, "Institutional runtime state unavailable")
    def number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    catalog = raw_state.get("state_catalog")
    safe_catalog = {}
    if isinstance(catalog, dict):
        safe_catalog = {str(k): int(v) for k, v in catalog.items()
                        if isinstance(k, str) and number(v) and int(v) == v}
    residents = raw_state.get("residents")
    safe_residents = []
    if isinstance(residents, list):
        for resident in residents:
            if not isinstance(resident, dict):
                continue
            row = {}
            for key in ("name", "state"):
                if isinstance(resident.get(key), str):
                    row[key] = resident[key]
            for key in ("state_number", "heartbeat", "failures"):
                if number(resident.get(key)):
                    row[key] = resident[key]
            safe_residents.append(row)
    events = raw_state.get("events")
    safe_events = []
    if isinstance(events, list):
        for event in events[-100:]:
            if not isinstance(event, dict):
                continue
            row = {}
            for key in ("resident", "kind", "state", "reason"):
                if isinstance(event.get(key), str):
                    row[key] = event[key]
            for key in ("at", "id", "state_number"):
                if number(event.get(key)):
                    row[key] = event[key]
            safe_events.append(row)
    result = {
        "observed_at": observed_at,
        "registered_residents": payload.get("registered_residents")
            if number(payload.get("registered_residents")) else len(safe_residents),
        "supervisor_age_seconds": payload.get("supervisor_age_seconds")
            if number(payload.get("supervisor_age_seconds")) else None,
        "state": {"state_catalog": safe_catalog, "residents": safe_residents, "events": safe_events},
    }
    from fastapi.responses import JSONResponse
    return JSONResponse(result, headers={"Cache-Control": "no-store"})

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


@app.get("/web/resident-avatar.js")
def resident_avatar_module():
    """Serve the fixed R3 website module; no request-controlled filesystem path."""
    module = ROOT / "web" / "resident-avatar.js"
    if not module.is_file():
        raise HTTPException(404, "Resident avatar module unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache"})




@app.get("/web/chat-client.js")
def chat_client_module():
    module = ROOT / "web" / "chat-client.js"
    if not module.is_file():
        raise HTTPException(404, "Chat client unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/web/chat-client.css")
def chat_client_styles():
    stylesheet = ROOT / "web" / "chat-client.css"
    if not stylesheet.is_file():
        raise HTTPException(404, "Chat styles unavailable")
    return FileResponse(stylesheet, media_type="text/css", headers={"Cache-Control": "no-cache"})


@app.get("/web/settings-workbench.js")
def settings_workbench_module():
    module = ROOT / "web" / "settings-workbench.js"
    if not module.is_file():
        raise HTTPException(404, "Settings workbench module unavailable")
    return FileResponse(module, media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/web/settings-workbench.css")
def settings_workbench_styles():
    stylesheet = ROOT / "web" / "settings-workbench.css"
    if not stylesheet.is_file():
        raise HTTPException(404, "Settings workbench stylesheet unavailable")
    return FileResponse(stylesheet, media_type="text/css", headers={"Cache-Control": "no-cache"})


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

from r3_steward_authority_api import build_steward_authority_router
app.include_router(build_steward_authority_router(ROOT))


# R3-STEWARD-AUTHORITY-ASSET-ROUTES
# These routes remain behind the existing site authentication middleware.
@app.get("/web/steward-authority.js", include_in_schema=False)
def steward_authority_javascript():
    return FileResponse(
        ROOT / "web" / "steward-authority.js",
        media_type="application/javascript",
    )

@app.get("/web/steward-authority.css", include_in_schema=False)
def steward_authority_stylesheet():
    return FileResponse(
        ROOT / "web" / "steward-authority.css",
        media_type="text/css",
    )
