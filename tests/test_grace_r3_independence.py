"""Permanent R3 independence regression for Grace native runtime modules.

This checks actual import resolution in an isolated subprocess as well as
forbidden source-level imports; R2 modules are not needed or loaded.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "runtime" / "capabilities.py",
          ROOT / "runtime" / "capability_authority.py",
          ROOT / "runtime" / "grant_management.py",
          ROOT / "runtime" / "resident_identity.py",
          ROOT / "runtime" / "governed_tools.py",
          ROOT / "runtime" / "grace_native_capabilities.py",
          ROOT / "runtime" / "native_tools.py",
          ROOT / "runtime" / "tool_server.py")


class GraceIndependenceTests(unittest.TestCase):
    def test_native_modules_do_not_import_legacy_application(self):
        for path in NATIVE:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    self.assertFalse(name == "riverview_core" or
                                     name.startswith("riverview_core."),
                                     f"{path}: forbidden R2 application import {name}")

    def test_native_authority_bootstraps_without_r2_python_path(self):
        script = """
import tempfile
from pathlib import Path
from runtime.capability_authority import R3Authority, initialize_empty_schema
from runtime.capabilities import CapabilityDenied
with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / 'r3-authority.db'
    initialize_empty_schema(db)
    authority = R3Authority(db)
    try:
        authority.authorize(principal='resident:grace',
                            resource_id='resource:office', action='office.update',
                            operation='write', scope_ref='office:grace')
    except CapabilityDenied:
        pass
    else:
        raise AssertionError('Empty R3 authority must deny')
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT)
        env.pop("R2_HOME", None)
        env.pop("RIVERVIEW_R2_HOME", None)
        completed = subprocess.run([sys.executable, "-I", "-c",
            "import sys; sys.path.insert(0, " + repr(str(ROOT)) + ");\n" + script],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
