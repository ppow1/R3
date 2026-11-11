# R3 CONTROLLED SOURCE
# File: tests/test_deployment_candidate_runtime.py
# Component: R3-MANIFEST-DEPLOY
# Purpose: Permanent fail-closed candidate runtime verification tests.
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deployment/verify_candidate_runtime.py"
spec = importlib.util.spec_from_file_location("verify_candidate_runtime", SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

class RuntimeVerificationTests(unittest.TestCase):
    def test_refuses_active_checkout(self):
        with patch.object(runtime.Path, "resolve", return_value=Path("/home/admin1/R3")):
            with self.assertRaises(ValueError):
                runtime.candidate_paths("/home/admin1/R3")

    def test_refuses_incomplete_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                runtime.candidate_paths(directory)

    def test_accepts_valid_health_and_homepage(self):
        health = {"service": "r3", "status": "running", "repository_present": True}
        def fake_request(url, timeout=2):
            if url.endswith("/api/v1/health"):
                return 200, "application/json", json.dumps(health).encode()
            return 200, "text/html", b"<html>R3</html>"
        with patch.object(runtime, "request", side_effect=fake_request):
            result = runtime.check_http(12345)
        self.assertEqual(result["homepage_status"], 200)

    def test_accepts_truthful_package_health_without_git_repository(self):
        health = {"service": "r3", "status": "running", "repository_present": False}
        def fake_request(url, timeout=2):
            if url.endswith("/api/v1/health"):
                return 200, "application/json", json.dumps(health).encode()
            return 200, "text/html", b"<html>R3 package</html>"
        with patch.object(runtime, "request", side_effect=fake_request):
            result = runtime.check_http(12345)
        self.assertFalse(result["health"]["repository_present"])

    def test_package_source_identity_comes_from_valid_release_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            commit = "a" * 40
            (root / "WEBSITE_PACKAGE_MANIFEST.json").write_text(json.dumps({
                "contract": "r3a.website-release-package.v1", "source_commit": commit,
            }))
            self.assertEqual(runtime.source_commit_for_candidate(source), commit)

    def test_package_without_git_or_source_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            with self.assertRaises(RuntimeError):
                runtime.source_commit_for_candidate(source)

    def test_rejects_bad_health(self):
        with patch.object(runtime, "request", return_value=(
                200, "application/json", b'{"service":"wrong","status":"running","repository_present":true}')):
            with self.assertRaises(RuntimeError):
                runtime.check_http(12345)

    def test_rejects_missing_homepage(self):
        health = b'{"service":"r3","status":"running","repository_present":true}'
        with patch.object(runtime, "request", side_effect=[
                (200, "application/json", health), (404, "text/html", b"")]):
            with self.assertRaises(RuntimeError):
                runtime.check_http(12345)

if __name__ == "__main__":
    unittest.main()
