"""Release-package tests: version isolation, contract compatibility, and digests."""
import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.package_knowledge_module import ENTRYPOINT, PACKAGE_DIR, build_entries, build_package
from r3a_runtime.capability_contracts import operation_from_manifest


ROOT = Path(__file__).resolve().parents[1]


class KnowledgeModulePackageTests(unittest.TestCase):
    def test_release_manifest_pins_all_files_and_generic_effect_versions(self):
        entries = build_entries()
        release = json.loads(entries["RELEASE_MANIFEST.json"])
        self.assertEqual("1.2.0", release["module_version"])
        self.assertEqual("r3a_plugins.institutional_knowledge_v1_2_0", release["package_path"].replace("/", "."))
        self.assertEqual(ENTRYPOINT, release["entrypoint"])
        indexed = {item["path"]: item["sha256"] for item in release["files"]}
        for path, content in entries.items():
            if path == "RELEASE_MANIFEST.json":
                continue  # The manifest cannot include its own digest.
            self.assertEqual(hashlib.sha256(content).hexdigest(), indexed[path])
        operations = {item["operation_id"]: item for item in release["capabilities"]}
        self.assertEqual("1.0.0", operations["institution.knowledge.read"]["contract_version"])
        self.assertEqual("1.1.0", operations["institution.knowledge.proposals.list"]["contract_version"])
        self.assertEqual("steward_read", operations["institution.knowledge.proposals.list"]["effect_class"])
        self.assertEqual("1.1.0", operations["institution.knowledge.proposals.decide"]["contract_version"])
        self.assertEqual("steward_write", operations["institution.knowledge.proposals.decide"]["effect_class"])

    def test_bundled_manifests_register_from_unique_path_without_replacing_11_path(self):
        entries = build_entries()
        archived_paths = set(entries)
        self.assertIn(f"{PACKAGE_DIR}/plugin.py", archived_paths)
        self.assertNotIn("r3a_plugins/institutional_knowledge/plugin.py", archived_paths)
        names = ("manifest.read.json", "manifest.proposals-list.json", "manifest.proposals-decide.json")
        descriptors = {}
        for filename in names:
            manifest = json.loads(entries[f"{PACKAGE_DIR}/{filename}"])
            self.assertNotIn("module_manifest", manifest)
            descriptor = operation_from_manifest(manifest)
            descriptors[descriptor["operation_id"]] = descriptor
            self.assertEqual("1.2.0", descriptor["provider"]["provider_version"])
            self.assertEqual(ENTRYPOINT, descriptor["provider"]["entrypoint"])
        read = descriptors["institution.knowledge.read"]
        self.assertEqual("1.0.0", read["contract_version"])
        self.assertEqual("1.1.0", read["operation_revision"])
        self.assertEqual("1.1.0", descriptors["institution.knowledge.proposals.list"]["contract_version"])
        self.assertEqual("1.1.0", descriptors["institution.knowledge.proposals.decide"]["contract_version"])

    def test_archive_build_is_deterministic_and_extracted_import_is_runnable(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first.tar.gz"
            second = Path(temporary) / "second.tar.gz"
            digest1, size1 = build_package(first)
            digest2, size2 = build_package(second)
            self.assertEqual((digest1, size1), (digest2, size2))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first, "r:gz") as archive:
                archive.extractall(Path(temporary) / "installed", filter="data")
            installed = Path(temporary) / "installed"
            package_file = installed / PACKAGE_DIR / "plugin.py"
            self.assertTrue(package_file.is_file())
            release = json.loads((installed / "RELEASE_MANIFEST.json").read_text())
            file_digests = {item["path"]: item["sha256"] for item in release["files"]}
            self.assertEqual(hashlib.sha256(package_file.read_bytes()).hexdigest(),
                             file_digests[f"{PACKAGE_DIR}/plugin.py"])

            runtime_root = Path(temporary) / "runtime"
            (runtime_root / "r3a_plugins").mkdir(parents=True)
            (runtime_root / "r3a_plugins/__init__.py").write_text('"""Test installation root."""\n')
            (runtime_root / PACKAGE_DIR).symlink_to(installed / PACKAGE_DIR, target_is_directory=True)
            policy = Path(temporary) / "policy.md"
            policy.write_text("# Test policy\n\nRetention lasts thirty days.\n")
            review_file = installed / PACKAGE_DIR / "review_store.py"
            release_digests = file_digests
            script = f'''import asyncio, json, sys
sys.path.insert(0, {str(runtime_root)!r})
sys.path.insert(1, {str(ROOT)!r})
from pathlib import Path
from r3a_runtime.capability_worker import CapabilityWorker
from r3a_plugins.institutional_knowledge_v1_2_0 import plugin
from pathlib import Path
artifact = Path({str(package_file)!r})
support = Path({str(review_file)!r})
worker = CapabilityWorker("r3a.institutional-knowledge", "1.2.0", {ENTRYPOINT!r}, artifact,
                          {file_digests[f"{PACKAGE_DIR}/plugin.py"]!r})
async def exercise():
    hello = await worker.handle("hello", {{}})
    assert hello["module_version"] == "1.2.0"
    await worker.handle("prepare", {{"configuration":{{"sources":[{{"source_id":"test.policy","path":{str(policy)!r},"freshness_max_age_seconds":86400}}],"max_results":5,"max_document_bytes":1024}},"pinned_artifacts":{{str(support):{file_digests[f"{PACKAGE_DIR}/review_store.py"]!r}}}}})
    await worker.handle("activate", {{}})
    response = await worker.handle("execute", {{"arguments":{{"query":"retention"}},"context":{{"operation_id":"institution.knowledge.read"}}}})
    result = response["provider_result"]["output"]
    assert Path(plugin.__file__).resolve() == artifact.resolve()
    assert result["schema_id"] == "r3a.institutional-knowledge-results.v1"
    assert result["results"][0]["content"] == "Retention lasts thirty days."
    return result["results"][0]["source_id"]
source_id = asyncio.run(exercise())
print(json.dumps({{"provider":"r3a.institutional-knowledge@1.2.0","source_id":source_id}}))
'''
            completed = subprocess.run([sys.executable, "-c", script], cwd=runtime_root,
                                       check=True, capture_output=True, text=True)
            self.assertIn('"provider": "r3a.institutional-knowledge@1.2.0"', completed.stdout)


if __name__ == "__main__":
    unittest.main()
