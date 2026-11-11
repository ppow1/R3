"""Permanent tests for immutable R3A Website source package creation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/deployment/package_r3a_website.py"
SPEC = importlib.util.spec_from_file_location("website_package", SCRIPT)
website_package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(website_package)


class WebsitePackageTests(unittest.TestCase):
    def test_deploy_lock_includes_database_runtime_driver_and_pool(self):
        lock = (Path(__file__).resolve().parents[1] / "requirements-deploy.lock").read_text()
        pinned = {line.split("==", 1)[0] for line in lock.splitlines() if "==" in line}
        self.assertTrue({"psycopg", "psycopg-binary", "psycopg-pool"} <= pinned)

    def test_package_is_deterministic_pinned_and_digest_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            files = {
                "r3_app.py": "app = object()\n",
                "requirements-deploy.lock": "fastapi==1.2 --hash=sha256:unused\n",
                "web/steward.html": "<main>Steward</main>\n",
                "web/steward-workspace-api.mjs": "export {};\n",
                "deploy/systemd/r3a-ap3-website-lan-https-backend.conf": "[Service]\n",
                "deploy/nginx/r3a-website-lan-https.conf": "server {}\n",
                "r3a_plugins/steward_access.r3a-native.config.example.json": "{}\n",
                "assets/visual-concepts/Riverview3_Visual_Concept_Library.zip": "not-runtime-data",
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Package Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "package-test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            first = Path(temporary) / "website-a.tar.gz"
            second = Path(temporary) / "website-b.tar.gz"
            result = website_package.create(root, commit, first)
            website_package.create(root, commit, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(result["source_commit"], commit)
            self.assertTrue(result["verified"])
            self.assertEqual(result["file_count"], 7)
            manifest = website_package.verify(first)
            self.assertEqual(manifest["package_sha256"], Path(str(first) + ".sha256").read_text().split()[0])
            with self.assertRaises(FileExistsError):
                website_package.create(root, commit, first)

    def test_verification_rejects_tampered_package_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "tampered.tar.gz"
            package.write_bytes(b"not a tarball")
            with self.assertRaises(Exception):
                website_package.verify(package)


if __name__ == "__main__":
    unittest.main()
