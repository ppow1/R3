# R3 CONTROLLED SOURCE
# File: r3_app.py
# Component: R3-APP
# File Revision: 1.0.6
# Created: Unknown (legacy; initial commit can establish earliest publication)
# Created By: Unknown (legacy)
# Purpose: Initial shared read-only institutional API
# Execution Model: Request-driven FastAPI service
# Observability: HTTP health endpoint; no deployed verification
# Dependencies: FastAPI, Git checkout, local artwork folder
# Authority: R3 engineering guidance; approved charter prevails
# Changed: 2026-11-01 UTC | R3-SNAPSHOT-003 | ChatGPT GPT-6 | Include canonical UI anchor in shared snapshot API
# Supersedes: None
# Contracts: hints/file-provenance.md
# Tests: Not run (metadata-only change)
# History/Predecessor: Git blob b3195f5a0ea8bacc030b642bc3dbb76258a4e747

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
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import FileResponse, Response

ROOT = Path(os.environ.get("R3_REPO", Path(__file__).resolve().parent)).resolve()
ART = (ROOT / "assets" / "artwork").resolve()
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
app = FastAPI(title="R3 Institutional Capabilities", version="0.1.0")

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
        "ui_contract": {\n            "engineering_entrance_image_fraction": {"x": 0.464, "y": 0.328},\n            "minimized_opacity": 0.45,\n            "background_rendering": "cover",\n        },\n        "engineering": {
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
