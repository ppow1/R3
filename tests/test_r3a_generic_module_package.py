"""Permanent acceptance tests for generic resident process-module packaging.

R3 CONTROLLED TEST SOURCE
File: tests/test_r3a_generic_module_package.py
Component: TEST-R3A-GENERIC-MODULE-PACKAGE
File Revision: 1.0.0
Created: 2026-11-11T18:20:00Z
Created By: Codex GPT-6
Purpose: Verify deterministic package integrity, safe immutable staging, version collision handling, and fail-closed package validation.
Execution Model: Temporary archives and install roots only; no CME or shared service calls.
Observability: Bundle digest, inventory, install path/mode, and explicit rejection behavior.
Dependencies: scripts.package_r3a_module; package schema v2; audited Grace package source spec.
Authority: Step 78 dispatch 6804259280; no activation, grant, or deployment authority.
Changed: 2026-11-11T18:20:00Z | R3A-MODULE-PACKAGE-V2 | Codex GPT-6 | Add package and installer regressions.
Supersedes: None.
Contracts: r3a.module-release-package.v2@2.0.0; AP0-M1.
Tests: python3 -m pytest -q tests/test_r3a_generic_module_package.py
History/Predecessor: New test source.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import jsonschema

from scripts.package_r3a_module import (
    ROOT,
    SPEC,
    RELEASE_NAME,
    build_package,
    install_package,
    resolve_launch_plan,
    verify_package,
)


def _alter_member(package: Path, destination: Path, member_name: str, replacement: bytes) -> None:
    entries = {}
    with tarfile.open(package, "r:gz") as archive:
        for member in archive.getmembers():
            stream = archive.extractfile(member)
            assert stream is not None
            entries[member.name] = stream.read()
    entries[member_name] = replacement
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, payload in sorted(entries.items()):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mode = 0o444
                archive.addfile(info, io.BytesIO(payload))
    destination.write_bytes(buffer.getvalue())


def test_audited_grace_worker_builds_deterministic_verified_package_and_installs_immutably():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        first, second = root / "first.tar.gz", root / "second.tar.gz"
        first_record = build_package(SPEC, ROOT, first)
        second_record = build_package(SPEC, ROOT, second)
        assert first_record["bundle_sha256"] == second_record["bundle_sha256"]
        assert first.read_bytes() == second.read_bytes()

        descriptor, entries = verify_package(first)
        schema = json.loads((ROOT / "r3a_runtime/schemas/module-release-package.v2.schema.json").read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(descriptor, schema)
        assert descriptor["schema_id"] == "r3a.module-release-package.v2"
        assert descriptor["module"]["module_id"] == "resident.grace"
        assert descriptor["module"]["module_version"] == "1.2.15"
        assert descriptor["role"]["contract_id"] == "r3a.resident.executor"
        assert descriptor["launch_profile"]["protocol_id"] == "r3a.module-jsonl-worker.v1"
        assert descriptor["launch_profile"]["argv_template"][0:2] == ["-m", "r3a_runtime.grace_module"]
        assert len(entries) == 12
        assert "runtime/r3a_runtime/grace_module.py" in entries
        assert hashlib.sha256(entries["runtime/r3a_runtime/grace_module.py"]).hexdigest() == \
               descriptor["module"]["entrypoint_sha256"]

        installed = install_package(first, root / "app")
        assert installed["state"] == "INSTALLED"
        assert not installed["idempotent"]
        package_root = Path(installed["install_path"])
        assert package_root.is_dir()
        assert package_root.stat().st_mode & 0o777 == 0o555
        assert json.loads((package_root / RELEASE_NAME).read_text(encoding="utf-8")) == descriptor
        assert (package_root / "runtime/r3a_runtime/grace_module.py").stat().st_mode & 0o777 == 0o444
        assert verify_package(package_root / "package.tar.gz")[0] == descriptor
        plan = resolve_launch_plan(
            package_root, descriptor, socket_path=Path("/tmp/r3a-package-fixture.sock"),
            module_id="resident.grace", module_version="1.2.15",
            configuration_path=Path("/tmp/r3a-package-fixture-config.json"))
        assert plan["shell"] is False
        assert plan["bundle_sha256"] == installed["bundle_sha256"]
        assert plan["argv"] == [
            "-m", "r3a_runtime.grace_module", "--socket", "/tmp/r3a-package-fixture.sock",
            "--module-id", "resident.grace", "--module-version", "1.2.15",
            "--config", "/tmp/r3a-package-fixture-config.json"]
        help_run = subprocess.run([plan["executable"], "-m", "r3a_runtime.grace_module", "--help"],
                                  cwd=plan["cwd"],
                                  env={**os.environ, **plan["environment"]},
                                  capture_output=True, text=True, check=False)
        assert help_run.returncode == 0, help_run.stderr
        assert "--socket" in help_run.stdout
        repeated = install_package(first, root / "app")
        assert repeated["idempotent"]
        assert repeated["install_path"] == installed["install_path"]


def test_install_rejects_same_module_version_with_different_archive_digest():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        first = root / "first.tar.gz"
        build_package(SPEC, ROOT, first)
        install_package(first, root / "app")

        modified_spec = json.loads(SPEC.read_text(encoding="utf-8"))
        modified_spec["module"]["owner"] = "Autonomy release candidate"
        spec_path = root / "alternate-spec.json"
        spec_path.write_text(json.dumps(modified_spec), encoding="utf-8")
        alternate = root / "alternate.tar.gz"
        build_package(spec_path, ROOT, alternate)
        assert hashlib.sha256(first.read_bytes()).digest() != hashlib.sha256(alternate.read_bytes()).digest()
        with pytest.raises(ValueError, match="different package digest"):
            install_package(alternate, root / "app")


def test_newer_release_install_keeps_prior_version_artifact_available_for_rollback():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        old_spec = json.loads(SPEC.read_text(encoding="utf-8"))
        old_spec["module"]["module_version"] = "1.2.14"
        old_spec_path = root / "old-spec.json"
        old_spec_path.write_text(json.dumps(old_spec), encoding="utf-8")
        old_package = root / "old.tar.gz"
        build_package(old_spec_path, ROOT, old_package)
        old_install = install_package(old_package, root / "app")

        new_package = root / "new.tar.gz"
        build_package(SPEC, ROOT, new_package)
        new_install = install_package(new_package, root / "app")

        assert old_install["module_version"] == "1.2.14"
        assert new_install["module_version"] == "1.2.15"
        assert Path(old_install["install_path"]).is_dir()
        assert Path(old_install["install_path"]).joinpath("package.tar.gz").is_file()
        assert verify_package(Path(old_install["install_path"]) / "package.tar.gz")[0]["module"]["module_version"] == "1.2.14"


def test_verifier_rejects_content_tampering_and_path_traversal():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        package = root / "good.tar.gz"
        build_package(SPEC, ROOT, package)
        tampered = root / "tampered.tar.gz"
        _alter_member(package, tampered, "runtime/r3a_runtime/grace_module.py", b"changed source")
        with pytest.raises(ValueError, match="file digest mismatch"):
            verify_package(tampered)

        unsafe = root / "unsafe.tar.gz"
        _alter_member(package, unsafe, "../escape", b"no")
        with pytest.raises(ValueError, match="unsafe package path"):
            verify_package(unsafe)


def test_build_rejects_modified_audited_source_closure():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        source = root / "source"
        shutil.copytree(ROOT / "r3a_runtime", source / "r3a_runtime")
        (source / "r3a_runtime/grace_module.py").write_text("# unexpected source\n", encoding="utf-8")
        with pytest.raises(ValueError, match="source artifact digest mismatch"):
            build_package(SPEC, source, root / "bad.tar.gz")


def test_launch_profile_rejects_shell_or_undeclared_argument_placeholders():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        spec["launch_profile"]["argv_template"] = ["/bin/sh", "-c", "{arbitrary_command}"]
        spec_path = root / "unsafe-spec.json"
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        with pytest.raises(ValueError, match="fixed Python module invocation"):
            build_package(spec_path, ROOT, root / "unsafe.tar.gz")


def test_launch_plan_rejects_mismatched_module_identity_and_modified_installed_bytes():
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        artifact = root / "package.tar.gz"
        build_package(SPEC, ROOT, artifact)
        installed = install_package(artifact, root / "app")
        descriptor, _ = verify_package(artifact)
        install_path = Path(installed["install_path"])
        with pytest.raises(ValueError, match="does not match the installed immutable module"):
            resolve_launch_plan(install_path, descriptor, socket_path=root / "worker.sock",
                                module_id="resident.other", module_version="1.2.15",
                                configuration_path=root / "bootstrap.json")
        (install_path / "runtime/r3a_runtime/grace_module.py").chmod(0o644)
        (install_path / "runtime/r3a_runtime/grace_module.py").write_text("# changed\n", encoding="utf-8")
        with pytest.raises(ValueError, match="installed module file differs"):
            resolve_launch_plan(install_path, descriptor, socket_path=root / "worker.sock",
                                module_id="resident.grace", module_version="1.2.15",
                                configuration_path=root / "bootstrap.json")
