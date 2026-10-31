# R3 CONTROLLED SOURCE
# File: tools/check_file_headers.py
# Component: ENG-PROVENANCE-CHECK
# File Revision: 1.0.0
# Created: 2026-10-31 UTC (exact time unavailable)
# Created By: ChatGPT GPT-6
# Purpose: Check mandatory provenance fields in controlled text/source files
# Execution Model: Command-line, on demand or CI
# Observability: stdout diagnostics and nonzero exit status
# Dependencies: Python standard library, local Git checkout
# Authority: Read-only validation; no file modification
# Changed: 2026-10-31 UTC | R3-PROVENANCE-001 | ChatGPT GPT-6 | Initial validator
# Supersedes: None
# Contracts: hints/file-provenance.md
# Tests: Not executed in target R3 checkout
# History/Predecessor: Initial revision; Git commit
"""Check headers of tracked R3 text/source files without modifying them."""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT = {".md", ".py", ".sh", ".ps1", ".js", ".ts", ".tsx", ".jsx", ".css", ".html"}
FIELDS = ("File:", "Component:", "File Revision:", "Created:", "Created By:",
          "Purpose:", "Execution Model:", "Observability:", "Dependencies:",
          "Authority:", "Changed:", "Supersedes:", "Contracts:", "Tests:", "History")
result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
failures = []
for raw in result.stdout.split(b"\0"):
    if not raw:
        continue
    relative = raw.decode("utf-8", "surrogateescape")
    path = ROOT / relative
    if path.suffix.lower() not in TEXT or not path.is_file():
        continue
    try:
        start = path.read_text(encoding="utf-8").splitlines()[:45]
    except (OSError, UnicodeError) as exc:
        failures.append(f"{relative}: unreadable ({exc})")
        continue
    header = "\n".join(start)
    missing = [field for field in FIELDS if field not in header]
    if missing:
        failures.append(f"{relative}: missing {', '.join(missing)}")
if failures:
    print("R3 provenance validation FAILED")
    print("\n".join(failures))
    sys.exit(1)
print("R3 provenance header fields present for tracked supported text files")
print("NOTE: Binary sidecars, revision monotonicity, backup retrieval, and timestamp authenticity are not validated.")
