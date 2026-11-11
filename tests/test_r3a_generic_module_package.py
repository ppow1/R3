"""Grace-specific source-pin acceptance for the shared module-release package v2 tool.

R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_generic_module_package.py
Component: TEST-R3A-GRACE-SHARED-PACKAGE-V2
File Revision: 2.0.0
Purpose: Verify the audited Grace source closure through the shared generic package and process-binding contracts.
Execution Model: Temporary archives/install roots and a local --help process only; no CME or shared service calls.
Authority: Step 78 dispatch 6804259280; no activation, grant, or deployment authority.
Contracts: r3a.module-release-package.v2@2.0.0; r3a.module-process-binding.v1@1.0.0; AP0-M1.
Tests: python3 -m pytest -q tests/test_r3a_generic_module_package.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.build_grace_module_package import (
    DEFAULT_SPEC,
    ROOT,
    artifact_tree_digest,
    build_grace_package,
    source_inputs,
)
from scripts.r3a_module_release_package import (
    build_package,
    discard_unactivated_candidate,
    install_package,
    verify_package,
)
from r3a_runtime.capability_contracts import validate_json


def test_audited_grace_closure_builds_deterministically_and_installs_with_shared_binding():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        first, second = root / "first.tar.gz", root / "second.tar.gz"
        a = build_grace_package(DEFAULT_SPEC, ROOT, first)
        b = build_grace_package(DEFAULT_SPEC, ROOT, second)
        assert a["bundle_sha256"] == b["bundle_sha256"]
        assert first.read_bytes() == second.read_bytes()

        descriptor, files, manifest = verify_package(first, expected_bundle_sha256=a["bundle_sha256"])
        assert descriptor["schema_id"] == "r3a.module-release-package.v2"
        assert descriptor["module_kind"] == "resident_executor"
        assert descriptor["module_id"] == "resident.grace"
        assert descriptor["module_version"] == "1.2.15"
        assert len(files) == 12
        assert descriptor["artifact_digest"] == artifact_tree_digest(files)
        assert manifest["resident_executor"]["contract_id"] == "r3a.resident.executor"
        assert descriptor["process_binding"]["contract_id"] == "r3a.module-process-binding.v1"
        assert descriptor["process_binding"]["entrypoint"] == "r3a_runtime.grace_module"
        assert "grant" not in json.dumps(descriptor).lower()

        installed = install_package(first, root / "stage", expected_bundle_sha256=a["bundle_sha256"])
        target = Path(installed["path"])
        artifact_root = Path(installed["artifact_root"])
        assert installed["installed"] and not installed["idempotent"]
        assert target.stat().st_mode & 0o777 == 0o555
        assert (artifact_root / "r3a_runtime/grace_module.py").is_file()
        assert (artifact_root / "r3a_runtime/grace_module.py").stat().st_mode & 0o777 == 0o444

        process = subprocess.run(
            [os.environ.get("PYTHON", "python3"), "-m", "r3a_runtime.grace_module", "--help"],
            cwd=artifact_root, env={**os.environ, "PYTHONPATH": str(artifact_root)},
            capture_output=True, text=True, check=False)
        assert process.returncode == 0, process.stderr
        assert "--socket" in process.stdout

        repeated = install_package(first, root / "stage", expected_bundle_sha256=a["bundle_sha256"])
        assert repeated["idempotent"]
        assert repeated["path"] == installed["path"]


def test_grace_adapter_fails_closed_when_audited_source_bytes_change(tmp_path):
    source = tmp_path / "source"
    for item in json.loads(DEFAULT_SPEC.read_text(encoding="utf-8"))["source_files"]:
        src = ROOT / item["source"]
        dst = source / item["source"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    changed = source / "r3a_runtime/grace_module.py"
    changed.write_bytes(changed.read_bytes() + b"\n# unreviewed change\n")
    with pytest.raises(ValueError, match="audited Grace source digest mismatch"):
        build_grace_package(DEFAULT_SPEC, source, tmp_path / "modified.tar.gz")


@pytest.mark.xfail(strict=True, reason=(
    "Shared package candidate's reduced 1.2 manifest does not validate against the audited standard module-manifest schema; #46 contract reconciliation required"
))
def test_packaged_manifest_is_accepted_by_the_audited_standard_module_manifest_contract():
    with TemporaryDirectory() as temporary:
        package = Path(temporary) / "grace.tar.gz"
        record = build_grace_package(DEFAULT_SPEC, ROOT, package)
        _, _, manifest = verify_package(package, expected_bundle_sha256=record["bundle_sha256"])
        schema_path = ROOT / "r3a_runtime/schemas/module-manifest.v1.1.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validate_json(manifest, schema)


def test_shared_installer_rejects_different_artifact_digest_for_same_version(tmp_path):
    manifest, binding, files = source_inputs(DEFAULT_SPEC, ROOT)
    first = tmp_path / "first.tar.gz"
    first_record = build_package(manifest, binding, files, first)
    install_package(first, tmp_path / "stage", expected_bundle_sha256=first_record["bundle_sha256"])

    changed_files = dict(files)
    changed_files["r3a_runtime/grace_module.py"] += b"\n# different artifact\n"
    changed_manifest = dict(manifest)
    changed_manifest["artifact_digest"] = artifact_tree_digest(changed_files)
    other = tmp_path / "other.tar.gz"
    other_record = build_package(changed_manifest, binding, changed_files, other)
    assert other_record["artifact_digest"] != first_record["artifact_digest"]
    with pytest.raises(FileExistsError, match="different immutable artifact digest"):
        install_package(other, tmp_path / "stage", expected_bundle_sha256=other_record["bundle_sha256"])


def test_shared_installer_retains_effective_prior_version_and_discards_only_failed_candidate(tmp_path):
    manifest, binding, files = source_inputs(DEFAULT_SPEC, ROOT)
    old_manifest = dict(manifest)
    old_manifest["module_version"] = "1.2.14"
    old_package = tmp_path / "old.tar.gz"
    old_record = build_package(old_manifest, binding, files, old_package)
    old_install = install_package(old_package, tmp_path / "stage",
                                  expected_bundle_sha256=old_record["bundle_sha256"])

    new_package = tmp_path / "new.tar.gz"
    new_record = build_package(manifest, binding, files, new_package)
    new_install = install_package(new_package, tmp_path / "stage",
                                  expected_bundle_sha256=new_record["bundle_sha256"])
    assert Path(old_install["path"]).is_dir()
    assert Path(new_install["path"]).is_dir()

    removed = discard_unactivated_candidate(
        tmp_path / "stage", "resident.grace", "1.2.15", new_record["artifact_digest"],
        effective_artifact_digest=old_record["artifact_digest"], effective_module_version="1.2.14",
        module_lifecycle_state="FAILED")
    assert removed
    assert Path(old_install["path"]).is_dir()
    assert not Path(new_install["path"]).exists()
    with pytest.raises(PermissionError, match="cannot discard the effective"):
        discard_unactivated_candidate(
            tmp_path / "stage", "resident.grace", "1.2.14", old_record["artifact_digest"],
            effective_artifact_digest=old_record["artifact_digest"], effective_module_version="1.2.14",
            module_lifecycle_state="STOPPED")
