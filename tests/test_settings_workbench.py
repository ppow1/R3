import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKBENCH = ROOT / "web" / "settings-workbench.js"
INDEX = ROOT / "web" / "index.html"
CATALOG = ROOT / "web" / "settings-catalog.json"


class SettingsWorkbenchRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = WORKBENCH.read_text(encoding="utf-8")
        cls.index = INDEX.read_text(encoding="utf-8")
        cls.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_settings_form_is_registry_driven_and_write_gated(self):
        self.assertIn("manifest", self.script)
        self.assertIn("settings-fields", self.script)
        self.assertIn("manifest?.write_enabled", self.script)
        self.assertIn("current.protected", self.script)

    def test_presentation_catalog_covers_only_registered_live_documents(self):
        self.assertEqual(set(self.catalog["files"]), {
            "runtime.json",
            "host-tools.json",
            "residents/grace.json",
            "residents/reviewer.json",
        })
        self.assertEqual(self.catalog["files"]["runtime.json"]["fields"]["scheduler_tick_seconds"][2], "number")
        self.assertEqual(self.catalog["files"]["residents/grace.json"]["fields"]["system_prompt_file"][2], "prompt-reference")
        self.assertNotIn("assignments.json", self.catalog["files"])

    def test_secret_row_container_is_removed_from_settings_ui(self):
        self.assertIn('n.closest(".settings-token-row")', self.script)
        self.assertIn("password", self.script.lower())

    def test_refresh_control_is_valid_and_has_no_replacement_characters(self):
        self.assertIn('title="Refresh settings">&#8635;</button>', self.script)
        self.assertNotIn("\ufffd+\ufffd", self.script)

    def test_settings_workbench_assets_are_loaded_by_page(self):
        self.assertIn("settings-workbench.js", self.index)
        self.assertIn("settings-workbench.css", self.index)


if __name__ == "__main__":
    unittest.main()
