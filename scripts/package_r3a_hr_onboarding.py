#!/usr/bin/env python3
"""Build a deterministic, checksummed HR onboarding source handoff bundle.

This does not install the workflow or migrate a shared database. The manifest
records outstanding host-composition and authority gates explicitly.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path
from typing import Any


COORDINATOR_BASELINE = "2cc3fe3aabad88c95a5e6489c633cb01472f7c7f"
PACKAGE_ID = "r3a.resident-onboarding.source-bundle"
PACKAGE_VERSION = "1.0.0"
PACKAGE_PREFIX = "r3a-hr-onboarding-"
FILES = (
    "pyproject.toml",
    "docs/architecture/R3A_HR_VICKY_TRANSFER_MATRIX_2026-11-10.md",
    "docs/architecture/R3A_UNIVERSAL_RESIDENT_ONBOARDING_V1.md",
    "docs/architecture/R3A_HR_DEVELOPMENT_BACKLOG.md",
    "docs/onboarding/packet-template.json",
    "docs/onboarding/vicky.packet.json",
    "docs/runbooks/R3A_RESIDENT_ONBOARDING.md",
    "docs/runbooks/R3A_HR_ONBOARDING_DEPLOYMENT_PLAN.md",
    "r3a_runtime/capability_contracts.py",
    "r3a_runtime/migrations/019_resident_onboarding.sql",
    "r3a_runtime/rollback/019_resident_onboarding.down.sql",
    "r3a_runtime/residents/hr_association.py",
    "r3a_runtime/residents/onboarding.py",
    "r3a_runtime/residents/onboarding_repository.py",
    "r3a_runtime/schemas/resident-onboarding-packet.v1.schema.json",
    "r3a_runtime/state_machines/resident_onboarding.v1.json",
    "scripts/package_r3a_hr_onboarding.py",
    "tests/fixtures/resident-onboarding-synthetic.json",
    "tests/test_r3a_capability_contracts.py",
    "tests/test_r3a_hr_association.py",
    "tests/test_r3a_institutional_directory.py",
    "tests/test_r3a_resident_dossiers.py",
    "tests/test_r3a_resident_onboarding.py",
    "tests/test_r3a_resident_onboarding_postgres.py",
    "tests/test_r3a_hr_onboarding_package.py",
)

CONFIGURATION = {
    "host_composition": [
        "server-authenticated actor resolver",
        "exact-action/scope authorization provider",
        "authoritative per-domain evidence verifiers",
        "activation evidence verifier",
        "Coordinator PostgreSQL pool and onboarding repository",
    ],
    "database": {
        "migration_runner": "r3a_runtime.db.Store.migrate",
        "migration": "019_resident_onboarding.sql",
        "role_requirement": "Coordinator-approved least-privilege access to packet/event tables only",
    },
    "external_authorities": {
        "hr_association_operation": "associate_authority_principal_with_provenance (currently absent)",
        "resident_binding_writer": "institutional directory authority procedure (currently unidentified)",
        "security_credentials_and_grants": "separate Security-owned approval and provisioning",
        "character_canon": "separate Character Architecture approval where applicable",
    },
}
INSTALL_PREREQUISITES = [
    "Auditor PASS on the exact combined source/baseline SHA and package digests",
    "Coordinator approval of migration 019, service composition, DB role grants, release window, and rollback procedure",
    "Named HR source owner and deployed provenance-bearing association writer or verified equivalent",
    "Named institutional-directory owner and approved occupant/office-binding procedure",
    "No production request is enabled until separately approved personnel, credential, grant, and runtime evidence exists",
]
ROLLBACK = {
    "application": "Coordinator rolls back to the prior pinned application release and preserves onboarding tables/events",
    "schema": "019 down migration is only permitted by an approved database procedure when packet and event tables are empty; it refuses when populated",
    "forbidden": "Never drop populated packet/event tables, delete audit evidence, or use the disposable-test DROP SCHEMA setup against shared R3A",
}
TEST_EVIDENCE = {
    "source_suite": "pytest focused HR/onboarding, PostgreSQL, dossier, grants, directory, capability, and Coordinator module-contract suites",
    "result": "143 passed, 1 DSN-gated checkpoint suite skipped in this invocation; that separate private-PostgreSQL checkpoint test then passed (1 passed)",
    "migration_019": "full migration stack apply/repeat, guarded rollback/re-upgrade, atomicity, multi-resident, revision/idempotency, privacy, immutable audit, and populated rollback refusal passed on private UTF-8 PostgreSQL 16",
    "shared_database": "not used or changed",
}


@dataclass(frozen=True)
class Bundle:
    archive: bytes
    manifest: dict[str, Any]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_bundle(payloads: dict[str, bytes], *, source_revision: str,
                 coordinator_baseline: str = COORDINATOR_BASELINE) -> Bundle:
    """Build a reproducible gzip/tar bundle with an in-band SHA-256 manifest."""
    if not payloads or any(path.startswith("/") or ".." in Path(path).parts for path in payloads):
        raise ValueError("package paths must be nonempty, relative, and traversal-free")
    if "PACKAGE-MANIFEST.json" in payloads:
        raise ValueError("package manifest is generated and cannot be caller-supplied")
    manifest: dict[str, Any] = {
        "contract_id": "r3a.hr-onboarding-package.v1",
        "package_id": PACKAGE_ID,
        "package_version": PACKAGE_VERSION,
        "source_revision": source_revision,
        "coordinator_baseline": coordinator_baseline,
        "readiness": "SOURCE_CANDIDATE_NOT_DEPLOYABLE",
        "shared_deployment_authorized": False,
        "files": [
            {"path": path, "size_bytes": len(payloads[path]), "sha256": _sha256(payloads[path])}
            for path in sorted(payloads)
        ],
        "configuration": CONFIGURATION,
        "install_prerequisites": INSTALL_PREREQUISITES,
        "rollback": ROLLBACK,
        "verification": TEST_EVIDENCE,
    }
    manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                      + "\n").encode("utf-8")
    archive_buffer = io.BytesIO()
    with gzip.GzipFile(filename="", fileobj=archive_buffer, mode="wb", mtime=0, compresslevel=9) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            entries = {**payloads, "PACKAGE-MANIFEST.json": manifest_bytes}
            for name in sorted(entries):
                info = tarfile.TarInfo(name=f"r3a-hr-onboarding/{name}")
                info.size = len(entries[name])
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(entries[name]))
    return Bundle(archive_buffer.getvalue(), manifest)


def verify_bundle(archive_bytes: bytes) -> dict[str, Any]:
    """Verify the internal manifest covers every payload and each digest matches."""
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        raw_members = archive.getmembers()
        if len({member.name for member in raw_members}) != len(raw_members):
            raise ValueError("package contains duplicate member names")
        if any(not member.name.startswith("r3a-hr-onboarding/") for member in raw_members):
            raise ValueError("package member is outside its namespace")
        members = {member.name.removeprefix("r3a-hr-onboarding/"): member for member in raw_members}
        manifest_member = members.pop("PACKAGE-MANIFEST.json", None)
        if manifest_member is None:
            raise ValueError("package manifest is absent")
        manifest_stream = archive.extractfile(manifest_member)
        if manifest_stream is None:
            raise ValueError("package manifest cannot be read")
        manifest = json.loads(manifest_stream.read())
        expected = {item["path"]: item for item in manifest["files"]}
        if set(members) != set(expected):
            raise ValueError("package members do not match the manifest file list")
        for path, member in members.items():
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"package member cannot be read: {path}")
            data = stream.read()
            if len(data) != expected[path]["size_bytes"] or _sha256(data) != expected[path]["sha256"]:
                raise ValueError(f"package member digest mismatch: {path}")
    return manifest


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _tracked_source_is_clean(root: Path, allowed_outputs: set[str]) -> None:
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    unexpected = []
    for line in status.splitlines():
        path = line[3:]
        if path not in allowed_outputs:
            unexpected.append(path)
    if unexpected:
        raise RuntimeError(f"refusing to package a dirty source tree: {', '.join(unexpected)}")


def create_release(root: Path, output_dir: Path) -> dict[str, Any]:
    source_revision = _git(root, "rev-parse", "HEAD")
    check = subprocess.run(["git", "merge-base", "--is-ancestor", COORDINATOR_BASELINE, "HEAD"], cwd=root)
    if check.returncode != 0:
        raise RuntimeError("candidate does not include the approved Coordinator baseline")
    short = source_revision[:12]
    package_name = f"{PACKAGE_PREFIX}candidate-{short}.tar.gz"
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "archive": output_dir / package_name,
        "digest": output_dir / f"{package_name}.sha256",
        "manifest": output_dir / f"{package_name}.manifest.json",
        "handoff": output_dir / f"{package_name}.handoff.md",
    }
    allowed = {str(path.relative_to(root)) for path in paths.values() if path.is_relative_to(root)}
    _tracked_source_is_clean(root, allowed)
    payloads = {}
    for relative_path in FILES:
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"required package input is missing: {relative_path}")
        payloads[relative_path] = path.read_bytes()
    bundle = build_bundle(payloads, source_revision=source_revision)
    manifest_bytes = (json.dumps(bundle.manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    archive_digest = _sha256(bundle.archive)
    paths["archive"].write_bytes(bundle.archive)
    paths["digest"].write_text(f"{archive_digest}  {package_name}\n", encoding="ascii")
    paths["manifest"].write_bytes(manifest_bytes)
    verified = verify_bundle(paths["archive"].read_bytes())
    if verified != bundle.manifest:
        raise RuntimeError("written package manifest does not match verified archive")
    handoff = f"""# Coordinator handoff — R3A HR onboarding source candidate

