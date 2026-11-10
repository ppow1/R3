#!/usr/bin/env python3
"""Measure repeatable local release build, verification, and isolated installation.

R3 CONTROLLED SOURCE
File: scripts/measure_octominer_module_install.py
Component: R3A-MODULE-ACCEPTANCE-PREP
File Revision: 1.0.0
Created: 2026-11-10 UTC
Created By: Codex GPT-6
Purpose: Capture per-phase local install preparation timings without touching shared services.
Execution Model: Temporary-directory package build, integrity verification, and install.
Observability: JSON digest, package size, and elapsed seconds per phase and total.
Dependencies: Python 3.12; scripts.package_octominer_module.
Authority: Steward Directive — Issue #46, managed-runtime acceptance preparation.
Changed: 2026-11-10 | R3A-LIVE-MODULAR | Add repeatable isolated installation timing.
Supersedes: None.
Contracts: r3a.module-release-package.v1.
Tests: tests/test_r3a_module_acceptance_prep.py.
History/Predecessor: New utility for acceptance preparation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.package_octominer_module import build_package, install_package, verify_package


def measure() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="r3a-module-install-measure-") as directory:
        root = Path(directory)
        artifact = root / "release.tar.gz"
        total_start = time.perf_counter()

        start = time.perf_counter()
        built = build_package(artifact)
        build_seconds = time.perf_counter() - start

        start = time.perf_counter()
        release, _entries = verify_package(artifact)
        verify_seconds = time.perf_counter() - start

        start = time.perf_counter()
        installed = install_package(artifact, root / "application")
        install_seconds = time.perf_counter() - start
        total_seconds = time.perf_counter() - total_start

        if installed["idempotent"]:
            raise RuntimeError("fresh temporary install unexpectedly reported idempotent")
        if release["module_id"] != built["module_id"] or release["module_version"] != built["module_version"]:
            raise RuntimeError("package identity changed between build and verification")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest != built["sha256"] or digest != installed["bundle_sha256"]:
            raise RuntimeError("measured package digest changed across lifecycle steps")

        return {
            "schema_id": "r3a.module-install-measurement.v1",
            "module_id": built["module_id"],
            "module_version": built["module_version"],
            "bundle_sha256": digest,
            "size_bytes": built["size_bytes"],
            "isolated_temporary_root": True,
            "shared_services_touched": False,
            "elapsed_seconds": {
                "build": round(build_seconds, 6),
                "verify": round(verify_seconds, 6),
                "install": round(install_seconds, 6),
                "total": round(total_seconds, 6),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path,
                        help="also write the measurement record to this path")
    args = parser.parse_args()
    result = measure()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
