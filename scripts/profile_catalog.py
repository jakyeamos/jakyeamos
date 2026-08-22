#!/usr/bin/env python3
"""Shared profile-catalog loading, validation, and README rendering helpers."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "jakyeamos-profile-catalog/v1"
FRESHNESS_STATES = {"current", "missing", "needs_review", "stale", "blocked", "unknown"}
VISIBILITY_POLICIES = {"public", "private_readme_allowed", "fully_private"}
CATALOG_STATES = FRESHNESS_STATES
ELIGIBLE_SECTIONS = {"Public Releases", "Public Systems", "Active Systems", "Product Work", "Writing"}
ENTRY_MARKER = re.compile(r"<!-- profile-catalog-entry: (?P<id>[^ ]+) -->")
CATALOG_MARKER = re.compile(
    r"<!-- profile-catalog: schema=(?P<schema>[^ ]+) catalog_sha256=(?P<hash>[0-9a-f]{64}) "
    r"source_commit=(?P<commit>[^ ]+) inventory_observed_at=(?P<observed>[^ ]+) "
    r"rendered_entry_count=(?P<count>\d+) -->"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_catalog(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"catalog schema must be {SCHEMA_VERSION}")
    inventory = catalog.get("inventory")
    if not isinstance(inventory, dict):
        errors.append("catalog inventory metadata is required")
    else:
        for key in ("source", "source_commit", "observed_at", "registered_repository_count"):
            if not inventory.get(key):
                errors.append(f"catalog inventory.{key} is required")
    freshness = catalog.get("freshness")
    if not isinstance(freshness, dict):
        errors.append("catalog freshness metadata is required")
    elif freshness.get("state") not in FRESHNESS_STATES:
        errors.append("catalog freshness.state is invalid")
    entries = catalog.get("entries")
    if not isinstance(entries, list):
        return errors + ["catalog entries must be a list"]
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        prefix = f"catalog entry {index}"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        repository_id = entry.get("repository_id")
        if not repository_id:
            errors.append(f"{prefix} repository_id is required")
        elif repository_id in seen:
            errors.append(f"duplicate catalog repository_id: {repository_id}")
        else:
            seen.add(repository_id)
        if not entry.get("name"):
            errors.append(f"{prefix} name is required")
        if entry.get("catalog_state") not in CATALOG_STATES:
            errors.append(f"{prefix} catalog_state is invalid")
        policy = entry.get("visibility_policy")
        if policy is not None and policy not in VISIBILITY_POLICIES:
            errors.append(f"{prefix} visibility_policy is invalid")
        if entry.get("catalog_state") == "current" and policy not in VISIBILITY_POLICIES:
            errors.append(f"{prefix} current entries require an explicit visibility_policy")
        if entry.get("section") not in ELIGIBLE_SECTIONS:
            errors.append(f"{prefix} section is invalid")
        if entry.get("catalog_state") == "current" and not entry.get("subcategory"):
            errors.append(f"{prefix} current entries require a subcategory")
        if entry.get("visibility_policy") == "private_readme_allowed" and entry.get("public_url"):
            errors.append(f"{prefix} private_readme_allowed entries cannot carry public_url")
    expected = inventory.get("registered_repository_count") if isinstance(inventory, dict) else None
    if isinstance(expected, int) and expected != len(entries):
        errors.append(f"catalog row count {len(entries)} does not match registered count {expected}")
    return errors


def _safe_link(entry: dict[str, Any]) -> str:
    policy = entry.get("visibility_policy")
    url = entry.get("public_url") if policy == "public" else None
    label = html.escape(str(entry.get("display_name") or entry.get("name")))
    return f"[{label}]({url})" if url else label


def _entry_line(entry: dict[str, Any]) -> str:
    marker = f"<!-- profile-catalog-entry: {entry['repository_id']} -->"
    link = _safe_link(entry)
    summary = html.escape(str(entry.get("summary") or "Catalog metadata pending owner review."))
    release = entry.get("release")
    if entry.get("section") == "Public Releases":
        return f"{marker}\n| {link} | {release or '—'} | {summary} |"
    return f"{marker}\n- {link} — {summary}"


def _render_grouped(entries: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        grouped[str(entry.get("category") or "Uncategorized")][str(entry.get("subcategory") or "Uncategorized")].append(entry)
    lines: list[str] = []
    for category in sorted(grouped):
        lines.extend(["<details>", f"<summary>{html.escape(category)}</summary>", ""])
        for subcategory in sorted(grouped[category]):
            lines.extend([f"<details>", f"<summary>{html.escape(subcategory)}</summary>", ""])
            for entry in sorted(grouped[category][subcategory], key=lambda item: str(item.get("display_name") or item.get("name"))):
                lines.extend([_entry_line(entry), ""])
            lines.extend(["</details>", ""])
        lines.extend(["</details>", ""])
    return lines


def eligible_entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry
        for entry in catalog.get("entries", [])
        if entry.get("catalog_state") == "current"
        and entry.get("visibility_policy") in {"public", "private_readme_allowed"}
    ]


def render_readme(catalog_path: Path, generated_at: str | None = None) -> str:
    catalog = load_catalog(catalog_path)
    errors = validate_catalog(catalog)
    if errors:
        raise ValueError("catalog validation failed: " + "; ".join(errors))
    eligible = eligible_entries(catalog)
    inventory = catalog["inventory"]
    marker = (
        f"<!-- profile-catalog: schema={SCHEMA_VERSION} catalog_sha256={catalog_hash(catalog_path)} "
        f"source_commit={inventory['source_commit']} inventory_observed_at={inventory['observed_at']} "
        f"rendered_entry_count={len(eligible)} -->"
    )
    releases = [entry for entry in eligible if entry.get("section") == "Public Releases"]
    grouped = [entry for entry in eligible if entry.get("section") != "Public Releases"]
    lines = [
        "# Jakye Amos",
        "",
        "Lead Engineer at Forward Automations. CS at Case Western Reserve University. 3x Amazon SDE intern across Ads and Fintech.",
        "",
        "I build developer tools, backend-heavy product systems, and local-first AI workflows.",
        "",
        "5,554 GitHub contributions in the past 12 months.",
        "",
        "---",
        "",
        marker,
        "",
        "## Public Releases",
        "",
        "| Project | Release | Focus |",
        "| --- | --- | --- |",
    ]
    lines.extend(_entry_line(entry) for entry in sorted(releases, key=lambda item: str(item.get("display_name") or item.get("name"))))
    lines.extend([
        "",
        "## Public Systems",
        "",
    ])
    public_systems = [entry for entry in grouped if entry.get("section") == "Public Systems"]
    lines.extend(_render_grouped(public_systems))
    lines.extend([
        "## Active Systems",
        "",
        "<details>",
        "<summary>Current focus</summary>",
        "",
        "Current work spans agent infrastructure, career operations, product engineering, music, sports analytics, and applied AI.",
        "",
        "</details>",
        "",
        "## Product Work",
        "",
    ])
    lines.extend(_render_grouped([entry for entry in grouped if entry.get("section") == "Product Work"]))
    lines.extend([
        "## Writing",
        "",
        "<details>",
        "<summary>Writing</summary>",
        "",
        "I write about implementation, evidence, and AI systems at [FRMWRK Labs](https://www.frmwrklabs.com/).",
        "",
        "</details>",
        "",
        "## Stack",
        "",
        "```text",
        "TypeScript · Python · Go · Java",
        "Next.js · React · tRPC · Prisma · FastAPI",
        "PostgreSQL · SQLite · Redis · AWS · Docker",
        "pnpm monorepos · LSPs · CLIs · local-first tooling",
        "```",
        "",
        "---",
        "",
        "[Portfolio](https://jakye.netlify.app/) · [LinkedIn](https://linkedin.com/in/jakyeamos) · [Email](mailto:jakyejobs@gmail.com)",
        "",
    ])
    return "\n".join(lines)


def validate_readme(readme_path: Path, catalog_path: Path) -> list[str]:
    errors = validate_catalog(load_catalog(catalog_path))
    text = readme_path.read_text(encoding="utf-8")
    marker = CATALOG_MARKER.search(text)
    if not marker:
        errors.append("missing or malformed profile catalog marker")
        return errors
    catalog = load_catalog(catalog_path)
    inventory = catalog["inventory"]
    expected_hash = catalog_hash(catalog_path)
    if marker.group("schema") != SCHEMA_VERSION:
        errors.append("README catalog marker schema does not match the catalog")
    if marker.group("hash") != expected_hash:
        errors.append("README catalog marker hash does not match profile-catalog.json")
    if marker.group("commit") != inventory.get("source_commit"):
        errors.append("README catalog marker source commit does not match the catalog")
    if marker.group("observed") != inventory.get("observed_at"):
        errors.append("README catalog marker inventory time does not match the catalog")
    entry_ids = ENTRY_MARKER.findall(text)
    counts: dict[str, int] = defaultdict(int)
    for repository_id in entry_ids:
        counts[repository_id] += 1
    eligible = eligible_entries(catalog)
    expected_ids = {entry["repository_id"] for entry in eligible}
    if int(marker.group("count")) != len(eligible):
        errors.append("README rendered_entry_count does not match eligible catalog rows")
    if set(counts) != expected_ids:
        missing = sorted(expected_ids - set(counts))
        unexpected = sorted(set(counts) - expected_ids)
        if missing:
            errors.append("current README-eligible catalog rows are missing: " + ", ".join(missing))
        if unexpected:
            errors.append("README contains entries that are not current README-eligible rows: " + ", ".join(unexpected))
    duplicates = sorted(repository_id for repository_id, count in counts.items() if count != 1)
    if duplicates:
        errors.append("README catalog rows must render exactly once: " + ", ".join(duplicates))
    return errors
