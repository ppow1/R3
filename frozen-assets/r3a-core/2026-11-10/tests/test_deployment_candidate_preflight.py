# R3 CONTROLLED SOURCE
# File: tests/test_deployment_candidate_preflight.py
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Permanent offline failure-path and isolation preflight regressions
# Execution Model: Python unittest with temporary local Git repository
# Observability: subprocess exit codes, filesystem assertions
# Dependencies: Python standard library and git
# Authority: Steward permanent regression policy
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-009 | ChatGPT GPT-6 | Add fail-closed candidate preflight tests
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not executed on Camrui at commit time
# History/Predecessor: None
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "deployment" / "prepare_candidate.py"


class CandidatePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="r3-preflight-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.active_marker = self.source / "active-marker"
        self.active_marker.write_text("must remain unchanged", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("add", ".")
        self.git("commit", "-qm", "preflight fixture")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.candidate = self.root / "candidate"

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.source), *args],
                                text=True, capture_output=True, timeout=20)
        if result.returncode:
            self.fail(f"Git fixture failed: {result.stderr}")
        return result

    def invoke(self, commit=None, target=None, requirements="requirements-deploy.lock"):
        return subprocess.run(
            [sys.executable, str(BUILDER),
             "--source", str(self.source),
             "--commit", self.commit if commit is None else commit,
             "--candidate-root", str(self.candidate if target is None else target),
             "--requirements", requirements,
             "--timeout", "5"],
            text=True, capture_output=True, timeout=20,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def assert_untouched(self):
        self.assertEqual(self.active_marker.read_text(encoding="utf-8"), "must remain unchanged")
        self.assertFalse(self.candidate.exists())
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.commit)

    def test_missing_lockfile_blocks_before_directory_creation(self):
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUILD_BLOCKED", result.stderr)
        self.assert_untouched()

    def test_invalid_revision_blocks_before_directory_creation(self):
        result = self.invoke(commit="f" * 40)
        self.assertNotEqual(result.returncode, 0)
        self.assert_untouched()

    def test_malformed_revision_blocks_before_directory_creation(self):
        result = self.invoke(commit="main")
        self.assertNotEqual(result.returncode, 0)
        self.assert_untouched()

    def test_candidate_inside_source_is_rejected(self):
        result = self.invoke(target=self.source / "nested")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.source / "nested").exists())
        self.assert_untouched()

    def test_existing_candidate_is_not_overwritten(self):
        self.candidate.mkdir()
        marker = self.candidate / "keep"
        marker.write_text("preserve", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
        self.assertEqual(self.active_marker.read_text(encoding="utf-8"), "must remain unchanged")

    def test_path_traversal_in_requirements_is_rejected(self):
        result = self.invoke(requirements="../requirements-deploy.lock")
        self.assertNotEqual(result.returncode, 0)
        self.assert_untouched()

    def test_invalid_lockfile_blocks_before_directory_creation(self):
        (self.source / "requirements-deploy.lock").write_text(
            "fastapi>=0.162.0", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "invalid lock")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Requirement must be an exact pinned package", result.stderr)
        self.assert_untouched()


if __name__ == "__main__":
    unittest.main()