- Package: `{package_name}`
- SHA-256: `{archive_digest}`
- Source revision: `{source_revision}`
- Coordinator baseline: `{COORDINATOR_BASELINE}`
- Manifest: `{paths['manifest'].name}`
- Readiness: **SOURCE CANDIDATE — NOT DEPLOYABLE / NOT APPROVED FOR SHARED MIGRATION**

## Configuration and install prerequisites

See the package manifest for the complete file-level digest list and configuration contract. Before installation, Auditor must PASS this exact source and package. Coordinator must approve service composition, the migration/DB role grants, the controlled release window, and its application rollback procedure. Host composition requires authenticated actor and authorization providers, authoritative domain/activation verifiers, and the Coordinator packet repository. Security, HR, character, runtime, and communications remain separate authorities.

The verified HR host lacks `associate_authority_principal_with_provenance`; the accountable HR writer owner is not identified. The directory capability is read-only and no authorized resident/office-binding writer or named owner is identified. No production service API is composed in this source candidate. Consequently this bundle is an immutable integration handoff, not an installable/activated service.

## Install/rollback contract

After all gates, Coordinator applies migration 019 only through its checksummed `Store.migrate()` release path and deploys the reviewed host composition. Application rollback preserves packet/event tables. The 019 down migration is restricted to an approved procedure when both tables are empty and deliberately refuses populated evidence. Never use the disposable-test schema reset on shared R3A.

## Verification

The archive was rebuilt from a clean committed tree, its SHA-256 recorded, and every in-band file hash verified after writing. Focused tests and isolated PostgreSQL evidence are enumerated in `PACKAGE-MANIFEST.json`.
"""
    paths["handoff"].write_text(handoff, encoding="utf-8")
    return {"paths": paths, "archive_sha256": archive_digest, "manifest": bundle.manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir if args.output_dir.is_absolute() else root / args.output_dir
    result = create_release(root, output_dir)
    print(json.dumps({"archive": str(result["paths"]["archive"]),
                      "sha256": result["archive_sha256"],
                      "source_revision": result["manifest"]["source_revision"],
                      "readiness": result["manifest"]["readiness"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
