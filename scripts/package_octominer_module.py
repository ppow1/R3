#!/usr/bin/env python3
"""Build, verify, and stage a deterministic OctoMiner telemetry module release.

R3 CONTROLLED SOURCE
File: scripts/package_octominer_module.py
Component: R3A-MODULE-RELEASE-PACKAGER
File Revision: 1.0.0
Created: 2026-11-10 UTC
Created By: Codex GPT-6
Purpose: Package and verify the existing read-only telemetry provider for governed lifecycle installation.
Execution Model: Deterministic tar.gz builder and safe local artifact stager; no service control.
Observability: Versioned release manifest, source pins, bundle digest, and install receipt.
Dependencies: Python 3.12; R3A capability contract validator.
Authority: Steward Directive — Issue #46, live modular delivery.
Changed: 2026-11-10 | R3A-LIVE-MODULAR | Package existing OctoMiner provider with versioned v1.1 module contract.
Supersedes: None.
Contracts: r3a.module-release-package.v1; r3a.module-manifest.v1@1.1.0; r3a.capability-operation.v1.
Tests: tests/test_r3a_module_release_package.py.
History/Predecessor: New file; package source is r3a_plugins/octominer_telemetry.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from r3a_runtime.capability_contracts import operation_from_manifest
from r3a_runtime.config import _validate_plugin_config
from r3a_runtime.module_contracts import semantic_version


SOURCE = ROOT / "r3a_plugins/octominer_telemetry"
MODULE_PREFIX = "r3a_plugins/octominer_telemetry_2_0_0"
ENTRYPOINT = f"{MODULE_PREFIX.replace('/', '.')}.plugin:create_provider"
PACKAGE_SCHEMA = "r3a.module-release-package.v1"
RELEASE_NAME = "RELEASE_MANIFEST.json"


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"unsafe package path: {value}")
    return path


def build_entries() -> dict[str, bytes]:
    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((SOURCE / "config.example.json").read_text(encoding="utf-8"))
    if manifest.get("module_manifest", {}).get("contract_version") != "1.1.0":
        raise ValueError("OctoMiner module must declare r3a.module-manifest.v1@1.1.0")
    semantic_version(manifest["plugin_version"])
    _validate_plugin_config(config, manifest["configuration_schema"], "octominer config.example.json")
    operation = operation_from_manifest(manifest)
    if operation["effect_class"] != "read":
        raise ValueError("OctoMiner telemetry release must remain read-only")
    module = manifest["module_manifest"]
    if not isinstance(module["dependencies"], list):
        raise ValueError("module dependencies must be a declared array")
    grant_ids = operation["required_grants"]
    if not grant_ids:
        raise ValueError("telemetry operation must declare its scoped authorization requirement")

    source_files = [SOURCE / name for name in (
        "__init__.py", "plugin.py", "history.py", "http_providers.py",
        "process_providers.py", "request_metrics.py", "config.example.json")]
    entries: dict[str, bytes] = {}
    for path in source_files:
        if path.is_file():
            rel = f"{MODULE_PREFIX}/{path.name}"
            _safe_relative(rel)
            entries[rel] = path.read_bytes()

    # Bind this package version to a unique Python import path so older or
    # newer installed versions can coexist without replacing each other's code.
    manifest["provider"]["entrypoint"] = ENTRYPOINT
    manifest["operation"]["provider"]["entrypoint"] = ENTRYPOINT
    module["binding"]["entrypoint"] = ENTRYPOINT
    entries[f"{MODULE_PREFIX}/manifest.json"] = _json_bytes(manifest)

    for ref in [manifest["artifact_ref"],
                *(item["artifact_ref"] for item in manifest.get("supporting_artifacts", []))]:
        rel = f"{MODULE_PREFIX}/{ref}"
        actual = _sha(entries[rel])
        expected = manifest["artifact_sha256"] if ref == manifest["artifact_ref"] else next(
            item["artifact_sha256"] for item in manifest["supporting_artifacts"]
            if item["artifact_ref"] == ref)
        if actual != expected:
            raise ValueError(f"source artifact digest mismatch: {ref}")

    operation = operation_from_manifest(manifest)
    release = {
        "schema_id": PACKAGE_SCHEMA,
        "schema_version": 1,
        "module_id": module["module_id"],
        "module_version": module["module_version"],
        "manifest_contract": f"{module['contract_id']}@{module['contract_version']}",
        "provider_id": operation["provider"]["provider_id"],
        "provider_version": operation["provider"]["provider_version"],
        "entrypoint": ENTRYPOINT,
        "capabilities": [{"operation_id": operation["operation_id"],
                           "contract_id": operation["contract_id"],
                           "contract_version": operation["contract_version"],
                           "operation_revision": operation["operation_revision"],
                           "effect_class": operation["effect_class"]}],
        "dependencies": module["dependencies"],
        "runtime_dependencies": [
            "OpenSSH client for configured host sources",
            "psycopg 3 only when read-only request telemetry is configured",
        ],
        "required_grants": grant_ids,
        "source_policy": "read-only; host-key-pinned OpenSSH and configured HTTPS/DB reads",
        "managed_activation": "requires explicit authorization, config reload, and CME lifecycle commands",
        "files": [{"path": path, "sha256": _sha(raw)} for path, raw in sorted(entries.items())],
    }
    entries[RELEASE_NAME] = _json_bytes(release)
    return entries


def build_package(output: Path) -> dict[str, Any]:
    entries = build_entries()
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for path, raw in sorted(entries.items()):
                info = tarfile.TarInfo(path)
                info.size = len(raw)
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
    payload = buffer.getvalue()
    output.write_bytes(payload)
    digest = _sha(payload)
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii")
    return {"artifact": str(output), "sha256": digest, "size_bytes": len(payload),
            "module_id": "r3a.octominer-telemetry", "module_version": "2.0.0"}


def verify_package(package_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw = package_path.read_bytes()
    entries: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            rel = _safe_relative(member.name)
            if not member.isfile() or member.issym() or member.islnk() or member.name in entries:
                raise ValueError(f"package contains unsupported or duplicate entry: {member.name}")
            handle = archive.extractfile(member)
            if handle is None:
                raise ValueError(f"package entry is unreadable: {member.name}")
            entries[str(rel)] = handle.read()
    release = json.loads(entries[RELEASE_NAME])
    if release.get("schema_id") != PACKAGE_SCHEMA or release.get("schema_version") != 1:
        raise ValueError("release manifest contract is unsupported")
    expected = {item["path"]: item["sha256"] for item in release["files"]}
    if set(expected) != set(entries) - {RELEASE_NAME}:
        raise ValueError("release manifest file inventory differs from package entries")
    for path, digest in expected.items():
        if _sha(entries[path]) != digest:
            raise ValueError(f"release package file digest mismatch: {path}")
    module_manifest_path = f"{MODULE_PREFIX}/manifest.json"
    manifest = json.loads(entries[module_manifest_path])
    _validate_plugin_config(json.loads(entries[f"{MODULE_PREFIX}/config.example.json"]),
                            manifest["configuration_schema"], "packaged config.example.json")
    descriptor = operation_from_manifest(manifest)
    if descriptor["effect_class"] != "read" or descriptor["required_grants"] != release["required_grants"]:
        raise ValueError("release authorization/effect metadata does not match the operation contract")
    if manifest["module_manifest"]["dependencies"] != release["dependencies"]:
        raise ValueError("release dependency inventory does not match the module contract")
    return release, entries


def install_package(package_path: Path, install_root: Path) -> dict[str, Any]:
    release, entries = verify_package(package_path)
    target = install_root / MODULE_PREFIX
    receipt_dir = install_root / ".r3a-module-receipts"
    receipt = receipt_dir / f"{release['module_id']}-{release['module_version']}.json"
    digest = _sha(package_path.read_bytes())
    install_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if receipt.is_file():
            existing = json.loads(receipt.read_text(encoding="utf-8"))
            if existing.get("bundle_sha256") == digest:
                return {"installed": True, "idempotent": True, "path": str(target),
                        "bundle_sha256": digest}
        raise FileExistsError(f"versioned install target already exists: {target}")

    staging_parent = target.parent
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=staging_parent))
    try:
        for path, data in entries.items():
            if path == RELEASE_NAME:
                continue
            relative = PurePosixPath(path).relative_to(PurePosixPath("r3a_plugins"))
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        staged_package = staging / PurePosixPath(MODULE_PREFIX).relative_to("r3a_plugins")
        if target.name != staged_package.name:
            raise ValueError("module installation layout does not match versioned import path")
        os.replace(staged_package, target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({"schema_id": "r3a.module-install-receipt.v1", "schema_version": 1,
                                   "module_id": release["module_id"], "module_version": release["module_version"],
                                   "bundle_sha256": digest, "installed_at": __import__("datetime").datetime.now(
                                       __import__("datetime").timezone.utc).isoformat(),
                                   "path": str(target)}, indent=2) + "\n", encoding="utf-8")
    return {"installed": True, "idempotent": False, "path": str(target), "bundle_sha256": digest,
            "receipt": str(receipt)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--output", type=Path, default=ROOT / "artifacts/r3a.octominer-telemetry-2.0.0.tar.gz")
    verify = commands.add_parser("verify")
    verify.add_argument("package", type=Path)
    install = commands.add_parser("install")
    install.add_argument("package", type=Path)
    install.add_argument("--root", type=Path, required=True,
                         help="isolated application/import root containing r3a_plugins/")
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_package(args.output.expanduser().resolve())
    elif args.command == "verify":
        release, entries = verify_package(args.package.expanduser().resolve())
        result = {"verified": True, "package": str(args.package.resolve()),
                  "bundle_sha256": _sha(args.package.read_bytes()),
                  "file_count": len(entries) - 1, "release": release}
    else:
        result = install_package(args.package.expanduser().resolve(), args.root.expanduser().resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
