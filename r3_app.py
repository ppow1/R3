# R3 CONTROLLED SOURCE
# File: r3_app.py
# Component: R3-APP
# File Revision: 1.0.3
# Created: Unknown (legacy; initial commit can establish earliest publication)
# Created By: Unknown (legacy)
# Purpose: Initial shared read-only institutional API
# Execution Model: Request-driven FastAPI service
# Observability: HTTP health endpoint; no deployed verification
# Dependencies: FastAPI, Git checkout, local artwork folder
# Authority: R3 engineering guidance; approved charter prevails
# Changed: 2026-10-31 UTC | R3-VISUAL-003 | ChatGPT GPT-6 | Serve clean approved estate background
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
from pathlib import Path
from fastapi import FastAPI, HTTPException
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
