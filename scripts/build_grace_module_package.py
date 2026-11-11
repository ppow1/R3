#!/usr/bin/env python3
"""Build and verify the pinned Grace release using the shared package v2 tool.

R3 CONTROLLED SOURCE
File: scripts/build_grace_module_package.py
Component: R3A-GRACE-PACKAGE-INPUT-ADAPTER
File Revision: 1.0.0
Purpose: Verify the audited Grace source closure and adapt it to the shared r3a.module-release-package.v2 builder.
Execution Model: Source-pin checking plus calls into scripts.r3a_module_release_package; no lifecycle or service access.
Authority: Step 78 dispatch 6804259280; no shared runtime, grant, or activation authority.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0.
Tests: tests/test_r3a_generic_module_package.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.r3a_module_release_package import (
    build_package,
    install_package,
    verify_package,
)

DEFAULT_SPEC = ROOT / "r3a_modules/resident_grace/package_spec.json"
_SOURCE_REVISION = re.compile(r"^[a-f0-9]{40}$")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def artifact_tree_digest(files: dict[str, bytes]) -> str:
    """Calculate the documented r3a-module-artifact-tree.v1 digest."""
    records = []
    for name, payload in sorted(files.items()):
        records.append(f"{name}\0{_sha(payload)}\0{len(payload)}\n")
    return _sha(("r3a-module-artifact-tree.v1\n" + "".join(records)).encode("utf-8"))


def source_inputs(spec_path: Path, source_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if set(spec) != {"source", "module_manifest", "process_binding", "source_files"}:
        raise ValueError("Grace package input fields differ from the source-pinned adapter contract")
    if not isinstance(spec["source"], dict) or not spec["source"].get("repository") or \
            not isinstance(spec["source"].get("revision"), str) or \
            not _SOURCE_REVISION.fullmatch(spec["source"]["revision"]):
        raise ValueError("Grace package source provenance is invalid")
    source_root = source_root.resolve()
    files: dict[str, bytes] = {}
    for item in spec["source_files"]:
        if not isinstance(item, dict) or set(item) != {"source", "path", "sha256"}:
            raise ValueError("Grace package source inventory entry is invalid")
        source_rel = Path(item["source"])
        archive_rel = Path(item["path"])
        if source_rel.is_absolute() or archive_rel.is_absolute() or any(part in {"", ".", ".."} for part in source_rel.parts + archive_rel.parts):
            raise ValueError("Grace package paths must be normalized relative paths")
        source_path = (source_root / source_rel).resolve()
        if not source_path.is_relative_to(source_root) or not source_path.is_file():
            raise ValueError(f"Grace source file is missing or escapes source root: {source_rel}")
        payload = source_path.read_bytes()
        if _sha(payload) != item["sha256"]:
            raise ValueError(f"audited Grace source digest mismatch: {source_rel}")
        archive_name = archive_rel.as_posix()
        if archive_name in files:
            raise ValueError(f"duplicate Grace package archive path: {archive_name}")
        files[archive_name] = payload
    manifest = dict(spec["module_manifest"])
    manifest["resident_executor"] = dict(manifest["resident_executor"])
    manifest["resident_executor"]["execution_contract_range"] = dict(
        manifest["resident_executor"]["execution_contract_range"])
    manifest["artifact_digest"] = artifact_tree_digest(files)
    return manifest, dict(spec["process_binding"]), files


def build_grace_package(spec_path: Path, source_root: Path, output_path: Path) -> dict[str, Any]:
    manifest, binding, files = source_inputs(spec_path, source_root)
    result = build_package(manifest, binding, files, output_path)
    Path(str(output_path) + ".sha256").write_text(
        f"{result['bundle_sha256']}  {output_path.name}\n", encoding="ascii")
    return result


def verify_grace_package(package_path: Path, expected_bundle_sha256: str):
    return verify_package(package_path, expected_bundle_sha256=expected_bundle_sha256)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument("--source-root", type=Path, default=ROOT)
    build.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("package", type=Path)
    verify.add_argument("--expected-sha256", required=True)
    install = commands.add_parser("install")
    install.add_argument("package", type=Path)
    install.add_argument("--expected-sha256", required=True)
    install.add_argument("--install-root", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_grace_package(args.spec, args.source_root, args.output)
    elif args.command == "verify":
        descriptor, files, manifest = verify_grace_package(args.package, args.expected_sha256)
        result = {"verified": True, "module_id": descriptor["module_id"],
                  "module_version": descriptor["module_version"],
                  "artifact_digest": descriptor["artifact_digest"],
                  "bundle_sha256": args.expected_sha256, "files": len(files),
                  "manifest_sha256": descriptor["manifest_sha256"]}
    else:
        result = install_package(args.package, args.install_root,
                                 expected_bundle_sha256=args.expected_sha256)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
