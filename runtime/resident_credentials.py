"""Read explicitly provisioned resident credentials; never issue or log them."""
from __future__ import annotations

import os
import re
from pathlib import Path


def load_resident_credential(directory: Path | None, resident: str) -> str | None:
    if directory is None:
        return None
    if not isinstance(resident, str) or not resident or not resident.isidentifier():
        raise ValueError("Invalid resident credential identity")
    path = directory / (resident + ".credential")
    if not path.exists():
        return None
    if path.is_symlink():
        raise PermissionError("Resident credential symlink prohibited")
    stat = path.stat()
    if not path.is_file() or stat.st_mode & 0o077:
        raise PermissionError("Resident credential must be a private regular file")
    if stat.st_uid != os.geteuid():
        raise PermissionError("Resident credential owner mismatch")
    value = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(
        r"r3resident_v1\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}",
        value,
    ):
        raise ValueError("Invalid resident credential format")
    return value
