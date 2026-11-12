#!/usr/bin/env python3
"""Build a deterministic, separately staged Knowledge 1.2.0 module bundle.

R3 CONTROLLED SOURCE
File: scripts/package_knowledge_module.py
Component: R3A-KNOWLEDGE-MODULE-PACKAGER
File Revision: 1.0.0
Created: 2026-11-08 UTC (exact time recorded in Git commit)
Created By: Codex GPT-6
Purpose: Package Knowledge 1.2.0 with independent hashes and a distinct import path.
Execution Model: Deterministic tar.gz build from versioned provider manifests and dependencies.
Observability: Package manifest, per-file digests, bundle SHA-256, and contract checks.
Dependencies: Python 3.12; R3A generic provider protocol v1 and host runtime capability provider.
Authority: Issue #47; package staging only, no managed activation.
Changed: 2026-11-08 | AP1-K2 | Codex GPT-6 | Add non-destructive versioned module packaging.
Supersedes: None.
Contracts: module manifest v1; capability provider v1; Steward capability contract 1.1.0.
Tests: tests/test_knowledge_module_package.py.
History/Predecessor: New file; initial publication recorded in Git.
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
MODULE_SOURCE = ROOT / "r3a_plugins/institutional_knowledge_v1_2_0"
PACKAGE_DIR = "r3a_plugins/institutional_knowledge_v1_2_0"
ENTRYPOINT = PACKAGE_DIR.replace("/", ".") + ".plugin:create_provider"
OPERATION_MANIFESTS = (
    "manifest.read.json", "manifest.proposals-list.json", "manifest.proposals-decide.json",
)
MODULE_FILES = ("__init__.py", "plugin.py", "review_store.py", "config.example.json")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def build_entries() -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    for relative in MODULE_FILES:
        entries[f"{PACKAGE_DIR}/{relative}"] = (MODULE_SOURCE / relative).read_bytes()
    for filename in OPERATION_MANIFESTS:
        manifest = json.loads((MODULE_SOURCE / filename).read_text(encoding="utf-8"))
        if manifest["plugin_version"] != "1.2.0" or manifest["provider"]["provider_version"] != "1.2.0":
            raise ValueError(f"{filename} is not bound to provider 1.2.0")
        if manifest["provider"]["entrypoint"] != ENTRYPOINT:
            raise ValueError(f"{filename} has unexpected source entrypoint")
        manifest["provider"]["entrypoint"] = ENTRYPOINT
        manifest["operation"]["provider"]["entrypoint"] = ENTRYPOINT
        module = manifest.pop("module_manifest", None)
        if module is not None and module.get("module_version") != "1.2.0":
            raise ValueError(f"{filename} has a mismatched module manifest")
        # The deployed Coordinator config loader currently rejects this optional
        # extension. The release manifest below carries module identity/protocol
        # pins; canonical operation manifests remain the runtime registration API.
        entries[f"{PACKAGE_DIR}/{filename}"] = _json_bytes(manifest)

    for relative in (
        "r3a_runtime/migrations/010_governed_knowledge.sql",
        "docs/knowledge-discovery/r3a-knowledge-review-api.v1.json",
        "docs/knowledge-discovery/KNOWLEDGE_1_2_0_RELEASE.md",
    ):
        entries[relative] = (ROOT / relative).read_bytes()

    # Verify the digests pinned by each released manifest before packaging.
    for filename in OPERATION_MANIFESTS:
        manifest = json.loads(entries[f"{PACKAGE_DIR}/{filename}"])
        for ref, expected in [(manifest["artifact_ref"], manifest["artifact_sha256"])]:
            actual = _sha(entries[f"{PACKAGE_DIR}/{ref}"])
            if actual != expected:
                raise ValueError(f"{filename} artifact pin mismatch for {ref}")
        for item in manifest.get("supporting_artifacts", []):
            actual = _sha(entries[f"{PACKAGE_DIR}/{item['artifact_ref']}"])
            if actual != item["artifact_sha256"]:
                raise ValueError(f"{filename} supporting-artifact pin mismatch")
        effect = manifest["operation"]["effect_class"]
        contract = manifest["operation"]["contract_version"]
        if effect.startswith("steward_") and contract != "1.1.0":
            raise ValueError("Steward operation must use the agreed generic contract 1.1.0")

    package_manifest = {
        "schema_id": "r3a.module-release-package.v1", "schema_version": 1,
        "module_id": "r3a.institutional-knowledge", "module_version": "1.2.0",
        "provider_id": "r3a.institutional-knowledge", "provider_version": "1.2.0",
        "package_path": PACKAGE_DIR,
        "entrypoint": ENTRYPOINT,
        "host_compatibility": {"contract_id": "r3a.capability-provider.v1", "protocol_major": 1,
                               "protocol_min_minor": 0, "protocol_max_minor": 1},
        "capabilities": [
            {"operation_id": "institution.knowledge.read", "contract_version": "1.0.0", "operation_revision": "1.1.0", "effect_class": "read"},
            {"operation_id": "institution.knowledge.proposals.list", "contract_version": "1.1.0", "operation_revision": "1.0.0", "effect_class": "steward_read"},
            {"operation_id": "institution.knowledge.proposals.decide", "contract_version": "1.1.0", "operation_revision": "1.0.0", "effect_class": "steward_write"},
        ],
        "database_migration": "r3a_runtime/migrations/010_governed_knowledge.sql",
        "runtime_dependencies": ["R3A runtime capability provider v1", "psycopg 3"],
        "files": [{"path": path, "sha256": _sha(raw)} for path, raw in sorted(entries.items())],
        "managed_activation": "not performed by package build",
    }
    entries["RELEASE_MANIFEST.json"] = _json_bytes(package_manifest)
    return entries


def build_package(output: Path) -> tuple[str, int]:
    entries = build_entries()
    output.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for path, raw in sorted(entries.items()):
                info = tarfile.TarInfo(path)
                info.size = len(raw)
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                tar.addfile(info, io.BytesIO(raw))
    payload = buffer.getvalue()
    output.write_bytes(payload)
    digest = _sha(payload)
    try:
        checksum_path = output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        checksum_path = output.name
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {checksum_path}\n", encoding="ascii")
    return digest, len(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/r3a.institutional-knowledge-1.2.0.tar.gz")
    args = parser.parse_args(argv)
    digest, size = build_package(args.output.expanduser().resolve())
    print(json.dumps({"module_id": "r3a.institutional-knowledge", "module_version": "1.2.0",
                      "artifact": str(args.output.expanduser().resolve()), "sha256": digest,
                      "size_bytes": size, "staged_import_path": PACKAGE_DIR,
                      "managed_activation": "not performed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
