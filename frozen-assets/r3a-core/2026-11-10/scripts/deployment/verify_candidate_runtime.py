#!/usr/bin/env python3
# R3 CONTROLLED SOURCE
# File: scripts/deployment/verify_candidate_runtime.py
# Component: R3-MANIFEST-DEPLOY
# Purpose: Bounded, loopback-only candidate runtime smoke verification.
# Never activates or restarts the production website.
"""Run the candidate on an ephemeral loopback port, verify HTTP, then terminate it."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

def candidate_paths(root):
    root = Path(root).resolve(strict=True)
    if root == Path("/home/admin1/R3") or root == Path("/home/admin1/R3").parent:
        raise ValueError("Refusing active checkout")
    source = root / "source"
    python = root / "venv" / "bin" / "python"
    if not source.is_dir() or not python.is_file() or not (source / "r3_app.py").is_file():
        raise ValueError("Incomplete candidate")
    return root, source, python

def request(url, timeout=2):
    with urlopen(url, timeout=timeout) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read(65536)

def check_http(port):
    base = f"http://127.0.0.1:{port}"
    status, kind, data = request(base + "/api/v1/health")
    if status != 200 or "json" not in kind:
        raise RuntimeError("Health endpoint HTTP/content type mismatch")
    health = json.loads(data)
    if health.get("service") != "r3" or health.get("status") != "running" or health.get("repository_present") is not True:
        raise RuntimeError("Candidate health contract mismatch")
    status, kind, data = request(base + "/")
    if status != 200 or "html" not in kind or not data:
        raise RuntimeError("Candidate homepage contract mismatch")
    return {"health": health, "homepage_status": status}

def verify(root, startup_timeout):
    root, source, python = candidate_paths(root)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    # Reserve a random loopback port; no production listener or proxy is touched.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env["R3_REPO"] = str(source)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    with (logs / "runtime-uvicorn.log").open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [str(python), "-m", "uvicorn", "r3_app:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log"],
            cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            deadline = time.monotonic() + startup_timeout
            while True:
                if proc.poll() is not None:
                    raise RuntimeError(f"Candidate server exited early: {proc.returncode}")
                try:
                    evidence = check_http(port)
                    break
                except (OSError, HTTPError, URLError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Candidate startup/HTTP verification timed out")
                    time.sleep(0.2)
            result = {
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=source, text=True, timeout=10).strip(),
                "candidate_path": str(root),
                "loopback_port": port,
                "health": evidence["health"],
                "homepage_status": evidence["homepage_status"],
                "runtime_pass": True,
                "activation": "NOT_RUN",
            }
            (logs / "runtime-verification.json").write_text(
                json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return result
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--startup-timeout", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.startup_timeout <= 120:
        parser.error("startup timeout must be 1..120")
    result = verify(args.candidate_root, args.startup_timeout)
    print("RUNTIME_VERIFICATION_PASS=TRUE")
    print("HEALTH_HTTP=200")
    print("HOMEPAGE_HTTP=200")
    print(f"CANDIDATE_COMMIT={result['source_commit']}")
    print("CANDIDATE_SERVER_STOPPED=TRUE")
    print("WEBSITE_ACTIVATION=NOT_RUN")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RUNTIME_VERIFICATION_PASS=FALSE; ERROR={exc}", file=sys.stderr)
        sys.exit(1)
