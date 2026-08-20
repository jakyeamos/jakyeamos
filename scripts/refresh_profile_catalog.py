#!/usr/bin/env python3
"""Refresh the profile catalog from Pronto's read-only registered-repository inventory."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts.profile_catalog import SCHEMA_VERSION, utc_now
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_catalog import SCHEMA_VERSION, utc_now


DEFAULT_REGISTRY = Path.home() / "Library/Application Support/Pronto/registry.db"


def git_head(path: Path) -> str:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def read_inventory(database: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            """
            SELECT id,
                   json_extract(payload_json, '$.name'),
                   json_extract(payload_json, '$.path'),
                   json_extract(payload_json, '$.remote_url'),
                   json_extract(payload_json, '$.workspace.last_commit')
              FROM repositories
             ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "repository_id": row[0],
            "name": row[1],
            "path": row[2],
            "remote_url": row[3],
            "source_commit": row[4],
        }
        for row in rows
    ]


PUBLIC_OVERRIDES: dict[str, dict[str, Any]] = {
    "quality-runner": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "Quality Runner", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Proof-oriented repository quality checks and machine-readable evidence",
        "release": "PyPI `v0.6.0`", "public_url": "https://github.com/jakyeamos/quality-runner/tree/v0.6.0",
    },
    "eslint-plugin-anti-slop": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "ESLint Anti-Slop", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Static analysis for low-signal AI and review patterns",
        "release": "npm `v0.5.0`", "public_url": "https://github.com/jakyeamos/eslint-plugin-anti-slop/releases/tag/v0.5.0",
    },
    "pre-cr-suite-lsp": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "Pre-CR Suite", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Changed-line coverage and pre-review readiness tooling",
        "release": "npm `@pre-cr/* v0.1.0`", "public_url": "https://github.com/jakyeamos/pre-cr-suite/tree/v0.1.0",
    },
    "agent-eval-contract": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "Agent Eval Contract", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Typed cases, rubrics, evidence, and result contracts for agent evaluation",
        "release": "PyPI `v0.2.0`; repo tag `v0.3.0`", "public_url": "https://github.com/jakyeamos/agent-eval-contract",
    },
    "research-domain-writing": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "Research Domain Writing", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Source-grounded writing workflows with claim discipline",
        "release": "PyPI `v0.1.0`; repo tag `v0.2.2`", "public_url": "https://github.com/jakyeamos/research-domain-writing",
    },
    "tmcp": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "TMCP", "visibility_policy": "public", "catalog_state": "current",
        "summary": "MCP/plugin workflows for audits, readiness, routing, and handoffs",
        "release": "GitHub release `v0.5.8`", "public_url": "https://github.com/jakyeamos/tmcp/releases/tag/v0.5.8",
    },
    "Terrace": {
        "section": "Public Releases", "category": "Public Releases", "subcategory": "Releases",
        "display_name": "Terrace", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Spec-driven workflow CLI for AI-assisted development",
        "release": "npm `v0.1.1`", "public_url": "https://github.com/jakyeamos/Terrace",
    },
    "pronto": {
        "section": "Public Systems", "category": "Public Systems", "subcategory": "Core Systems",
        "display_name": "Pronto", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Local-first repository, worktree, quality-evidence, and release-preparation command center",
        "public_url": "https://github.com/jakyeamos/pronto",
    },
    "jakyeamos-agent-skills": {
        "section": "Public Systems", "category": "Public Systems", "subcategory": "Core Systems",
        "display_name": "Portable Agentic Workbench", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Vendor-neutral context, routing, safety, evaluation, and durable-handoff contracts",
        "public_url": "https://github.com/jakyeamos/jakyeamos-agentic-setup",
    },
    "context-compiler-contract": {
        "section": "Public Systems", "category": "Public Systems", "subcategory": "Core Systems",
        "display_name": "Context Compiler Contract", "visibility_policy": "public", "catalog_state": "current",
        "summary": "Portable ESM validators for compiled-context results and routing manifests",
        "public_url": "https://github.com/jakyeamos/context-compiler-contract",
    },
}


def default_group(name: str) -> tuple[str, str]:
    tool_signal = ("agent", "ai-", "quality", "pronto", "eslint", "pre-cr", "context", "contract", "router", "workflow", "automation", "browser", "codex", "skill", "readiness", "evidence", "failure", "change", "debug", "review", "route", "relay", "mac-control", "attentiond", "gmail", "profile", "research", "tmcp", "terrace")
    return ("Developer Tooling", "Agent-enabled" if any(token in name.lower() for token in tool_signal) else "Unreviewed")


def build_catalog(database: Path, profile_root: Path, observed_at: str) -> dict[str, Any]:
    inventory = read_inventory(database)
    previous_path = profile_root / "profile-catalog.json"
    previous: dict[str, dict[str, Any]] = {}
    if previous_path.exists():
        previous = {entry["repository_id"]: entry for entry in json.loads(previous_path.read_text(encoding="utf-8")).get("entries", [])}
    source_repo = Path("/Users/jakyeamos/Documents/pronto")
    entries: list[dict[str, Any]] = []
    for item in inventory:
        prior = previous.get(item["repository_id"], {})
        override = PUBLIC_OVERRIDES.get(item["name"], {})
        category, subcategory = default_group(item["name"])
        entry = {
            "repository_id": item["repository_id"],
            "name": item["name"],
            "path": item["path"],
            "remote_url": item["remote_url"],
            "section": prior.get("section", "Product Work"),
            "category": prior.get("category", category),
            "subcategory": prior.get("subcategory", subcategory),
            "display_name": prior.get("display_name", item["name"]),
            "visibility_policy": prior.get("visibility_policy"),
            "catalog_state": prior.get("catalog_state", "needs_review"),
            "summary": prior.get("summary"),
            "release": prior.get("release"),
            "public_url": prior.get("public_url"),
            "source_commit": item["source_commit"],
            "inventory_observed_at": observed_at,
        }
        entry.update(override)
        entries.append(entry)
    current_count = sum(entry["catalog_state"] == "current" for entry in entries)
    freshness_state = "current" if current_count == len(entries) else "needs_review"
    return {
        "schema_version": SCHEMA_VERSION,
        "inventory": {
            "source": "pronto-registry",
            "registry_database": str(database),
            "source_repository": str(source_repo),
            "source_commit": git_head(source_repo),
            "observed_at": observed_at,
            "registered_repository_count": len(entries),
            "catalog_row_count": len(entries),
        },
        "freshness": {
            "state": freshness_state,
            "window_minutes": 2880,
            "reason": "Every registered repository has a row; rows still require explicit owner review before README eligibility.",
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
    print(json.dumps({"status": "written", "path": str(destination), "repository_count": len(catalog["entries"]), "freshness": catalog["freshness"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
