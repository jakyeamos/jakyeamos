from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_profile import REQUIRED_HEADINGS, validate
from scripts.profile_catalog import SCHEMA_VERSION, eligible_entries, render_readme, validate_catalog, validate_readme
from scripts.refresh_profile_catalog import parse_remote


def entry(repository_id: str, name: str, **overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "repository_id": repository_id,
        "inventory_scope": "local_registered",
        "name": name,
        "display_name": name.title(),
        "provider_visibility": "public",
        "profile_visibility": "public",
        "readme_disposition": "include",
        "catalog_state": "current",
        "category": "Developer Tooling",
        "subcategory": "Agent-enabled",
        "featured_rank": None,
        "summary": "A bounded project description.",
        "summary_source": "test-fixture",
        "release": None,
        "public_url": f"https://github.com/jakyeamos/{name}",
        "provider_is_fork": False,
        "provider_is_archived": False,
        "provider_observed_at": "2026-08-23T00:00:00Z",
    }
    value.update(overrides)
    return value


def catalog(entries: list[dict[str, object]]) -> dict[str, object]:
    registered = sum(item["inventory_scope"] == "local_registered" for item in entries)
    provider_only = sum(item["inventory_scope"] == "provider_only" for item in entries)
    return {
        "schema_version": SCHEMA_VERSION,
        "inventory": {
            "source": "test",
            "source_commit": "abc",
            "observed_at": "2026-08-23T00:00:00Z",
            "registered_repository_count": registered,
            "provider_only_count": provider_only,
            "catalog_row_count": len(entries),
        },
        "freshness": {"state": "current", "window_minutes": 2880},
        "entries": entries,
    }


class ProfileContractTests(unittest.TestCase):
    def test_repository_readme_passes(self) -> None:
        self.assertEqual(validate(Path(__file__).resolve().parents[1] / "README.md"), [])

    def test_missing_heading_and_broken_local_link_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            readme = Path(raw_root) / "README.md"
            readme.write_text("\n\n".join([*REQUIRED_HEADINGS[:-1], "[missing](missing.md)"]) + "\n", encoding="utf-8")
            errors = validate(readme)
        self.assertIn("missing heading: ## Stack", errors)
        self.assertIn("invalid local link: missing.md", errors)

    def test_current_rows_require_resolved_policy(self) -> None:
        unresolved = entry("one", "one", provider_visibility="unknown", profile_visibility=None, readme_disposition="defer")
        errors = validate_catalog(catalog([unresolved]))
        self.assertIn("current rows require resolved provider, profile, and README policy", " ".join(errors))

    def test_visibility_and_disposition_boundaries(self) -> None:
        public = entry("public", "public")
        private = entry(
            "private", "private", provider_visibility="private", profile_visibility="private_readme_allowed", public_url=None
        )
        excluded = entry(
            "excluded", "excluded", provider_visibility="private", profile_visibility="fully_private",
            readme_disposition="exclude", category=None, subcategory=None, summary=None, public_url=None,
        )
        deferred = entry(
            "deferred", "deferred", provider_visibility="unknown", profile_visibility=None,
            readme_disposition="defer", catalog_state="needs_review", category=None, subcategory=None,
            summary=None, public_url=None,
        )
        data = catalog([public, private, excluded, deferred])
        self.assertEqual(validate_catalog(data), [])
        self.assertEqual({item["repository_id"] for item in eligible_entries(data)}, {"public", "private"})

    def test_private_url_and_public_evidence_conflicts_fail(self) -> None:
        private = entry(
            "private", "private", provider_visibility="private", profile_visibility="private_readme_allowed",
            public_url="https://github.com/example/private",
        )
        public = entry("public", "public", provider_visibility="private")
        errors = " ".join(validate_catalog(catalog([private, public])))
        self.assertIn("private README entries cannot carry public_url", errors)
        self.assertIn("public profile entries require public provider evidence", errors)

    def test_included_rows_require_description_provenance(self) -> None:
        undocumented = entry("undocumented", "undocumented", summary_source=None)
        self.assertIn("included rows require summary provenance", " ".join(validate_catalog(catalog([undocumented]))))

    def test_nested_navigation_highlights_and_exact_once_rendering(self) -> None:
        highlighted = entry("highlight", "highlight", featured_rank=1)
        private = entry(
            "private", "private", provider_visibility="private", profile_visibility="private_readme_allowed", public_url=None
        )
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            catalog_path = root / "profile-catalog.json"
            catalog_path.write_text(json.dumps(catalog([highlighted, private])), encoding="utf-8")
            readme = root / "README.md"
            readme.write_text(render_readme(catalog_path), encoding="utf-8")
            rendered = readme.read_text(encoding="utf-8")
            self.assertEqual(validate_readme(readme, catalog_path), [])
        self.assertIn("<strong>Developer Tooling</strong> · 2 repositories", rendered)
        self.assertIn("<summary>Agent-enabled · 1 repository</summary>", rendered)
        self.assertEqual(rendered.count("profile-catalog-entry: highlight"), 1)
        self.assertIn("Private work", rendered)
        self.assertNotIn("example.com/private", rendered)

    def test_public_release_marker_stays_inside_table_row(self) -> None:
        release = entry(
            "release", "quality-runner", display_name="Quality Runner",
            release="PyPI `v0.6.0`", public_url="https://github.com/jakyeamos/quality-runner/tree/v0.6.0",
        )
        with tempfile.TemporaryDirectory() as raw_root:
            catalog_path = Path(raw_root) / "profile-catalog.json"
            catalog_path.write_text(json.dumps(catalog([release])), encoding="utf-8")
            rendered = render_readme(catalog_path)
        self.assertIn("| <!-- profile-catalog-entry: release --> [Quality Runner]", rendered)
        self.assertNotIn("<!-- profile-catalog-entry: release -->\n|", rendered)

    def test_generated_readme_detects_stale_catalog_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog_path = root / "profile-catalog.json"
        readme = root / "README.md"
        self.assertEqual(validate_readme(readme, catalog_path), [])
        original = catalog_path.read_text(encoding="utf-8")
        try:
            catalog_path.write_text(original.replace('"window_minutes": 2880', '"window_minutes": 1440', 1), encoding="utf-8")
            self.assertTrue(validate_readme(readme, catalog_path))
        finally:
            catalog_path.write_text(original, encoding="utf-8")

    def test_remote_parser_and_provider_only_inventory(self) -> None:
        self.assertEqual(parse_remote("git@github.com:jakyeamos/pronto.git"), ("jakyeamos", "pronto"))
        self.assertEqual(parse_remote("https://github.com/jakyeamos/Terrace.git"), ("jakyeamos", "Terrace"))
        provider = entry("provider", "LIS", inventory_scope="provider_only", provider_visibility="private", profile_visibility="private_readme_allowed", public_url=None)
        self.assertEqual(validate_catalog(catalog([provider])), [])

    def test_catalog_does_not_expose_local_paths_or_remote_urls(self) -> None:
        unsafe = entry("unsafe", "unsafe", path="/Users/example/project", remote_url="git@github.com:owner/private.git")
        errors = " ".join(validate_catalog(catalog([unsafe])))
        self.assertIn("must not expose path", errors)
        self.assertIn("must not expose remote_url", errors)


if __name__ == "__main__":
    unittest.main()
