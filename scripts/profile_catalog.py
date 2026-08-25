#!/usr/bin/env python3
"""Shared profile-catalog loading, validation, and README rendering helpers."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.profile_policy import CATEGORY_METADATA, PUBLIC_RELEASES, SUBCATEGORY_METADATA
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_policy import CATEGORY_METADATA, PUBLIC_RELEASES, SUBCATEGORY_METADATA

SCHEMA_VERSION = "jakyeamos-profile-catalog/v2"
FRESHNESS_STATES = {"current", "missing", "needs_review", "stale", "blocked", "unknown"}
PROVIDER_VISIBILITIES = {"public", "private", "internal", "unknown"}
PROFILE_VISIBILITIES = {"public", "private_readme_allowed", "fully_private"}
README_DISPOSITIONS = {"include", "exclude", "defer"}
ENTRY_MARKER = re.compile(r"<!-- profile-catalog-entry: (?P<id>[^ ]+) -->")
CATALOG_MARKER = re.compile(
    r"<!-- profile-catalog: schema=(?P<schema>[^ ]+) catalog_sha256=(?P<hash>[0-9a-f]{64}) "
    r"source_commit=(?P<commit>[^ ]+) inventory_observed_at=(?P<observed>[^ ]+) "
    r"rendered_entry_count=(?P<count>\d+) -->"
)
CATEGORY_ORDER = tuple(CATEGORY_METADATA)


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
        inventory = {}
    else:
        for key in ("source", "source_commit", "observed_at", "registered_repository_count", "provider_only_count", "catalog_row_count"):
            if inventory.get(key) is None:
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
        state = entry.get("catalog_state")
        provider = entry.get("provider_visibility")
        profile = entry.get("profile_visibility")
        disposition = entry.get("readme_disposition")
        if state not in FRESHNESS_STATES:
            errors.append(f"{prefix} catalog_state is invalid")
        if provider not in PROVIDER_VISIBILITIES:
            errors.append(f"{prefix} provider_visibility is invalid")
        if profile is not None and profile not in PROFILE_VISIBILITIES:
            errors.append(f"{prefix} profile_visibility is invalid")
        if disposition not in README_DISPOSITIONS:
            errors.append(f"{prefix} readme_disposition is invalid")
        if entry.get("inventory_scope") not in {"local_registered", "provider_only"}:
            errors.append(f"{prefix} inventory_scope is invalid")
        if state == "current" and (provider == "unknown" or profile not in PROFILE_VISIBILITIES or disposition == "defer"):
            errors.append(f"{prefix} current rows require resolved provider, profile, and README policy")
        if disposition == "include":
            if state != "current":
                errors.append(f"{prefix} included rows must be current")
            if not entry.get("summary"):
                errors.append(f"{prefix} included rows require a summary")
            if not entry.get("summary_source"):
                errors.append(f"{prefix} included rows require summary provenance")
            if entry.get("category") not in CATEGORY_METADATA:
                errors.append(f"{prefix} included rows require a supported category")
            if entry.get("subcategory") not in SUBCATEGORY_METADATA:
                errors.append(f"{prefix} included rows require a supported subcategory")
            if profile == "public":
                if provider != "public":
                    errors.append(f"{prefix} public profile entries require public provider evidence")
                if not str(entry.get("public_url") or "").startswith("https://github.com/"):
                    errors.append(f"{prefix} public profile entries require a GitHub public_url")
            elif profile == "private_readme_allowed":
                if provider not in {"private", "internal"}:
                    errors.append(f"{prefix} private README entries require private or internal provider evidence")
                if entry.get("public_url"):
                    errors.append(f"{prefix} private README entries cannot carry public_url")
            else:
                errors.append(f"{prefix} included rows require public or private_readme_allowed profile visibility")
        if profile == "fully_private" and disposition == "include":
            errors.append(f"{prefix} fully_private rows cannot be included")
        for forbidden in ("path", "remote_url", "registry_database", "source_repository"):
            if forbidden in entry:
                errors.append(f"{prefix} must not expose {forbidden}")

    registered = sum(entry.get("inventory_scope") == "local_registered" for entry in entries)
    provider_only = sum(entry.get("inventory_scope") == "provider_only" for entry in entries)
    if inventory.get("registered_repository_count") != registered:
        errors.append(f"catalog registered row count {registered} does not match inventory metadata")
    if inventory.get("provider_only_count") != provider_only:
        errors.append(f"catalog provider-only row count {provider_only} does not match inventory metadata")
    if inventory.get("catalog_row_count") != len(entries):
        errors.append(f"catalog row count {len(entries)} does not match inventory metadata")
    return errors


def eligible_entries(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        entry for entry in catalog.get("entries", [])
        if entry.get("catalog_state") == "current"
        and entry.get("readme_disposition") == "include"
        and entry.get("profile_visibility") in {"public", "private_readme_allowed"}
    ]


def _safe_link(entry: dict[str, Any]) -> str:
    label = html.escape(str(entry.get("display_name") or entry.get("name")))
    if entry.get("profile_visibility") == "public":
        return f"[{label}]({entry['public_url']})"
    return label


def _entry_line(entry: dict[str, Any]) -> str:
    marker = f"<!-- profile-catalog-entry: {entry['repository_id']} -->"
    link = _safe_link(entry)
    summary = html.escape(str(entry["summary"]))
    if entry.get("name") in PUBLIC_RELEASES:
        # A standalone HTML comment between Markdown table rows terminates the
        # table in GitHub's renderer. Keep the exact-once marker inside cell 1.
        return f"| {marker} {link} | {entry['release']} | {summary} |"
    return f"{marker}\n- {link} — {summary}"


def _plural(count: int) -> str:
    return "repository" if count == 1 else "repositories"


def _render_catalog(entries: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        grouped[entry["category"]][entry["subcategory"]].append(entry)
    lines: list[str] = []
    for category in CATEGORY_ORDER:
        subgroups = grouped.get(category)
        if not subgroups:
            continue
        category_entries = [entry for values in subgroups.values() for entry in values]
        highlights = sorted(
            (entry for entry in category_entries if isinstance(entry.get("featured_rank"), int)),
            key=lambda item: (item["featured_rank"], str(item.get("display_name") or item["name"]).lower()),
        )[:3]
        highlight_ids = {entry["repository_id"] for entry in highlights}
        lines.extend([
            "<details>",
            f"<summary><strong>{html.escape(category)}</strong> · {len(category_entries)} {_plural(len(category_entries))}</summary>",
            "",
            html.escape(CATEGORY_METADATA[category]),
            "",
        ])
        if highlights:
            lines.extend(["**Highlights**", ""])
            for entry in highlights:
                lines.extend([_entry_line(entry), ""])
        for subcategory in SUBCATEGORY_METADATA:
            remaining = [entry for entry in subgroups.get(subcategory, []) if entry["repository_id"] not in highlight_ids]
            if not remaining:
                continue
            lines.extend([
                "<details>",
                (
                    f"<summary>&nbsp;&nbsp;<span aria-hidden=\"true\">↳</span>&nbsp;"
                    f"{html.escape(subcategory)} · {len(remaining)} {_plural(len(remaining))}</summary>"
                ),
                "",
                html.escape(SUBCATEGORY_METADATA[subcategory]),
                "",
            ])
            for entry in sorted(remaining, key=lambda item: str(item.get("display_name") or item["name"]).lower()):
                lines.extend([_entry_line(entry), ""])
            lines.extend(["</details>", ""])
        lines.extend(["</details>", ""])
    return lines


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
    releases = [entry for entry in eligible if entry.get("name") in PUBLIC_RELEASES]
    portfolio = [entry for entry in eligible if entry.get("name") not in PUBLIC_RELEASES]
    lines = [
        "# Jakye Amos",
        "",
        "Lead Engineer at Forward Automations. CS at Case Western Reserve University. 3x Amazon SDE intern across Ads and Fintech.",
        "",
        "I build product systems, developer tooling, applied AI workflows, and data-intensive software—with an emphasis on evidence, clear operating boundaries, and usable interfaces.",
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
    for entry in sorted(releases, key=lambda item: str(item.get("display_name") or item["name"]).lower()):
        lines.append(_entry_line(entry))
    lines.extend([
        "",
        "## Product Work",
        "",
    ])
    lines.extend(_render_catalog(portfolio))
    lines.extend([
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
    catalog = load_catalog(catalog_path)
    errors = validate_catalog(catalog)
    text = readme_path.read_text(encoding="utf-8")
    marker = CATALOG_MARKER.search(text)
    if not marker:
        return errors + ["missing or malformed profile catalog marker"]
    inventory = catalog["inventory"]
    if marker.group("schema") != SCHEMA_VERSION:
        errors.append("README catalog marker schema does not match the catalog")
    if marker.group("hash") != catalog_hash(catalog_path):
        errors.append("README catalog marker hash does not match profile-catalog.json")
    if marker.group("commit") != inventory.get("source_commit"):
        errors.append("README catalog marker source commit does not match the catalog")
    if marker.group("observed") != inventory.get("observed_at"):
        errors.append("README catalog marker inventory time does not match the catalog")
    counts = Counter(ENTRY_MARKER.findall(text))
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
    if re.search(r"/(Users|home)/|git@github\.com:|https://github\.com/(LayerC0de|realtypulse73|alec-angello)/", text):
        errors.append("README exposes a private remote or local filesystem path")
    for entry in eligible:
        safe_name = html.escape(str(entry.get("display_name") or entry.get("name")))
        if entry.get("profile_visibility") == "private_readme_allowed" and safe_name not in text:
            errors.append(f"private README entry is missing safe metadata: {entry['repository_id']}")
    return errors
