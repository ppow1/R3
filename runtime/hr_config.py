# R3 CONTROLLED SOURCE
# File: runtime/hr_config.py
# Component: HR-CONFIG
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (date precision)
# Created By: ChatGPT GPT-6
# Purpose: Load and validate R/3 HR JSON operational configuration
# Execution Model: Local Python; explicit config path
# Observability: Explicit validation errors
# Dependencies: Python 3.10+ standard library
# Authority: R/3 deployment configuration; identity verification required
# Changed: 2026-11-05 UTC | HR-005 | Add JSON loader
# Supersedes: None
# Contracts: config/hr.json; hints/architecture.md
# Tests: tests/test_hr_config.py
# History/Predecessor: New file
"""Configuration loader for shared HR adapters and deployment."""
from __future__ import annotations
import json
from pathlib import Path

def load_hr_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("unsupported HR configuration version")
    for name in ("service", "directory", "storage", "operations", "authorization"):
        if not isinstance(config.get(name), dict):
            raise ValueError("missing HR configuration section: " + name)
    auth = config["authorization"]
    if auth.get("require_verified_principal") is not True:
        raise ValueError("HR identity verification is required")
    if not isinstance(auth.get("provider"), str) or not auth["provider"]:
        raise ValueError("HR authority provider required")
    ops = config["operations"]
    for key in ("worker_concurrency", "request_timeout_seconds"):
        value = ops.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError("invalid HR setting: " + key)
    return config
