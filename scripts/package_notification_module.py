#!/usr/bin/env python3
"""Build a deterministic staged package for the notification delivery provider.

Packaging only: this does not alter CME configuration, grants, activation, or services.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "artifacts/r3a-notification-delivery-1.0.0.tar.gz")
    args = parser.parse_args(argv)
    digest, size = build_package(args.output.expanduser().resolve())
    print(json.dumps({"module_id": "r3a.notification-delivery", "module_version": "1.0.0",
                      "artifact": str(args.output.expanduser().resolve()), "sha256": digest,
                      "size_bytes": size, "managed_activation": "not performed",
                      "write_operations_registered": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
