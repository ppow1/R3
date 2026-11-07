"""Bounded workspace file provider used for isolated Engineering operations."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any


class IsolatedWorkspaceProvider:
    def __init__(self, configuration: dict[str, Any]):
        self.root = Path(configuration["workspace_root"]).resolve(strict=True)

    def invoke(self, arguments: dict[str, Any], *, context: dict[str, Any]) -> dict[str, Any]:
        relative = arguments["path"]
        if (not isinstance(relative, str) or relative.startswith("/") or "\\" in relative
                or any(part in {"", ".", ".."} for part in relative.split("/"))):
            raise ValueError("workspace path must be normalized and relative")
        order = context["work_order"]
        if context["effect_class"] != "isolated_write" or context["target"]["workspace_id"] != order["workspace_id"]:
            raise PermissionError("provider target is outside the authorized isolated workspace")
        if not any(relative == pattern.removesuffix("**").rstrip("/")
                   or (pattern.endswith("**") and relative.startswith(pattern[:-2]))
                   for pattern in order["allowed_paths"]):
            raise PermissionError("workspace path is outside the work-order allowlist")
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise PermissionError("workspace path escapes its configured root")
        payload = arguments["content"].encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            existing = destination.read_bytes()
            if existing != payload:
                raise FileExistsError("idempotent target already contains different bytes")
            return {"path": relative, "sha256": hashlib.sha256(existing).hexdigest(),
                    "bytes_written": 0, "replayed": True}
        temporary = destination.with_name(destination.name + "." + context["invocation_id"] + ".tmp")
        created = False
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, destination)
                created = True
            except FileExistsError:
                if destination.read_bytes() != payload:
                    raise FileExistsError("concurrent invocation wrote different bytes")
            return {"path": relative, "sha256": digest, "bytes_written": len(payload),
                    "replayed": not created}
        finally:
            temporary.unlink(missing_ok=True)


def create_provider(configuration: dict[str, Any]) -> IsolatedWorkspaceProvider:
    return IsolatedWorkspaceProvider(configuration)
