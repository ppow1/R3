"""Build, verify, stage, and discard immutable resident-executor artifacts.

R3 CONTROLLED SOURCE
File: scripts/r3a_module_release_package.py
Component: R3A-GENERIC-RESIDENT-PACKAGE-TOOL
File Revision: 1.0.5
Created: 2026-11-11T18:59:02Z
Created By: Codex GPT-6
Purpose: Implement a generic, content-addressed package boundary for versioned resident JSON-lines workers.
Execution Model: Deterministic archive build, integrity verification, atomic local staging, and guarded candidate cleanup.
Observability: Release descriptor, package SHA-256, artifact tree digest, immutable install path, and staging result.
Dependencies: Python standard library; existing R3A JSON Schema validator and semantic-version helper.
Authority: AD-024; Roadmap Baseline 1.0 AP0-007/008/009; Modular Plugins #46 Step 70/84. Does not activate modules or edit CME/Ring 0.
Changed: 2026-11-11T18:59:02Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Add generic resident package and staging implementation.
Changed: 2026-11-11T19:00:40Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Add a generic build CLI and verify staged bytes during idempotent installs.
Changed: 2026-11-11T19:04:46Z | R3A-MODULAR-PLUGINS-STEP-70 | Codex GPT-6 | Enforce resident-executor role and preserve failed staging safely.
Changed: 2026-11-11T19:11:23Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Reject link traversal and special files; pair lifecycle effective pins.
Changed: 2026-11-11T19:32:00Z | R3A-MODULAR-PLUGINS-STEP-84 | Codex GPT-6 | Use a distinct versioned release-metadata contract rather than module-manifest v1.
Changed: 2026-11-11T21:54:04Z | R3A-MODULAR-PLUGINS-STEP-129 | Codex GPT-6 | Validate install-root components before resolving or writing.
Supersedes: None.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-release-metadata.v1@1.0.0; r3a.module-process-binding.v1@1.0.0; AP0-M1 r3a.module.v1 JSON-lines protocol.
Tests: tests/test_r3a_module_release_v2.py.
History/Predecessor: New file; reuses module identity, JSON Schema, protocol, and lifecycle contracts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r3a_runtime.capability_contracts import validate_json
from r3a_runtime.module_contracts import semantic_version

RELEASE_SCHEMA = ROOT / "r3a_runtime/schemas/module-release-package.v2.schema.json"
METADATA_SCHEMA = ROOT / "r3a_runtime/schemas/module-release-metadata.v1.schema.json"
PROCESS_BINDING_SCHEMA = ROOT / "r3a_runtime/schemas/module-process-binding.v1.schema.json"
RELEASE_PATH = "RELEASE_MANIFEST.json"
MODULE_METADATA_PATH = "MODULE_METADATA.json"
ARTIFACT_ROOT = "artifact"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MODULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$")
_ENTRYPOINT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_ARGUMENTS = ["--socket", "{socket_path}", "--module-id", "{module_id}",
              "--module-version", "{module_version}", "--config", "{configuration_path}"]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _safe_relative(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("package file path must be normalized relative POSIX text")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")) or str(path) != value:
        raise ValueError(f"unsafe or noncanonical package path: {value}")
    return path


def _tree_digest(files: dict[str, bytes]) -> str:
    records = []
    for name, payload in sorted(files.items()):
        rel = _safe_relative(name)
        records.append(f"{rel.as_posix()}\0{_sha(payload)}\0{len(payload)}\n")
    return _sha(("r3a-module-artifact-tree.v1\n" + "".join(records)).encode("utf-8"))


def _validate_process_binding(binding: Any) -> dict[str, Any]:
    schema = json.loads(PROCESS_BINDING_SCHEMA.read_text(encoding="utf-8"))
    validate_json(binding, schema, path="$.process_binding")
    if binding["protocol_max_minor"] < binding["protocol_min_minor"]:
        raise ValueError("process protocol minor range is reversed")
    if not _ENTRYPOINT.fullmatch(binding["entrypoint"]):
        raise ValueError("process entrypoint must be a Python module path")
    if binding["arguments_template"] != _ARGUMENTS:
        raise ValueError("process arguments must use the standard socket/module/configuration placeholders")
    return dict(binding)


def _validate_module_metadata(metadata: Any, *, expected_module_id: str | None = None,
                              expected_version: str | None = None,
                              expected_artifact_digest: str | None = None) -> dict[str, Any]:
    schema = json.loads(METADATA_SCHEMA.read_text(encoding="utf-8"))
    validate_json(metadata, schema, path="$.module_metadata")
    module_id = metadata.get("module_id")
    version = metadata.get("module_version")
    digest = metadata.get("artifact_digest")
    if not isinstance(module_id, str) or not _MODULE_ID.fullmatch(module_id):
        raise ValueError("module metadata has an invalid module_id")
    semantic_version(version)
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError("module metadata has an invalid artifact_digest")
    if expected_module_id is not None and module_id != expected_module_id:
        raise ValueError("module metadata ID differs from release descriptor")
    if expected_version is not None and version != expected_version:
        raise ValueError("module metadata version differs from release descriptor")
    if expected_artifact_digest is not None and digest != expected_artifact_digest:
        raise ValueError("module metadata artifact digest differs from release descriptor")
    role = metadata["role"]
    if role["contract_id"] != "r3a.resident.executor" or role["contract_version"] != "1.0.0":
        raise ValueError("module metadata must declare the generic resident executor role")
    contract_range = role["execution_contract_range"]
    if contract_range["min_minor"] > contract_range["max_minor"]:
        raise ValueError("resident execution contract minor range is reversed")
    return dict(metadata)


def _release_descriptor(module_metadata: dict[str, Any], process_binding: dict[str, Any],
                        files: dict[str, bytes]) -> dict[str, Any]:
    metadata = _validate_module_metadata(module_metadata)
    binding = _validate_process_binding(process_binding)
    artifact_digest = _tree_digest(files)
    if metadata["artifact_digest"] != artifact_digest:
        raise ValueError("module metadata artifact_digest does not match the packaged file tree")
    entries = [{"path": name, "sha256": _sha(payload), "size_bytes": len(payload)}
               for name, payload in sorted(files.items())]
    descriptor = {
        "schema_id": "r3a.module-release-package.v2",
        "schema_version": 2,
        "module_id": metadata["module_id"],
        "module_version": metadata["module_version"],
        "module_kind": "resident_executor",
        "metadata_ref": MODULE_METADATA_PATH,
        "metadata_sha256": _sha(_json_bytes(metadata)),
        "artifact_digest": artifact_digest,
        "files": entries,
        "process_binding": binding,
    }
    schema = json.loads(RELEASE_SCHEMA.read_text(encoding="utf-8"))
    validate_json(descriptor, schema, path="$.release")
    return descriptor


def build_package(module_metadata: dict[str, Any], process_binding: dict[str, Any],
                  files: dict[str, bytes], output: Path) -> dict[str, Any]:
    """Build a deterministic package from caller-supplied generic module inputs."""
    if not isinstance(files, dict) or not files:
        raise ValueError("package files must be a nonempty path-to-bytes mapping")
    clean_files: dict[str, bytes] = {}
    for name, payload in files.items():
        rel = _safe_relative(name)
        if rel.as_posix() in {RELEASE_PATH, MODULE_METADATA_PATH} or rel.parts[0] == ARTIFACT_ROOT:
            raise ValueError("package source paths collide with reserved package entries")
        if not isinstance(payload, bytes):
            raise ValueError(f"package payload must be bytes: {name}")
        clean_files[rel.as_posix()] = payload
    if len(clean_files) != len(files):
        raise ValueError("package contains duplicate normalized paths")
    metadata = _validate_module_metadata(module_metadata)
    descriptor = _release_descriptor(metadata, process_binding, clean_files)
    entries = {
        RELEASE_PATH: _json_bytes(descriptor),
        MODULE_METADATA_PATH: _json_bytes(metadata),
        **{f"{ARTIFACT_ROOT}/{name}": payload for name, payload in clean_files.items()},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, payload in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(payload))
    packed = buffer.getvalue()
    output.write_bytes(packed)
    return {"path": str(output), "bundle_sha256": _sha(packed), "size_bytes": len(packed),
            "module_id": metadata["module_id"], "module_version": metadata["module_version"],
            "artifact_digest": metadata["artifact_digest"]}


def verify_package(package_path: Path, *, expected_bundle_sha256: str) -> tuple[dict[str, Any], dict[str, bytes], dict[str, Any]]:
    raw = package_path.read_bytes()
    if not isinstance(expected_bundle_sha256, str) or not _SHA256.fullmatch(expected_bundle_sha256):
        raise ValueError("an externally pinned expected bundle SHA-256 is required")
    if _sha(raw) != expected_bundle_sha256:
        raise ValueError("module package bundle digest does not match external pin")
    entries: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            rel = _safe_relative(member.name)
            if not member.isfile() or member.issym() or member.islnk() or member.name in entries:
                raise ValueError(f"package contains unsupported or duplicate entry: {member.name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"package entry is unreadable: {member.name}")
            entries[rel.as_posix()] = handle.read()
    if RELEASE_PATH not in entries or MODULE_METADATA_PATH not in entries:
        raise ValueError("package is missing its release or module metadata")
    descriptor = json.loads(entries[RELEASE_PATH])
    schema = json.loads(RELEASE_SCHEMA.read_text(encoding="utf-8"))
    validate_json(descriptor, schema, path="$.release")
    if descriptor["module_kind"] != "resident_executor":
        raise ValueError("release package v2 currently supports the resident-executor module role")
    declared_paths = {RELEASE_PATH, MODULE_METADATA_PATH,
                      *(f"{ARTIFACT_ROOT}/{item['path']}" for item in descriptor["files"])}
    if set(entries) != declared_paths:
        raise ValueError("package archive has undeclared entries")
    expected_files = {item["path"]: item for item in descriptor["files"]}
    actual_artifacts = {name[len(ARTIFACT_ROOT) + 1:]: value for name, value in entries.items()
                        if name.startswith(ARTIFACT_ROOT + "/")}
    if set(expected_files) != set(actual_artifacts):
        raise ValueError("release file inventory differs from package artifact entries")
    if len(expected_files) != len(descriptor["files"]):
        raise ValueError("release file inventory contains duplicate paths")
    for name, payload in actual_artifacts.items():
        item = expected_files[name]
        _safe_relative(name)
        if _sha(payload) != item["sha256"] or len(payload) != item["size_bytes"]:
            raise ValueError(f"module package file digest/size mismatch: {name}")
    if _tree_digest(actual_artifacts) != descriptor["artifact_digest"]:
        raise ValueError("module package artifact tree digest mismatch")
    metadata_raw = entries[MODULE_METADATA_PATH]
    if _sha(metadata_raw) != descriptor["metadata_sha256"]:
        raise ValueError("module metadata digest mismatch")
    module_metadata = _validate_module_metadata(
        json.loads(metadata_raw), expected_module_id=descriptor["module_id"],
        expected_version=descriptor["module_version"],
        expected_artifact_digest=descriptor["artifact_digest"])
    _validate_process_binding(descriptor["process_binding"])
    return descriptor, actual_artifacts, module_metadata


def _install_parent(install_root: Path, module_id: str, module_version: str) -> Path:
    safe_id = quote(module_id, safe="._-")
    return install_root / ".r3a-module-artifacts" / safe_id / module_version


def _validate_install_root(install_root: Path) -> Path:
    """Normalize an install root without following any supplied symlink component."""
    requested = Path(install_root).expanduser()
    if not requested.is_absolute():
        requested = Path.cwd() / requested
    current = Path(requested.anchor)
    components = requested.parts[1:]
    for index, component in enumerate(components):
        if component in {"", "."}:
            continue
        if component == "..":
            current = current.parent
            continue
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"cannot safely inspect module install root component: {current}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise ValueError(f"module install root must not traverse a symlink: {current}")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"module install root component is not a directory: {current}")
    return current


def _reject_links_or_special_files(root: Path) -> None:
    if root.is_symlink():
        raise ValueError("module install target must not be a symlink")
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"module install contains a link or special file: {path}")


def _verify_installed_target(target: Path, descriptor: dict[str, Any]) -> None:
    _reject_links_or_special_files(target)
    metadata_path = target / MODULE_METADATA_PATH
    release_path = target / RELEASE_PATH
    if not metadata_path.is_file() or not release_path.is_file():
        raise ValueError("existing immutable module install is incomplete")
    installed_descriptor = json.loads(release_path.read_text(encoding="utf-8"))
    metadata_raw = metadata_path.read_bytes()
    if installed_descriptor != descriptor or _sha(metadata_raw) != descriptor["metadata_sha256"]:
        raise ValueError("existing immutable module install metadata differs from package")
    installed_files: dict[str, bytes] = {}
    for item in descriptor["files"]:
        path = _safe_relative(item["path"])
        file_path = target / ARTIFACT_ROOT / path
        if not file_path.is_file():
            raise ValueError(f"existing immutable module artifact is incomplete: {path}")
        payload = file_path.read_bytes()
        if _sha(payload) != item["sha256"] or len(payload) != item["size_bytes"]:
            raise ValueError(f"existing immutable module artifact digest mismatch: {path}")
        installed_files[path.as_posix()] = payload
    if _tree_digest(installed_files) != descriptor["artifact_digest"]:
        raise ValueError("existing immutable module artifact tree digest mismatch")


def install_package(package_path: Path, install_root: Path, *, expected_bundle_sha256: str) -> dict[str, Any]:
    install_root = _validate_install_root(install_root)
    descriptor, files, module_metadata = verify_package(
        package_path, expected_bundle_sha256=expected_bundle_sha256)
    parent = _install_parent(install_root, descriptor["module_id"], descriptor["module_version"])
    for path in (install_root / ".r3a-module-artifacts", parent.parent, parent):
        if path.is_symlink():
            raise ValueError("module install path must not traverse a symlink")
    target = parent / descriptor["artifact_digest"]
    if target.exists():
        _verify_installed_target(target, descriptor)
        return {"installed": True, "idempotent": True, "path": str(target),
                "artifact_root": str(target / ARTIFACT_ROOT), "artifact_digest": descriptor["artifact_digest"]}
    if parent.exists() and any(child.is_dir() for child in parent.iterdir()):
        raise FileExistsError("module version is already installed with a different immutable artifact digest")
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".candidate-", dir=parent))
    try:
        (staging / MODULE_METADATA_PATH).write_bytes(_json_bytes(module_metadata))
        (staging / RELEASE_PATH).write_bytes(_json_bytes(descriptor))
        for name, payload in files.items():
            destination = staging / ARTIFACT_ROOT / _safe_relative(name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        os.replace(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    for path in target.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    target.chmod(0o555)
    return {"installed": True, "idempotent": False, "path": str(target),
            "artifact_root": str(target / ARTIFACT_ROOT), "artifact_digest": descriptor["artifact_digest"]}


def discard_unactivated_candidate(install_root: Path, module_id: str, module_version: str,
                                  artifact_digest: str, *, effective_artifact_digest: str | None,
                                  effective_module_version: str | None,
                                  module_lifecycle_state: str) -> bool:
    """Remove a failed staged candidate only when CME reports it is not effective."""
    if not _MODULE_ID.fullmatch(module_id):
        raise ValueError("module_id is invalid")
    semantic_version(module_version)
    if not _SHA256.fullmatch(artifact_digest):
        raise ValueError("artifact_digest is invalid")
    if (effective_module_version is None) != (effective_artifact_digest is None):
        raise ValueError("effective module version and artifact digest must be supplied together")
    if module_lifecycle_state not in {"INSTALLED", "STOPPED", "FAILED", "INCOMPATIBLE"}:
        raise PermissionError("candidate cleanup requires a non-effective terminal/installed CME lifecycle state")
    if (effective_module_version == module_version
            and effective_artifact_digest == artifact_digest):
        raise PermissionError("cannot discard the effective module artifact")
    install_root = _validate_install_root(install_root)
    parent = _install_parent(install_root, module_id, module_version)
    for path in (install_root / ".r3a-module-artifacts", parent.parent, parent):
        if path.is_symlink():
            raise ValueError("module cleanup path must not traverse a symlink")
    target = parent / artifact_digest
    if not target.exists():
        return False
    _reject_links_or_special_files(target)
    descriptor = json.loads((target / RELEASE_PATH).read_text(encoding="utf-8"))
    if descriptor.get("module_id") != module_id or descriptor.get("module_version") != module_version \
            or descriptor.get("artifact_digest") != artifact_digest:
        raise ValueError("installed candidate identity differs from requested cleanup")
    for path in sorted(target.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o755)
        else:
            path.chmod(0o644)
    target.chmod(0o755)
    shutil.rmtree(target)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build a deterministic immutable module package")
    build_parser.add_argument("--module-metadata", type=Path, required=True)
    build_parser.add_argument("--process-binding", type=Path, required=True)
    build_parser.add_argument("--source-root", type=Path, required=True)
    build_parser.add_argument("--file", action="append", required=True,
                              help="normalized relative runtime file; repeat for the complete dependency closure")
    build_parser.add_argument("--output", type=Path, required=True)
    install_parser = subparsers.add_parser("install", help="verify and stage an immutable module artifact")
    install_parser.add_argument("package", type=Path, help="prebuilt r3a.module-release-package.v2 archive")
    install_parser.add_argument("--expected-sha256", required=True, help="external approved bundle digest pin")
    install_parser.add_argument("--install-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        source_root = args.source_root.resolve()
        files: dict[str, bytes] = {}
        for name in args.file:
            rel = _safe_relative(name)
            candidate = (source_root / Path(*rel.parts)).resolve()
            try:
                candidate.relative_to(source_root)
            except ValueError:
                raise ValueError(f"source file escapes declared root: {name}") from None
            if not candidate.is_file():
                raise FileNotFoundError(f"declared module source file is missing: {name}")
            files[rel.as_posix()] = candidate.read_bytes()
        metadata = json.loads(args.module_metadata.read_text(encoding="utf-8"))
        binding = json.loads(args.process_binding.read_text(encoding="utf-8"))
        metadata["artifact_digest"] = _tree_digest(files)
        result = build_package(metadata, binding, files, args.output)
    else:
        result = install_package(args.package, args.install_root,
                                 expected_bundle_sha256=args.expected_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
