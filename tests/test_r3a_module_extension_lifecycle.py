"""
R3 CONTROLLED SOURCE
File: tests/test_r3a_module_extension_lifecycle.py
Component: TEST-R3A-MODULE-EXTENSION-LIFECYCLE
File Revision: 1.0.0
Created: 2026-11-10T01:09:23Z
Created By: Codex GPT-6
Purpose: Verify generic module metadata survives restart-free configuration reload.
Execution Model: Async in-memory CME/provider lifecycle fixture; no live process or database.
Observability: Stable CME and provider process identities are asserted across reload.
Dependencies: r3a_runtime.cme config.reload and provider process registry contracts.
Authority: AD-024; Modular Plugins #46; fixture acceptance only.
Changed: 2026-11-10T01:09:23Z | R3A-MODULAR-PLUGINS-46 | Codex GPT-6 | Add restart-free module configuration reload regression.
Supersedes: None
Contracts: MOD-013; module.lifecycle v2; provider configuration reload.
Tests: python3 -m pytest -q tests/test_r3a_module_extension_lifecycle.py
History/Predecessor: New file; initial publication recorded in Git.
"""
from __future__ import annotations

import asyncio
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import types
from unittest.mock import AsyncMock, patch

if importlib.util.find_spec("psycopg") is None:
    pg_module = types.ModuleType("psycopg")
    pg_module.__spec__ = importlib.machinery.ModuleSpec("psycopg", loader=None)
    pg_module.AsyncConnection = type("AsyncConnection", (), {})
    rows_module = types.ModuleType("psycopg.rows")
    rows_module.__spec__ = importlib.machinery.ModuleSpec("psycopg.rows", loader=None)
    rows_module.dict_row = object()
    pg_module.rows = rows_module
    sys.modules["psycopg"] = pg_module
    sys.modules["psycopg.rows"] = rows_module
if importlib.util.find_spec("psycopg_pool") is None:
    pool_module = types.ModuleType("psycopg_pool")
    pool_module.__spec__ = importlib.machinery.ModuleSpec("psycopg_pool", loader=None)
    pool_module.AsyncConnectionPool = type("AsyncConnectionPool", (), {})
    sys.modules["psycopg_pool"] = pool_module

from r3a_runtime.cme import CME


class _Registry:
    def __init__(self, provider_id: str, version: str):
        self.provider_id = provider_id
        self.version = version

    def discover(self, *, include_disabled=False, include_versions=False):
        return [{"descriptor": {"provider": {"provider_id": self.provider_id,
                                                "provider_version": self.version},
                                 "lifecycle": {"desired_state": "enabled"}}}]


def _settings(revision: str):
    return SimpleNamespace(
        source_path=Path("/tmp/r3a-config.json"), source_digest=revision,
        instance_id="r3a_fixture", database="r3a_fixture", database_user="r3a_runtime",
        database_socket_dir=Path("/tmp/r3a-pg"), database_port=55432,
        control_socket=Path("/tmp/r3a/control.sock"),
        diagnostics_socket=Path("/tmp/r3a/diagnostics.sock"),
        module_socket=Path("/tmp/r3a/module.sock"),
        capability_registry=_Registry("example.provider", "1.0.0"),
        authorization_provider=SimpleNamespace(provider_id="capability_grants", options={}),
        notification_sources=(), worker_concurrency=2, model_roles=(), module_id="resident.fixture")


def test_compatible_module_config_reload_keeps_core_and_provider_processes():
    async def run():
        previous, current = _settings("a" * 64), _settings("b" * 64)
        provider_process = SimpleNamespace(returncode=None, pid=41201)
        provider_runtime = SimpleNamespace(
            settings=previous, registry=previous.capability_registry,
            processes={("example.provider", "1.0.0"): SimpleNamespace(
                process=provider_process)}, install_all=AsyncMock())
        store = SimpleNamespace(
            settings=previous, activate_config=AsyncMock(return_value="b" * 64),
            register_resource=AsyncMock(), register_model_role=AsyncMock())
        cme = object.__new__(CME)
        cme.settings = previous
        cme.store = store
        cme.module_id = "resident.fixture"
        cme.provider_runtime = provider_runtime
        cme.active_activities = {}
        cme.module_pid = 41200
        cme.module_process = SimpleNamespace(pid=41200)
        prior_processes = dict(provider_runtime.processes)
        prior_cme_pid, prior_module_pid = cme.module_pid, cme.module_process.pid
        with patch("r3a_runtime.cme.load_settings", return_value=current), \
                patch("r3a_runtime.cme.create_authorization_provider", return_value=object()):
            result = await CME._control_request(cme, "config.reload", {}, "config-reload-1")
        assert result["activated"] is True
        assert cme.settings is current
        assert provider_runtime.settings is current
        assert provider_runtime.registry is current.capability_registry
        assert cme.module_pid == prior_cme_pid
        assert cme.module_process.pid == prior_module_pid
        assert provider_runtime.processes == prior_processes
        assert provider_process.pid == 41201 and provider_process.returncode is None
        provider_runtime.install_all.assert_awaited_once()

    asyncio.run(run())
