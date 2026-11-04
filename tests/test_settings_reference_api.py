import json
import tempfile
import unittest
from pathlib import Path

from r3_settings_api import build_settings_router


class SettingsReferenceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "persistent-config"
        prompt = self.data / "residents" / "prompts"
        prompt.mkdir(parents=True)
        (prompt / "grace.md").write_text("prompt", encoding="utf-8")
        (self.data / "residents" / "private.md").write_text("outside prompt folder", encoding="utf-8")
        config = self.root / "config"
        config.mkdir()
        (config / "settings-registry.json").write_text(json.dumps({
            "configuration_root": str(self.data)
        }), encoding="utf-8")
        web = self.root / "web"
        web.mkdir()
        self.catalog = {"schema_version": "test", "files": {"runtime.json": {"fields": {}}}}
        (web / "settings-catalog.json").write_text(json.dumps(self.catalog), encoding="utf-8")
        router = build_settings_router(self.root)
        self.endpoints = {route.path: route.endpoint for route in router.routes}

    def test_catalog_is_served_from_website_metadata(self):
        self.assertEqual(self.endpoints["/api/v1/settings/catalog"](), self.catalog)

    def test_prompt_picker_only_lists_markdown_under_prompt_root(self):
        self.assertEqual(
            self.endpoints["/api/v1/settings/references/prompts"](),
            {"paths": ["residents/prompts/grace.md"]},
        )


if __name__ == "__main__":
    unittest.main()
