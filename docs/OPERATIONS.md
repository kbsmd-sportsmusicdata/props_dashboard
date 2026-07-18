# Operations

## Manual verification

```bash
python3 -m pytest -q
python3 scripts/validate_outputs.py --data data/processed/dashboard_data.json --site site/index.html
python3 cli/prop_lookup.py --list-players
```

## Recovery

- `download_failed`: verify network access and the SportsDataverse release URLs; downstream stages were skipped.
- `validation_failed`: inspect the structured run log and test output. The previous site remains published.
- `push_failed`: inspect `git status -sb` and `git log -1`; after resolving authentication or remote drift, rerun verification and push the existing commit.
- `no_new_data`: expected on off days or before the newest game is marked complete upstream.

The unattended job stages only `data/canonical`, `data/processed`, `data/manifests`, and `site/index.html`. It never commits source-code or documentation changes.

## GitHub Pages

The Pages workflow deploys `site/` after relevant pushes to `main`. Enable GitHub Pages with “GitHub Actions” as the source in repository settings. CI runs independently on every pull request and push.
