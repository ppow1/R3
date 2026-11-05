#!/usr/bin/env python3
# R3 CONTROLLED SOURCE
# File: scripts/deployment/generate_dependency_lock.py
# Component: R3-MANIFEST-DEPLOY
# Purpose: Generate a candidate-only, Linux/Python-3.12 wheel hash lock.
# No writes to the active R3 checkout or virtual environment.
"""Resolve candidate requirements in a disposable directory; emit a reviewed lock candidate.

The output contains SHA256 hashes of downloaded wheels, not invented hashes.
The lock is target-platform-specific. Review and test it before committing.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from email.parser import BytesParser
from email.policy import default

# pip vendors packaging, so no installation into the production venv is needed.
from pip._vendor.packaging.utils import parse_wheel_filename, canonicalize_name

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if not args.inputs.is_file():
        ap.error("Missing dependency input file")
    if args.output.exists():
        ap.error("Output already exists: refusing overwrite")
    if not 1 <= args.timeout <= 1800:
        ap.error("Invalid timeout")
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux":
        ap.error("Target must be Linux Python 3.12")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.output.name):
        ap.error("Unsafe output filename")
    with tempfile.TemporaryDirectory(prefix="r3-lock-wheels-") as td:
        wheel_dir = Path(td)
        cmd = [sys.executable, "-m", "pip", "download", "--disable-pip-version-check",
               "--only-binary=:all:", "--dest", str(wheel_dir), "-r", str(args.inputs)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
        if result.returncode:
            print(result.stdout[-5000:], file=sys.stderr)
            print(result.stderr[-5000:], file=sys.stderr)
            raise RuntimeError(f"pip download failed: {result.returncode}")
        packages = {}
        for wheel in wheel_dir.iterdir():
            if wheel.suffix != ".whl":
                raise RuntimeError(f"Non-wheel artifact: {wheel.name}")
            name, version, build, tags = parse_wheel_filename(wheel.name)
            key = canonicalize_name(str(name))
            if key in packages:
                raise RuntimeError(f"Multiple wheels for package: {key}")
            with ZipFile(wheel) as archive:
                metadata_names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
                if len(metadata_names) != 1:
                    raise RuntimeError(f"Missing/ambiguous wheel metadata: {wheel.name}")
                meta = BytesParser(policy=default).parsebytes(archive.read(metadata_names[0]))
                if canonicalize_name(meta["Name"]) != key or str(meta["Version"]) != str(version):
                    raise RuntimeError(f"Wheel metadata mismatch: {wheel.name}")
            packages[key] = (str(version), hashlib.sha256(wheel.read_bytes()).hexdigest(), wheel.name)
        if not packages:
            raise RuntimeError("No wheels resolved")
        lines = [
            "# R3 deployment lock; Linux CPython 3.12, candidate platform only.",
            "# Generated from downloaded wheel bytes; review before committing.",
            "# Regenerate and retest for other platforms or Python versions.",
        ]
        for key, (version, digest, _) in sorted(packages.items()):
            lines.append(f"{key}=={version} --hash=sha256:{digest}")
        data = "\n".join(lines) + "\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8", errors="strict")
        print(f"LOCK_GENERATED={args.output}")
        print(f"PINNED_PACKAGES={len(packages)}")
        print(f"LOCK_SHA256={hashlib.sha256(data.encode()).hexdigest()}")
        print("PRODUCTION_MODIFIED=FALSE")
        print("LOCK_REVIEW_REQUIRED=TRUE")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        sys.exit(1)
