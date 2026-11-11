# R3 CONTROLLED SOURCE
# File: tests/test_deployment_candidate_execution.py
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.0
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Verify candidate staging, regression gating and failure diagnostics offline
# Execution Model: Python unittest; real temporary Git clone, mocked venv/pip/tests
# Observability: assertions on logs, outputs and unchanged source
# Dependencies: Python standard library and git
# Authority: Steward permanent regression policy
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-010 | ChatGPT GPT-6 | Offline execution-path integration fixtures
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not executed at commit time
# History/Predecessor: None
import contextlib
import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BUILDER = Path(__file__).resolve().parents[1] / "scripts" / "deployment" / "prepare_candidate.py"
spec = importlib.util.spec_from_file_location("r3_candidate_execution", BUILDER)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class CandidateExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="r3-execution-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "requirements-deploy.lock").write_text(
            "example==1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
        (self.source / "sentinel").write_text("unchanged", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("add", ".")
        self.git("commit", "-qm", "isolated fixture")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()
        self.target = self.root / "candidate"
        self.calls = []
        self.real_run = builder.run

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.source), *args],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def simulated_run(self, args, *, cwd=None, timeout=300, output=None, env=None):
        self.calls.append(tuple(args))
        if len(args) >= 3 and args[1:3] == ["-m", "venv"]:
            venv = Path(args[3])
            (venv / "bin").mkdir(parents=True)
            (venv / "bin" / "python").touch()
            if output:
                output.write_text("venv simulated\n", encoding="utf-8")
            return ""
        if len(args) >= 3 and args[1:3] == ["-m", "pip"]:
            self.assertIn("--require-hashes", args)
            self.assertTrue(str(args[0]).startswith(str(self.target / "venv")))
            if output:
                output.write_text("pip simulated\n", encoding="utf-8")
            if getattr(self, "fail_phase", None) == "pip":
                raise RuntimeError("simulated pip failure")
            return ""
        if len(args) >= 3 and args[1:3] == ["-m", "unittest"]:
            self.assertEqual(cwd, self.target / "source")
            self.assertEqual(env.get("PYTHONDONTWRITEBYTECODE"), "1")
            if output:
                output.write_text("unittest simulated\n", encoding="utf-8")
            if getattr(self, "fail_phase", None) == "tests":
                raise RuntimeError("simulated regression failure")
            return ""
        return self.real_run(args, cwd=cwd, timeout=timeout, output=output, env=env)

    def execute(self, fail_phase=None):
        self.fail_phase = fail_phase
        args = ["prepare_candidate.py", "--source", str(self.source),
                "--commit", self.commit, "--candidate-root", str(self.target),
                "--timeout", "20"]
        captured = io.StringIO()
        with patch.object(sys, "argv", args), patch.object(builder, "run", self.simulated_run):
            with contextlib.redirect_stdout(captured):
                if fail_phase:
                    with self.assertRaisesRegex(RuntimeError, "simulated"):
                        builder.main()
                else:
                    builder.main()
        self.assertEqual((self.source / "sentinel").read_text(encoding="utf-8"), "unchanged")
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.commit)
        return captured.getvalue()

    def test_success_stages_exact_revision_and_never_activates(self):
        result = self.execute()
        self.assertIn("BUILD_PASS=TRUE", result)
        self.assertIn("REGRESSION_PASS=TRUE", result)
        self.assertIn("ACTIVATION=DISABLED", result)
        self.assertEqual(subprocess.run(
            ["git", "-C", str(self.target / "source"), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip(), self.commit)
        self.assertTrue((self.target / "logs" / "regressions.log").exists())
        self.assertFalse(any("systemctl" in " ".join(map(str, c)) for c in self.calls))

    def test_pip_failure_aborts_before_regressions_and_preserves_logs(self):
        result = self.execute("pip")
        self.assertNotIn("REGRESSION_PASS=TRUE", result)
        self.assertTrue((self.target / "logs" / "dependencies.log").exists())
        self.assertFalse((self.target / "logs" / "regressions.log").exists())
        self.assertFalse(any(len(c) > 2 and c[1:3] == ("-m", "unittest") for c in self.calls))

    def test_regression_failure_keeps_candidate_and_diagnostics(self):
        result = self.execute("tests")
        self.assertIn("BUILD_PASS=TRUE", result)
        self.assertNotIn("REGRESSION_PASS=TRUE", result)
        self.assertTrue((self.target / "logs" / "regressions.log").exists())
        self.assertTrue((self.target / "source" / "sentinel").exists())


if __name__ == "__main__":
    unittest.main()
