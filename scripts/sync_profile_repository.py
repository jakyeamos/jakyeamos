#!/usr/bin/env python3
"""Synchronize one confirmed GitHub visibility state into the profile README.

The adapter is deliberately narrower than the catalog refresh: it works from a
clean origin/main worktree, requires a live provider state that matches the
requested repository and visibility, permits only the generated catalog and
README outputs, and treats hosted readback as part of publication success.
"""

from __future__ import annotations

import argparse
import base64
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.profile_catalog import CATALOG_MARKER, ENTRY_MARKER, validate_readme
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from profile_catalog import CATALOG_MARKER, ENTRY_MARKER, validate_readme


CONFIRM_PUSH = "PUBLISH PROFILE README"
ALLOWED_OUTPUTS = {"profile-catalog.json", "README.md"}
EXPECTED_GLOBAL_CATALOG_FIELDS = {
    "inventory": {"source_commit", "observed_at"},
    "freshness": {"state", "counts"},
}


class SyncError(RuntimeError):
    """A publication precondition or verification failed."""


def run(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise SyncError(f"command failed ({' '.join(command)}): {detail}")
    return result.stdout


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_visibility(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"public", "private", "internal"}:
        raise SyncError(f"unsupported confirmed GitHub visibility: {value}")
    return normalized


def find_selected_entry(catalog: dict[str, Any], repository_name: str) -> dict[str, Any]:
    matches = [entry for entry in catalog.get("entries", []) if entry.get("name") == repository_name]
    if len(matches) != 1:
        raise SyncError(
            f"expected exactly one profile catalog row named {repository_name!r}; found {len(matches)}"
        )
    return matches[0]


def assert_confirmed_visibility(
    catalog: dict[str, Any], repository_name: str, expected_visibility: str
) -> dict[str, Any]:
    expected = normalize_visibility(expected_visibility)
    entry = find_selected_entry(catalog, repository_name)
    observed = str(entry.get("provider_visibility") or "unknown").lower()
    if observed != expected:
        raise SyncError(
            f"provider visibility for {repository_name} is {observed!r}, not confirmed {expected!r}"
        )
    if observed == "public":
        public_url = str(entry.get("public_url") or "")
        if not public_url.startswith("https://github.com/"):
            raise SyncError(f"public profile row for {repository_name} has no safe GitHub URL")
    elif entry.get("public_url"):
        raise SyncError(f"non-public profile row for {repository_name} carries a public URL")
    return entry


def _entry_without_observation(entry: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(entry)
    value.pop("provider_observed_at", None)
    return value


def assert_catalog_scope(
    before: dict[str, Any], after: dict[str, Any], repository_name: str
) -> None:
    before_entries = {entry.get("repository_id"): entry for entry in before.get("entries", [])}
    after_entries = {entry.get("repository_id"): entry for entry in after.get("entries", [])}
    if set(before_entries) != set(after_entries):
        added = sorted(set(after_entries) - set(before_entries))
        removed = sorted(set(before_entries) - set(after_entries))
        details = []
        if added:
            details.append("added=" + ",".join(str(repository_id) for repository_id in added))
        if removed:
            details.append("removed=" + ",".join(str(repository_id) for repository_id in removed))
        raise SyncError(
            "profile catalog row identities changed outside the selected repository"
            + (f" ({'; '.join(details)})" if details else "")
        )
    for repository_id, previous in before_entries.items():
        current = after_entries[repository_id]
        if previous.get("name") == repository_name:
            continue
        if _entry_without_observation(previous) != _entry_without_observation(current):
            raise SyncError(
                f"profile catalog row {previous.get('name')!r} changed outside the selected repository"
            )

    for section, allowed_keys in EXPECTED_GLOBAL_CATALOG_FIELDS.items():
        previous_section = before.get(section, {})
        current_section = after.get(section, {})
        if not isinstance(previous_section, dict) or not isinstance(current_section, dict):
            raise SyncError(f"profile catalog {section} metadata is malformed")
        for key in set(previous_section) | set(current_section):
            if key in allowed_keys:
                continue
            if previous_section.get(key) != current_section.get(key):
                raise SyncError(f"profile catalog {section}.{key} changed outside the allowed generated metadata")


def _catalog_marker_normalized(text: str) -> str:
    return CATALOG_MARKER.sub("<!-- profile-catalog: generated-marker -->", text)


def _remove_entry_section(text: str, repository_id: str) -> str:
    matches = list(ENTRY_MARKER.finditer(text))
    selected = next((match for match in matches if match.group("id") == repository_id), None)
    if selected is None:
        return text
    line_start = text.rfind("\n", 0, selected.start()) + 1
    next_match = next((match for match in matches if match.start() > selected.start()), None)
    line_end = text.find("\n", next_match.start()) + 1 if next_match else len(text)
    return text[:line_start] + text[line_end:]


def assert_readme_scope(
    before_text: str, after_text: str, selected_repository_id: str
) -> None:
    before_without_selected = _remove_entry_section(before_text, selected_repository_id)
    after_without_selected = _remove_entry_section(after_text, selected_repository_id)
    if _catalog_marker_normalized(before_without_selected) != _catalog_marker_normalized(after_without_selected):
        raise SyncError("README changed outside the generated marker and selected repository entry")


def assert_readme_visibility(
    readme_text: str,
    catalog: dict[str, Any],
    repository_name: str,
    expected_visibility: str,
) -> None:
    entry = assert_confirmed_visibility(catalog, repository_name, expected_visibility)
    repository_id = str(entry["repository_id"])
    matches = [match for match in ENTRY_MARKER.finditer(readme_text) if match.group("id") == repository_id]
    if expected_visibility == "public":
        public_url = str(entry.get("public_url") or "")
        if len(matches) != 1:
            raise SyncError(f"README does not contain exactly one public link for {repository_name}")
        start = readme_text.rfind("\n", 0, matches[0].start()) + 1
        next_match = next((match for match in ENTRY_MARKER.finditer(readme_text) if match.start() > matches[0].start()), None)
        end = readme_text.find("\n", next_match.start()) + 1 if next_match else len(readme_text)
        section = readme_text[start:end]
        if public_url not in section:
            raise SyncError(f"README does not contain exactly one public link for {repository_name}")
        return

    if entry.get("public_url"):
        raise SyncError(f"non-public catalog row for {repository_name} has a public URL")
    if not matches:
        return
    start = readme_text.rfind("\n", 0, matches[0].start()) + 1
    next_match = next((match for match in ENTRY_MARKER.finditer(readme_text) if match.start() > matches[0].start()), None)
    end = readme_text.find("\n", next_match.start()) + 1 if next_match else len(readme_text)
    section = readme_text[start:end]
    if "https://github.com/" in section:
        raise SyncError(f"README section for non-public repository {repository_name} contains a GitHub URL")


def read_remote_readme(profile_repository: str, branch: str = "main") -> str:
    payload = json.loads(
        run(["gh", "api", f"repos/{profile_repository}/contents/README.md?ref={branch}"])
    )
    if payload.get("encoding") != "base64" or not payload.get("content"):
        raise SyncError("hosted profile README response did not contain base64 content")
    try:
        return base64.b64decode(payload["content"], validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as error:
        raise SyncError(f"hosted profile README could not be decoded: {error}") from error


def assert_hosted_readback(
    remote_text: str,
    local_text: str,
    catalog: dict[str, Any],
    repository_name: str,
    expected_visibility: str,
) -> None:
    local_marker = CATALOG_MARKER.search(local_text)
    remote_marker = CATALOG_MARKER.search(remote_text)
    if not local_marker or not remote_marker or local_marker.group(0) != remote_marker.group(0):
        raise SyncError("hosted profile README generated marker does not match the validated candidate")
    assert_readme_visibility(remote_text, catalog, repository_name, expected_visibility)


def changed_paths(profile_root: Path) -> list[str]:
    output = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=profile_root)
    paths: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def sync_in_worktree(
    *,
    profile_worktree: Path,
    repository_name: str,
    expected_visibility: str,
    registry: Path,
    pronto_root: Path,
    observed_at: str | None,
) -> tuple[dict[str, Any], str, dict[str, Any], str]:
    before_catalog_path = profile_worktree / "profile-catalog.json"
    before_readme_path = profile_worktree / "README.md"
    before_catalog = load_json(before_catalog_path)
    before_readme = before_readme_path.read_text(encoding="utf-8")

    command = [
        "python3",
        "scripts/refresh_profile_catalog.py",
        "--registry",
        str(registry),
        "--profile-root",
        str(profile_worktree),
        "--pronto-root",
        str(pronto_root),
    ]
    if observed_at:
        command.extend(["--observed-at", observed_at])
    run(command, cwd=profile_worktree)
    run(["python3", "scripts/generate_profile_readme.py", "--profile-root", str(profile_worktree)], cwd=profile_worktree)
    run(["python3", "scripts/check_profile.py"], cwd=profile_worktree)
    run(
        ["python3", "scripts/generate_profile_readme.py", "--check", "--profile-root", str(profile_worktree)],
        cwd=profile_worktree,
    )

    after_catalog = load_json(before_catalog_path)
    after_readme = before_readme_path.read_text(encoding="utf-8")
    selected = assert_confirmed_visibility(after_catalog, repository_name, expected_visibility)
    assert_catalog_scope(before_catalog, after_catalog, repository_name)
    assert_readme_scope(before_readme, after_readme, str(selected["repository_id"]))
    assert_readme_visibility(after_readme, after_catalog, repository_name, expected_visibility)
    paths = changed_paths(profile_worktree)
    unexpected = sorted(set(paths) - ALLOWED_OUTPUTS)
    if unexpected:
        raise SyncError("profile publication produced unexpected paths: " + ", ".join(unexpected))
    return before_catalog, before_readme, after_catalog, after_readme


def create_worktree(profile_root: Path, base_ref: str) -> Path:
    run(["git", "fetch", "origin", "main"], cwd=profile_root)
    run(["git", "rev-parse", "--verify", base_ref], cwd=profile_root)
    path = Path(tempfile.mkdtemp(prefix="profile-readme-sync-"))
    try:
        run(["git", "worktree", "add", "--detach", str(path), base_ref], cwd=profile_root)
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise
    return path


def remove_worktree(profile_root: Path, path: Path) -> None:
    if path.exists():
        status = run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=path,
        ).strip()
        if status:
            raise SyncError(
                "profile publication worktree was still dirty during cleanup; "
                f"retained at {path} for review"
            )
        run(["git", "worktree", "remove", str(path)], cwd=profile_root)


def publish(
    *,
    profile_root: Path,
    profile_repository: str,
    repository_name: str,
    expected_visibility: str,
    registry: Path,
    pronto_root: Path,
    base_ref: str,
    target_branch: str,
    observed_at: str | None,
    push: bool,
    confirmation: str,
) -> dict[str, Any]:
    if target_branch != "main":
        raise SyncError("profile publication is restricted to the generated profile repository's main branch")
    expected = normalize_visibility(expected_visibility)
    worktree = create_worktree(profile_root, base_ref)
    try:
        _, _, catalog, readme = sync_in_worktree(
            profile_worktree=worktree,
            repository_name=repository_name,
            expected_visibility=expected,
            registry=registry,
            pronto_root=pronto_root,
            observed_at=observed_at,
        )
        paths = changed_paths(worktree)
        if not paths:
            result = {
                "status": "no_op",
                "repository": repository_name,
                "visibility": expected,
                "readback": "not_required",
            }
        else:
            run(["git", "add", "--", "profile-catalog.json", "README.md"], cwd=worktree)
            run(
                ["git", "commit", "-m", f"chore: sync profile visibility for {repository_name}"],
                cwd=worktree,
            )
            commit = run(["git", "rev-parse", "HEAD"], cwd=worktree).strip()
            if not push:
                result = {
                    "status": "validated",
                    "repository": repository_name,
                    "visibility": expected,
                    "changed_paths": paths,
                    "prepared_commit": commit,
                    "readback": "blocked_until_publish_authorization",
                }
            else:
                if confirmation != CONFIRM_PUSH:
                    raise SyncError(f"publishing requires --confirm-push {CONFIRM_PUSH!r}")
                run(["git", "push", "origin", f"HEAD:{target_branch}"], cwd=worktree)
                remote_text = read_remote_readme(profile_repository, target_branch)
                assert_hosted_readback(remote_text, readme, catalog, repository_name, expected)
                result = {
                    "status": "published",
                    "repository": repository_name,
                    "visibility": expected,
                    "changed_paths": paths,
                    "readback": "matched",
                }
    except Exception as error:
        try:
            remove_worktree(profile_root, worktree)
        except SyncError as cleanup_error:
            raise SyncError(f"{error}; {cleanup_error}") from error
        raise
    else:
        remove_worktree(profile_root, worktree)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile-repository", default="jakyeamos/jakyeamos")
    parser.add_argument("--repository-name", required=True)
    parser.add_argument("--expected-visibility", required=True, choices=("public", "private", "internal"))
    parser.add_argument("--registry", type=Path, default=Path.home() / "Library/Application Support/Pronto/registry.db")
    parser.add_argument("--pronto-root", type=Path, default=Path("/Users/jakyeamos/Documents/pronto"))
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--target-branch", default="main")
    parser.add_argument("--observed-at")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--confirm-push", default="")
    args = parser.parse_args()
    try:
        result = publish(
            profile_root=args.profile_root.resolve(),
            profile_repository=args.profile_repository,
            repository_name=args.repository_name,
            expected_visibility=args.expected_visibility,
            registry=args.registry.expanduser().resolve(),
            pronto_root=args.pronto_root.resolve(),
            base_ref=args.base_ref,
            target_branch=args.target_branch,
            observed_at=args.observed_at,
            push=args.push,
            confirmation=args.confirm_push,
        )
    except SyncError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
