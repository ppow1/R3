#!/usr/bin/env python3
"""Build, verify, and immutably stage generic AP0 process-module packages.

R3 CONTROLLED SOURCE
File: scripts/package_r3a_module.py
Component: R3A-GENERIC-MODULE-PACKAGER
File Revision: 1.0.0
Created: 2026-11-11T18:20:00Z
Created By: Codex GPT-6
Purpose: Package arbitrary declared process-module artifacts with immutable identity and an integrity-checked file inventory.
Execution Model: Deterministic local archive build, verification, and atomic staging; never activates or registers modules.
Observability: Source revision, module/version, package digest, file inventory, and install path.
Dependencies: Python standard library; r3a.module-release-package.v2@2.0.0.
Authority: Step 78 dispatch 6804259280; no CME, grant, or shared-runtime authority.
Changed: 2026-11-11T18:20:00Z | R3A-MODULE-PACKAGE-V2 | Codex GPT-6 | Add generic process module package and immutable stager.
Supersedes: None.
Contracts: AP0-M1; r3a.module-release-package.v2@2.0.0; r3a.resident.executor@1.0.0.
Tests: tests/test_r3a_generic_module_package.py.
History/Predecessor: New utility.
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
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "r3a_modules/resident_grace/package_spec.json"
SCHEMA = ROOT / "r3a_runtime/schemas/module-release-package.v2.schema.json"
RELEASE_NAME = "RELEASE_MANIFEST.json"
SCHEMA_ID = "r3a.module-release-package.v2"
SCHEMA_VERSION = "2.0.0"
_MODULE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,159}$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_PLACEHOLDERS = {"{socket_path}", "{module_id}", "{module_version}", "{configuration_path}"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _safe_relative(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("package path must be a non-empty normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or str(path) != value:
        raise ValueError(f"unsafe package path: {value}")
    return path


def _validate_descriptor(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
            "schema_id", "schema_version", "source", "module", "role", "launch_profile",
            "runtime_dependencies", "files"}:
        raise ValueError("package descriptor fields are invalid")
    if value["schema_id"] != SCHEMA_ID or value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("package descriptor contract is unsupported")
    source = value["source"]
    if not isinstance(source, dict) or set(source) != {"repository", "revision"} or \
            not isinstance(source["repository"], str) or not source["repository"].strip() or \
            not isinstance(source["revision"], str) or not re.fullmatch(r"[a-f0-9]{40}", source["revision"]):
        raise ValueError("package source provenance is invalid")
    module = value["module"]
    expected_module = {"module_id", "module_version", "owner", "manifest_contract", "entrypoint", "entrypoint_sha256"}
    if not isinstance(module, dict) or set(module) != expected_module:
        raise ValueError("package module identity fields are invalid")
    if not isinstance(module["module_id"], str) or not _MODULE_ID.fullmatch(module["module_id"]):
        raise ValueError("package module_id is invalid")
    if not isinstance(module["module_version"], str) or not _SEMVER.fullmatch(module["module_version"]):
        raise ValueError("package module_version must be semantic major.minor.patch")
    if not isinstance(module["owner"], str) or not module["owner"].strip():
        raise ValueError("package owner is required")
    manifest_contract = module["manifest_contract"]
    if not isinstance(manifest_contract, dict) or set(manifest_contract) != {"contract_id", "contract_version"} or \
            manifest_contract.get("contract_id") != "r3a.module-manifest.v1" or \
            manifest_contract.get("contract_version") not in {"1.1.0", "1.2.0"}:
        raise ValueError("package module manifest contract is unsupported")
    if not isinstance(module["entrypoint"], str) or not _DOTTED.fullmatch(module["entrypoint"]):
        raise ValueError("package module entrypoint is invalid")
    if not isinstance(module["entrypoint_sha256"], str) or not _SHA.fullmatch(module["entrypoint_sha256"]):
        raise ValueError("package entrypoint digest is invalid")
    role = value["role"]
    if not isinstance(role, dict) or set(role) != {"contract_id", "contract_version", "execution_contract_range"} or \
            role.get("contract_id") != "r3a.resident.executor" or role.get("contract_version") != "1.0.0":
        raise ValueError("package resident executor role is invalid")
    contract_range = role["execution_contract_range"]
    if not isinstance(contract_range, dict) or set(contract_range) != {"contract_id", "major", "min_minor", "max_minor"} or \
            contract_range.get("contract_id") != "r3a.resident.execution-profile" or contract_range.get("major") != 1 or \
            not isinstance(contract_range.get("min_minor"), int) or not isinstance(contract_range.get("max_minor"), int) or \
            contract_range["min_minor"] < 0 or contract_range["max_minor"] < contract_range["min_minor"]:
        raise ValueError("package resident execution contract range is invalid")
    launch = value["launch_profile"]
    expected_launch = {"binding", "protocol_id", "protocol_major", "protocol_min_minor", "protocol_max_minor",
                       "import_root", "entrypoint", "argv_template"}
    if not isinstance(launch, dict) or set(launch) != expected_launch or launch.get("binding") != "process" or \
            launch.get("protocol_id") != "r3a.module-jsonl-worker.v1" or launch.get("protocol_major") != 1 or \
            not isinstance(launch.get("protocol_min_minor"), int) or not isinstance(launch.get("protocol_max_minor"), int) or \
            launch["protocol_min_minor"] < 0 or launch["protocol_max_minor"] < launch["protocol_min_minor"]:
        raise ValueError("package process launch profile is invalid")
    _safe_relative(launch.get("import_root"))
    if not isinstance(launch.get("entrypoint"), str) or not _DOTTED.fullmatch(launch["entrypoint"]) or \
            launch["entrypoint"] != module["entrypoint"]:
        raise ValueError("package launch and module entrypoints do not agree")
    argv = launch.get("argv_template")
    expected_argv = ["-m", launch["entrypoint"], "--socket", "{socket_path}",
                     "--module-id", "{module_id}", "--module-version", "{module_version}",
                     "--config", "{configuration_path}"]
    if not isinstance(argv, list) or any(not isinstance(item, str) or not item for item in argv) or \
            argv != expected_argv or any("{" in token and token not in _PLACEHOLDERS for token in argv):
        raise ValueError("package argv template must be a fixed Python module invocation")
    if not isinstance(value["runtime_dependencies"], list) or any(
            not isinstance(item, str) or not item.strip() for item in value["runtime_dependencies"]):
        raise ValueError("package runtime dependencies must be declared strings")
    if not isinstance(value["files"], list) or not value["files"]:
        raise ValueError("package file inventory is required")
    paths: set[str] = set()
    for item in value["files"]:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValueError("package file inventory entry is invalid")
        path = str(_safe_relative(item["path"]))
        if path == RELEASE_NAME or path in paths:
            raise ValueError("package file inventory contains reserved or duplicate path")
        paths.add(path)
        if not isinstance(item["sha256"], str) or not _SHA.fullmatch(item["sha256"]):
            raise ValueError("package file inventory digest is invalid")
    return value


def _source_spec(spec_path: Path, source_root: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if set(spec) != {"schema_id", "schema_version", "source", "module", "role", "launch_profile",
                     "runtime_dependencies", "source_files"}:
        raise ValueError("package source specification fields are invalid")
    files: dict[str, bytes] = {}
    inventory = []
    for item in spec["source_files"]:
        if not isinstance(item, dict) or set(item) != {"source", "path", "sha256"}:
            raise ValueError("package source file entry is invalid")
        source = _safe_relative(item["source"])
        path = str(_safe_relative(item["path"]))
        source_path = (source_root / Path(*source.parts)).resolve()
        if not source_path.is_relative_to(source_root.resolve()) or not source_path.is_file():
            raise ValueError(f"package source file is missing or escapes source root: {source}")
        raw = source_path.read_bytes()
        if not isinstance(item["sha256"], str) or _sha(raw) != item["sha256"]:
            raise ValueError(f"source artifact digest mismatch: {source}")
        if path in files or path == RELEASE_NAME:
            raise ValueError("package source maps duplicate or reserved archive path")
        files[path] = raw
        inventory.append({"path": path, "sha256": item["sha256"]})
    descriptor = {key: spec[key] for key in (
        "schema_id", "schema_version", "source", "module", "role", "launch_profile", "runtime_dependencies")}
    descriptor["module"] = {key: value for key, value in spec["module"].items() if key != "entrypoint_path"}
    descriptor["files"] = sorted(inventory, key=lambda item: item["path"])
    _validate_descriptor(descriptor)
    entrypoint_path = spec["module"].get("entrypoint_path")
    entrypoint_digest = next((item["sha256"] for item in spec["source_files"]
                              if item["source"] == entrypoint_path), None)
    if entrypoint_digest != descriptor["module"]["entrypoint_sha256"]:
        raise ValueError("module entrypoint is not pinned by the declared source inventory")
    return descriptor, files


def build_package(spec_path: Path, source_root: Path, output_path: Path) -> dict[str, Any]:
    descriptor, files = _source_spec(spec_path, source_root)
    entries = {**files, RELEASE_NAME: _json_bytes(descriptor)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, payload in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = 0o444
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(payload))
    raw = buffer.getvalue()
    output_path.write_bytes(raw)
    digest = _sha(raw)
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(
        f"{digest}  {output_path.name}\n", encoding="ascii")
    return {"artifact": str(output_path), "bundle_sha256": digest, "size_bytes": len(raw),
            "module_id": descriptor["module"]["module_id"],
            "module_version": descriptor["module"]["module_version"]}


def verify_package(package_path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    entries: dict[str, bytes] = {}
    with tarfile.open(package_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 256:
            raise ValueError("package contains too many files")
        total_bytes = 0
        for member in members:
            path = str(_safe_relative(member.name))
            if not member.isfile() or member.issym() or member.islnk() or path in entries:
                raise ValueError(f"package contains unsupported or duplicate entry: {member.name}")
            total_bytes += member.size
            if total_bytes > 64 * 1024 * 1024:
                raise ValueError("package uncompressed content exceeds the 64 MiB limit")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"package entry is unreadable: {path}")
            data = stream.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("package entry exceeds the 8 MiB limit")
            entries[path] = data
    descriptor_raw = entries.pop(RELEASE_NAME, None)
    if descriptor_raw is None:
        raise ValueError("package release descriptor is missing")
    descriptor = _validate_descriptor(json.loads(descriptor_raw.decode("utf-8")))
    expected = {item["path"]: item["sha256"] for item in descriptor["files"]}
    if set(expected) != set(entries):
        raise ValueError("package file inventory differs from archive contents")
    for path, digest in expected.items():
        if _sha(entries[path]) != digest:
            raise ValueError(f"package file digest mismatch: {path}")
    entrypoint_path = "runtime/" + descriptor["module"]["entrypoint"].replace(".", "/") + ".py"
    if _sha(entries.get(entrypoint_path, b"")) != descriptor["module"]["entrypoint_sha256"]:
        raise ValueError("package entrypoint digest does not match module identity")
    return descriptor, entries


def install_package(package_path: Path, install_root: Path) -> dict[str, Any]:
    descriptor, entries = verify_package(package_path)
    module = descriptor["module"]
    module_segment = quote(module["module_id"], safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    version_root = install_root.resolve() / "r3a-modules" / module_segment / module["module_version"]
    digest = _sha(package_path.read_bytes())
    destination = version_root / digest
    version_root.mkdir(parents=True, exist_ok=True)
    existing_versions = [path for path in version_root.iterdir() if path.name != digest]
    if existing_versions:
        raise ValueError("same module version is already installed with a different package digest")
    if destination.exists():
        prior_descriptor, _ = verify_package(destination / "package.tar.gz") if (destination / "package.tar.gz").is_file() else (None, None)
        if prior_descriptor != descriptor:
            raise ValueError("existing content-addressed installation does not match the package")
        return {"state": "INSTALLED", "idempotent": True, "module_id": module["module_id"],
                "module_version": module["module_version"], "bundle_sha256": digest,
                "install_path": str(destination), "launch_profile": descriptor["launch_profile"]}

    staging = Path(tempfile.mkdtemp(prefix=".r3a-stage-", dir=version_root))
    try:
        (staging / RELEASE_NAME).write_bytes(_json_bytes(descriptor))
        (staging / RELEASE_NAME).chmod(0o444)
        for relative, payload in entries.items():
            path = staging / Path(*PurePosixPath(relative).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            path.chmod(0o444)
        original = package_path.resolve()
        shutil.copyfile(original, staging / "package.tar.gz")
        (staging / "package.tar.gz").chmod(0o444)
        for directory in sorted((p for p in staging.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            directory.chmod(0o555)
        staging.chmod(0o555)
        os.rename(staging, destination)
    except Exception:
        for path in staging.rglob("*"):
            try:
                path.chmod(0o755 if path.is_dir() else 0o644)
            except OSError:
                pass
        try:
            staging.chmod(0o755)
        except OSError:
            pass
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {"state": "INSTALLED", "idempotent": False, "module_id": module["module_id"],
            "module_version": module["module_version"], "bundle_sha256": digest,
            "install_path": str(destination), "launch_profile": descriptor["launch_profile"]}


def resolve_launch_plan(install_path: Path, descriptor: dict[str, Any], *, socket_path: Path,
                        module_id: str, module_version: str, configuration_path: Path) -> dict[str, Any]:
    """Render a shell-free AP0 process invocation from a verified package profile."""
    descriptor = _validate_descriptor(descriptor)
    module = descriptor["module"]
    if module_id != module["module_id"] or module_version != module["module_version"]:
        raise ValueError("launch identity does not match the installed immutable module")
    if not socket_path.is_absolute() or not configuration_path.is_absolute():
        raise ValueError("launch socket and external configuration paths must be absolute")
    package_path = install_path / "package.tar.gz"
    installed_descriptor, archive_entries = verify_package(package_path)
    bundle_digest = _sha(package_path.read_bytes())
    if installed_descriptor != descriptor or install_path.name != bundle_digest:
        raise ValueError("installed package identity or content-addressed path is invalid")
    for relative, expected in archive_entries.items():
        staged_file = install_path / Path(*PurePosixPath(relative).parts)
        if not staged_file.is_file() or _sha(staged_file.read_bytes()) != _sha(expected):
            raise ValueError("installed module file differs from its verified archive")
    profile = descriptor["launch_profile"]
    values = {"{socket_path}": str(socket_path), "{module_id}": module_id,
              "{module_version}": module_version, "{configuration_path}": str(configuration_path)}
    argv = [values.get(item, item) for item in profile["argv_template"]]
    import_root = (install_path / profile["import_root"]).resolve()
    if not import_root.is_dir():
        raise ValueError("installed module import root is unavailable")
    return {"executable": sys.executable, "argv": argv, "cwd": str(import_root),
            "environment": {"PYTHONPATH": str(import_root)}, "shell": False,
            "module_id": module_id, "module_version": module_version,
            "bundle_sha256": bundle_digest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--spec", type=Path, default=SPEC)
    build.add_argument("--source-root", type=Path, default=ROOT)
    build.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("package", type=Path)
    install = commands.add_parser("install")
    install.add_argument("package", type=Path)
    install.add_argument("--root", type=Path, required=True)
    plan = commands.add_parser("launch-plan")
    plan.add_argument("install_path", type=Path)
    plan.add_argument("--socket", type=Path, required=True)
    plan.add_argument("--module-id", required=True)
    plan.add_argument("--module-version", required=True)
    plan.add_argument("--configuration", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "build":
        result = build_package(args.spec, args.source_root, args.output)
    elif args.command == "verify":
        descriptor, entries = verify_package(args.package)
        result = {"verified": True, "module_id": descriptor["module"]["module_id"],
                  "module_version": descriptor["module"]["module_version"],
                  "files": len(entries), "bundle_sha256": _sha(args.package.read_bytes())}
    elif args.command == "install":
        result = install_package(args.package, args.root)
    else:
        installed_manifest = args.install_path / RELEASE_NAME
        descriptor = _validate_descriptor(json.loads(installed_manifest.read_text(encoding="utf-8")))
        result = resolve_launch_plan(args.install_path, descriptor, socket_path=args.socket,
                                     module_id=args.module_id, module_version=args.module_version,
                                     configuration_path=args.configuration)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
