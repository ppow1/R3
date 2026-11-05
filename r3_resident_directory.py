"""Public website resident directory projection; never an HR authority or authorization grant."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from fastapi import HTTPException

DEFAULT_PATH = Path(__file__).resolve().parent / "config" / "website-residents.json"
RESIDENT_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

def load_residents(path: Path | None = None) -> list[dict]:
    path = path or Path(os.environ.get("R3_WEBSITE_RESIDENTS_CONFIG", str(DEFAULT_PATH)))
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Resident directory configuration unavailable") from exc
    rows = raw.get("residents") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(503, "Resident directory configuration invalid")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not RESIDENT_ID.fullmatch(row["id"]) or row["id"] in seen:
            raise HTTPException(503, "Resident directory configuration invalid")
        seen.add(row["id"])
        for field in ("name", "position", "department"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise HTTPException(503, "Resident directory configuration invalid")
        # Protected residents are not listed without a future explicit authorization contract.
        if row.get("visibility") == "protected":
            continue
        result.append({key: row[key] for key in ("id", "name", "position", "department")})
    return result

def require_resident(resident_id: str) -> dict:
    for resident in load_residents():
        if resident["id"] == resident_id:
            return resident
    raise HTTPException(404, "Resident unavailable")
