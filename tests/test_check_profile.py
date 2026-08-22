from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_profile import REQUIRED_HEADINGS, validate
from scripts.profile_catalog import render_readme, validate_catalog, validate_readme


class ProfileContractTests(unittest.TestCase):
    def test_repository_readme_passes(self) -> None:
        self.assertEqual(validate(Path(__file__).resolve().parents[1] / "README.md"), [])

    def test_missing_heading_and_broken_local_link_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            readme = Path(raw_root) / "README.md"
            readme.write_text(
                "\n\n".join([*REQUIRED_HEADINGS[:-1], "[missing](missing.md)"]) + "\n",
                encoding="utf-8",
            )

            errors = validate(readme)

        self.assertIn("missing heading: ## Stack", errors)

    def test_catalog_requires_policy_for_current_rows(self) -> None:
        catalog = {
            "schema_version": "jakyeamos-profile-catalog/v1",
            "inventory": {"source": "test", "source_commit": "abc", "observed_at": "2026-08-20T00:00:00Z", "registered_repository_count": 1},
            "freshness": {"state": "current", "window_minutes": 2880},
            "entries": [{"repository_id": "r1", "name": "one", "section": "Product Work", "category": "Developer Tooling", "subcategory": "Agent-enabled", "catalog_state": "current", "visibility_policy": None}],
        }
        self.assertIn("current entries require an explicit visibility_policy", " ".join(validate_catalog(catalog)))

    def test_generated_readme_detects_stale_catalog_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = root / "profile-catalog.json"
        readme = root / "README.md"
        self.assertEqual(validate_readme(readme, catalog), [])
        original = catalog.read_text(encoding="utf-8")
        try:
            catalog.write_text(original.replace('"window_minutes": 2880', '"window_minutes": 1440', 1), encoding="utf-8")
            self.assertTrue(validate_readme(readme, catalog))
        finally:
            catalog.write_text(original, encoding="utf-8")

    def test_nested_product_work_navigation_and_private_url_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            catalog = root / "profile-catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "schema_version": "jakyeamos-profile-catalog/v1",
                        "inventory": {"source": "test", "source_commit": "abc", "observed_at": "2026-08-20T00:00:00Z", "registered_repository_count": 2},
                        "freshness": {"state": "current", "window_minutes": 2880},
                        "entries": [
                            {"repository_id": "public", "name": "public", "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases", "display_name": "Public", "visibility_policy": "public", "catalog_state": "current", "summary": "safe", "release": "v1", "public_url": "https://example.com/public"},
                            {"repository_id": "private", "name": "private", "section": "Product Work", "category": "Developer Tooling", "subcategory": "Agent-enabled", "display_name": "Private", "visibility_policy": "private_readme_allowed", "catalog_state": "current", "summary": "safe metadata", "public_url": None},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            readme = root / "README.md"
            readme.write_text(render_readme(catalog), encoding="utf-8")
            rendered = readme.read_text(encoding="utf-8")

        self.assertIn("<summary>Developer Tooling</summary>", rendered)
        self.assertIn("<summary>Agent-enabled</summary>", rendered)
        self.assertIn("Private — safe metadata", rendered)
        self.assertNotIn("example.com/private", rendered)


if __name__ == "__main__":
    unittest.main()
