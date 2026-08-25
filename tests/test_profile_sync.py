from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.profile_catalog import SCHEMA_VERSION, render_readme
from scripts.sync_profile_repository import (
    SyncError,
    assert_catalog_scope,
    assert_hosted_readback,
    assert_readme_scope,
    assert_readme_visibility,
)


def entry(
    repository_id: str,
    name: str,
    *,
    provider_visibility: str = "public",
    public_url: str | None = None,
    summary: str = "A bounded project description.",
) -> dict[str, object]:
    is_public = provider_visibility == "public"
    return {
        "repository_id": repository_id,
        "inventory_scope": "local_registered",
        "name": name,
        "display_name": name.title(),
        "provider_visibility": provider_visibility,
        "profile_visibility": "public" if is_public else "private_readme_allowed",
        "readme_disposition": "include",
        "catalog_state": "current",
        "category": "Developer Tooling",
        "subcategory": "Agent-enabled",
        "featured_rank": None,
        "summary": summary,
        "summary_source": "test-fixture",
        "release": None,
        "public_url": public_url if is_public else None,
        "provider_is_fork": False,
        "provider_is_archived": False,
        "provider_observed_at": "2026-08-24T00:00:00Z",
    }


def catalog(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "inventory": {
            "source": "test",
            "source_commit": "abc",
            "observed_at": "2026-08-24T00:00:00Z",
            "registered_repository_count": len(entries),
            "provider_only_count": 0,
            "catalog_row_count": len(entries),
        },
        "freshness": {
            "state": "current",
            "window_minutes": 2880,
            "counts": {"current": len(entries), "needs_review": 0, "blocked": 0},
        },
        "entries": entries,
    }


class ProfileSyncContractTests(unittest.TestCase):
    def test_public_link_insertion_and_private_link_removal_are_scoped(self) -> None:
        public = entry("selected", "aios", public_url="https://github.com/jakyeamos/aios")
        companion = entry("companion", "companion", public_url="https://github.com/jakyeamos/companion")
        private = entry("selected", "aios", provider_visibility="private")
        before = catalog([public, companion])
        after = catalog([private, companion])
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            before_path = root / "before.json"
            after_path = root / "after.json"
            before_path.write_text(json.dumps(before), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            before_readme = render_readme(before_path)
            after_readme = render_readme(after_path)

        assert_catalog_scope(before, after, "aios")
        assert_readme_scope(before_readme, after_readme, "selected")
        assert_readme_visibility(after_readme, after, "aios", "private")
        self.assertIn("[Aios](https://github.com/jakyeamos/aios)", before_readme)
        self.assertNotIn("https://github.com/jakyeamos/aios", after_readme)

    def test_internal_visibility_is_non_public_and_url_safe(self) -> None:
        internal = entry("selected", "aios", provider_visibility="internal")
        data = catalog([internal])
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "catalog.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            readme = render_readme(path)
        assert_readme_visibility(readme, data, "aios", "internal")
        self.assertNotIn("https://github.com/", readme)

    def test_unselected_catalog_changes_fail_exact_scope_check(self) -> None:
        before = catalog([
            entry("selected", "aios", public_url="https://github.com/jakyeamos/aios"),
            entry("companion", "companion", public_url="https://github.com/jakyeamos/companion"),
        ])
        after = catalog([
            entry("selected", "aios", provider_visibility="private"),
            entry("companion", "companion", public_url="https://github.com/jakyeamos/companion", summary="Changed"),
        ])
        with self.assertRaisesRegex(SyncError, "outside the selected repository"):
            assert_catalog_scope(before, after, "aios")

    def test_private_url_injected_into_selected_section_fails(self) -> None:
        private = entry("selected", "aios", provider_visibility="private")
        data = catalog([private])
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "catalog.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            readme = render_readme(path) + "\nPrivate URL: https://github.com/jakyeamos/aios\n"
        with self.assertRaisesRegex(SyncError, "contains a GitHub URL"):
            assert_readme_visibility(readme, data, "aios", "private")

    def test_hosted_readback_must_match_the_validated_marker_and_link_state(self) -> None:
        public = entry("selected", "aios", public_url="https://github.com/jakyeamos/aios")
        data = catalog([public])
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "catalog.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            local_readme = render_readme(path)
        mismatched_link = local_readme.replace(
            "https://github.com/jakyeamos/aios",
            "https://github.com/jakyeamos/other",
        )
        with self.assertRaisesRegex(SyncError, "exactly one public link"):
            assert_hosted_readback(mismatched_link, local_readme, data, "aios", "public")

        mismatched_marker = local_readme.replace("rendered_entry_count=1", "rendered_entry_count=2")
        with self.assertRaisesRegex(SyncError, "generated marker"):
            assert_hosted_readback(mismatched_marker, local_readme, data, "aios", "public")


if __name__ == "__main__":
    unittest.main()
