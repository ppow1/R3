# R3 CONTROLLED SOURCE
# File: runtime/hr_local.py
# Component: HR-LOCAL
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Reusable local stdio host with injectable local identity and policy
# Execution Model: Long-lived JSON-lines session over stdin/stdout
# Observability: Structured responses; no confidential payload logging
# Dependencies: Python 3.10+ standard library; runtime/hr_stdio.py
# Authority: Embedding application provides authenticated principal and policy
# Changed: 2026-11-05 UTC | HR-006 | Implement local stdio host composition
# Supersedes: None
# Contracts: runtime/hr_capability.py; runtime/hr_config.py
# Tests: tests/test_hr_local.py
# History/Predecessor: New file
"""Embed HR stdio in a trusted local application, without an MCP dependency.

The embedding host supplies a principal it has established independently
(e.g., its authenticated session or OS service identity), and its local
authorization policy. Never accept identity or permissions from stdin.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Callable, TextIO
from runtime.hr_capability import HRCapability, VerifiedPrincipal
from runtime.hr_config import load_hr_config
from runtime.hr_store import HRStore
from runtime.hr_stdio import serve

def run_local_stdio(
    *, config_path: str | Path, principal: VerifiedPrincipal,
    authorize: Callable[[VerifiedPrincipal, str, str], bool],
    input_stream: TextIO | None = None, output_stream: TextIO | None = None,
) -> None:
    """Run until input closes; no one-shot request limit or network dependency."""
    config = load_hr_config(config_path)
    if not config["service"].get("transports", {}).get("stdio", False):
        raise RuntimeError("stdio transport disabled in configuration")
    if not isinstance(principal, VerifiedPrincipal) or not principal.principal_id:
        raise PermissionError("authenticated local principal required")
    db_env = config["storage"].get("database_path_env")
    if not isinstance(db_env, str) or not db_env:
        raise ValueError("database environment setting missing")
    db_path = os.environ.get(db_env)
    if not db_path:
        raise RuntimeError("HR database path not configured")
    store = HRStore(db_path)
    try:
        capability = HRCapability(store, authorize)
        serve(capability, principal,
              input_stream if input_stream is not None else sys.stdin,
              output_stream if output_stream is not None else sys.stdout)
    finally:
        store.close()
