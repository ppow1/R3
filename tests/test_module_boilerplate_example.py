"""Focused conformance checks for the offline R3A module boilerplate example.

R3 CONTROLLED SOURCE
File: tests/test_module_boilerplate_example.py
Component: TEST-R3A-MODULE-BOILERPLATE
File Revision: 1.0.3
Created: 2026-11-11T21:52:37Z
Created By: Codex GPT-6
Purpose: Check the example metadata, immutable source pins, external configuration, resident binding and lifecycle-only process behavior.
Execution Model: unittest; launches one disposable local Unix-socket process fixture.
Observability: Assertions over actual fixture bytes and correlated JSON-lines responses.
Dependencies: Python 3.12 standard library; project r3a_runtime.protocol and capability_contracts.validate_json; existing resident module binding schema.
Authority: Steward assignment #68 comment 6807799874; Planned Step 126 comment 6807801282. Offline source validation only.
Changed: 2026-11-11T21:52:37Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Add focused offline boilerplate conformance and lifecycle checks.
Changed: 2026-11-11T21:59:39Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Cover undeclared config rejection and authority-free metadata.
Changed: 2026-11-11T22:04:26Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Pin only the explicit package file list and prevent bytecode from entering the artifact tree.
Changed: 2026-11-11T22:07:30Z | R3A-MODULE-BOILERPLATES-STEP-120 | Codex GPT-6 | Align the test command with the executable Python 3 command.
Supersedes: None.
Contracts: r3a.module-release-metadata.v1@1.0.0; r3a.module-process-binding.v1@1.0.0; r3a.resident.module-binding.v1@1.0.0; r3a.module.v1.
Tests: python3 -m unittest tests.test_module_boilerplate_example.
History/Predecessor: New file.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from r3a_runtime.capability_contracts import validate_json
from r3a_runtime.protocol import request


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/r3a_module_boilerplate"
ARTIFACT = EXAMPLE / "artifact"
MODULE_ID = "example.module-boilerplate"
MODULE_VERSION = "1.0.0"
ARTIFACT_FILES = ("boilerplate_worker/__init__.py", "boilerplate_worker/worker.py")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _artifact_tree_digest() -> str:
    records = []
    actual = sorted(p.relative_to(ARTIFACT).as_posix() for p in ARTIFACT.rglob("*") if p.is_file())
    if actual != sorted(ARTIFACT_FILES):
        raise AssertionError(f"artifact contains undeclared files: {actual}")
    for relative in sorted(ARTIFACT_FILES):
        raw = (ARTIFACT / relative).read_bytes()
        records.append(f"{relative}\0{_sha(raw)}\0{len(raw)}\n")
    return _sha(("r3a-module-artifact-tree.v1\n" + "".join(records)).encode("utf-8"))


class ModuleBoilerplateExampleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = json.loads((EXAMPLE / "MODULE_METADATA.json").read_text(encoding="utf-8"))
        self.binding = json.loads((EXAMPLE / "process-binding.json").read_text(encoding="utf-8"))
        self.config_schema = json.loads((EXAMPLE / "configuration.schema.json").read_text(encoding="utf-8"))
        self.config = json.loads((EXAMPLE / "configuration.example.json").read_text(encoding="utf-8"))
        self.resident_binding = json.loads(
            (EXAMPLE / "resident-module-binding.example.json").read_text(encoding="utf-8"))

    def test_release_metadata_process_binding_and_tree_digest_are_pinned(self):
        digest = _artifact_tree_digest()
        self.assertRegex(digest, r"^[a-f0-9]{64}$")
        self.assertEqual(self.metadata["schema_id"], "r3a.module-release-metadata.v1")
        self.assertEqual(self.metadata["schema_version"], 1)
        self.assertEqual(self.metadata["module_id"], MODULE_ID)
        self.assertEqual(self.metadata["module_version"], MODULE_VERSION)
        self.assertEqual(self.metadata["artifact_digest"], digest)
        self.assertEqual(self.metadata["role"]["contract_id"], "r3a.resident.executor")
        self.assertEqual(self.binding["contract_id"], "r3a.module-process-binding.v1")
        self.assertEqual(self.binding["contract_version"], "1.0.0")
        self.assertEqual(self.binding["protocol_id"], "r3a.module.v1")
        self.assertEqual(self.binding["runtime_id"], "python3")
        self.assertEqual(self.binding["entrypoint"], "boilerplate_worker.worker")
        self.assertEqual(self.binding["arguments_template"], [
            "--socket", "{socket_path}", "--module-id", "{module_id}",
            "--module-version", "{module_version}", "--config", "{configuration_path}"])
        self.assertNotIn("shell", json.dumps(self.binding).lower())
        metadata_text = json.dumps(self.metadata).lower()
        self.assertNotIn("grant", metadata_text)
        self.assertNotIn("capability", metadata_text)

    def test_external_configuration_and_synthetic_resident_binding_validate(self):
        validate_json(self.config, self.config_schema, path="$.configuration")
        schema = json.loads((ROOT / "r3a_runtime/schemas/resident-module-binding.v1.schema.json")
                            .read_text(encoding="utf-8"))
        self.resident_binding["artifact_digest"] = self.metadata["artifact_digest"]
        self.resident_binding["configuration_revision"] = _sha(
            (EXAMPLE / "configuration.example.json").read_bytes())
        validate_json(self.resident_binding, schema, path="$.resident_binding")
        self.assertEqual(self.resident_binding["resident_id"], "resident:example")
        self.assertEqual(self.resident_binding["identity_association"]["authority"], "fixture-only")
        self.assertIn("example-not-registered", self.resident_binding["identity_association"]["record_id"])
        self.assertNotIn("secret", json.dumps(self.config).lower())

    def test_worker_lifecycle_runs_over_existing_protocol_and_execute_fails_closed(self):
        with tempfile.TemporaryDirectory(prefix="r3a-module-boilerplate-") as temp:
            temp_path = Path(temp)
            socket_path = temp_path / "run" / "module.sock"
            config_path = EXAMPLE / "configuration.example.json"
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH", "")]))
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.Popen([
                sys.executable, "-m", self.binding["entrypoint"],
                "--socket", str(socket_path), "--module-id", MODULE_ID,
                "--module-version", MODULE_VERSION, "--config", str(config_path)],
                cwd=ARTIFACT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                deadline = time.monotonic() + 5
                while not socket_path.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(socket_path.exists(), "worker did not create its private socket")
                hello = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "hello"))
                self.assertEqual(hello["result"], {
                    "contract_id": "r3a.resident.execution", "contract_version": "1.0.0"})
                health = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "health"))
                self.assertEqual(health["result"]["state"], "READY")
                prepared = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "prepare"))
                self.assertTrue(prepared["result"]["accepted"])
                activated = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "activate"))
                self.assertEqual(activated["result"]["state"], "ACTIVE")
                checkpoint = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "checkpoint"))
                self.assertEqual(checkpoint["result"]["state"], "ACTIVE")
                with self.assertRaisesRegex(RuntimeError, "NotImplementedError"):
                    asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "execute"))
                stopped = asyncio.run(request(socket_path, MODULE_ID, MODULE_VERSION, "stop"))
                self.assertTrue(stopped["result"]["stopped"])
                self.assertEqual(process.wait(timeout=5), 0)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()

    def test_worker_rejects_undeclared_external_configuration(self):
        with tempfile.TemporaryDirectory(prefix="r3a-module-config-check-") as temp:
            temp_path = Path(temp)
            config_path = temp_path / "invalid.json"
            config_path.write_text(json.dumps({**self.config, "settings": {"secret": "value"}}),
                                   encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH", "")]))
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            result = subprocess.run([
                sys.executable, "-m", self.binding["entrypoint"],
                "--socket", str(temp_path / "unused.sock"), "--module-id", MODULE_ID,
                "--module-version", MODULE_VERSION, "--config", str(config_path)],
                cwd=ARTIFACT, env=env, capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("undeclared setting", result.stderr)


if __name__ == "__main__":
    unittest.main()
