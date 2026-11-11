"""Build deterministic immutable OctoMiner telemetry provider packages.

R3 CONTROLLED SOURCE
File: scripts/package_octominer_telemetry.py
Component: R3A-OCTOMINER-TELEMETRY-RELEASE-PACKAGER
File Revision: 1.0.1
Created: 2026-11-11T19:24:00Z
Created By: Codex GPT-6
Purpose: Build digest-pinned release archives for telemetry provider v2.1.0/v2.1.1.
Execution Model: Deterministic tar.gz construction from already-pinned manifest artifacts.
Observability: Release manifest, per-file SHA-256 inventory, archive SHA-256 and size.
Dependencies: Python standard library; existing immutable telemetry manifests and provider files.
Authority: AD-024; #46 Step 98. Package build does not activate or authorize a provider.
Changed: 2026-11-11T19:24:00Z | R3A-MODULAR-PLUGINS-STEP-98 | Codex GPT-6 | Add immutable telemetry package builder.
Changed: 2026-11-11T19:25:02Z | R3A-MODULAR-PLUGINS-STEP-98 | Codex GPT-6 | Derive process entrypoint from validated provider operation metadata.
Supersedes: None.
Contracts: r3a.module-release-package.v1; r3a.capability-provider.v1; capability-operation.v1.
Tests: tests/test_r3a_octominer_release_package.py.
History/Predecessor: Follows existing scripts/package_knowledge_module.py deterministic release format.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "r3a_plugins/octominer_telemetry"
VERSIONS = {"2.1.0": "manifest.v2.1.0.json", "2.1.1": "manifest.v2.1.1.json"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def build_entries(version: str) -> dict[str, bytes]:
    if version not in VERSIONS:
        raise ValueError(f"unsupported immutable telemetry version: {version}")
    manifest_name = VERSIONS[version]
    raw_manifest = (PACKAGE / manifest_name).read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get("plugin_version") != version:
        raise ValueError("telemetry manifest version does not match requested package")
    operation = manifest.get("operation")
    if not isinstance(operation, dict) or operation.get("required_grants") != [
            "infrastructure.octominer.telemetry.read"]:
        raise ValueError("telemetry release must preserve the existing read grant")
    if version == "2.1.1":
        target_schema = operation.get("target_scope_schema")
        if not isinstance(target_schema, dict) or target_schema.get("required") != ["host_ids", "source_ids"]:
            raise ValueError("v2.1.1 release must require explicit host and source selectors")

    references = [manifest["artifact_ref"],
                  *(item["artifact_ref"] for item in manifest.get("supporting_artifacts", []))]
    if len(references) != len(set(references)):
        raise ValueError("telemetry release contains duplicate artifact references")
    entries: dict[str, bytes] = {f"{PACKAGE.relative_to(ROOT).as_posix()}/{manifest_name}": raw_manifest}
    for item in [{"artifact_ref": manifest["artifact_ref"],
                  "artifact_sha256": manifest["artifact_sha256"]},
                 *manifest.get("supporting_artifacts", [])]:
        rel = PurePosixPath(item["artifact_ref"])
        if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError(f"unsafe telemetry artifact path: {rel}")
        payload = (PACKAGE / Path(*rel.parts)).read_bytes()
        if _sha(payload) != item["artifact_sha256"]:
            raise ValueError(f"pinned telemetry artifact digest mismatch: {rel}")
        entries[f"{PACKAGE.relative_to(ROOT).as_posix()}/{rel.as_posix()}"] = payload

    release = {
        "schema_id": "r3a.module-release-package.v1", "schema_version": 1,
        "module_id": "r3a.octominer-telemetry", "module_version": version,
        "provider_id": "r3a.octominer-telemetry", "provider_version": version,
        "package_path": PACKAGE.relative_to(ROOT).as_posix(),
        "manifest_ref": f"{PACKAGE.relative_to(ROOT).as_posix()}/{manifest_name}",
        "entrypoint": operation["provider"]["entrypoint"],
        "host_compatibility": {"contract_id": "r3a.capability-provider.v1",
                               "protocol_major": 1, "protocol_min_minor": 0,
                               "protocol_max_minor": 1},
        "capabilities": [{"operation_id": operation["operation_id"],
                           "contract_version": operation["contract_version"],
                           "operation_revision": operation["operation_revision"],
                           "effect_class": operation["effect_class"],
                           "required_grants": operation["required_grants"]}],
        "files": [{"path": path, "sha256": _sha(payload), "size_bytes": len(payload)}
                  for path, payload in sorted(entries.items())],
        "managed_activation": "not performed by package build",
    }
    entries["RELEASE_MANIFEST.json"] = _json_bytes(release)
    return entries


def build_package(version: str, output: Path) -> tuple[str, int]:
    entries = build_entries(version)
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for path, payload in sorted(entries.items()):
                info = tarfile.TarInfo(path)
                info.size = len(payload)
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                tar.addfile(info, io.BytesIO(payload))
    packed = buffer.getvalue()
    output.write_bytes(packed)
    digest = _sha(packed)
    try:
        sidecar_name = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        sidecar_name = output.name
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {sidecar_name}\n", encoding="ascii")
    return digest, len(packed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=sorted(VERSIONS), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    digest, size = build_package(args.version, output)
    print(json.dumps({"module_id": "r3a.octominer-telemetry", "module_version": args.version,
                      "artifact": str(output), "sha256": digest, "size_bytes": size,
                      "activation": "not performed"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
