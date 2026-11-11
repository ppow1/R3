# R3 CONTROLLED SOURCE
# File: tests/test_deployment_candidate.py
# Component: R3-MANIFEST-DEPLOY
# File Revision: 1.0.1
# Created: 2026-11-05 UTC (exact time not independently verified)
# Created By: ChatGPT GPT-6
# Purpose: Permanent offline regression tests for fail-closed candidate preparation
# Execution Model: Python unittest; no SSH, pip installation, or service operations
# Observability: unittest assertions
# Dependencies: Python standard library
# Authority: Steward permanent regression testing policy
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-008 | ChatGPT GPT-6 | Correct continuation fixture to include actual backslash/newline
# Changed: 2026-11-05 UTC | R3-MANIFEST-DEPLOY-006 | ChatGPT GPT-6 | Initial candidate lock/preflight tests
# Supersedes: None
# Superseded By: None
# Contracts: docs/runbooks/R3_MANIFEST_DEPLOYMENT.md
# Tests: Not yet executed on Camrui
# History/Predecessor: Git blob 4240e80eb3fb1c73e50662fa73b27f6f6b405be7
import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "deployment" / "prepare_candidate.py"
spec = importlib.util.spec_from_file_location("r3_prepare_candidate", MODULE)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)

H = "a" * 64


class CandidateLockTests(unittest.TestCase):
    def test_accepts_exact_pinned_hash(self):
        self.assertEqual(candidate.validate_lock(f"fastapi==0.162.0 --hash=sha256:{H}\n"), 1)

    def test_accepts_continuation_and_multiple_hashes(self):
        continuation = chr(92) + chr(10)
        content = (
            f"fastapi==0.162.0 {continuation}"
            f"  --hash=sha256:{H} {continuation}"
            f"  --hash=sha256:{'b'*64}" + chr(10)
        )
        self.assertEqual(candidate.validate_lock(content), 1)

    def test_rejects_unpinned_requirement(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock(f"fastapi>=0.162.0 --hash=sha256:{H}")

    def test_rejects_missing_hash(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("fastapi==0.162.0")

    def test_rejects_requirements_include(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("-r other.txt")

    def test_rejects_index_url(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock(f"--index-url https://example.org\nfastapi==0.162.0 --hash=sha256:{H}")

    def test_rejects_editable_or_local_requirement(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("-e .")

    def test_rejects_empty_lockfile(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("# no packages\n")

    def test_rejects_unterminated_continuation(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("fastapi==0.162.0 \\")

    def test_rejects_non_sha256_hash(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock("fastapi==0.162.0 --hash=sha512:" + H)

    def test_rejects_trailing_unknown_options(self):
        with self.assertRaises(ValueError):
            candidate.validate_lock(f"fastapi==0.162.0 --hash=sha256:{H} --trusted-host=example.org")


if __name__ == "__main__":
    unittest.main()
