#!/usr/bin/env python3
"""Validate the repository-owned profile README and catalog contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from scripts.profile_catalog import validate_readme
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_catalog import validate_readme

REQUIRED_HEADINGS = ("# Jakye Amos", "## Public Releases", "## Product Work", "## Stack")
LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def validate(readme: Path) -> list[str]:
    text = readme.read_text(encoding="utf-8")
    errors = [f"missing heading: {heading}" for heading in REQUIRED_HEADINGS if heading not in text]
    for target in LINK_PATTERN.findall(text):
        if target.startswith(("https://", "http://", "mailto:")):
            continue
        local_target = (readme.parent / target.split("#", maxsplit=1)[0]).resolve()
        if not local_target.exists() or readme.parent.resolve() not in local_target.parents:
            errors.append(f"invalid local link: {target}")
    catalog = readme.parent / "profile-catalog.json"
    if catalog.exists():
        errors.extend(validate_readme(readme, catalog))
    return errors


def main() -> int:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    errors = validate(readme)
    print(json.dumps({"status": "passed" if not errors else "failed", "errors": errors}))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
