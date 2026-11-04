"""Guarded local JSON configuration API for the R3 settings workbench."""
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Body, HTTPException, Query

_LOCK = threading.RLock()
_LIMIT = 1_048_576
_SECRET_KEY = re.compile(r"(secret|token|password|credential|private.?key|api.?key)", re.I)
_REDACTED = "[REDACTED]"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _load_json(path, fallback=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _scope(relative, registry):
    name = PurePosixPath(relative).as_posix()
    mapping = registry.get("path_scope_prefixes", {}) if isinstance(registry, dict) else {}
    for prefix, scope in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
        if name.startswith(prefix):
            return scope
    return "Institutional"


def _secret_fields(value, path=()):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = path + (key,)
            if _SECRET_KEY.search(key) and item not in (None, "", _REDACTED):
                found.append(next_path)
            else:
                found.extend(_secret_fields(item, next_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_secret_fields(item, path + (index,)))
    return found


def _redact(value):
    if isinstance(value, dict):
        return {key: (_REDACTED if _SECRET_KEY.search(key) and item not in (None, "") else _redact(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def build_settings_router(root):
    root = Path(root).resolve()
    control_root = (root / "config").resolve()
    router = APIRouter()
    lock = _LOCK

    def registry():
        data = _load_json(control_root / "settings-registry.json", {})
        return data if isinstance(data, dict) else {}

    def policy():
        data = _load_json(control_root / "settings-access.json", {})
        return data if isinstance(data, dict) else {}

    def settings_root():
        config = registry()
        configured = os.environ.get("R3_SETTINGS_CONFIG_ROOT") or config.get("configuration_root")
        path = Path(configured).expanduser() if configured else control_root
        if not path.is_absolute():
            path = root / path
        return path.resolve()

    def resolve(relative, allow_missing=False):
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise HTTPException(422, "Invalid configuration path")
        part = PurePosixPath(relative)
        if part.is_absolute() or any(piece in ("", ".", "..") for piece in part.parts) or part.suffix.lower() != ".json":
            raise HTTPException(422, "Only relative JSON configuration paths are supported")
        data_root = settings_root()
        path = (data_root.joinpath(*part.parts)).resolve()
        if not path.is_relative_to(data_root) or (path.exists() and path.is_symlink()):
            raise HTTPException(422, "Configuration path escapes the config directory")
        if not allow_missing and not path.is_file():
            raise HTTPException(404, "Configuration file not found")
        return path, part.as_posix()

    def authorize(cfg):
        if cfg.get("write_enabled") is not True:
            raise HTTPException(423, "Settings write mode is disabled by local policy")

    def manifest_file(path, relative, cfg, reg):
        try:
            raw = path.read_bytes()
            doc = json.loads(raw.decode("utf-8"))
            valid = isinstance(doc, dict)
            err = None if valid else "JSON root must be an object"
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raw, doc, valid, err = b"", None, False, str(exc)
        return {
            "path": relative,
            "scope": _scope(relative, reg),
            "sha256": _sha(raw) if raw else None,
            "bytes": len(raw),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat() if path.exists() else None,
            "valid": valid,
            "error": err,
            "protected": relative == "settings-access.json",
            "writeable_by_policy": cfg.get("write_enabled") is True and relative != "settings-access.json",
        }

    @router.get("/api/v1/settings/catalog")
    def get_catalog():
        source = root / "web" / "settings-catalog.json"
        if source.is_symlink() or not source.is_file():
            raise HTTPException(404, "Settings presentation catalog is unavailable")
        path = source.resolve()
        if not path.is_relative_to(root):
            raise HTTPException(404, "Settings presentation catalog is unavailable")
        data = _load_json(path)
        if not isinstance(data, dict):
            raise HTTPException(500, "Settings presentation catalog is invalid")
        return data

    @router.get("/api/v1/settings/references/prompts")
    def get_prompt_references():
        data_root = settings_root()
        prompt_root = data_root / "residents" / "prompts"
        if not prompt_root.is_dir() or prompt_root.is_symlink():
            return {"paths": []}
        safe_root = prompt_root.resolve()
        if not safe_root.is_relative_to(data_root):
            return {"paths": []}
        paths = []
        for path in sorted(safe_root.rglob("*.md")):
            if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(safe_root):
                paths.append(path.relative_to(data_root).as_posix())
        return {"paths": paths}

    @router.get("/api/v1/settings/manifest")
    def get_manifest():
        cfg, reg = policy(), registry()
        data_root = settings_root()
        files = []
        if data_root.is_dir():
            for path in sorted(data_root.rglob("*.json")):
                if path.is_file() and not path.is_symlink():
                    relative = path.relative_to(data_root).as_posix()
                    files.append(manifest_file(path, relative, cfg, reg))
        scopes = reg.get("scopes", [])
        return {
            "schema_version": "r3.settings.manifest.v1",
            "files": files,
            "scopes": scopes,
            "inheritance": reg.get("inheritance", {"status": "not_defined"}),
            "write_enabled": cfg.get("write_enabled") is True,
            "write_policy_source": "config/settings-access.json",
            "configuration_root": reg.get("configuration_root_label", "local persistent R3 configuration"),
            "source_label": reg.get("source_label", "local persistent R3 configuration"),
            "runtime_activation": reg.get("runtime_activation", "Runtime activation is not registered."),
            "validation": "JSON syntax and object-root validation; runtime schema validators are reported per file when available.",
        }

    @router.get("/api/v1/settings/file")
    def get_file(path: str = Query(...)):
        file, relative = resolve(path)
        try:
            raw = file.read_bytes()
            if len(raw) > _LIMIT:
                raise HTTPException(413, "Configuration file exceeds 1 MiB")
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(422, "Configuration file contains invalid JSON") from exc
        if not isinstance(doc, dict):
            raise HTTPException(422, "Configuration JSON root must be an object")
        return {
            "path": relative,
            "sha256": _sha(raw),
            "document": _redact(doc),
            "redacted": bool(_secret_fields(doc)),
            "protected": relative == "settings-access.json",
            "scope": _scope(relative, registry()),
            "history": _history_entries(root, relative),
        }

    @router.get("/api/v1/settings/history")
    def get_history(path: str = Query(...)):
        _, relative = resolve(path)
        return {"path": relative, "entries": _history_entries(root, relative)}

    @router.put("/api/v1/settings/file")
    def put_file(body: dict = Body(...)):
        relative = body.get("path")
        file, relative = resolve(relative, allow_missing=True)
        cfg = policy()
        authorize(cfg)
        if relative == "settings-access.json":
            raise HTTPException(403, "The write gate is managed outside the settings editor")
        document = body.get("document")
        if not isinstance(document, dict):
            raise HTTPException(422, "Configuration must be a JSON object")
        encoded = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if len(encoded) > _LIMIT:
            raise HTTPException(413, "Configuration file exceeds 1 MiB")
        if _secret_fields(document):
            raise HTTPException(422, "Secret-bearing fields cannot be written through the browser editor")
        expected = body.get("expected_sha256")
        with lock:
            existing = file.read_bytes() if file.exists() else b""
            current = _sha(existing) if existing else None
            if expected != current:
                raise HTTPException(409, "Configuration changed since it was loaded; reload before saving")
            if existing:
                try:
                    old = json.loads(existing.decode("utf-8"))
                    if not isinstance(old, dict):
                        raise ValueError()
                except (UnicodeDecodeError, ValueError):
                    raise HTTPException(422, "Existing configuration is invalid and was not overwritten")
                for key_path in _secret_fields(old):
                    target = document
                    for part in key_path[:-1]:
                        target = target.get(part, {}) if isinstance(target, dict) else {}
                    if isinstance(target, dict) and key_path[-1] not in target:
                        source = old
                        for part in key_path[:-1]:
                            source = source[part]
                        target[key_path[-1]] = source[key_path[-1]]
                encoded = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            history_root = root / "var" / "config-history"
            history_file = history_root / stamp / relative
            history_file.parent.mkdir(parents=True, exist_ok=True)
            if existing:
                history_file.write_bytes(existing)
            file.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=str(file.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, file)
                dir_fd = os.open(file.parent, os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            entry = {
                "changed_at": datetime.now(timezone.utc).isoformat(),
                "path": relative,
                "before_sha256": current,
                "after_sha256": _sha(encoded),
                "bytes": len(encoded),
            }
            index = history_root / "index.jsonl"
            with index.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return {"saved": True, **entry, "restart_required": True}

    return router


def _history_entries(root, relative):
    index = Path(root) / "var" / "config-history" / "index.jsonl"
    if not index.is_file():
        return []
    entries = []
    try:
        for line in index.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("path") == relative:
                entries.append(item)
    except (OSError, ValueError):
        return []
    return list(reversed(entries[-20:]))
