# R3 CONTROLLED SOURCE
# File: runtime/configuration.py
# Component: R3-CONFIGURATION
# File Revision: 1.0.2
# Created: 2026-11-02 UTC
# Purpose: Validate externally defined runtime and resident settings.
# Dependencies: Python standard library only.
# Contracts: hints/milestones/2026-11-02-r3-six-phase-roadmap-phase1.md
# Tests: tests/test_configuration.py
# Changed: 2026-11-03T01:37:00.460Z | R3-VERIFY-WIRING-001 | Codex | Validate the configured independent reviewer, tools and manager.
# Changed: 2026-11-03T01:39:59.849Z | R3-VERIFY-WIRING-002 | Codex | Preserve loading of resident configurations without an optional reviewer.
# History/Predecessor: Git blob b42c627df1ad343e27a6f1779fe5c4fab6cde1c7
"""Small, strict JSON configuration loader; no implicit runtime defaults."""
from __future__ import annotations

import json
import math
from pathlib import Path


class ConfigurationError(ValueError):
    pass


def _object(value, where):
    if not isinstance(value, dict):
        raise ConfigurationError(f"{where} must be an object")
    return value


def _text(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{where} must be nonempty text")
    return value


def _positive(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"{where} must be a finite positive number")
    return float(value)


def _url(value, where):
    value = _text(value, where)
    if not value.startswith(("http://", "https://")):
        raise ConfigurationError(f"{where} must use HTTP(S)")
    return value


def _read_json(path):
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Cannot load {path}: {exc}") from exc


def load_configuration(directory: str | Path):
    """Return validated settings and resident definitions; never silently default."""
    root = Path(directory).resolve()
    runtime = _read_json(root / "runtime.json")
    _positive(runtime.get("scheduler_tick_seconds"), "scheduler_tick_seconds")
    _positive(runtime.get("health_interval_seconds"), "health_interval_seconds")
    _positive(runtime.get("sqlite_busy_timeout_ms"), "sqlite_busy_timeout_ms")
    residents = _object(runtime.get("residents"), "residents")
    if not residents:
        raise ConfigurationError("At least one resident must be configured")
    definitions = []
    names = set()
    for key, relative in residents.items():
        _text(key, "resident key")
        relative = _text(relative, f"resident {key} file")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ConfigurationError("Resident configuration escapes config directory")
        entry = _read_json(path)
        name = _text(entry.get("name"), f"{key}.name")
        if name in names:
            raise ConfigurationError(f"Duplicate resident name: {name}")
        names.add(name)
        enabled = entry.get("enabled")
        if not isinstance(enabled, bool):
            raise ConfigurationError(f"{key}.enabled must be boolean")
        _text(entry.get("role"), f"{key}.role")
        inference = _object(entry.get("inference"), f"{key}.inference")
        _url(inference.get("endpoint"), f"{key}.inference.endpoint")
        _text(inference.get("model"), f"{key}.inference.model")
        _positive(inference.get("timeout_seconds"), f"{key}.inference.timeout_seconds")
        _positive(entry.get("schedule_interval_seconds"), f"{key}.schedule_interval_seconds")
        activity_types = entry.get("continuation_event_types", [])
        if not isinstance(activity_types, list) or any(not isinstance(t, str) or not t.strip() for t in activity_types) or len(activity_types) != len(set(activity_types)):
            raise ConfigurationError(f"{key}.continuation_event_types must be unique nonempty strings")
        tools = _object(entry.get("tools"), f"{key}.tools")
        if tools.get("provider") not in ("none", "r3-native"):
            raise ConfigurationError(f"{key}.tools.provider must be none or r3-native")
        if tools["provider"] == "r3-native":
            _url(tools.get("endpoint"), f"{key}.tools.endpoint")
            _positive(tools.get("timeout_seconds"), f"{key}.tools.timeout_seconds")
            allowed = tools.get("allowed_tools")
            if not isinstance(allowed, list) or any(not isinstance(t, str) or not t for t in allowed) or len(allowed) != len(set(allowed)):
                raise ConfigurationError(f"{key}.tools.allowed_tools must be a unique list of names")
        prompt_path = (root / _text(entry.get("system_prompt_file"), f"{key}.system_prompt_file")).resolve()
        if not prompt_path.is_relative_to(root):
            raise ConfigurationError("System prompt escapes config directory")
        try:
            prompt = prompt_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigurationError(f"Cannot read prompt {prompt_path}: {exc}") from exc
        _text(prompt, f"{key}.system_prompt")
        definitions.append({"settings": entry, "system_prompt": prompt})
    if runtime.get("independent_reviewer") is None:
        return {"runtime": runtime, "residents": definitions, "reviewer": None}
    reviewer_relative = _text(runtime.get("independent_reviewer"), "independent_reviewer")
    reviewer_path = (root / reviewer_relative).resolve()
    if not reviewer_path.is_relative_to(root):
        raise ConfigurationError("Reviewer configuration escapes config directory")
    reviewer = _read_json(reviewer_path)
    reviewer_name = _text(reviewer.get("name"), "reviewer.name")
    if reviewer_name in names:
        raise ConfigurationError("Reviewer identity must be distinct from residents")
    manager = _text(reviewer.get("manager"), "reviewer.manager")
    if manager not in names:
        raise ConfigurationError("Reviewer manager must name a configured resident")
    enabled = reviewer.get("enabled")
    if not isinstance(enabled, bool) or not enabled:
        raise ConfigurationError("Independent reviewer must be enabled")
    inference = _object(reviewer.get("inference"), "reviewer.inference")
    _url(inference.get("endpoint"), "reviewer.inference.endpoint")
    _text(inference.get("model"), "reviewer.inference.model")
    _positive(inference.get("timeout_seconds"), "reviewer.inference.timeout_seconds")
    tools = _object(reviewer.get("tools"), "reviewer.tools")
    if tools.get("provider") != "r3-native":
        raise ConfigurationError("reviewer.tools.provider must be r3-native")
    _url(tools.get("endpoint"), "reviewer.tools.endpoint")
    _positive(tools.get("timeout_seconds"), "reviewer.tools.timeout_seconds")
    allowed = tools.get("allowed_tools")
    if not isinstance(allowed, list) or any(not isinstance(t, str) or not t for t in allowed) or len(allowed) != len(set(allowed)):
        raise ConfigurationError("reviewer.tools.allowed_tools must be a unique list of names")
    prompt_path = (root / _text(reviewer.get("system_prompt_file"), "reviewer.system_prompt_file")).resolve()
    if not prompt_path.is_relative_to(root):
        raise ConfigurationError("Reviewer system prompt escapes config directory")
    try:
        reviewer_prompt = prompt_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ConfigurationError(f"Cannot read reviewer prompt {prompt_path}: {exc}") from exc
    _text(reviewer_prompt, "reviewer.system_prompt")
    return {"runtime": runtime, "residents": definitions,
            "reviewer": {"settings": reviewer, "system_prompt": reviewer_prompt}}
