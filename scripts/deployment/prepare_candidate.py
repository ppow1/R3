#!/usr/bin/env python3
# R3 CONTROLLED SOURCE
# File: scripts/deployment/prepare_candidate.py
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.2
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Prepare isolated website candidate and run bounded unittest regression suite
# Execution Model: Python 3.12; explicit opt-in; no website activation
# Observability: stdout status and candidate-local build/test logs
# Dependencies: git, Python venv, pip, reviewed hash-locked requirements
# Authority: Steward directive for R3 isolated candidate build
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-007 | ChatGPT GPT-6 | Repair literal escaped newline in Python preflight
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-005 | ChatGPT GPT-6 | Fail-closed lock parser and candidate preflight hardening
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-004 | ChatGPT GPT-6 | Initial fail-closed candidate stage
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not executed against Camrui; requires independent verification
# History/Predecessor: Git blob 74330358a4ae0d63f439efaf4c1bf9ecfd37d663
"""Never stops/restarts services, mutates active checkout, or activates candidates."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

SHA = re.compile(r"^[0-9a-fA-F]{40}$")
HASH = re.compile(r"--hash=sha256:[0-9a-fA-F]{64}")
LOCK_ENTRY = re.compile(r"^[A-Za-z0-9_.-]+==[^\s;]+")
ACTIVE = Path("/home/admin1/R3").resolve()


def run(args, *, cwd=None, timeout=300, output=None, env=None):
    with subprocess.Popen(args, cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, env=env) as proc:
        try:
            data, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            data, _ = proc.communicate()
            if output:
                output.write_text(data, encoding="utf-8")
            raise RuntimeError(f"TIMEOUT: {' '.join(args[:3])} after {timeout}s")
        if output:
            output.write_text(data, encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"EXIT={proc.returncode}: {' '.join(args[:3])}; output={output or data[-1200:]}")
        return data


def validate_lock(contents):
    """Allow only exact pinned package entries with explicit SHA256 hashes.

    This deliberately supports a narrow pip-compile style subset. Reject
    unsupported syntax rather than silently weakening hash enforcement.
    """
    entries = []
    current = ""
    for raw in contents.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("\\"):
            current += line[:-1].strip() + " "
            continue
        current += line
        entries.append(current.strip())
        current = ""
    if current:
        raise ValueError("Unterminated requirements continuation")
    if not entries:
        raise ValueError("Lockfile has no pinned packages")
    for entry in entries:
        parts = entry.split()
        if not parts or not re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.!+~-]+", parts[0]):
            raise ValueError("Requirement must be an exact pinned package")
        if len(parts) < 2 or any(not re.fullmatch(r"--hash=sha256:[0-9a-fA-F]{64}", part) for part in parts[1:]):
            raise ValueError("Every package must have SHA256 hashes and no other options")
    return len(entries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Existing Git repository")
    ap.add_argument("--commit", required=True, help="Exact 40-character Git commit")
    ap.add_argument("--candidate-root", required=True, help="New, nonexisting directory")
    ap.add_argument("--requirements", default="requirements-deploy.lock")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if not SHA.fullmatch(args.commit):
        ap.error("--commit must be an exact 40-character SHA")
    if not 1 <= args.timeout <= 1800:
        ap.error("--timeout must be between 1 and 1800 seconds")
    if (not re.fullmatch(r"[A-Za-z0-9_./-]+", args.requirements) or
            Path(args.requirements).is_absolute() or ".." in Path(args.requirements).parts):
        ap.error("--requirements must be a relative path without ..")
    source = Path(args.source).resolve(strict=True)
    target = Path(args.candidate_root).resolve()
    if not source.is_dir() or not (source / ".git").exists():
        ap.error("--source must be a Git working checkout")
    if target.exists():
        ap.error("--candidate-root must not exist (no overwrite)")
    if target == ACTIVE or ACTIVE in target.parents or target in ACTIVE.parents:
        ap.error("Candidate path overlaps active website checkout")
    if target == source or source in target.parents or target in source.parents:
        ap.error("Candidate path overlaps source checkout")
    if target.parent == Path("/") or not target.parent.is_dir():
        ap.error("Candidate parent directory must already exist")
    if target.is_symlink() or any(p.is_symlink() for p in target.parents):
        ap.error("Candidate path/parent must not be a symlink")
    resolved = run(["git", "-C", str(source), "rev-parse", "--verify", f"{args.commit}^{{commit}}"], timeout=30).strip()
    if resolved.lower() != args.commit.lower():
        raise RuntimeError("Commit identity mismatch")
    lock_bytes = subprocess.run(["git", "-C", str(source), "show",
                                 f"{args.commit}:{args.requirements}"],
                                capture_output=True, timeout=30)
    if lock_bytes.returncode:
        raise RuntimeError("BUILD_BLOCKED: lockfile missing from selected commit")
    package_count = validate_lock(lock_bytes.stdout.decode("utf-8"))
    print(f"LOCKFILE_VERIFIED=TRUE; PINNED_PACKAGES={package_count}", flush=True)
    target.mkdir(mode=0o700)
    logs = target / "logs"
    logs.mkdir()
    try:
        run(["git", "clone", "--no-checkout", "--local", str(source), str(target / "source")],
            timeout=120, output=logs / "clone.log")
        checkout = target / "source"
        run(["git", "checkout", "--detach", args.commit], cwd=checkout,
            timeout=60, output=logs / "checkout.log")
        actual = run(["git", "rev-parse", "HEAD"], cwd=checkout, timeout=30).strip()
        if actual.lower() != args.commit.lower():
            raise RuntimeError("Candidate revision mismatch")
        venv = target / "venv"
        run([sys.executable, "-m", "venv", str(venv)], timeout=120, output=logs / "venv.log")
        python = venv / "bin" / "python"
        if not python.is_file():
            raise RuntimeError("Candidate Python missing")
        run([str(python), "-m", "pip", "install", "--require-hashes",
             "-r", str(checkout / args.requirements)],
            timeout=args.timeout, output=logs / "dependencies.log")
        print("BUILD_PASS=TRUE", flush=True)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run([str(python), "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_*.py", "-v"], cwd=checkout, timeout=args.timeout,
            output=logs / "regressions.log", env=env)
        print("REGRESSION_PASS=TRUE", flush=True)
        print(f"CANDIDATE_PATH={target}", flush=True)
        print("ACTIVATION=DISABLED", flush=True)
        print("DEPLOY_PASS=NOT_RUN", flush=True)
        print("ACCEPTANCE_PASS=NOT_RUN", flush=True)
    except Exception:
        print("BUILD_OR_REGRESSION_PASS=FALSE; ACTIVATION=DISABLED", flush=True)
        raise


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        sys.exit(1)
