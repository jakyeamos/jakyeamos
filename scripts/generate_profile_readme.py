#!/usr/bin/env python3
"""Render README.md from the repository-owned profile catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from scripts.profile_catalog import render_readme, validate_readme
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_catalog import render_readme, validate_readme


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--profile-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.profile_root.resolve()
    catalog = root / "profile-catalog.json"
    readme = root / "README.md"
    if args.check:
        errors = validate_readme(readme, catalog)
        print({"status": "passed" if not errors else "failed", "errors": errors})
        return 1 if errors else 0
    readme.write_text(render_readme(catalog), encoding="utf-8")
    errors = validate_readme(readme, catalog)
    print({"status": "written" if not errors else "failed", "path": str(readme), "errors": errors})
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
