# Profile validation and publication commands

Run from the profile repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_profile.py
python3 scripts/generate_profile_readme.py --check
```

The publication adapter is prepared from a clean detached `origin/main` worktree:

```sh
python3 scripts/sync_profile_repository.py \
  --repository-name AIOS \
  --expected-visibility public \
  --profile-root /Users/jakyeamos/projects/jakyeamos-profile \
  --pronto-root /Users/jakyeamos/Documents/pronto
```

That route validates a candidate but does not push. Publishing requires the explicit
external-write gate and then performs hosted README readback:

```sh
python3 scripts/sync_profile_repository.py \
  --repository-name AIOS \
  --expected-visibility public \
  --profile-root /Users/jakyeamos/projects/jakyeamos-profile \
  --pronto-root /Users/jakyeamos/Documents/pronto \
  --push --confirm-push "PUBLISH PROFILE README"
```

The selected provider state must be a fresh live match. `private` and `internal`
remove public URLs while retaining only policy-allowed non-public labels; an unknown
or mismatched state stops before any profile output is published.
