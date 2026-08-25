---
id: jakyeamos-profile.context
title: Generated profile publication context
tier: project
status: active
last_reviewed: 2026-08-24
applies_when:
  - profile catalog
  - profile README
  - visibility sync
---

# Profile workflow context

The generated profile surface is `/Users/jakyeamos/projects/jakyeamos-profile/README.md`.
`profile-catalog.json` is its source-controlled input; `scripts/profile_catalog.py`
owns the schema, eligibility, privacy boundary, and rendering contract.

Read [commands.md](commands.md) for the exact validation and publication route.
Keep these evidence lanes separate:

- Pronto local inventory identifies registered repositories without exposing paths.
- Fresh authenticated GitHub evidence supplies `public`, `private`, or `internal` visibility.
- Catalog policy decides whether safe metadata may appear in the profile README.
- Hosted `README.md` readback proves publication only after an explicitly authorized push.

`scripts/sync_profile_repository.py` may project a confirmed provider state into a
detached worktree based on `origin/main`. It never changes GitHub visibility. Unknown,
stale, failed, or mismatched provider evidence leaves the hosted README unchanged.
The adapter may modify only the generated catalog and README, and it must verify the
remote README marker and selected link state after a successful push.
