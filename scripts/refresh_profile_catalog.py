#!/usr/bin/env python3
"""Refresh the public-safe catalog from Pronto inventory and live GitHub evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.profile_catalog import SCHEMA_VERSION, utc_now
    from scripts.profile_policy import POLICY, PUBLIC_RELEASES
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_catalog import SCHEMA_VERSION, utc_now
    from profile_policy import POLICY, PUBLIC_RELEASES

DEFAULT_REGISTRY = Path.home() / "Library/Application Support/Pronto/registry.db"
GITHUB_REMOTE = re.compile(r"(?:git@github\.com:|https://github\.com/)(?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$")


def run_json(command: list[str]) -> Any:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def git_head(path: Path) -> str:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def read_inventory(database: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute("SELECT id, payload_json FROM repositories ORDER BY id").fetchall()
    finally:
        connection.close()
    inventory: list[dict[str, Any]] = []
    for repository_id, payload_json in rows:
        payload = json.loads(payload_json)
        inventory.append({
            "registry_id": repository_id,
            "name": payload.get("name"),
            "remote_url": payload.get("remote_url"),
            "identity": (payload.get("project_compass") or {}).get("identity"),
        })
    return inventory


def parse_remote(remote_url: str | None) -> tuple[str, str] | None:
    if not remote_url:
        return None
    match = GITHUB_REMOTE.match(remote_url)
    return (match.group("owner"), match.group("name")) if match else None


def live_provider_inventory(local_inventory: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    owned = run_json([
        "gh", "repo", "list", "jakyeamos", "--limit", "200", "--json",
        "name,nameWithOwner,url,visibility,isFork,isArchived,description,owner",
    ])
    providers = {(row["owner"]["login"].lower(), row["name"].lower()): row for row in owned}
    identities = {remote for item in local_inventory if (remote := parse_remote(item.get("remote_url")))}
    identities.add(("jakyeamos", "LIS"))
    for owner, name in sorted(identities):
        key = (owner.lower(), name.lower())
        if key in providers:
            continue
        try:
            providers[key] = run_json([
                "gh", "repo", "view", f"{owner}/{name}", "--json",
                "name,nameWithOwner,url,visibility,isFork,isArchived,description,owner",
            ])
        except subprocess.CalledProcessError as error:
            providers[key] = {"name": name, "owner": {"login": owner}, "visibility": "UNKNOWN", "provider_error": error.stderr.strip()}
    return providers


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _repository_id(scope: str, identity: str) -> str:
    return f"repository:{scope}:{_digest(identity)[:16]}"


def _provider_visibility(provider: dict[str, Any] | None) -> str:
    raw = str((provider or {}).get("visibility") or "UNKNOWN").lower()
    return raw if raw in {"public", "private"} else "unknown"


def _summary(
    identity: str | None,
    policy: dict[str, Any],
    previous: dict[str, Any],
) -> tuple[str | None, str | None]:
    if policy.get("summary"):
        value = policy["summary"]
        source = policy.get("summary_source", "curated-profile-policy")
    elif previous.get("summary"):
        value = previous["summary"]
        source = previous.get("summary_source", "approved-catalog-metadata")
    else:
        value = identity
        source = "project-compass" if identity else None
    if not value:
        return None, None
    text = " ".join(str(value).split())
    for prefix in ("A standalone ", "A local-first ", "A private ", "A public ", "An archived historical ", "An ", "A "):
        if text.startswith(prefix):
            text = text[len(prefix):]
            text = text[:1].upper() + text[1:]
            break
    if len(text) <= 240:
        return text, source
    sentence = text.split(". ", 1)[0].rstrip(".") + "."
    summary = sentence if len(sentence) <= 240 else text[:236].rstrip(" ,;:") + "…"
    return summary, source


def _entry(
    *,
    name: str,
    inventory_scope: str,
    opaque_identity: str,
    provider_identity: tuple[str, str] | None,
    provider: dict[str, Any] | None,
    identity: str | None,
    previous: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    policy = POLICY.get(name, {"readme_disposition": "defer", "review_reason": "No editorial policy is registered."})
    disposition = policy["readme_disposition"]
    provider_visibility = _provider_visibility(provider)
    if disposition == "defer":
        state, profile_visibility = "needs_review", None
    elif provider_visibility == "unknown":
        state, profile_visibility, disposition = "blocked", None, "defer"
    elif disposition == "include":
        state = "current"
        profile_visibility = "public" if provider_visibility == "public" else "private_readme_allowed"
    else:
        state = "current"
        profile_visibility = "public" if provider_visibility == "public" else "fully_private"
    summary, summary_source = _summary(identity, policy, previous) if disposition == "include" else (None, None)
    public_url = None
    if disposition == "include" and profile_visibility == "public" and provider:
        public_url = provider.get("url")
    release = None
    if name in PUBLIC_RELEASES and disposition == "include" and profile_visibility == "public":
        release = PUBLIC_RELEASES[name]["release"]
        public_url = PUBLIC_RELEASES[name]["public_url"]
    entry: dict[str, Any] = {
        "repository_id": _repository_id(inventory_scope, opaque_identity),
        "inventory_scope": inventory_scope,
        "name": name,
        "display_name": policy.get("display_name", name),
        "provider_visibility": provider_visibility,
        "profile_visibility": profile_visibility,
        "readme_disposition": disposition,
        "catalog_state": state,
        "category": policy.get("category"),
        "subcategory": policy.get("subcategory"),
        "featured_rank": policy.get("featured_rank"),
        "summary": summary,
        "summary_source": summary_source,
        "release": release,
        "public_url": public_url,
        "provider_is_fork": (provider or {}).get("isFork"),
        "provider_is_archived": (provider or {}).get("isArchived"),
        "provider_observed_at": observed_at,
    }
    if provider_identity:
        canonical = f"github:{provider_identity[0]}/{provider_identity[1]}"
        if provider_visibility == "public":
            entry["provider_identity"] = canonical
        else:
            entry["provider_identity_digest"] = _digest(canonical)
    if policy.get("exclusion_reason"):
        entry["exclusion_reason"] = policy["exclusion_reason"]
    if policy.get("review_reason"):
        entry["review_reason"] = policy["review_reason"]
    return entry


def build_catalog(database: Path, profile_root: Path, observed_at: str) -> dict[str, Any]:
    inventory = read_inventory(database)
    previous_path = profile_root / "profile-catalog.json"
    previous_entries = json.loads(previous_path.read_text(encoding="utf-8")).get("entries", []) if previous_path.exists() else []
    previous = {entry.get("name"): entry for entry in previous_entries}
    providers = live_provider_inventory(inventory)
    entries: list[dict[str, Any]] = []
    for item in inventory:
        remote = parse_remote(item.get("remote_url"))
        provider = providers.get((remote[0].lower(), remote[1].lower())) if remote else None
        entries.append(_entry(
            name=item["name"], inventory_scope="local_registered", opaque_identity=item["registry_id"],
            provider_identity=remote, provider=provider, identity=item.get("identity"),
            previous=previous.get(item["name"], {}), observed_at=observed_at,
        ))
    lis_identity = ("jakyeamos", "LIS")
    entries.append(_entry(
        name="LIS", inventory_scope="provider_only", opaque_identity="github:jakyeamos/LIS",
        provider_identity=lis_identity, provider=providers.get(("jakyeamos", "lis")), identity=None,
        previous=previous.get("LIS", {}), observed_at=observed_at,
    ))
    entries.sort(key=lambda entry: (entry["inventory_scope"], entry["name"].lower()))
    counts = {state: sum(entry["catalog_state"] == state for entry in entries) for state in ("current", "needs_review", "blocked")}
    freshness_state = "current" if counts["current"] == len(entries) else "needs_review"
    return {
        "schema_version": SCHEMA_VERSION,
        "inventory": {
            "source": "pronto-registry+github-provider",
            "source_commit": git_head(Path("/Users/jakyeamos/Documents/pronto")),
            "observed_at": observed_at,
            "registered_repository_count": len(inventory),
            "provider_only_count": 1,
            "catalog_row_count": len(entries),
        },
        "freshness": {
            "state": freshness_state,
            "window_minutes": 2880,
            "counts": counts,
            "reason": "README eligibility is limited to current rows with explicit provider and profile visibility evidence.",
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--profile-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--observed-at", default=utc_now())
    args = parser.parse_args()
    catalog = build_catalog(args.registry, args.profile_root, args.observed_at)
    destination = args.profile_root / "profile-catalog.json"
    destination.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "written", "path": str(destination), "repository_count": len(catalog["entries"]),
        "included": sum(entry["readme_disposition"] == "include" for entry in catalog["entries"]),
        "freshness": catalog["freshness"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
