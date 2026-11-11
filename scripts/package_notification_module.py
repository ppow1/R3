#!/usr/bin/env python3
"""Build and verify the deterministic notification delivery read-provider package.

R3 CONTROLLED SOURCE
File: scripts/package_notification_module.py
Component: R3A-NOTIFICATION-PACKAGER
File Revision: 1.1.0
Created: 2026-11-11 (inherited implementation; exact original time unknown)
Created By: Codex GPT-6
Purpose: Build and verify the immutable, read-only Notifications provider archive.
Execution Model: Deterministic local archive build and integrity verification.
Observability: In-band release inventory, SHA-256 sidecar, CLI JSON result.
Dependencies: R3A module-release-package.v1; notification.delivery.read manifest.
Authority: Issue #48, Planned Step 128; packaging only, no grant or activation.
Changed: 2026-11-11 | STEP-128 | Codex GPT-6 | Bind release to provider 1.2.2 and verify inventory/sidecar.
Supersedes: Source revision inherited from reviewed notification package builder.
Contracts: r3a.module-release-package.v1; notification.delivery.read.
Tests: tests/test_r3a_notification_package.py.
History/Predecessor: Source implementation from a3f82a0203b706dd75a831331004ffa294e984ba.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = "r3a_plugins/notification_service"
MODULE_SOURCE = ROOT / PACKAGE_PATH
FILES = ("capability.py", "store.py", "manifest.read.json", "capability.config.example.json")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_entries() -> dict[str, bytes]:
    entries = {f"{PACKAGE_PATH}/{name}": _canonical_bytes(MODULE_SOURCE / name) for name in FILES}
    manifest_path = MODULE_SOURCE / "manifest.read.json"
    operation_manifest = json.loads(entries[f"{PACKAGE_PATH}/manifest.read.json"])
    if operation_manifest["operation"]["required_grants"] != ["notification.delivery.read"]:
        raise ValueError("notification read package must keep the exact read grant")
    if operation_manifest["operation"]["effect_class"] != "read":
        raise ValueError("notification delivery package must remain read-only")
    for reference in [operation_manifest["artifact_ref"], *[
        item["artifact_ref"] for item in operation_manifest.get("supporting_artifacts", [])
    ]]:
        actual = _sha(entries[f"{PACKAGE_PATH}/{reference}"])
        expected = (operation_manifest["artifact_sha256"] if reference == operation_manifest["artifact_ref"]
                    else next(item["artifact_sha256"] for item in operation_manifest["supporting_artifacts"]
                              if item["artifact_ref"] == reference))
        if actual != expected:
            raise ValueError(f"notification manifest digest mismatch: {reference}")
    release_manifest = {
        "schema_id": "r3a.module-release-package.v1",
        "schema_version": 1,
        "module_id": operation_manifest["module_manifest"]["module_id"],
        "module_version": operation_manifest["module_manifest"]["module_version"],
        "provider_id": operation_manifest["provider"]["provider_id"],
        "provider_version": operation_manifest["provider"]["provider_version"],
        "package_path": PACKAGE_PATH,
        "entrypoint": operation_manifest["provider"]["entrypoint"],
        "host_compatibility": {"contract_id": "r3a.capability-provider.v1",
                               "protocol_major": 1, "protocol_min_minor": 0, "protocol_max_minor": 0},
        "capabilities": [{"operation_id": operation_manifest["operation"]["operation_id"],
                          "contract_version": operation_manifest["operation"]["contract_version"],
                          "operation_revision": operation_manifest["operation"]["operation_revision"],
                          "effect_class": operation_manifest["operation"]["effect_class"]}],
        "runtime_dependencies": ["R3A runtime capability provider v1", "psycopg 3"],
        "files": [{"path": path, "sha256": _sha(raw)} for path, raw in sorted(entries.items())],
        "managed_activation": "not performed by package build",
        "write_operations_registered": False,
    }
    entries["RELEASE_MANIFEST.json"] = _json_bytes(release_manifest)
    return entries


def build_package(output: Path) -> tuple[str, int]:
    entries = build_entries()
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, raw in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                archive.addfile(info, io.BytesIO(raw))
    payload = buffer.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    digest = _sha(payload)
    try:
        label = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        label = output.name
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {label}\n", encoding="ascii")
    return digest, len(payload)


def verify_package(artifact: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Verify the outer digest, safe archive inventory, pins and read-only grant."""
    artifact = artifact.expanduser().resolve()
    payload = artifact.read_bytes()
    digest = _sha(payload)
    sidecar = artifact.with_suffix(artifact.suffix + ".sha256")
    fields = sidecar.read_text(encoding="ascii").strip().split()
    try:
        expected_label = artifact.relative_to(ROOT).as_posix()
    except ValueError:
        expected_label = artifact.name
    if len(fields) != 2 or fields[0] != digest or fields[1] != expected_label:
        raise ValueError("notification package SHA-256 sidecar does not match")
    entries: dict[str, bytes] = {}
    with tarfile.open(artifact, "r:gz") as archive:
        for member in archive.getmembers():
            if (not member.isfile() or member.name.startswith("/") or "\\" in member.name
                    or any(part in {"", ".", ".."} for part in member.name.split("/"))
                    or member.name in entries):
                raise ValueError("notification package contains an unsafe or duplicate member")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("notification package member cannot be read")
            entries[member.name] = stream.read()
    release_raw = entries.pop("RELEASE_MANIFEST.json", None)
    if release_raw is None:
        raise ValueError("notification package has no in-band release manifest")
    release = json.loads(release_raw)
    if (release.get("schema_id") != "r3a.module-release-package.v1"
            or release.get("schema_version") != 1
            or release.get("module_id") != "r3a.notification-delivery"
            or release.get("module_version") != "1.2.2"
            or release.get("capabilities") != [{"operation_id": "notification.delivery.read",
                "contract_version": "1.0.0", "operation_revision": "1.0.0", "effect_class": "read"}]
            or release.get("write_operations_registered") is not False):
        raise ValueError("notification release metadata violates the read-only 1.2.2 contract")
    inventory = release.get("files")
    if not isinstance(inventory, list):
        raise ValueError("notification package inventory is invalid")
    expected: dict[str, str] = {}
    for item in inventory:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                or item["path"] in expected):
            raise ValueError("notification package inventory entry is invalid")
        expected[item["path"]] = item["sha256"]
    if set(expected) != set(entries):
        raise ValueError("notification package inventory does not cover the archive payload")
    for name, raw in entries.items():
        if _sha(raw) != expected[name]:
            raise ValueError(f"notification package payload digest mismatch: {name}")
    operation_path = f"{PACKAGE_PATH}/manifest.read.json"
    operation_manifest = json.loads(entries[operation_path])
    if (operation_manifest["operation"]["required_grants"] != ["notification.delivery.read"]
            or operation_manifest["operation"]["effect_class"] != "read"):
        raise ValueError("notification provider does not declare the exact read-only grant")
    for item in [{"artifact_ref": operation_manifest["artifact_ref"],
                  "artifact_sha256": operation_manifest["artifact_sha256"]},
                 *operation_manifest.get("supporting_artifacts", [])]:
        path = f"{PACKAGE_PATH}/{item['artifact_ref']}"
        if path not in entries or _sha(entries[path]) != item["artifact_sha256"]:
            raise ValueError(f"notification operation artifact pin mismatch: {item['artifact_ref']}")
    return release, entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/r3a-notification-delivery-1.2.2.tar.gz")
    args = parser.parse_args(argv)
    digest, size = build_package(args.output.expanduser().resolve())
    release, entries = verify_package(args.output.expanduser().resolve())
    print(json.dumps({"module_id": "r3a.notification-delivery", "module_version": "1.2.2",
                      "artifact": str(args.output.expanduser().resolve()), "sha256": digest,
                      "size_bytes": size, "verified_files": len(entries),
                      "managed_activation": "not performed",
                      "write_operations_registered": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
